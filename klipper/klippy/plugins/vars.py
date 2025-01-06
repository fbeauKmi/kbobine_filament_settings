# Load global variables to replace placeholders in config and macros
#
# Copyright (C) 2024  Frédéric Beaucamp <fbeaukmi@mailo.eu>
#
# This file may be distributed under the terms of the GNU GPLv3 license.

import ast
import json


class GlobalVars:
    def __init__(self, config):
        self.config = config
        self.vars = {}
        self.filename = config.get("filename", None)
        if config.has_section("vars"):
            raise config.error("'vars' must be a named section. See docs.")

    def set_var(self, section, variable, value, save=False):
        if section not in self.vars:
            self.vars[section] = {}
        self.vars[section][variable] = value
        if save:
            configfile = self.printer.lookup_object("configfile")
            configfile.set(section, variable, json.dumps(value, indent=2))
            self.gcode.respond_info(
                "Use SAVE_CONFIG command to keep new value for `%s` in printer"
                "config at restart." % variable
            )

    def clear_var(self, section, name):
        if section in self.vars:
            self.vars[section].pop(name, None)

    def get_status(self, eventtime):
        return self.vars


class Vars:
    def __init__(self, config):
        self.config = config
        self.section = config.get_name().split()[-1]
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object("gcode")
        self.globalvars = self.printer.load_object(config, "vars")

        try:
            options = config.get_prefix_options("")
        except Exception:
            options = []

        self.vars = {}
        for opt in options:
            v = self.get_literal(config.get(opt))
            self.globalvars.set_var(self.section, opt, v)

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
        save = gcmd.get_int("SAVE", 0, minval=0, maxval=1)
        variables = gcmd.get_command_parameters()
        for variable, value in variables.items():
            variable = variable.lower()
            if variable == "save":
                continue

            self.globalvars.set_var(
                self.section, variable, self.get_literal(value), save
            )

    cmd_DEL_VARIABLE_help = (
        "Remove a global variable. The config file remains unchanged."
    )

    def cmd_DEL_VARIABLE(self, gcmd):
        variable = gcmd.get("VARIABLE")
        variable = variable.lower()
        self.globalvars.clear_var(self.section, variable)

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
