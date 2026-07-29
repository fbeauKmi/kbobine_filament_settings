# kbobine.py - Klipper plugin to manage filament spooling
#
#
# Copyright (C) 2025-2026 Frederic Beaucamp <fbeaukmi@mailo.eu>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import re
import json
import logging
import os
import socket


class sentinel:
    pass


class Kbobine:
    def __init__(self, config):
        self.config_ref = config
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()

        # Register endpoints for webhooks
        self.wh = self.printer.lookup_object("webhooks")
        self.wh.register_endpoint("kbobine/set_spool", self._handle_webrequest)
        self.wh.register_endpoint("kbobine/response", self._handle_webresponse)

        # Initialize the settings helper
        self.ks = KbobineSettingsHelper(self.config_ref, self.wh)
        self._register_commands()

        self.printer.register_event_handler("klippy:ready", self._handle_ready)

    def _handle_ready(self):
        self.ks.printer_cmds = self.ks.gcode.get_status(0).get("commands", {})
        my_timer = self.reactor.register_timer(
            self._call_get_spoolman_datas, self.reactor.monotonic() + 1
        )
        self.my_timer = my_timer

    # Remote called method to get spoolman datas
    def _call_get_spoolman_datas(self, eventtime):
        try:
            self.wh.call_remote_method("get_spoolman_datas")
        except self.printer.command_error:
            logging.info("Remote Call Error")
        self.reactor.unregister_timer(self.my_timer)
        return self.reactor.NEVER

    def _handle_webrequest(self, web_request):
        """Handle web request to set parameters"""
        try:
            spoolman = web_request.get_dict("spoolman")
            # Check if spool is valid
            self.ks.load_spool_data(spoolman)
            web_request.send(
                "Spool data received for %s " % (self.ks.spool_id or "None")
            )
        except (AttributeError, KeyError, TypeError, ValueError) as err:
            raise web_request.error(f"Error: {err}")

    def _handle_webresponse(self, web_request):
        try:
            caller_id = web_request.get("caller_id")
            response = web_request.get_dict("response")

            if not caller_id:
                raise self.gcode.error("No caller provided")
            if "error" in response:
                self.gcode._respond_error(
                    "{} : {}".format(caller_id, response["error"])
                )
                self.printer.send_event("gcode:command_error")
            if "message" in response:
                self.gcode.respond_info(
                    "{} : {}".format(caller_id, response["message"])
                )
            return "done"
        except (AttributeError, KeyError, TypeError, ValueError) as err:
            raise web_request.error(f"Error: {err}")

    def _register_commands(self):
        """Register G-code commands and add fake macros to the config file
        to show them in UIs"""
        self.gcode = self.printer.lookup_object("gcode")

        lines = ""
        for parameter in self.ks.parameters:
            lines += f"{{% set _=params.{parameter.upper()} %}}\n"

        macros = {
            "SET_SPOOL": lines,
            "SET_LOADED_MATERIAL": lines,
            "GET_SPOOL": "",
            "GET_LOADED_MATERIAL": "",
            "LOAD_DEFAULT_MATERIAL": "",
            "DEL_SPOOL": "",
            "APPLY_SETTINGS": "",
            "SELECT_MATERIAL": "",
        }

        for macro, gcode_str in macros.items():
            macro_name = f"gcode_macro {macro.lower()}"

            # Register commands for each macro
            self.gcode.register_command(
                f"_{macro}",
                getattr(self.ks, f"cmd_{macro}"),
                desc=getattr(self.ks, f"cmd_{macro}_help"),
            )

            # Check if the macro already exists in the config file
            # thanks to frix_x for the tip to inject the macro in the config file
            if not self.config_ref.fileconfig.has_section(macro_name):
                self.config_ref.fileconfig.add_section(macro_name)
            else:
                raise self.config_ref.error(
                    f"Macro {macro_name} already exists in the config file"
                )
            # Add the macro to the config file
            self.config_ref.fileconfig.set(
                macro_name,
                "description",
                getattr(self.ks, f"cmd_{macro}_help"),
            )
            gcode = gcode_str + f"_{macro.upper()} {{rawparams}}\n"
            self.config_ref.fileconfig.set(macro_name, "gcode", gcode)
            self.config_ref.access_tracking[(macro_name, "gcode")] = 1
            self.printer.load_object(self.config_ref, macro_name)

    def get_status(self, eventtime):
        """Return current status of the plugin"""
        status = {
            "default": self.ks.default,
            "current_settings": self.ks.current,
            "spoolman": self.ks.spoolman,
            "spool_id": self.ks.spool_id,
            "spool_name": self.ks.spool_name,
        }
        return status


