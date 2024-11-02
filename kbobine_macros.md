## Kbobine configuration and usage

![kbobine](./images/kbobine.png)

Configuration is done by adjusting ``k_bobine/config.cfg``
### parameters 

Parameters stored in a macro named ``_KBOBINE``:

``verbose`` : 0 or 1 More verbose in console.

``autoremove_default`` 0 or 1 Autoremove settings when equal to default (see ``CLEAN_DEFAULT``)

``apply_on_load`` 0 or 1 Apply settings on load / change (see ``APPLY_SETTINGS``). In order to apply settings ``<setting>_enabled: True`` variable must be set for some parameters(fan_speed, max_flow, extruder_temp, bed_temp, chamber_temp, filament_sensor). 

``default`` Array containing default settings. Settings can be add/remove/change be sure to modify macros ``SET_SPOOL`` and ``SET_LOADED_MATERIAL`` according this change.

``required`` A list of required settings, If a spool doesn't have this settings
a warning will prompt to add it.

``th_depend`` A list of settings that depend on toolhead. For now it only check ``nozzle_diameter`` of ``[extruder]`` section, the mechanism will be improved. TO BE IMPROVE

``current_settings`` Array that contains settings used by ``APPLY_SETTINGS``, Settings can be changed with ``SET_LOADED_MATERIAL``

``spoolman`` contains spool id, name, vendor and material of current spool

``spool_id`` Loaded spool id

``<setting>_enabled`` allow setting to be applied with ``APPLY_SETTINGS``.

``<setting>_command`` to overwrite command in ``APPLY_SETTINGS``.

## Usage / Macros

>[!NOTE]
>Macros are optimized for easy use in the Fluidd/Mainsail UI

``SET_SPOOL`` Store settings for current spool. If auto apply is enabled
the settings will be apply at change.

``SET_LOADED_MATERIAL`` Change settings to be used by printer. The difference with
previous command, it is not related to spool . The changes will not be stored.
Useful when you want to test value while printing for example.

``LOAD_DEFAULT_MATERIAL`` Load default filament settings instead of spool settings.

``APPLY_SETTINGS`` Apply settings or enable/disable automatic apply on load/change. 

``GET_SPOOL`` Display current spool settings in console.

``GET_LOADED_MATERIAL`` Display actual loaded settings in console.

``DEL_SPOOL`` Delete spool settings from ``kbobine_table``.

``CLEAN_DEFAULT`` Remove settings from `kbobine_table`` for current filament if same as default value .

## Includes

``core/*`` files that contains functions. You don't have to edit this one

``addons/save_variables.cfg`` to include if there's no \[saved_variable\] section in the config.

``klippain.cfg`` an experimental feature that populate ``material_parameters`` variable of Klippain with stored settings. Allowed settings : 'pressure_advance', 'retract_length', 'unretract_extra_length', 'retract_speed', 'unretract_speed', 'filter_speed', 'additional_z_offset', 'filament_sensor'. 
Initial ``material_parameters`` is used as reference according material type from Spoolman
More information about [Klippain]()

``addons/max_flow.cfg`` experimental feature that limit max_flow. It requires some changes in slicer in order to work. (NOT DOCUMENTED YET)

``addons/fan_speed.cfg`` experimental feature to scale the partfan speed. It requires some changes in slicer in order to work. (NOT DOCUMENTED YET)
