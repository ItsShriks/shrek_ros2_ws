# Shrek robot setup: from wiring to standing

Tools to wire, check, map, calibrate and stand up the 17-servo robot
(MG996R servos, one PCA9685 board, 5 V 10 A supply, Raspberry Pi).

| Script | What it does | Moves servos? |
|---|---|---|
| `setup_pi.sh` | One-time install: I2C, Python libraries, permissions | no |
| `01_check_system.py` | Checks Pi power, libraries, I2C, PCA9685 and the config | no |
| `02_identify_channels.py` | Wiggles each channel; you say which joint moved | yes, ±15° |
| `03_calibrate.py` | Per joint: set neutral (straight), direction, limits | yes |
| `04_stand.py` | Switches servos on one by one into the stand pose; live balance trims | yes |
| `relax.py` | Stops all pulses, servos go limp | releases |
| `shrek_servos.py` | Shared library used by all of the above | - |

Everything is stored in `src/shrek_essentials/config/servo_config.yaml`.

Every script takes `--dry-run` (no hardware) and `--help`.

---

## 1. Fix the wiring first (from the photos)

### Servo power: replace the jumper wires

The 5 V supply is connected to the PCA9685's green terminal with **thin Dupont
jumper wires**. Those are good for roughly 1–3 A. 17 MG996R servos holding the
robot up can draw several amps and peak far higher when they switch on. Thin
wires drop the voltage, which shows up as twitching, servos resetting, or
the robot sagging, and the wires and connectors get hot.

- Use **18 AWG (0.75–1 mm²) wire**, red and black, kept as short as practical.
- **Strip the ends and clamp the bare copper** directly in both screw terminals
  (supply `+V`/`-V`, PCA `V+`/`GND`). No Dupont pins in screw terminals.
- Polarity on your parts: supply terminal **⊖ left, ⊕ right**. PCA terminal
  **V+ left, GND right** (label next to the terminal). Your photos show this
  the right way round. Keep it that way.
- After the robot has stood for a minute, feel the wires and the PCA terminal.
  Warm = too thin or a loose screw.

### Mains side of the supply

The 230 V terminal (brown L, blue N, yellow-green earth) is exposed. Keep the
clear cover clipped on, never touch the supply while it's plugged in, and fix
it to something (or put it in a box) so it can't slide around on the desk next
to loose wires and a screwdriver.

### Pi ↔ PCA9685 (the 6-pin header on the left edge of the board)

| PCA9685 | Raspberry Pi pin |
|---|---|
| GND | pin 6 (GND) |
| OE | not connected |
| SCL | pin 5 (GPIO3 / SCL) |
| SDA | pin 3 (GPIO2 / SDA) |
| VCC | **pin 1 (3.3 V)**, logic power only |
| V+ | not connected (servo power comes in on the green terminal) |

- **Pi power:** power the Pi from its **own** USB-C supply, not from the
  servo supply. The PCA's GND pin already links the two grounds, which is
  all that's needed.
