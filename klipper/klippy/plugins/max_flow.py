# max_flow
#   - trim speed to limit hotend flow
#
# Copyright (C) 2024 Frederic Beaucamp <fbeaukmi@mailo.eu>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import math


class MaxFlow:
    # Class init
    def __init__(self, config):
        self.config_ref = config
        self.printer = config.get_printer()

        self.enable = self.config_ref.getboolean("enable", False)
        self.max_flow = self.config_ref.getfloat("max_flow", 999999.0, minval=1)

        self.last_position = [0.0, 0.0, 0.0, 0.0]
        self.last_speed = 25.0
        self.speed = 25.0
        self.flow = 0.0

        printer_config = config.getsection("extruder")
        filament_diameter = printer_config.getfloat("filament_diameter")

        self.filament_area = math.pi * (filament_diameter / 2) ** 2

        self.printer.register_event_handler("klippy:connect", self._handle_connect)

        # Register new G-code commands for Setting max_flow
        self.gcode = self.printer.lookup_object("gcode")
        self.gcode.register_command(
            "SET_MAX_FLOW",
            self.cmd_SET_MAX_FLOW,
            desc=self.cmd_SET_MAX_FLOW_help,
        )
        self.gcode.register_command(
            "GET_MAX_FLOW",
            self.cmd_GET_MAX_FLOW,
            desc=self.cmd_GET_MAX_FLOW_help,
        )

    # Helper method to register commands and instantiate required objects
    def _handle_connect(self):
        self.gcode_move = self.printer.lookup_object("gcode_move")

        # Register move transformation while printer rconnect
        self.next_transform = self.gcode_move.set_move_transform(self, force=True)

    # Helper method to return the current retraction parameters
    def get_status(self, eventtime):
        return {
            "enabled": self.enable,
            "max_flow": self.max_flow,
            "request_flow": self.flow,
        }

    # Command to set the max_flow parameters
    cmd_SET_MAX_FLOW_help = "Set max_flow parameters"

    def cmd_SET_MAX_FLOW(self, gcmd):
        enable = 1 if self.enable else 0
        self.enable = gcmd.get_int("ENABLE", enable, minval=0, maxval=1) == 1
        self.max_flow = gcmd.get_float("MAX_FLOW", self.max_flow, minval=1.0)
        if not self.enable:
            self.flow = 0.0

    # Command to get the max_flow parameters
    cmd_GET_MAX_FLOW_help = "Set max_flow parameters"

    def cmd_GET_MAX_FLOW(self, gcmd):
        gcmd.respond_info(
            "MAX_FLOW=%.2f REQUEST_FLOW=%.2f ENABLED=%s"
            % (
                self.max_flow,
                self.flow,
                self.enable,
            )
        )

    # gcode_move transform position helper
    def get_position(self):
        position = self.next_transform.get_position()
        self.last_position[:] = position
        return position

    # gcode_move transform move helper
    def move(self, newpos, speed):
        # check speed only if speed changed
        if newpos[3] != self.last_position[3] and self.enable:
            self.speed, self.flow = self._get_speed(newpos, self.last_position, speed)
            new_speed = self.speed
        else:
            new_speed = speed

        self.next_transform.move(newpos, new_speed)
        self.last_position[:] = newpos
        self.last_speed = speed

    # Helper to limit z_hop while z_max is reached
    def _get_speed(self, oldpos, newpos, speed):
        x1, y1, z1, e1 = oldpos
        x2, y2, z2, e2 = newpos

        dx = x2 - x1
        dy = y2 - y1
        dz = z2 - z1
        de = abs(e2 - e1)

        distance = math.sqrt(dx**2 + dy**2 + dz**2)
        

        # handle extrusion on moves or only extrusion
        # calculcate filamant effective area and speed
        if distance > 0.0:
            e_area = de * self.filament_area / distance
            newspeed = min(speed, self.max_flow / e_area)
        else:
            e_area = self.filament_area
            newspeed = speed
        flow = newspeed * e_area

        return [newspeed, flow]


def load_config(config):
    return MaxFlow(config)
