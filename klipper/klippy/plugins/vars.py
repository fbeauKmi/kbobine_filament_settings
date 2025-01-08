# Load global variables to replace placeholders in config and macros
#
# Copyright (C) 2024  Frédéric Beaucamp <fbeaukmi@mailo.eu>
#
# This file may be distributed under the terms of the GNU GPLv3 license.

import ast
import configparser
import json
import os


class GlobalVars:
    def __init__(self, config):
        self.config = config
        printer = config.get_printer()

        # Get the config file path and directory
        configfilename = printer.get_start_args()["config_file"]
        configdir = os.path.dirname(configfilename)
        filename = os.path.join(configdir, "vars.dat")
        # Get the filename from the config or use the default filename
        self.filename = os.path.expanduser(config.get("filename", filename))

        # Initialize variables and file variables dictionaries
        self.vars = {}
        self.filevars = {}

        # Load existing variables from vars.dat if it exists
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r") as f:
                    vars_config = configparser.ConfigParser()
                    vars_config.read_file(f)
                f.close()
            except Exception as e:
                raise config.error("Failed to read %s file: %s" % (e, self.filename))

            # Parse the sections and options from the vars.dat file
            for vars_section in vars_config.sections():
                _, section = vars_section.split(" ", 1)
                self.filevars[section] = {}
                for option in vars_config.options(vars_section):
                    value = vars_config.get(vars_section, option)
                    self.filevars[section][option] = json.loads(value)

            # Update the vars dictionary with the filevars
            self.vars = {
                section: options.copy() for section, options in self.filevars.items()
            }

    def init_var(self, section, varname, value, replace=True):
        # Initialize a variable in the specified section
        if section not in self.vars:
            self.vars[section] = {}
        if self.vars[section].get(varname) is None or replace:
            self.vars[section][varname] = value

    def set_var(self, section, varname, value, persistent=False):
        # Set a variable and optionally make it persistent
        self.init_var(section, varname, value)
        if persistent:
            self.filevars.setdefault(section, {})
            self.filevars[section][varname] = value
            self.write_vars()

    def clear_var(self, section, name, persistent=False):
        # Clear a variable from the specified section
        # if persistent, clear it from the filevars,
        # otherwise clear it from the vars
        if persistent:
            if self.filevars[section].get(name) is not None:
                self.filevars[section].pop(name, None)
                self.write_vars()
        elif section in self.vars:
            self.vars[section].pop(name, None)

    def write_vars(self):
        varfile = configparser.ConfigParser()
        for section, options in self.filevars.items():
            vars_section = "vars %s" % section
            varfile.add_section(vars_section)
            for key, value in self.filevars[section].items():
                varfile.set(vars_section, key, json.dumps(value, indent=2))
        try:
            # Write the variables to the file
            with open(self.filename, "w") as f:
                varfile.write(f)
            f.close()
        except Exception as e:
            raise self.config.error("Failed to write %s file: %s" % (e, self.filename))

    def get_status(self, eventtime):
        # Return the current variables
        return self.vars


class Vars:
    def __init__(self, config):
        self.config = config
        self.section = config.get_name().split()[-1]
        _ = config.get("dummy", "_")  # Hack to avoid warning on empty section

        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object("gcode")

        self.globalvars = self.printer.load_object(config, "vars")

        try:
            options = config.get_prefix_options("")
        except Exception:
            options = []
        # Initialize variables from the config options
        for opt in options:
            v = self.get_literal(config.get(opt))
            self.globalvars.init_var(self.section, opt, v, replace=False)

        # Register G-code commands for setting and deleting variables
        self.gcode.register_command(
            f"SET_VARS_{self.section.upper()}",
            self.cmd_SET_VARIABLE,
            desc=self.cmd_SET_VARIABLE_help,
        )

        self.gcode.register_command(
            f"DEL_VARS_{self.section.upper()}",
            self.cmd_DEL_VARIABLE,
            desc=self.cmd_DEL_VARIABLE_help,
        )

    cmd_SET_VARIABLE_help = "Set the value of a global variable"

    def cmd_SET_VARIABLE(self, gcmd):
        persistent = gcmd.get_int("PERSISTENT", 0, minval=0, maxval=1) == 1
        variables = gcmd.get_command_parameters()
        for variable, value in variables.items():
            variable = variable.lower()
            if variable == "persistent":
                continue

            self.globalvars.set_var(
                self.section, variable, self.get_literal(value), persistent
            )

    cmd_DEL_VARIABLE_help = (
        "Remove a global variable. The config file remains unchanged."
    )

    def cmd_DEL_VARIABLE(self, gcmd):
        persistent = gcmd.get_int("PERSISTENT", 0, minval=0, maxval=1) == 1
        variable = gcmd.get("VARIABLE")
        variable = variable.lower()
        self.globalvars.clear_var(self.section, variable, persistent)

    def get_literal(self, value):
        try:
            literal = ast.literal_eval(value)
            return literal
        except Exception:
            return value


def load_config(config):
    return GlobalVars(config)


def load_config_prefix(config):
    return Vars(config)
