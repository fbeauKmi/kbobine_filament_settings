## Kbobine configuration and usage

![kbobine](./images/kbobine.png)

`klipper/plugins/kbobine.py` adds max flow module. See [klipper/docs/kbobine.md](./klipper/docs/kbobine.md).

## Includes

`addons/buildplate.cfg` : do not depend of filament settings, store `z_offset` value against buildplate.

`addons/calibrate.cfg` : save calibration values, See Klippain calibration macros.

`addons/fan_speed.cfg` experimental feature to scale the partfan speed. It requires some changes in slicer in order to work. (NOT DOCUMENTED YET)

`addons/klippain-chocolate.cfg` : Klippain-chocolate uses a "kbobine-lite" for material management, this addon overrides some macros to use full Kbobine instead.

`addons/max_flow.cfg` adds max flow module. See [klipper/docs/max_flow.md](./klipper/docs/max_flow.md).

`addons/shrinkage.cfg` adds shrinkage module. See [klipper/docs/shrinkage.md](./klipper/docs/shrinkage.md).

## Required Klipper modules

To get Kbobine working, install [`kbobine.py`](./klipper/klippy/plugins/kbobine.py).

Additionally, some addons require additional module : 
- [`max_flow.py`](./klipper/klippy/plugins/max_flow.py) to limit the maximum volumetric extrusion rate.
- [`shrinkage.py`](./klipper/klippy/plugins/shrinkage.py) to compensate shrinkage via Kbobine instead of slicer.
- [`vars.py`](./klipper/docs/vars.md) to store variables, required by addons macros.
