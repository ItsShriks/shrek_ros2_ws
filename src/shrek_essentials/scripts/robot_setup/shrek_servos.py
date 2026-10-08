#!/usr/bin/env python3
"""
Shared servo layer for the Shrek robot setup tools.

Every joint is described in config/servo_config.yaml:

    l_knee: {board: 0x40, channel: 2, neutral: 90, direction: 1, min: 10, max: 170, calibrated: false}
    head_yaw: {gpio: 12, neutral: 90, direction: 1, min: 30, max: 150, calibrated: false}

- `board`/`channel`: PCA9685 I2C address and output (0-15), or
- `gpio`: BCM pin number for a servo wired straight to the Pi.
- `neutral`: servo angle (0-180) at which the joint is in its straight,
  upright "standing" position.
- `direction`: +1 or -1, so that a positive joint angle always moves the
  joint the way JOINT_HELP describes, whichever way the servo is mounted.
- `min`/`max`: servo angle limits, so the joint never drives into the frame.

Poses are stored as joint angles relative to neutral, in degrees, so
`stand: {}` means "every joint at neutral".
"""

import os
import sys
import time

try:
    import yaml
except ImportError:
    sys.exit("PyYAML missing. Run: sudo apt install python3-yaml")

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = os.path.normpath(os.path.join(HERE, "..", "..", "config", "servo_config.yaml"))

# What a POSITIVE joint angle should do once `direction` is calibrated.
# Seen from the robot's own point of view (its left is "left").
JOINT_HELP = {
    "hip_yaw": "leg twists so the toes turn OUTWARD",
    "hip_roll": "leg swings OUT to the side, away from the body",
    "hip_pitch": "leg swings FORWARD",
    "knee": "knee BENDS (lower leg folds backward)",
    "ankle_pitch": "toes LIFT UP",
    "ankle_roll": "foot's OUTER edge lifts",
    "shoulder_pitch": "arm swings FORWARD / up in front",
    "shoulder_roll": "arm lifts OUT to the side",
    "upper_arm_yaw": "upper arm twists so the forearm turns OUTWARD",
    "elbow": "elbow BENDS",
    "wrist": "wrist turns OUTWARD",
    "head_yaw": "head turns to the robot's LEFT",
    "head_pitch": "head tilts UP",
}

LEG_PARTS = ["hip_yaw", "hip_roll", "hip_pitch", "knee", "ankle_pitch", "ankle_roll"]
ARM_PARTS = ["shoulder_pitch", "shoulder_roll", "upper_arm_yaw", "elbow", "wrist"]
HEAD_PARTS = ["head_yaw", "head_pitch"]
KNOWN_JOINTS = ([f"{s}_{p}" for s in "lr" for p in LEG_PARTS]
                + [f"{s}_{p}" for s in "lr" for p in ARM_PARTS]
                + HEAD_PARTS)

JOINT_DEFAULTS = {"neutral": 90.0, "direction": 1, "min": 10.0, "max": 170.0, "calibrated": False}
I2C_PINS = {2, 3}  # SDA/SCL, can't be used for a GPIO servo while the PCA9685 is attached


def joint_part(name):
    """'l_knee' -> 'knee', 'head_yaw' -> 'head_yaw'."""
    return name[2:] if name[:2] in ("l_", "r_") else name


def describe(name):
    return JOINT_HELP.get(joint_part(name), "(custom joint, no convention)")


def group_of(name):
    part = joint_part(name)
    if part in LEG_PARTS:
        return "leg"
    if part in ARM_PARTS:
        return "arm"
    return "head"


# ---------------------------------------------------------------- config ---

def load_config(path=DEFAULT_CONFIG):
    if not os.path.exists(path):
        sys.exit(f"Config not found: {path}")
    with open(path) as f:
        cfg = yaml.safe_load(f) or {}
    cfg.setdefault("hardware", {})
    hw = cfg["hardware"]
    hw.setdefault("pca9685_addresses", [0x40])
    hw.setdefault("pwm_frequency", 50)
    hw.setdefault("pca_reference_clock", 25000000)
    hw.setdefault("min_pulse_us", 500)
    hw.setdefault("max_pulse_us", 2500)
    hw.setdefault("gpio_backend", "auto")
    cfg.setdefault("startup", {})
    cfg["startup"].setdefault("stagger_s", 0.3)
    cfg.setdefault("joints", {})
    for name, j in cfg["joints"].items():
        for key, val in JOINT_DEFAULTS.items():
            j.setdefault(key, val)
    cfg.setdefault("poses", {})
    for name in list(cfg["poses"]):
        cfg["poses"][name] = cfg["poses"][name] or {}
    cfg["_path"] = path
    return cfg


