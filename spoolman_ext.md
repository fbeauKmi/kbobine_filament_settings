# spoolman_ext.py

``spoolman_ext.py`` is the extension for Moonraker that allows Spoolman to transmit datas to klipper. In order to use it you must have
a working Spoolman configuration in moonraker (See [Spoolman repository](https://github.com/Donkie/Spoolman) and [Spoolman config reference](https://moonraker.readthedocs.io/en/latest/configuration/#spoolman) in Moonraker)

## Installation 
See [kbobine installation](README.md#run-the-installer)  

you can also manually copy the file in ``~/moonraker/moonraker/components``.

## Configuration reference for ``moonraker.conf``

```ini
[spoolman_ext]
gcode:
#   A gcode jinja2 template to execute after a spool change. 
#   The default is no gcode.
#   {spool} is the available dict in the template it contains datas
#   returned by Spoolman API 
#   https://donkie.github.io/Spoolman/#tag/spool/operation/Get_spool_spool__spool_id__get 
```
## Callable API

The ``gcode`` is callable from a klipper macro with
``{action_call_remote_method("get_spoolman_datas")}``.  It is useful after a firmware restart for exemple. See example below.

## Simple use case: Check in ``PRINT_START`` if a spool is selected

Setup `` moonraker.conf``
```ini
[spoolman_ext]
gcode:
    SET_GCODE_VARIABLE MACRO=PRINT_START VARIABLE=spoolman_loaded VALUE="{% if spool.id %}1{% else %}0{% endif %}"
```

add in Klipper config
```ini
[delayed_gcode _KLIPPER_STARTUP_HANDLER]
# delay to call spool datas after klipper startup
initial_duration: 5
# Ask moonraker to render template configured in spoolman_ext.conf 
gcode: {action_call_remote_method("get_spoolman_datas")} 
```

Modify PRINT_START Macro
```ini
[gcode_macro PRINT_START]
variable_spoolman_loaded: 0
gcode:
    {% if spoolman_loaded|int == 0 %}
        {action_raise_error("Hey! Stop sleeping and select a spool! ")}
    {% endif %}
    ... <The rest of your PRINT_START here>
```


