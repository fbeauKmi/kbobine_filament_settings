# Load global variables to replace placeholders in config and macros
#
# Copyright (C) 2024  Frédéric Beaucamp <fbeaukmi@mailo.eu>
#
# This file may be distributed under the terms of the GNU GPLv3 license.

import ast
import json

class GlobalVars:
    def __init__(self,config):
        self.vars = {}
    
    def set_var(self, section, value):
        if section not in self.vars:
            self.vars[section] = {}
        self.vars[section].update(value)
    
    def get_var(self, section, name, default=None):
        if section in self.vars:
            return self.vars[section].get(name, default)
        return default
    
    def get_vars(self,section):
        return self.vars.get(section,{})
    
    def get_status(self,eventtime):
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
            self.vars[opt.lower()] = self.get_literal(config.get(opt))
        
        self.globalvars.set_var(self.section, self.vars)

        self.gcode.register_command(
            f"SET_VARS_{self.section.upper()}",
            self.cmd_SET_VARIABLE,
            desc=self.cmd_SET_VARIABLE_help,
        )

    cmd_SET_VARIABLE_help = "Set the value of a global variable"

    def cmd_SET_VARIABLE(self, gcmd):
        configfile = self.printer.lookup_object("configfile")
        save = gcmd.get_int("SAVE", 0, minval=0, maxval=1)
        variables = gcmd.get_command_parameters()
        v = dict(self.globalvars.get_vars(self.section))
        for variable, value in variables.items():
            variable = variable.lower()
            if variable == "save":
                continue

            v[variable] = self.get_literal(value)

            if save:
                configfile.set(self.section, variable, value)
                self.gcode.respond_info(
                    "Use SAVE_CONFIG command to keep new value for `%s` in printer"
                    "config at restart." % (variable)
                )
        self.globalvars.set_var(self.section, v)

    def get_literal(self, value):
        try:
            literal = ast.literal_eval(value)
            json.dumps(literal, separators=(",", ":"), indent=2)
            return literal
        except Exception:
            return value

def load_config(config):
    return GlobalVars(config)

def load_config_prefix(config):
    return Vars(config)