def validate_config(cfg):
    """Return (errors, warnings) as lists of strings."""
    errors, warnings = [], []
    hw = cfg["hardware"]
    boards = set(hw["pca9685_addresses"])
    seen = {}
    for name, j in cfg["joints"].items():
        if "gpio" in j:
            key = ("gpio", j["gpio"])
            if j["gpio"] in I2C_PINS:
                errors.append(f"{name}: GPIO{j['gpio']} is an I2C pin used by the PCA9685")
        elif "board" in j and "channel" in j:
            key = (j["board"], j["channel"])
            if j["board"] not in boards:
                errors.append(f"{name}: board 0x{j['board']:02x} not in hardware.pca9685_addresses")
            if not 0 <= j["channel"] <= 15:
                errors.append(f"{name}: channel {j['channel']} must be 0-15")
        else:
            errors.append(f"{name}: needs either 'board' + 'channel' or 'gpio'")
            continue
        if key in seen:
            errors.append(f"{name} and {seen[key]} are both on {fmt_output(j)}")
        seen[key] = name
        if not 0 <= j["min"] < j["max"] <= 180:
            errors.append(f"{name}: need 0 <= min < max <= 180")
        elif not j["min"] <= j["neutral"] <= j["max"]:
            errors.append(f"{name}: neutral {j['neutral']} outside min/max")
        if j["direction"] not in (1, -1):
            errors.append(f"{name}: direction must be 1 or -1")
        if name not in KNOWN_JOINTS:
            warnings.append(f"{name}: not a standard joint name, poses/balance keys won't use it")
        if not j["calibrated"]:
            warnings.append(f"{name}: not calibrated yet")
        elif abs(j["neutral"] - 90) > 30:
            warnings.append(f"{name}: neutral is {j['neutral']:.0f} deg, far from 90; "
                            "consider re-seating the servo horn to keep range in both directions")
    for pose, angles in cfg["poses"].items():
        for name in angles:
            if name not in cfg["joints"]:
                warnings.append(f"pose '{pose}' uses unknown joint '{name}'")
    return errors, warnings


def fmt_output(j):
    if "gpio" in j:
        return f"GPIO{j['gpio']}"
    return f"PCA 0x{j['board']:02x} ch{j['channel']}"


def _num(v):
    v = float(v)
    return str(int(v)) if v.is_integer() else f"{v:.1f}"


def save_config(cfg, path=None):
    """Write the config back in a stable, readable layout."""
    path = path or cfg["_path"]
    hw, st = cfg["hardware"], cfg["startup"]
    lines = [
        "# Shrek servo configuration (17 DoF, PCA9685).",
        "# The robot_setup tools rewrite this file when you save, so keep notes",
        "# in the README rather than in comments here. Field meanings: see",
        "# src/shrek_essentials/scripts/robot_setup/README.md",
        "",
        "hardware:",
        "  pca9685_addresses: [" + ", ".join(f"0x{a:02x}" for a in hw["pca9685_addresses"]) + "]",
        f"  pwm_frequency: {hw['pwm_frequency']}",
        f"  pca_reference_clock: {hw['pca_reference_clock']}",
        f"  min_pulse_us: {hw['min_pulse_us']}   # servo angle 0",
        f"  max_pulse_us: {hw['max_pulse_us']}  # servo angle 180",
        f"  gpio_backend: {hw['gpio_backend']}   # for joints on a Pi pin: auto | pigpio | lgpio | default",
        "",
        "startup:",
        f"  stagger_s: {st['stagger_s']}  # pause between switching on each servo (limits inrush current)",
        "",
        "joints:",
    ]

    def sort_key(item):
        j = item[1]
        return (1, j["gpio"], 0) if "gpio" in j else (0, j["board"], j["channel"])

    width = max((len(n) for n in cfg["joints"]), default=0) + 1
    for name, j in sorted(cfg["joints"].items(), key=sort_key):
        where = f"gpio: {j['gpio']}" if "gpio" in j else f"board: 0x{j['board']:02x}, channel: {j['channel']:2d}"
        lines.append(
            f"  {name + ':':<{width}} {{{where}, neutral: {_num(j['neutral']):>5}, "
            f"direction: {j['direction']:2d}, min: {_num(j['min']):>3}, max: {_num(j['max']):>3}, "
            f"calibrated: {'true' if j['calibrated'] else 'false'}}}"
        )
    lines += ["", "# Joint angles in degrees relative to neutral (see JOINT_HELP for signs).",
              "# Joints that are not listed stay at 0 (neutral).", "poses:"]
    for pose, angles in cfg["poses"].items():
        inner = ", ".join(f"{k}: {_num(v)}" for k, v in angles.items() if abs(float(v)) > 1e-6)
        lines.append(f"  {pose}: {{{inner}}}")
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(tmp, path)


