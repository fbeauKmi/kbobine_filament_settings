# [vars]

A klipper helper to manage global variables for macros.

## Configuration reference

```
[vars]
#filename: ~/printer_data/config/vars.dat
#  The file used to store persistent variables. If unset the default is 
#  `.vars.dat` located in the same directory as your Klipper configuration
#  files. 

[vars <SECTION_NAME>]
#<variable_name>: value
```

## Commands

The following commands are available when
[vars](#configuration-reference) is enabled.

### SET_VARS_<SECTION>
`SET_VARS_<SECTION> <var_name>=<value> PERSISTENT=[0|1]`: Set the value of a global variable. If `PERSISTENT` is set to `1`, the variable will be saved to a file.

### DEL_VARS_<SECTION>
`DEL_VARS_<SECTION> VARIABLE=<name> PERSISTENT=[0|1]`: Remove a global variable. If `PERSISTENT` is set to `1`, the variable will be removed from the file, not from the config.

## Status reference

The `vars` section contains the current variables.

## Persistent Variable Management

The file is created automatically when a variable is set with the `PERSISTENT` 
flag enabled. This file is used to store persistent variables across restarts.
Persistent variables will overwrite the variables present in the configuration.

### Example

To create and store a persistent variable, use the following command:

```
SET_VARS_<SECTION> VARIABLE=<value> PERSISTENT=1
```

This will create a file if it does not already exist and store the variable in it.

To remove a persistent variable, use:

```
DEL_VARS_<SECTION> VARIABLE=<name> PERSISTENT=1
```
This will update the file accordingly.

> [!NOTE]
> This will not remove variable from configuration or dictionnary. To remove from
> dictionnary run `DEL_VARS_<SECTION> VARIABLE=<name>`


## Using Variables in Macros

To use a variable in a macro, you can reference it by its name within the macro definition. Here is an example:

```
[vars my_section]
my_variable: 42

[gcode_macro EXAMPLE_MACRO]
gcode:
    {% set my_variable = printer.vars.my_section.my_variable %}
    M117 The value of my_variable is { my_variable }
    SET_VARS_MY_SECTION MY_VARIABLE={ my_variable|int + 1 } PERSISTENT=1
```

In this example, `my_variable` is retrieved from the `vars` section and used within the macro to display its value on the printer's screen.