class KbobineSettingsHelper:
    # Constants for parameter keys
    DEFAULT_KEY = "default"
    MIN_KEY = "min"
    MAX_KEY = "max"

    def __init__(self, config, wh):
        self.config = config
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object("gcode")

        # Initialize data structures
        self.current = {}
        self.spoolman = {}
        self.spool_id = "0"
        self.spool_name = None
        self.local_data = {}
        self.need_calibration = False
        self.hostname = socket.gethostname()
        self.available_kbobine_datas = []
        self.printer_cmds = {}

        # Helpers
        self.wh = wh  # webhooks
        self.prompt = PromptUIHelper(self.printer)

        # Get configured parameters
        # TO REPORT IN KBOBINE.MD
        self.apply_on_load = config.getboolean("apply_on_load", default=False)
        self.store_in_spoolman = config.getboolean("store_in_spoolman", default=False)
        self.commands = config.getlists(
            "commands", seps=("=", ","), count=2, default={}
        )
        self.parameters = self.get_parameters(config, "parameters")
        self.default = {
            param: self.parameters[param][self.DEFAULT_KEY] for param in self.parameters
        }

        self.th_depend = config.getlist(
            "th_depend",
            default=(
                "extrude_factor",
                "pressure_advance",
                "pa_smooth_time",
                "max_flow",
                "retract_length",
                "retract_speed",
                "unretract_extra_length",
            ),
        )

        self.required_params = config.getlist(
            "required_params",
            default=(
                "extrude_factor",
                "pressure_advance",
            ),
        )
        for param in self.required_params:
            if param not in self.parameters:
                raise config.error(
                    f"Kbobine : required parameter '{param}' is not defined in parameters"
                )

        gcode_macro = self.printer.load_object(config, "gcode_macro")
        self.calibrate_gcode = gcode_macro.load_template(
            config, "calibrate_gcode", "PROMPT_CLOSE"
        )

        # Get the config file path and directory
        configfilename = self.printer.get_start_args()["config_file"]
        configdir = os.path.dirname(configfilename)
        spool_file = os.path.join(configdir, "spool.json")
        # Get the filename from the config or use the default filename
        self.spool_file = os.path.expanduser(config.get("spool_file", spool_file))

        if os.path.exists(self.spool_file):
            try:
                with open(self.spool_file, "r") as f:
                    self.local_data = json.load(f)
            except (OSError, TypeError, ValueError) as e:
                raise config.error(f"Failed to read {self.spool_file} file: {e}")

        # Register commands for the plugin
        # TO REPORT IN KBOBINE.MD

        self.gcode.register_command(
            "IMPORT_KBOBINE", self.cmd_IMPORT_KBOBINE, desc="Import kbobine settings"
        )

    def get_parameters(self, config, name, default=sentinel, keys=None) -> dict:
        """Parse parameters.
        Ensure there's 3 values and min <= default <= max"""
        if keys is None:
            keys = [self.DEFAULT_KEY, self.MIN_KEY, self.MAX_KEY]
        if default == sentinel:
            parameters = self.config.get(name)
        else:
            parameters = self.config.get(name, None)
        output = {}

        # parameters format: name : [0,0,0], other_name : [1,2,3]
        try:
            if isinstance(parameters, str):
                # Split by commas, but ignore commas inside brackets
                parameters = re.split(r",\s*(?![^\[]*\])", parameters)
            for parameter in parameters:
                if isinstance(parameter, str):
                    parameter = parameter.strip()
                if not parameter:
                    raise ValueError("invalid parameter: empty string")
                if ":" not in parameter:
                    raise ValueError(f"Missing ':' in parameter: {parameter}")
                name, values_str = parameter.split(":", 1)
                name = name.strip()
                values_str = values_str.strip()
                if not values_str.startswith("[") or not values_str.endswith("]"):
                    raise ValueError(
                        f"Values must be enclosed in brackets for parameter: {name} : {values_str} {parameter}"
                    )
                values_str = values_str[1:-1].strip()  # Remove brackets
                values = [v.strip() for v in values_str.split(",") if v.strip()]
                if len(values) != 3:
                    raise ValueError(
                        f"Expected 3 values for parameter {name}, got {len(values)}"
                    )
                numeric_values = []
                for v in values:
                    try:
                        numeric_values.append(float(v))
                    except ValueError:
                        raise ValueError(
                            f"Non-numeric value '{v}' for parameter {name}"
                        )
                if not (numeric_values[1] <= numeric_values[0] <= numeric_values[2]):
                    raise ValueError(
                        f"Values for parameter {name} must satisfy min <= default <= max"
                    )
                output[name] = dict(zip(keys, numeric_values))
        except (TypeError, ValueError, AttributeError) as err:
            raise self.config.error(f"parameters is invalid: {err}")

        return output

    def get_namespace(self) -> str:
        toolhead = self.printer.lookup_object("toolhead")

        try:
            extruder = toolhead.get_extruder()
            nozzle_diameter = extruder.nozzle_diameter * 10
            return str(nozzle_diameter)
        except (NameError, AttributeError):
            return "dummy"

    def load_spool_data(self, spoolman_datas: dict) -> None:

        if spoolman_datas.get("spool_id") == self.spool_id:
            self.gcode.respond_info(f"Spool {self.spool_id} already loaded")
            return

        self.current = {}
        self.need_calibration = False
        self.spoolman = spoolman_datas
        self.spool_name = "default"
        self.available_kbobine_datas = list(self.spoolman.get("kbobine", {}).keys())
        self.spool_id = self.spoolman.get("spool_id", "0")
        spool_id = str(self.spool_id)

        if spoolman_datas == {}:
            self.gcode.respond_info("!! No spool data provided !")
            return

        if spoolman_datas.get("spool_id") == 0:
            self.gcode.respond_info("No active spool detected, No settings loaded...")
            return

        vendor = self.spoolman.get("vendor", "Unknown")
        material = self.spoolman.get("material", "Unknown")
        filament = self.spoolman.get("filament", "Unknown")
        self.spool_name = vendor + " - " + material + " " + filament

        # Main case : spool is already in local data, load settings from there
        if spool_id in self.local_data:
            self.current = self.get_settings()
            if vendor == "Unknown" and material == "Unknown" and filament == "Unknown":
                self.spoolman["vendor"] = self.local_data[spool_id]["vendor"]
                self.spoolman["material"] = self.local_data[spool_id]["material"]
                self.spoolman["filament"] = self.local_data[spool_id]["filament"]
                self.spool_name = (
                    self.spoolman["vendor"]
                    + " - "
                    + self.spoolman["material"]
                    + " - "
                    + self.spoolman["filament"]
                )

            self.gcode.respond_info(f"{self.spool_name} loaded from local !")
            self.show_settings()
            if self.apply_on_load:
                self.apply_settings(list(self.current.keys()))
            return

        if self.store_in_spoolman:
            # 2nd case : spool datas are available in Spoolman
            if self.hostname in self.available_kbobine_datas:
                self.prompt.select(
                    f"No local settings found for this spool on {self.hostname}, but kbobine datas are available on Spoolman for this printer, import settings from ?",
                    options=[
                        "Import from Spoolman",
                        "Use local default settings",
                    ],
                    values=[self.hostname, "default"],
                    key="HOST",
                    colors=["primary", "secondary"],
                    action="IMPORT_KBOBINE",
                    title=self.spool_name,
                )
                return

            # 3rd case : spool datas are available in Spoolman but from another printer
            if len(self.available_kbobine_datas) > 0:
                self.need_calibration = True
                self.prompt.select(
                    f"No settings found for this spool on '{self.hostname}', but kbobine datas are available from another printer, import settings from:",
                    options=list(self.available_kbobine_datas)
                    + ["Use local default settings"],
                    values=list(self.available_kbobine_datas) + ["default"],
                    key="HOST",
                    colors=["primary"] * len(self.available_kbobine_datas)
                    + ["secondary"],
                    action="IMPORT_KBOBINE",
                    title=self.spool_name,
                )
                return

        # Mark as new spool.
        self.need_calibration = True

        # 4th case : similar spools in local data
        ids = []
        # Find similar spools with same vendor, material and filament
        for id in self.local_data:
            if (
                self.local_data[id].get("vendor") == vendor
                and self.local_data[id].get("material") == material
                and self.local_data[id].get("filament") == filament
            ):
                ids.append(id)
        # Find similar spools with same vendor and material
        if len(ids) == 0:
            for id in self.local_data:
                if (
                    self.local_data[id].get("vendor") == vendor
                    and self.local_data[id].get("material") == material
                ):
                    ids.append(id)
        # Find similar spools with same material
        if len(ids) == 0:
            for id in self.local_data:
                if self.local_data[id].get("material") == material:
                    ids.append(id)
        if len(ids) > 0:
            options = [
                "{} : {} - {} - {}".format(
                    id,
                    self.local_data[id].get("filament"),
                    self.local_data[id].get("vendor"),
                    self.local_data[id].get("material"),
                )
                for id in ids
            ]
            colors = ["primary"] * len(ids)
            options.append("Use default settings")
            ids.append("0")
            colors.append("secondary")
            self.prompt.select(
                "No settings found for this spool, but similar spools are available locally, import settings from ?:",
                options=options,
                values=ids,
                key="ID",
                colors=colors,
                action="IMPORT_KBOBINE",
                title=self.spool_name,
            )
            return

        # last case : no settings found for this spool, propose to initialize it with default values
        self.prompt.select(
            "No settings found for this spool, do you want to initialize it with default values ?",
            options=["Use default settings"],
            values=["default"],
            key="HOST",
            colors=["secondary"],
            action="IMPORT_KBOBINE",
            title=self.spool_name,
        )

    def save_local_data(self) -> None:
        try:
            datas = json.dumps(self.local_data, indent=1, sort_keys=True)
            with open(self.spool_file, "w") as f:
                f.write(datas)
        except OSError as e:
            raise self.gcode.error(f"Failed to write {e} file: {self.spool_file}")

    def save_remote_data(self) -> None:
        if not self.store_in_spoolman or self.spool_id == "0":
            return
        settings = self.format_settings_for_spoolman()
        if (
            self.spoolman is None
            or self.spoolman.get("kbobine", {}).get(self.hostname, None) == settings
        ):
            return
        try:
            self.wh.call_remote_method("set_spoolman_datas", spoolman_datas=settings)
        except self.printer.command_error:
            logging.info("set_spoolman_datas : Remote Call Error")

    def del_local_spool(self, spool_id=None) -> None:

        spool_id = self.spool_id if spool_id is None else spool_id

        self.local_data.pop(str(spool_id), None)
        self.save_local_data()

    def update_local_data(self, settings) -> None:
        datas = self.format_settings(settings)
        datas = self.filter_settings_to_store(datas)
        self.build_datas(datas)

    def build_datas(self, datas) -> None:
        if self.spool_id == "0":
            return
        entry = self.local_data.setdefault(
            str(self.spool_id),
            {
                "material": self.spoolman.get("material", "Unknown"),
                "vendor": self.spoolman.get("vendor", "Unknown"),
                "filament": self.spoolman.get("filament", "Unknown"),
                "settings": {},
            },
        )
        entry["settings"] = datas
        self.local_data[str(self.spool_id)] = entry

        self.save_local_data()

    def validate_settings(self, settings) -> dict:
        """Validate settings and return a dict with only valid settings"""
        valid_settings = {}
        for param, value in settings.items():
            param = param.lower()
            if self.parameters.get(param) is None:
                raise self.gcode.error(f"Unknown parameter {param}")
            if (float(value) > self.parameters[param][self.MAX_KEY]) or (
                float(value) < self.parameters[param][self.MIN_KEY]
            ):
                raise self.gcode.error(
                    f"{value} not in allowed range for {param} [min {self.parameters[param][self.MIN_KEY]}, max {self.parameters[param][self.MAX_KEY]}], check your kbobine config"
                )
            valid_settings[param] = float(value)
        return valid_settings

    def format_settings(self, settings, namespaces=None, keep_defaults=False) -> dict:
        """Set settings in the local data for the current spool and namespace (default if not in th_depend)"""
        original_settings = self.local_data.get(str(self.spool_id), {}).get(
            "settings", {}
        )
        local_settings = {ns: dict(params) for ns, params in original_settings.items()}

        if namespaces is None:
            namespaces = [self.get_namespace()]

        # Initialize namespaces in local settings if they don't exist
        local_settings.setdefault(self.DEFAULT_KEY, {})
        for namespace in namespaces:
            local_settings.setdefault(namespace, {})

        for param, value in settings.items():
            param = param.lower()
            ns = namespaces if param in self.th_depend else [self.DEFAULT_KEY]
            for n in ns:
                local_settings[n][param] = value
        return local_settings

    def filter_settings_to_store(self, settings) -> dict:
        """Filter settings to store only parameters that are different from the default value, to avoid storing unnecessary datas in Spoolman"""
        filtered_settings = {}
        try:
            for ns, params in settings.items():
                for param, value in params.items():
                    if (
                        self.default.get(param) == float(value)
                        and param not in self.required_params
                    ):
                        continue
                    filtered_settings.setdefault(ns, {})[param] = float(value)
        except Exception as e:
            raise self.gcode.error(
                f"Kbobine detects an error while filtering settings: {e}"
            )
        return filtered_settings

    def format_settings_for_spoolman(self) -> dict:
        """Format settings to store in spoolman extra, without namespaces"""
        original_settings = self.local_data.get(str(self.spool_id), {}).get(
            "settings", {}
        )
        local_settings = {ns: dict(params) for ns, params in original_settings.items()}
        namespaces = set(local_settings.keys()) | {
            self.get_namespace(),
            self.DEFAULT_KEY,
        }

        for ns in namespaces:
            local_settings.setdefault(ns, {})
            for param, meta in self.parameters.items():
                is_default_param = (
                    param not in self.th_depend and ns == self.DEFAULT_KEY
                )
                is_th_depend_param = param in self.th_depend and ns != self.DEFAULT_KEY
                if (
                    is_default_param or is_th_depend_param
                ) and param not in local_settings[ns]:
                    # Set default value only if parameter is missing in this namespace
                    local_settings[ns][param] = meta[self.DEFAULT_KEY]

        return local_settings

    def get_settings(self, namespace=None, include_defaults=True) -> dict:
        """Get settings from the local data for the current spool and namespace"""
        if namespace is None:
            namespace = self.get_namespace()

        if include_defaults:
            default_parameters = self.default.copy()
        else:
            default_parameters = {}

        local_datas = self.local_data.get(str(self.spool_id), {}).copy()
        settings = local_datas.get("settings", {}).copy()

        default_settings = settings.get(self.DEFAULT_KEY, {}).copy()
        ns_settings = settings.get(namespace, {})

        # Check if all required parameters are present in the settings, if not mark the spool as needing calibration
        to_calibrate = []
        for param in self.required_params:
            if param not in default_settings and param not in ns_settings:
                self.need_calibration = True
                to_calibrate.append(param)

        if self.need_calibration:
            self.need_calibration = False
            if len(to_calibrate) > 0:
                missing_params = ", ".join(to_calibrate)
                sentence = f"Some required parameters are missing ({missing_params})"
            else:
                sentence = "Newly imported spool"
            self.prompt.question(
                f"{sentence} , do you want to calibrate it now ?",
                yes_action=self.calibrate_gcode.render(),
                title=self.spool_name,
            )

        merged_settings = {
            **default_parameters,
            **default_settings,
            **ns_settings,
        }

        return merged_settings

    def show_settings(self, type: str = "local db") -> None:

        info = []

        if (len(self.current) == 0 and type == "loaded") or (
            self.spool_id == "0" and type == "local db"
        ):
            self.gcode.respond_info("No settings")
            return

        info = [f"---- {self.spool_name} ({type}) ----"]
        if type == "loaded":
            for param, value in self.current.items():
                default_value = self.parameters[param][self.DEFAULT_KEY]
                default_mark = " (default)" if default_value == value else ""
                info.append(f"- {param}: {value}{default_mark}")
        else:
            local_datas = self.local_data.get(str(self.spool_id), {}).get(
                "settings", {}
            )
            for th, params in local_datas.items():
                info.append(f"---- {th} ----")
                for param, value in params.items():
                    info.append(f"- {param}: {value}")

        if len(info) == 1:
            info.append("No settings")

        self.gcode.respond_info("\n".join(info))

    # Apply settings by sending G-code commands to the printer, only for parameters that have a command
    # associated in the config and that are present in the printer commands list (to avoid sending
    # commands that would be ignored by the printer and fill the logs with warnings)
    def apply_settings(self, settings: list) -> None:
        actions = {}

        def add_action(function, default_function, value, enable=True) -> None:
            if enable:
                function = function if function is not None else default_function
                if function.upper() in self.printer_cmds:
                    actions.setdefault(function, []).append(value)

        # Mapping of settings to (command, value_formatter)
        setting_map = {
            "speed_factor": ("M220", lambda v, s: f"S{v * 100.0:.3f}"),
            "extrude_factor": ("M221", lambda v, s: f"S{v * 100.0:.3f}"),
            "max_flow": ("SET_MAX_FLOW", lambda v, s: f"VALUE={v}"),
            "fan_speed": ("_KBOBINE_FAN_SPEED", lambda v, s: f"S={v}"),
            "filament_sensor": (
                "SET_FILAMENT_SENSOR",
                lambda v, s: f'SENSOR="filament_sensor" ENABLE={v}',
            ),
            "pressure_advance": ("SET_PRESSURE_ADVANCE", lambda v, s: f"ADVANCE={v}"),
            "pa_smooth_time": ("SET_PRESSURE_ADVANCE", lambda v, s: f"SMOOTH_TIME={v}"),
            "retract_length": ("SET_RETRACTION", lambda v, s: f"{s}={v}"),
            "retract_speed": ("SET_RETRACTION", lambda v, s: f"{s}={v}"),
            "unretract_extra_length": ("SET_RETRACTION", lambda v, s: f"{s}={v}"),
            "unretract_speed": ("SET_RETRACTION", lambda v, s: f"{s}={v}"),
            "z_hop_height": ("SET_RETRACTION", lambda v, s: f"{s}={v}"),
            "shrinkage_xy": ("SET_SHRINKAGE", lambda v, s: f"XY_VALUE={v}"),
            "shrinkage_z": ("SET_SHRINKAGE", lambda v, s: f"Z_VALUE={v}"),
        }

        for setting in settings:
            if setting not in self.current:
                continue

            cmd = self.commands.get(setting, None)
            value = self.current[setting]

            if setting in setting_map:
                command, formatter = setting_map[setting]
                add_action(cmd, command, formatter(value, setting.upper()))
            elif setting == "extruder_temp":
                toolhead = self.printer.lookup_object("toolhead")
                if (
                    toolhead.get_extruder().get_name()
                    and toolhead.get_extruder().get_status().get("target", 0) > 0
                ):
                    add_action(cmd, "M104", f"S={value}")
            elif setting == "bed_temp":
                heater_bed = self.printer.lookup_object("heater_bed", None)
                if heater_bed and heater_bed.get_status().get("target", 0) > 0:
                    add_action(cmd, "M140", f"S={value}")

        for action, values in actions.items():
            script = f"{action} {' '.join(values)}"
            try:
                self.gcode.run_script_from_command(script)
            except Exception as e:
                logging.error(f"Failed to run gcode script '{script}': {e}")

    cmd_APPLY_SETTINGS_help = "Apply current settings to the printer"

    def cmd_APPLY_SETTINGS(self, gcmd):
        enable = gcmd.get_int("ENABLE", None)
        if enable is not None:
            if enable == 0:
                self.apply_on_load = False
                self.gcode.respond_info("Apply settings disabled")
                return
            elif enable == 1:
                self.apply_on_load = True
                self.gcode.respond_info("Apply settings enabled")
            else:
                raise gcmd.error("ENABLE parameter must be 0 or 1")
        else:
            self.apply_settings(list(self.current.keys()))
            self.gcode.respond_info("Settings applied")

    def cmd_IMPORT_KBOBINE(self, gcmd):
        """Import kbobine settings from another printer or default values"""
        host = gcmd.get("HOST", self.DEFAULT_KEY)
        spool_id = gcmd.get_int("ID", 0)

        # Close UI prompt if open
        self.prompt.cmd_PROMPT_CLOSE(gcmd)

        if spool_id != 0:
            if spool_id == self.spool_id:
                raise gcmd.error(f"Spool ID {spool_id} is already in local data")
            settings = self.local_data.get(str(spool_id), {}).get("settings", {}).copy()
            source = f"spool #{spool_id}"
            self.build_datas(settings)

        elif host == "default":
            self.current = self.default.copy()
            source = "default settings"
            self.update_local_data({})

        elif host in self.available_kbobine_datas:
            tmp_settings = self.spoolman.get("kbobine", {}).get(host, {})
            source = "Spoolman settings"
            settings = self.filter_settings_to_store(tmp_settings)
            self.build_datas(settings)

        else:
            raise gcmd.error(f"Unknown host {host}")

        self.current = self.get_settings()

        self.save_remote_data()

        self.gcode.respond_info(
            f"{self.spool_name} imported from {source} and loaded !"
        )
        self.show_settings()
        if self.apply_on_load:
            self.apply_settings(list(self.current.keys()))

    cmd_SET_SPOOL_help = "Set loaded spool parameters"

    def cmd_SET_SPOOL(self, gcmd):
        """Set loaded spool parameters"""
        params = gcmd.get_command_parameters()
        settings = self.validate_settings(params)

        self.update_local_data(settings)
        self.save_remote_data()

        self.current.update(settings)
        self.gcode.respond_info(f"{self.spool_name} settings updated !")
        if self.apply_on_load:
            self.apply_settings(list(settings.keys()))

    cmd_SET_LOADED_MATERIAL_help = "Set current material parameters"

    def cmd_SET_LOADED_MATERIAL(self, gcmd):
        """Set current material parameters"""
        params = gcmd.get_command_parameters()
        settings = self.validate_settings(params)
        self.current.update(settings)
        self.gcode.respond_info("loaded material settings updated !")
        if self.apply_on_load:
            self.apply_settings(list(settings.keys()))

    cmd_GET_SPOOL_help = "Get loaded spool parameters"

    def cmd_GET_SPOOL(self, gcmd):
        """Get loaded spool parameters"""
        self.show_settings()

    cmd_GET_LOADED_MATERIAL_help = "Get current material parameters"

    def cmd_GET_LOADED_MATERIAL(self, gcmd):
        """Get currently loaded material parameters"""
        self.show_settings(type="loaded")

    cmd_LOAD_DEFAULT_MATERIAL_help = (
        "Load default material parameters instead of current spool"
    )

    def cmd_LOAD_DEFAULT_MATERIAL(self, gcmd):
        """Load default material parameters instead of current spool"""
        self.current = self.default.copy()
        self.show_settings(type="loaded")
        if self.apply_on_load:
            self.apply_settings(list(self.current.keys()))

    cmd_DEL_SPOOL_help = "Delete current spool from local data"

    def cmd_DEL_SPOOL(self, gcmd):
        """Delete current spool from local data"""
        params = gcmd.get_command_parameters()

        if self.spool_id == "0":
            self.gcode.respond_info("No spool loaded, nothing to delete")
            return
        if params.get("CONFIRM", None) is not None:
            self.del_local_spool()

            self.gcode.respond_info(f"{self.spool_name} deleted from local data")

            self.current = {}
            self.spoolman = {}
            self.spool_id = "0"
            self.spool_name = None
            self.available_kbobine_datas = []

            # Close UI prompt if open
            self.prompt.cmd_PROMPT_CLOSE(gcmd)
        else:
            self.prompt.question(
                f"Are you sure you want to delete {self.spool_name} from local data ? The datas remains in Spoolman.",
                yes_action="DEL_SPOOL CONFIRM=1",
                title=f"Delete {self.spool_name}",
            )

    cmd_SELECT_MATERIAL_help = (
        "Select material from local db if spoolman is unavailable"
    )

    def cmd_SELECT_MATERIAL(self, gcmd):
        """Select material from local db if spoolman is unavailable"""
        if gcmd.get("ID", None) is not None:
            self.spool_id = gcmd.get_int("ID", 0)
            if self.spool_id == 0:
                self.current = self.default.copy()
                self.spool_name = "Default"
                self.gcode.respond_info("Default settings loaded !")
                self.show_settings(type="loaded")
            elif str(self.spool_id) in self.local_data:
                self.current = self.get_settings()
                self.spool_name = (
                    self.local_data[str(self.spool_id)]["vendor"]
                    + " - "
                    + self.local_data[str(self.spool_id)]["material"]
                    + " - "
                    + self.local_data[str(self.spool_id)]["filament"]
                )
                self.gcode.respond_info("Loading settings from local data !")
                self.show_settings()
            else:
                raise gcmd.error(f"Unknown spool ID {self.spool_id}")
            if self.apply_on_load:
                self.apply_settings(list(self.current.keys()))
            self.prompt.cmd_PROMPT_CLOSE(gcmd)
            return

        if "spool_id" in self.spoolman:
            self.gcode.respond_info(
                "Spoolman is available, use spoolman to select material"
            )
            return

        if len(self.local_data) == 0:
            self.gcode.respond_info("No local data available")
            return

        options = [
            "{} : {} - {} - {}".format(
                id,
                self.local_data[id].get("filament"),
                self.local_data[id].get("vendor"),
                self.local_data[id].get("material"),
            )
            for id in self.local_data
        ]
        colors = ["primary"] * len(self.local_data)
        options.append("Use default settings")
        ids = list(self.local_data.keys()) + ["0"]
        colors.append("secondary")
        self.prompt.select(
            "Select material from local db:",
            options=options,
            values=ids,
            key="ID",
            colors=colors,
            action="SELECT_MATERIAL",
            title="Select Material",
        )