# --------------------------------------------------------------- drivers ---

class MockOutput:
    def __init__(self, label, log):
        self.label, self.log = label, log
        self.pulse_us = None

    def set_pulse(self, us):
        self.pulse_us = us
        if self.log:
            print(f"    [mock] {self.label} <- {us:.0f} us")

    def off(self):
        self.pulse_us = None
        if self.log:
            print(f"    [mock] {self.label} off")


class PcaOutput:
    def __init__(self, pca, channel):
        self.channel = pca.channels[channel]
        self.period_us = 1e6 / pca.frequency  # read once; the getter costs an I2C transfer

    def set_pulse(self, us):
        self.channel.duty_cycle = int(round(us / self.period_us * 0xFFFF))

    def off(self):
        self.channel.duty_cycle = 0


class GpioOutput:
    def __init__(self, pin):
        from gpiozero import Servo
        self.servo = Servo(pin, initial_value=None, min_pulse_width=0.0004,
                           max_pulse_width=0.0026, frame_width=0.02)

    def set_pulse(self, us):
        self.servo.pulse_width = us / 1e6

    def off(self):
        self.servo.detach()


def _setup_gpio_backend(name):
    from gpiozero import Device
    import socket
    if name in ("auto", "pigpio"):
        try:
            socket.create_connection(("localhost", 8888), timeout=0.5).close()
            from gpiozero.pins.pigpio import PiGPIOFactory
            Device.pin_factory = PiGPIOFactory()
            return
        except Exception:
            if name == "pigpio":
                raise
    if name in ("auto", "lgpio"):
        try:
            from gpiozero.pins.lgpio import LGPIOFactory
            Device.pin_factory = LGPIOFactory()
        except Exception:
            if name == "lgpio":
                raise


