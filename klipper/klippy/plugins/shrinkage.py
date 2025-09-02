# shrinkage.py
# - Klipper plugin to resize model to compensate for shrinkage
#
# Copyright (C) 2025 Frederic Beaucamp <fbeaukmi@mailo.eu>
#
# This file may be distributed under the terms of the GNU GPLv3 license.


class Shrinkage:
    # Class init
    def __init__(self, config):
        self.config_ref = config
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.toolhead = None #object will be set on connect
        self.gcode_move = None #object will be set on connect

        self.enable = False
        self.allowed = False
        self.shrinkage_xy = self.config_ref.getfloat(
            "xy_value", 1, minval=0.95, maxval=1
        )
        self.shrinkage_z = self.config_ref.getfloat("z_value", 1, minval=0.95, maxval=1)
        self.center = [0.0, 0.0]
        self.deltacenter = [0.0, 0.0]
        self.last_position = [0.0, 0.0, 0.0, 0.0]

        self.printer.register_event_handler("klippy:connect", self._handle_connect)

        self.pause_resume = self.printer.lookup_object("pause_resume")

        # Register new G-code commands
        self.gcode = self.printer.lookup_object("gcode")
        self.gcode.register_command(
            "SET_SHRINKAGE",
            self.cmd_SET_SHRINKAGE,
            desc=self.cmd_SET_SHRINKAGE_help,
        )
        self.gcode.register_command(
            "GET_SHRINKAGE",
            self.cmd_GET_SHRINKAGE,
            desc=self.cmd_GET_SHRINKAGE_help,
        )

    # Helper method to register commands and instantiate required objects
    def _handle_connect(self):
        self.gcode_move = self.printer.lookup_object("gcode_move")

        self.toolhead = self.printer.lookup_object("toolhead")

        kin_status = self.toolhead.get_kinematics().get_status(None)
        # Calculate the center of the bed
        self.center[0] = (
            kin_status["axis_minimum"][0] + kin_status["axis_maximum"][0]
        ) / 2
        self.center[1] = (
            kin_status["axis_minimum"][1] + kin_status["axis_maximum"][1]
        ) / 2
        self._deltacenter()

        # Register move transformation while printer connect
        self.next_transform = self.gcode_move.set_move_transform(self, force=True)

        # Register event handlers
        self.printer.register_event_handler(
            "print_stats:start_printing", self._allow_shrinkage
        )
        self.printer.register_event_handler(
            "print_stats:complete_printing", self._disable_shrinkage
        )
        self.printer.register_event_handler(
            "print_stats:cancelled_printing",
            self._disable_shrinkage,
        )

    # Helper method to return the current shrinkage parameters
    def get_status(self, eventtime):
        return {
            "enabled": self.enable,
            "xy_value": self.shrinkage_xy,
            "z_value": self.shrinkage_z,
        }

    # Command to set the shrinkage parameters
    cmd_SET_SHRINKAGE_help = "Set shrinkage parameters"

    def cmd_SET_SHRINKAGE(self, gcmd):
        enable = 1 if self.enable else 0
        self.enable = gcmd.get_int("ENABLE", enable, minval=0, maxval=1) == 1
        self.shrinkage_xy = gcmd.get_float(
            "XY_VALUE", self.shrinkage_xy, minval=0.95, maxval=1
        )
        self.shrinkage_z = gcmd.get_float(
            "Z_VALUE", self.shrinkage_z, minval=0.95, maxval=1
        )
        self._deltacenter()

    # Command to get the shrinkage parameters
    cmd_GET_SHRINKAGE_help = "Get shrinkage values"

    def cmd_GET_SHRINKAGE(self, gcmd):
        gcmd.respond_info(
            "SHRINKAGE XY_VALUE=%.4f Z_VALUE=%.4f ENABLED=%s"
            % (
                self.shrinkage_xy,
                self.shrinkage_z,
                self.enable,
            )
        )

    # gcode_move transform position helper
    def get_position(self):
        position = self.next_transform.get_position()
        self.last_position = position  # save last extrusion for next move
        return position

    # gcode_move transform move helper
    def move(self, newpos, speed):
        # Shrinkage is only applied when the printer is printing
        if self.enable:
            # Disable the shrinkage when the printer is paused or not homed
            eventtime = self.reactor.monotonic()
            if self.allowed and (
                self.pause_resume.get_status(eventtime)["is_paused"]
                or self.toolhead.get_status(eventtime)["homed_axes"] != "xyz"
            ):
                self.allowed = False
            if self.allowed:
                if newpos[:2] != self.last_position[:2]:
                    newpos[:2] = [
                        pos / self.shrinkage_xy - delta
                        for pos, delta in zip(newpos[:2], self.deltacenter)
                    ]
                if newpos[2] != self.last_position[2]:
                    newpos[2] /= self.shrinkage_z
                v = newpos[3] - self.last_position[3]
                newpos[3] = self.last_position[3] + v / (
                    self.shrinkage_xy**2 * self.shrinkage_z
                )
        self.last_position = newpos  # save last extrusion for next move

        self.next_transform.move(newpos, speed)

    # Helper method to calculate the center of the bed
    def _deltacenter(self):
        self.deltacenter = [c * (1 / self.shrinkage_xy - 1) for c in self.center[:2]]

    # Helper method to allow shrinkage
    def _allow_shrinkage(self):
        self.allowed = True

    # Helper method to disable shrinkage
    def _disable_shrinkage(self):
        self.enable = False
        self.allowed = False


def load_config(config):
    return Shrinkage(config)
