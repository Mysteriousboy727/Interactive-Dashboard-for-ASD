MockGPIO & Simulation

This file explains how the project behaves on non-Raspberry Pi systems and how to use the simulation mode.

Why this exists

- `bongos_controller.py` attempts to import `RPi.GPIO`. If unavailable, it falls back to a `MockGPIO` implementation so the script still runs on Windows or other machines without hardware.

Simulation mode

- Run the script with `--simulate` to enable an interactive console where you can simulate button presses:

  - `l` or `left`  — triggers the left button handler (plays `left.mp4`).
  - `r` or `right` — triggers the right button handler (plays `right.mp4`).
  - `q` or `quit`  — exit simulation mode and stop the script.

Examples

```bash
python bongos_controller.py --simulate
```

Notes

- Video playback tries to use VLC if installed. On Windows it uses the default associated app, and on Linux it tries `xdg-open` if `vlc` is not found.
- When running with the mock, the script prints informative messages for GPIO operations but does not manipulate physical pins.
- Simulation mode is intended for development and testing only.