class Robot:
    """Joint-level access to every servo in the config."""

    def __init__(self, cfg, dry_run=False, verbose=False):
        self.cfg = cfg
        self.joints = cfg["joints"]
        self.hw = cfg["hardware"]
        self.dry_run = dry_run
        self.current = {}  # joint -> last commanded servo angle (only for enabled joints)
        self._pcas = {}
        self._outputs = {}
        if not dry_run:
            self._open_hardware()
        for name, j in self.joints.items():
            self._outputs[name] = self._make_output(name, j, verbose)

    def _open_hardware(self):
        need_pca = any("board" in j for j in self.joints.values())
        if need_pca:
            try:
                import board
                import busio
                from adafruit_pca9685 import PCA9685
            except ImportError as exc:
                sys.exit(f"Missing library ({exc.name}). Run setup_pi.sh first.")
            i2c = busio.I2C(board.SCL, board.SDA)
            used = {j["board"] for j in self.joints.values() if "board" in j}
            for addr in self.hw["pca9685_addresses"]:
                if addr not in used:
                    continue
                try:
                    pca = PCA9685(i2c, address=addr, reference_clock_speed=self.hw["pca_reference_clock"])
                except ValueError:
                    sys.exit(f"No PCA9685 answering at 0x{addr:02x}. Run 01_check_system.py.")
                pca.frequency = self.hw["pwm_frequency"]
                self._pcas[addr] = pca
        if any("gpio" in j for j in self.joints.values()):
            _setup_gpio_backend(self.hw["gpio_backend"])

    def _make_output(self, name, j, verbose):
        if self.dry_run:
            return MockOutput(f"{name} ({fmt_output(j)})", verbose)
        if "gpio" in j:
            return GpioOutput(j["gpio"])
        return PcaOutput(self._pcas[j["board"]], j["channel"])

    # -- raw servo-angle level (used for calibration)
    def angle_to_pulse(self, angle):
        lo, hi = self.hw["min_pulse_us"], self.hw["max_pulse_us"]
        return lo + (hi - lo) * angle / 180.0

    def set_servo_angle(self, name, angle, respect_limits=True):
        j = self.joints[name]
        if respect_limits:
            angle = max(j["min"], min(j["max"], angle))
        angle = max(0.0, min(180.0, angle))
        self._outputs[name].set_pulse(self.angle_to_pulse(angle))
        self.current[name] = angle
        return angle

    # -- joint level (relative to neutral, direction-corrected)
    def joint_to_servo(self, name, rel_deg):
        j = self.joints[name]
        return j["neutral"] + j["direction"] * rel_deg

    def servo_to_joint(self, name, angle):
        j = self.joints[name]
        return (angle - j["neutral"]) * j["direction"]

    def set_joint(self, name, rel_deg):
        return self.set_servo_angle(name, self.joint_to_servo(name, rel_deg))

    def pose(self, pose_name, extra=None):
        """Target joint angles for every joint: pose values plus optional offsets."""
        if pose_name not in self.cfg["poses"]:
            sys.exit(f"Pose '{pose_name}' not in config. Known: {', '.join(self.cfg['poses'])}")
        base = self.cfg["poses"][pose_name]
        target = {n: float(base.get(n, 0.0)) for n in self.joints}
        for n, v in (extra or {}).items():
            if n in target:
                target[n] += v
        return target

    def enable_staggered(self, target, order=None, gap=None, announce=True):
        """Switch servos on one by one, straight to their target, to spread the inrush current."""
        gap = self.cfg["startup"]["stagger_s"] if gap is None else gap
        for name in order or ordered_joints(self.joints):
            if name not in target:
                continue
            angle = self.set_joint(name, target[name])
            if announce:
                print(f"  on: {name:<18} servo {angle:5.1f} deg  ({fmt_output(self.joints[name])})")
            time.sleep(gap)

    def move_to(self, target, duration=1.0, rate_hz=50):
        """Smoothly move enabled joints to `target` (joint angles); others jump straight there."""
        start = {n: self.servo_to_joint(n, self.current[n]) for n in target if n in self.current}
        steps = max(1, int(duration * rate_hz))
        for i in range(1, steps + 1):
            s = i / steps
            s = s * s * (3 - 2 * s)  # smoothstep: gentle start and stop
            for n, goal in target.items():
                a = start.get(n, goal)
                self.set_joint(n, a + (goal - a) * s)
            if duration > 0:
                time.sleep(duration / steps)

    def relax(self, names=None):
        for n in names or list(self.joints):
            self._outputs[n].off()
            self.current.pop(n, None)

    def close(self, hold=True):
        """hold=True leaves the PCA9685 generating pulses after the script exits."""
        if not hold:
            self.relax()
        for out in self._outputs.values():
            if isinstance(out, GpioOutput):
                out.servo.close()  # GPIO servos can't keep holding once the script ends


def ordered_joints(joints):
    """Legs first (hip -> ankle), then arms, then head."""
    order = {p: i for i, p in enumerate(LEG_PARTS + ARM_PARTS + HEAD_PARTS)}
    groups = {"leg": 0, "arm": 1, "head": 2}
    return sorted(joints, key=lambda n: (groups[group_of(n)], order.get(joint_part(n), 99), n))


# ------------------------------------------------------------- terminal ---

def read_key(prompt=""):
    """Read one key press (no Enter needed) on a terminal; a whole line otherwise."""
    if prompt:
        print(prompt, end="", flush=True)
    if not sys.stdin.isatty():
        line = sys.stdin.readline()
        if not line:
            raise EOFError
        return line.strip()
    import termios
    import tty
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    if ch == "\x03":
        raise KeyboardInterrupt
    if ch == "\x04":
        raise EOFError
    print()
    return "" if ch in ("\r", "\n") else ch


def confirm(question, assume_yes=False):
    if assume_yes:
        return True
    try:
        return input(f"{question} [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


def can_save(cfg, dry_run):
    """A dry run never overwrites the real config (a copy given with --config is fine)."""
    if dry_run and os.path.abspath(cfg["_path"]) == os.path.abspath(DEFAULT_CONFIG):
        print("(dry run: not saving the real config; pass --config <copy.yaml> to try saving)")
        return False
    return True


def add_common_args(parser):
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="servo config YAML")
    parser.add_argument("--dry-run", action="store_true", help="no hardware, print what would happen")
    parser.add_argument("-v", "--verbose", action="store_true", help="print every pulse sent (dry run)")
