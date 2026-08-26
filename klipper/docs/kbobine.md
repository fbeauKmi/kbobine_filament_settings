# [kbobine]

A gateway klipper module to get/set datas from/to Spoolman

## Configuration reference

```
[kbobine]
apply_on_load: true
#   true|false. Apply settings on load / change (see `APPLY_SETTINGS`). In order to
#   apply settings `<setting>_enabled: True` variable must be set for some
#   parameters(fan_speed, max_flow, extruder_temp, bed_temp, chamber_temp,
#   filament_sensor). 
default: 
     ## Default settings    [default, min, max, enabled, command]
    bed_temp              : [ 100,  50, 125, True, M104],
    extruder_temp         : [ 250, 190, 270],
#   Settings to store (depend of the user need)
required: bed_temp,extruder_temp
#   Coma separated list of required settings, If a spool doesn't have this settings. A
#   warning will prompt to add it.
th_depend: extruder_temp
#   A list of settings that depend on toolhead. For now it only check
#   nozzle_diameter of [extruder] section, the mechanism will be improved.
#   TO BE IMPROVE
store_in_spoolman: true     # True|False Store settings in Spoolman db (see doc)
spool_file: ~/printer_data/config/spool.json
# File that contains filament/spool settings

[vars KBOBINE]
<setting>_enabled: <string>
#   allow setting to be applied with `APPLY_SETTINGS`.
<setting>_command: <string>
#   command to overwrite command in `APPLY_SETTINGS`.
```

## Commands

The following commands are available when
[kbobine](#configuration-reference) is enabled.

>[!NOTE]
>Commands are optimized for easy use in the Fluidd/Mainsail UI,
>The kbobine module adds fake macros at klipper startup, that can be used in UI

`SET_SPOOL` Store settings for current spool. If auto apply is enabled
the settings will be apply at change.

`SET_LOADED_MATERIAL` Change settings to be used by printer. The difference with
previous command, it is not related to spool . The changes will not be stored.
Useful when you want to test value while printing for example.

`LOAD_DEFAULT_MATERIAL` Load default filament settings instead of spool settings.

`APPLY_SETTINGS` Apply settings or enable/disable automatic apply on load/change. 

`GET_SPOOL` Display current spool settings in console.

`GET_LOADED_MATERIAL` Display actual loaded settings in console.

`DEL_SPOOL` Delete spool settings from json file.

`SELECT_MATERIAL` Choose a material among available settings on printer (only when spoolman is unavailable)

## Status reference

The following information is available in the
`kbobine` object:
- `defaut`: An array of default settings 
- `current_settings`: an array of the value of loaded settings
- `spoolman`: an array of the datas from Spoolman (spoolid, filament, endor, material, printer settings, ...)
- `spool_id` : 0 if no spool is loaded
- `spool_name`: Unified name of the loaded spool