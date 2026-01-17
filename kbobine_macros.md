## Kbobine configuration and usage

![kbobine](./images/kbobine.png)

Configuration is done by adjusting ``k_bobine/config.cfg``
### parameters 

Parameters stored in a `vars` section named ``KBOBINE``:
```
[vars KBOBINE]
verbose: 0
#   Allowed values 0 or 1. 1 means more verbose in console.
autoremove_default: 0 
#   0 or 1 Autoremove settings when equal to default (see CLEAN_DEFAULT)
apply_on_load: 1
#   0 or 1 Apply settings on load / change (see `APPLY_SETTINGS`). In order to
#   apply settings `<setting>_enabled: True` variable must be set for some
#   parameters(fan_speed, max_flow, extruder_temp, bed_temp, chamber_temp,
#   filament_sensor). 
default: {'parameter': value}
#   Array containing default settings. Settings can be add/remove/change be
#   sure to modify macros `SET_SPOOL` and `SET_LOADED_MATERIAL` according this
#   change.
required: []
#   A list of required settings, If a spool doesn't have this settings. A
#   warning will prompt to add it.
th_depend: []
#   A list of settings that depend on toolhead. For now it only check
#   nozzle_diameter of [extruder] section, the mechanism will be improved.
#   TO BE IMPROVE
<setting>_enabled: <string>
#   allow setting to be applied with `APPLY_SETTINGS`.
<setting>_command: <string>
#   command to overwrite command in `APPLY_SETTINGS`.
```

## Usage / Macros

>[!NOTE]
>Macros are optimized for easy use in the Fluidd/Mainsail UI

`SET_SPOOL` Store settings for current spool. If auto apply is enabled
the settings will be apply at change.

`SET_LOADED_MATERIAL` Change settings to be used by printer. The difference with
previous command, it is not related to spool . The changes will not be stored.
Useful when you want to test value while printing for example.

`LOAD_DEFAULT_MATERIAL` Load default filament settings instead of spool settings.

`APPLY_SETTINGS` Apply settings or enable/disable automatic apply on load/change. 

`GET_SPOOL` Display current spool settings in console.

`GET_LOADED_MATERIAL` Display actual loaded settings in console.

`DEL_SPOOL` Delete spool settings from `kbobine_table`.

`CLEAN_DEFAULT` Remove settings from `kbobine_table` for current filament if same as default value .

`SELECT_MATERIAL` Choose a material among available settings on printer (only when spoolman is unavailable)

## Includes

`core/*` files that contains functions. You don't have to edit this one

`addons/buildplate.cfg` : do not depend of filament settings, store `z_offset` value against buildplate.

`addons/calibrate.cfg` : save calibration values, See Klippain calibration macros.

`addons/fan_speed.cfg` experimental feature to scale the partfan speed. It requires some changes in slicer in order to work. (NOT DOCUMENTED YET)

`addons/klippain-chocolate.cfg` : Klippain-chocolate uses a "kbobine-lite" for material management, this addon overrides some macros to use full Kbobine instead.

`addons/max_flow.cfg` adds max flow module. See [klipper/docs/max_flow.md](./klipper/docs/max_flow.md).

`addons/shrinkage.cfg` adds shrinkage module. See [klipper/docs/shrinkage.md](./klipper/docs/shrinkage.md).

## Required Klipper modules

To get Kbobine working, install [`vars.py`](./klipper/docs/vars.md).

Additionally, some addons require additional module : 
- [`max_flow.py`](./klipper/klippy/plugins/max_flow.py) to limit the maximum volumetric extrusion rate.
- [`shrinkage.py`](./klipper/klippy/plugins/shrinkage.py) to compensate shrinkage via Kbobine instead of slicer.