# Helper class to send prompts to the UI (Mainsail, Fluidd and KlipperScreen)
# This class is used to send prompts to the UI for user interaction, such as selecting options,
# asking questions, or displaying messages. It integrates with the printer's G-code system to display
# selection dialogs, questions, and notifications, allowing users to interact with the Kbobine plugin
# for tasks such as importing, confirming, or displaying filament settings.
class PromptUIHelper:
    """
    Helper class to send interactive prompts and messages to the user interface (UI) of supported Klipper frontends
    such as Mainsail, Fluidd, and KlipperScreen. This class integrates with the printer's G-code system to display
    selection dialogs, questions, and notifications, allowing users to interact with the Kbobine plugin for tasks
    such as importing, confirming, or displaying filament settings.
    """

    def __init__(self, printer):
        self.printer = printer
        self.gcode = printer.lookup_object("gcode")
        self.gcode.register_command("PROMPT_CLOSE", self.cmd_PROMPT_CLOSE)

    def _respond_prompt(self, cmds):
        RESPOND = 'RESPOND TYPE=command MSG="action:prompt_'
        commands = (f'{RESPOND}{cmd}"' for cmd in cmds)
        self.gcode.run_script_from_command("\n".join(commands))

    def select(
        self, message, options, values, key, action, title="Kbobine", colors=[]
    ) -> None:
        """Send a prompt to the UI with options to select from"""
        commands = [
            f"begin {title}",
            f"text {message}",
        ]
        # Extend the colors list with "secondary" to ensure each option has a color (fallback if not enough colors specified)
        commands.extend(
            f'button {opt}|{action} {key}="{val}"|{color}'
            for opt, val, color in zip(
                options, values, colors + ["secondary"] * len(options)
            )
        )
        commands.extend(
            [
                "footer_button ABORT|PROMPT_CLOSE|error",
                "show",
            ]
        )
        self._respond_prompt(commands)

    def question(self, message, yes_action, title="Kbobine") -> None:
        """Send a yes/no question prompt to the UI"""
        commands = [
            f"begin {title}",
            f"text {message}",
            f"footer_button Yes|{yes_action}",
            "footer_button No|PROMPT_CLOSE|error",
            "show",
        ]
        self._respond_prompt(commands)

    def msg(self, message, title="Kbobine") -> None:
        """Show a message prompt in the UI"""
        commands = [
            f"begin {title}",
            f"text {message}",
            "footer_button OK|PROMPT_CLOSE",
            "show",
        ]
        self._respond_prompt(commands)

    def cmd_PROMPT_CLOSE(self, gcmd):
        """Close the prompt"""
        self._respond_prompt(["end"])


def load_config(config):
    return Kbobine(config)
