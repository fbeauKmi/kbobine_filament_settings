# [max_flow]

A klipper helper to limit print speed according max flow

## Configuration reference

```
[max_flow]
#enable: False
#   Set to `True` to enable at startup
value: 35.0
#   Flow in mm^3/s the toolhead must not exceed.
```

Requirements : `filament_diameter` in `[extruder]` must be properly set.

## Commands

The following commands are available when
[max_flow](#configuration-reference) is enabled.

### SET_MAX_FLOW
`SET_MAX_FLOW ENABLE=[0|1] VALUE=<value>`: Set the values
for max_flow. MAX_FLOW value must be in mm^3/s

### GET_MAX_FLOW
Report the current values

## Status reference

The following information is available in the
`max_flow` object:
- `value`: The value of actual setting in mm^3/s
- `request_flow`: The value of last requested extrusion in mm^3/s
- `enabled`: `True` if the max_flow is used, if not `False`

