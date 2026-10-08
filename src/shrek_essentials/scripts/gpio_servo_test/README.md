# 4-servo GPIO test (no PCA9685)

Tests up to 4 servos wired straight to the Raspberry Pi's GPIO header. Use it to
check single servos (and their wiring) before you connect them to the PCA9685
boards used by `shrek_navigation/scripts/*.py`.

## Wiring

| Servo | Signal (orange/yellow) | BCM pin | Physical pin |
|-------|------------------------|---------|--------------|
| 0     | GPIO12                 | 12      | 32           |
| 1     | GPIO13                 | 13      | 33           |
| 2     | GPIO18                 | 18      | 12           |
| 3     | GPIO19                 | 19      | 35           |

- **Servo red (V+)** → `+` of an **external 5–6 V supply** (≥1 A per SG90, ≥2 A per MG995).
- **Servo brown/black (GND)** → `−` of that supply **and** any Pi GND pin (e.g. physical pin 6, 9, 14, 20, 30, 34 or 39).
  Without this shared ground the servos jitter or don't move at all.
- **Don't power servos from the Pi's 5 V pin.** Stall current will brown out or reset the Pi.

The servos read the Pi's 3.3 V signal without a level shifter.

To use other pins, pass them with `--pins`, e.g. `--pins 17 27 22 23`.

## Setup (once, on the Pi)

```bash
cd src/shrek_essentials/scripts/gpio_servo_test
bash setup_rpi.sh
```

This installs `gpiozero` + `lgpio`. On a Pi 3 or 4 it also installs and starts
`pigpiod`, which gives jitter-free pulses on any pin. The script picks the best
backend it finds on its own.

## Usage

```bash
python3 servo_gpio_test.py                 # sweep: each servo one at a time (start here)
python3 servo_gpio_test.py all             # all 4 move together
python3 servo_gpio_test.py center          # all to 90°, hold (good for mounting horns)
python3 servo_gpio_test.py wave --hold 20  # sine wave across servos for 20 s
python3 servo_gpio_test.py interactive     # drive them by hand
python3 servo_gpio_test.py --dry-run all   # no hardware, just checks the script runs
```

In `interactive` mode:

```
servo> 0 45        # servo 0 to 45°
servo> all 90      # every servo to 90°
servo> p 2 1500    # raw 1500 µs pulse on servo 2 (for calibration)
servo> off         # stop pulses, servos go limp
servo> q
```

Useful options (see `--help` for all):

| Option | Default | Meaning |
|--------|---------|---------|
| `--min-angle` / `--max-angle` | 45 / 135 | Sweep range. Kept narrow so servos mounted in the robot don't hit their limits. Widen to 0/180 for loose servos. |
| `--min-pulse` / `--max-pulse` | 500 / 2500 µs | Pulse widths for 0° and 180° (same as the PCA scripts). Use 1000/2000 if a servo buzzes at the ends. |
| `--cycles` | 1 | Number of repeats for `sweep` / `all`. |
| `--step`, `--delay` | 2°, 0.02 s | Ramp smoothness and speed. |
| `--backend` | auto | Force `pigpio`, `lgpio` or `default`. |
| `--no-detach` | off | Keep holding torque after the script exits. |

On exit or Ctrl+C the script returns every servo to `--center` and then stops
the pulses.

## Troubleshooting

- **Servo twitches or jitters:** check the shared ground first. Then make sure the supply holds 5 V under load. Some jitter is normal on the `lgpio` backend. On a Pi 3 or 4, run `sudo systemctl start pigpiod` to get clean pulses.
- **`Failed to open GPIO pins`:** run the setup script, log out and back in (for the `gpio` group), or try `sudo`.
- **Nothing moves:** check the signal wire is on the BCM pin, not the physical pin with the same number. Run `interactive` and try `p 0 1500`.
- **Pi reboots when servos move:** the servos are drawing power from the Pi. Use the external supply.