- **POWER LED:** the LED on the PCA board shows VCC (the Pi's 3.3 V), not
  servo power.

### Servos ↔ PCA9685

Each servo plug: **brown → GND row (black, board edge), red → V+ row (red),
orange → PWM row (yellow)**. A plug in backwards won't damage anything
usually, but the servo won't move.

### The 17th servo

One PCA9685 has 16 channels. The config puts the 17th servo (head) on
**Pi GPIO12 (physical pin 32)**:

- **Signal:** orange wire to pin 32.
- **Power:** red and brown wires to the 5 V supply, not the Pi.

The head isn't needed for standing. If you have a second PCA9685, solder its
`A0` pad (address `0x41`), add `0x41` to `pca9685_addresses`, and give the
head `board: 0x41, channel: 0` instead of `gpio: 12`.

### Is 5 V / 10 A enough?

For standing and slow moves, yes, as long as the wires are thick enough. Fast
moves (jump/run) can briefly exceed 10 A. If the supply's protection trips,
the servos all go limp at once. `04_stand.py` switches servos on one at a
time (0.3 s apart) to avoid a 17-servo inrush spike.

---

## 2. Install (once, on the Pi)

```bash
cd ~/shrek_ros2_ws/src/shrek_essentials/scripts/robot_setup
bash setup_pi.sh
sudo reboot
```

If setup created `~/shrek_venv`, run `source ~/shrek_venv/bin/activate` in each
new terminal before using the scripts.

## 3. Get it standing today

Run everything from `src/shrek_essentials/scripts/robot_setup`.

### Step 1: system check (nothing moves)

```bash
python3 01_check_system.py
```

Fix every `FAIL`. Expect `WARN ... not calibrated` until step 3. The most
common failure is `No PCA9685 at 0x40`: check SDA/SCL aren't swapped and
VCC goes to 3.3 V.

### Step 2: which channel is which joint

The config starts from the layout your existing scripts assume:

| Channels | Joints |
|---|---|
| 0–3 | left leg: `hip_roll`, `hip_pitch`, `knee`, `ankle_pitch` |
| 4–7 | right leg: same order |
| 8–11 | left arm: `shoulder_pitch`, `shoulder_roll`, `upper_arm_yaw`, `elbow` |
| 12–15 | right arm: same order |
| GPIO12 | `head_yaw` |

Check it against the real robot:

```bash
python3 02_identify_channels.py --all-channels
```

Lay the robot on its back with the limbs free. Each channel wiggles. Press
Enter if the name shown is right, otherwise type the joint name or number, or
`n` if nothing moved. Save at the end. If your legs are built differently
(e.g. `hip_pitch`, `knee`, `ankle_pitch`, `ankle_roll`), name them as they
really are. Standing and the balance keys use whichever leg joints exist.

### Step 3: calibrate (the important one)

```bash
python3 03_calibrate.py
```

Hang the robot (string or a clamp at the torso) or have someone hold it. Type
`a` to step through all uncalibrated joints. For each joint:

1. Jog with `]` `[` (5°) and `+` `-` (1°) until the joint is **straight**:
   leg vertical, knee straight, foot flat and parallel to the floor, arm
   hanging down, head forward. Use the same leg pose for left and right.
2. Press `n` to store it as **neutral**.
3. Press `t`: the joint moves +15°. The screen says which way that should be
   (e.g. "knee BENDS"). If it went the other way, press `r`, then `t` again.
4. Optional: jog to the furthest **safe** position each way and press `,`
   (min) and `.` (max). Do this at least for knees and ankles, where the frame
   collides.
5. Press `c`, then go on to the next joint. At the end, answer `y` to save.

If a joint's neutral comes out far from 90° (more than about 30°), take the
horn off and put it back one spline tooth over. Otherwise the servo runs out
of range on one side.

### Step 4: stand

```bash
python3 04_stand.py
```

1. Hold the robot in the air by the torso and confirm. The servos switch on
   one by one (legs first).
2. Lower it onto its feet on a flat, non-slippery surface. Keep your hands
   around it at first.
3. Trim with the keys:
   - `w` / `s`: lean forward / back. If it keeps falling backwards, press `w`.
   - `a` / `d`: shift weight to the robot's left / right.
   - `c` / `v`: bend / straighten the knees. A little bend (`c` 2–3 times) is
     usually steadier.
   - `p`: save the trims into the pose.
   - `q`: quit. **The PCA keeps holding the pose after the script exits.**
   - `x`: sit down, then relax. Hold the robot.

Next time `python3 04_stand.py` stands it straight into the saved pose.
`--pose ready` starts from slightly bent knees.

To let go later: hold the robot, then `python3 relax.py`.

---

## Config reference (`servo_config.yaml`)

```yaml
joints:
  l_knee: {board: 0x40, channel: 2, neutral: 97, direction: -1, min: 40, max: 160, calibrated: true}
```

| Field | Meaning |
|---|---|
| `board`, `channel` | PCA9685 I2C address and output 0–15 (or `gpio: <BCM pin>` instead) |
| `neutral` | servo angle (0–180) at which the joint is straight / standing |
| `direction` | `1` or `-1`, so that positive joint angles always move the same way (`JOINT_HELP` in `shrek_servos.py`) |
| `min`, `max` | servo-angle limits; commands are clamped to these |
| `calibrated` | set by `03_calibrate.py` |

Pose values are joint angles **relative to neutral**, so `stand: {}` means
"everything straight".

Sign conventions (positive = …):

| Joint | Positive angle |
|---|---|
| `hip_pitch` | leg forward |
| `hip_roll` | leg out to the side |
| `knee` | bends |
| `ankle_pitch` | toes up |
| `ankle_roll` | outer edge of foot up |
| `shoulder_pitch` | arm forward |
| `shoulder_roll` | arm out |
| `elbow` | bends |
| `head_yaw` | head turns to the robot's left |

The `hardware` section has the pulse range (500–2500 µs = 0–180°, the
same as the existing scripts) and `pca_reference_clock`.

The tools rewrite the file when saving, so comments you add inside it are
not kept.

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `No PCA9685 at 0x40` | SDA/SCL swapped, VCC not on 3.3 V, I2C not enabled (`sudo raspi-config nonint do_i2c 0`, reboot). `sudo i2cdetect -y 1` should list `40`. |
| Servos twitch or all jerk when one moves | Servo voltage sagging: thin wires (see above) or a loose terminal. Measure 5 V at the PCA terminal while standing. |
| Pi reboots / check reports under-voltage | Pi is sharing the servo supply, or its own supply is weak. Use the Pi's own adapter. |
| Everything goes limp at once | Supply over-current protection tripped. Switch on with a larger `startup.stagger_s`, avoid fast moves. |
| One servo hums / gets hot while standing | It's pushing against the frame: tighten its `min`/`max` in calibration, or the neutral is off. |
| A servo moves the wrong way in the stand trims | Its `direction` is wrong: `03_calibrate.py <joint>`, then `t`, `r`, `c`. |
| Robot falls backwards / forwards | `w` / `s` in `04_stand.py`, then `p` to save. Bending the knees a little (`c`) helps too. |
| Joint can't reach straight | Horn is a tooth off: re-seat it near 90° and recalibrate that joint. |
| Servo jitters only on GPIO12 | lgpio software PWM. On a Pi 3/4 run `sudo systemctl start pigpiod`. On a Pi 5, move it to a PCA channel. |

## Notes

- **Older scripts:** `shrek_navigation/scripts/{walk,run,jump,wave}.py` still
  open a second PCA9685 at `0x41` and fail with only one board. They also
  ignore this calibration.
- **Single servos:** `../gpio_servo_test/` tests up to 4 servos straight from
  GPIO, handy for checking one servo away from the robot.
