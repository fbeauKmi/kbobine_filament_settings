> [!WARNING]
This is an experimental feature, use it with extreme care. 

# What shrinkage is ?

Shrinkage in 3D printing refers to the reduction in size of the final 
model due to temperature changes from the melted thermoplastic to the
cooled extruded
material layers.

# [shrinkage] _experimental_

A Klipper/kalico plugin that modifies the gcode to compensate for shrinkage.
Typically, slicers scale the model before slicing to apply compensation.
This plugin scales the extrusion and adjusts the toolhead position according
to the shrinkage value.

It uses the center of the bed as reference to modify
the request X Y toolhead position.

> [!NOTE]
To determine the shrinkage value, print a 100mm long model, allow it to cool down, and measure its length. Calculate the shrinkage value using the formula: `value = measured_length / model_length`. Be sure shrinkage or any other compensation is inactive in printer/slicer.
Shrinkage can be different for XY and Z axis.

## Configuration reference

```
[shrinkage]
xy_value: 1.0
#   Shrinkage factor to apply to the model dimensions in xy. 
#   Min value 0.95, max value 1.00
z_value: 1.0
#   Shrinkage factor to apply to the model dimensions in z.
#   Min value 0.95, max value 1.00
```

Shrinkage compensation is always disabled at print startup. You must enable it at the end of your Strat print macro. Compensation occurs only during printing, never when the printer is paused to avoid issues with PARK, NOZZLE_CLEAN.

## Commands

The following commands are available when [shrinkage](#configuration-reference) is enabled.

### SET_SHRINKAGE
`SET_SHRINKAGE ENABLE=[0|1] XY_VALUE=<value> Z_VALUE=<value>` : Set the values for shrinkage. VALUE must be between 0.95 and 1.00.

### GET_SHRINKAGE
Report the current values.

## Status reference

The following information is available in the `shrinkage` object:
- `shrinkage_xy`: The current shrinkage factor for xy.
- `shrinkage_z`: The current shrinkage factor for z.
- `enabled`: `True` if shrinkage is used, otherwise `False`.
