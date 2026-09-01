# shrinkage.py
# - Klipper plugin to resize model to compensate for shrinkage
#
# Copyright (C) 2025-2026 Frederic Beaucamp <fbeaukmi@mailo.eu>
# Changes:
# - 2025-06-15: Initial version
# - 2026-07-28: Fixed bug with E offset calculation and added support for pause/resume events
#
# This file may be distributed under the terms of the GNU GPLv3 license.


class Shrinkage:
    # Class init
    def __init__(self, config):
        self.config_ref = config
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.toolhead = None  # object will be set on connect
        self.gcode_move = None  # object will be set on connect

        self.enable = False
        self.allowed = False
        self.th_homed = False
        self.printing = False
        self.shrinkage_xy = self.config_ref.getfloat(
            "xy_value", 1, minval=0.95, maxval=1
        )
        self.shrinkage_z = self.config_ref.getfloat("z_value", 1, minval=0.95, maxval=1)
        self.center = [0.0, 0.0]
        self.deltacenter = [0.0, 0.0]
        self.last_e = 0.0
        self.base_e = 0.0
        self.current_offset_e = 0.0

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
            "print_stats:start_printing", self._is_printing
        )
        self.printer.register_event_handler(
            "print_stats:complete_printing", self._disable_shrinkage
        )
        self.printer.register_event_handler(
            "print_stats:cancelled_printing",
            self._disable_shrinkage,
        )
        self.printer.register_event_handler(
            "homing:home_rails_end", self.handle_homing_move_end
        )
        self.printer.register_event_handler("stepper_enable:motor_off", self.motor_off)

    def handle_homing_move_end(self, homing_state, rails):
        if 2 in homing_state.get_axes():
            self.th_homed = True

    def motor_off(self, print_time):
        self.th_homed = False
        self._disable_shrinkage()

    def _check_allowed(self):
        allowed = (
            not self.pause_resume.get_status(None)["is_paused"]
            and self.th_homed
            and self.printing
        )
        if allowed != self.allowed:
            self.allowed = allowed
            if allowed:
                self.base_e = (
                    self.last_e
                )  # Update base_e to the current last_e when shrinkage is enabled
            else:
                self._reset_offset_e()

    # Helper method to allow shrinkage
    def _is_printing(self):
        self.printing = True

    # Helper method to disable shrinkage
    def _disable_shrinkage(self):
        self.enable = False
        self.printing = False
        self._reset_offset_e()

    def _reset_offset_e(self):
        offset = self.current_offset_e
        self.current_offset_e = 0.0
        self.gcode.run_script_from_command(f"SET_GCODE_OFFSET E_ADJUST={offset} MOVE=1")

    # Helper method to return the current shrinkage parameters
    def get_status(self, eventtime):
        return {
            "enabled": self.enable,
            "active": self.allowed,
            "xy_value": self.shrinkage_xy,
            "z_value": self.shrinkage_z,
            "offset_e": self.current_offset_e,
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
            f"SHRINKAGE XY_VALUE={self.shrinkage_xy:.4f} Z_VALUE={self.shrinkage_z:.4f} ENABLED={self.enable}"
        )

    # gcode_move transform position helper
    def get_position(self):
        position = self.next_transform.get_position()
        if self.enable and self.allowed:
            position[:2] = [
                (pos + delta) * self.shrinkage_xy
                for pos, delta in zip(position[:2], self.deltacenter)
            ]
            position[2] *= self.shrinkage_z
            position[3] = self.base_e + (position[3] - self.base_e) * (
                self.shrinkage_xy**2 * self.shrinkage_z
            )
        else:
            position[3] -= self.current_offset_e

        return position

    # gcode_move transform move helper
    def move(self, newpos, speed):
        # Shrinkage is only applied when the printer is printing
        # Disable the shrinkage when the printer is paused or not homed
        self._check_allowed()
        if self.enable and self.allowed:
            newpos[:2] = [
                pos / self.shrinkage_xy - delta
                for pos, delta in zip(newpos[:2], self.deltacenter)
            ]
            newpos[2] /= self.shrinkage_z
            self.last_e = newpos[3]  # Update last_e before modifying newpos[3]
            newpos[3] = self.base_e + (self.last_e - self.base_e) / (
                self.shrinkage_xy**2 * self.shrinkage_z
            )
            self.current_offset_e = (
                newpos[3] - self.last_e
            )  # Update offset_e based on the change in E
        else:
            newpos[3] += self.current_offset_e

        self.next_transform.move(
            newpos, speed
        )  # move to the new position with the next transform

    # Helper method to calculate the center of the bed
    def _deltacenter(self):
        self.deltacenter = [c * (1 / self.shrinkage_xy - 1) for c in self.center[:2]]


def load_config(config):
    return Shrinkage(config)
