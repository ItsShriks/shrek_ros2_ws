#!/usr/bin/env python3
"""
Test up to 4 hobby servos wired directly to Raspberry Pi GPIO (no PCA9685).

Default wiring (BCM numbering, these are the Pi's hardware-PWM capable pins):

    Servo 0 -> GPIO12 (physical pin 32)
    Servo 1 -> GPIO13 (physical pin 33)
    Servo 2 -> GPIO18 (physical pin 12)
    Servo 3 -> GPIO19 (physical pin 35)

Power the servos from an EXTERNAL 5-6 V supply and connect its GND to a Pi
GND pin. Never power servos from the Pi's 5 V pin.

Modes:
    sweep        move each servo on its own (default; use to check wiring)
    all          move all servos together
    center       send every servo to the center angle and hold
    wave         phase-shifted sine wave across all servos
    interactive  type commands to drive single servos or raw pulse widths

Examples:
    python3 servo_gpio_test.py
    python3 servo_gpio_test.py all --min-angle 30 --max-angle 150
    python3 servo_gpio_test.py interactive
    python3 servo_gpio_test.py sweep --pins 17 27 22 23
    python3 servo_gpio_test.py wave --dry-run      # no hardware needed
"""

import argparse
import math
import socket
import sys
import time

try:
    from gpiozero import AngularServo, Device
except ImportError:
    sys.exit("gpiozero is not installed. Run: sudo apt install python3-gpiozero "
             "(or: pip install gpiozero)")

DEFAULT_PINS = [12, 13, 18, 19]


def pigpio_daemon_running(host="localhost", port=8888):
    """Check for pigpiod without letting the pigpio module print its banner."""
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def setup_pin_factory(backend, dry_run):
    """Pick the GPIO backend. pigpio gives jitter-free, DMA-timed pulses."""
    if dry_run:
        from gpiozero.pins.mock import MockFactory, MockPWMPin
        Device.pin_factory = MockFactory(pin_class=MockPWMPin)
        return "mock (dry run)"

    if backend in ("auto", "pigpio"):
        if pigpio_daemon_running():
            try:
                from gpiozero.pins.pigpio import PiGPIOFactory
                Device.pin_factory = PiGPIOFactory()
                return "pigpio"
            except Exception as exc:  # module missing or connect failed
                if backend == "pigpio":
                    sys.exit(f"Could not use pigpio: {exc}")
        elif backend == "pigpio":
            sys.exit("pigpiod is not running. Start it with: sudo systemctl start pigpiod")

    if backend == "lgpio" or backend == "auto":
        try:
            from gpiozero.pins.lgpio import LGPIOFactory
            Device.pin_factory = LGPIOFactory()
            return "lgpio (software PWM, small jitter is normal)"
        except Exception as exc:
            if backend == "lgpio":
                sys.exit(f"Could not use lgpio: {exc}")

    # Let gpiozero choose whatever it can find when the first pin is opened.
    return "gpiozero default"


class ServoBank:
    def __init__(self, pins, min_pulse_us, max_pulse_us, verbose):
        self.pins = pins
        self.verbose = verbose
        self.servos = [
            AngularServo(
                pin,
                initial_angle=None,  # don't move until told to
                min_angle=0,
                max_angle=180,
                min_pulse_width=min_pulse_us / 1e6,
                max_pulse_width=max_pulse_us / 1e6,
                frame_width=0.02,  # 50 Hz
            )
            for pin in pins
        ]

    def __len__(self):
        return len(self.servos)

    def set_angle(self, idx, angle):
        angle = max(0.0, min(180.0, float(angle)))
        self.servos[idx].angle = angle
        if self.verbose:
            print(f"  servo {idx} (GPIO{self.pins[idx]}) -> {angle:6.1f} deg")

    def set_all(self, angle):
        for idx in range(len(self.servos)):
            self.set_angle(idx, angle)

    def set_pulse_us(self, idx, pulse_us):
        self.servos[idx].pulse_width = pulse_us / 1e6
        if self.verbose:
            print(f"  servo {idx} (GPIO{self.pins[idx]}) -> {pulse_us:.0f} us")

    def detach(self, idx=None):
        targets = self.servos if idx is None else [self.servos[idx]]
        for s in targets:
            s.detach()

    def close(self):
        for s in self.servos:
            s.close()


def ramp(bank, indices, start, end, step_deg, step_delay):
    """Move the given servos from start to end in small steps."""
    if start == end:
        for i in indices:
            bank.set_angle(i, end)
        return
    step = step_deg if end > start else -step_deg
    angle = start
    while (step > 0 and angle < end) or (step < 0 and angle > end):
        for i in indices:
            bank.servos[i].angle = angle
        time.sleep(step_delay)
        angle += step
    for i in indices:
        bank.servos[i].angle = end


def mode_center(bank, args):
    print(f"Centering all servos at {args.center} deg. Ctrl+C to stop.")
    bank.set_all(args.center)
    if args.hold > 0:
        time.sleep(args.hold)
    else:
        while True:
            time.sleep(1)


def mode_sweep(bank, args):
    for cycle in range(args.cycles):
        print(f"\n=== Sweep cycle {cycle + 1}/{args.cycles} ===")
        for idx in range(len(bank)):
            print(f"Servo {idx} on GPIO{bank.pins[idx]}: "
                  f"{args.center} -> {args.min_angle} -> {args.max_angle} -> {args.center}")
            bank.set_angle(idx, args.center)
            time.sleep(0.5)
            ramp(bank, [idx], args.center, args.min_angle, args.step, args.delay)
            time.sleep(0.3)
            ramp(bank, [idx], args.min_angle, args.max_angle, args.step, args.delay)
            time.sleep(0.3)
            ramp(bank, [idx], args.max_angle, args.center, args.step, args.delay)
            time.sleep(0.5)


def mode_all(bank, args):
    everyone = list(range(len(bank)))
    print("Moving all servos together.")
    bank.set_all(args.center)
    time.sleep(1)
    for cycle in range(args.cycles):
        print(f"Cycle {cycle + 1}/{args.cycles}")
        ramp(bank, everyone, args.center, args.min_angle, args.step, args.delay)
        time.sleep(0.3)
        ramp(bank, everyone, args.min_angle, args.max_angle, args.step, args.delay)
        time.sleep(0.3)
        ramp(bank, everyone, args.max_angle, args.center, args.step, args.delay)
        time.sleep(0.5)


def mode_wave(bank, args):
    amplitude = (args.max_angle - args.min_angle) / 2.0
    mid = (args.max_angle + args.min_angle) / 2.0
    phase_gap = 2 * math.pi / len(bank)
    duration = args.hold if args.hold > 0 else 10.0
    print(f"Sine wave for {duration:.0f}s (amplitude {amplitude:.0f} deg around {mid:.0f} deg).")
    t0 = time.monotonic()
    while (t := time.monotonic() - t0) < duration:
        for idx in range(len(bank)):
            bank.servos[idx].angle = mid + amplitude * math.sin(2 * math.pi * 0.5 * t - idx * phase_gap)
        time.sleep(0.02)


INTERACTIVE_HELP = """
Commands:
  <servo> <angle>     e.g. "0 45"     move one servo (angle 0-180)
  all <angle>         e.g. "all 90"   move every servo
  p <servo> <us>      e.g. "p 2 1500" send a raw pulse width (calibration)
  off [servo]         stop pulses (servo goes limp); all servos if none given
  help                show this text
  q                   quit
"""


def mode_interactive(bank, args):
    print(INTERACTIVE_HELP)
    for idx, pin in enumerate(bank.pins):
        print(f"  servo {idx} -> GPIO{pin}")
    bank.verbose = True
    while True:
        try:
            line = input("servo> ").strip().lower()
        except EOFError:
            break
        if not line:
            continue
        parts = line.split()
        try:
            if parts[0] in ("q", "quit", "exit"):
                break
            elif parts[0] in ("h", "help", "?"):
                print(INTERACTIVE_HELP)
            elif parts[0] == "all" and len(parts) == 2:
                bank.set_all(float(parts[1]))
            elif parts[0] == "off":
                bank.detach(int(parts[1]) if len(parts) > 1 else None)
                print("  pulses stopped")
            elif parts[0] == "p" and len(parts) == 3:
                pulse = float(parts[2])
                if not 400 <= pulse <= 2600:
                    print("  pulse must be between 400 and 2600 us")
                    continue
                bank.set_pulse_us(int(parts[1]), pulse)
            elif len(parts) == 2:
                bank.set_angle(int(parts[0]), float(parts[1]))
            else:
                print("  unknown command, type 'help'")
        except (ValueError, IndexError):
            print(f"  bad input; servo index must be 0-{len(bank) - 1}, type 'help'")


MODES = {
    "sweep": mode_sweep,
    "all": mode_all,
    "center": mode_center,
    "wave": mode_wave,
    "interactive": mode_interactive,
}


def parse_args():
    p = argparse.ArgumentParser(
        description="Test servos connected directly to Raspberry Pi GPIO pins.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("mode", nargs="?", default="sweep", choices=MODES.keys())
    p.add_argument("--pins", type=int, nargs="+", default=DEFAULT_PINS,
                   help="BCM GPIO numbers, one per servo (1-4 pins)")
    p.add_argument("--min-pulse", type=float, default=500,
                   help="pulse width in us for 0 deg (same as the PCA scripts)")
    p.add_argument("--max-pulse", type=float, default=2500,
                   help="pulse width in us for 180 deg")
    p.add_argument("--min-angle", type=float, default=45,
                   help="lowest angle used by sweep/all/wave")
    p.add_argument("--max-angle", type=float, default=135,
                   help="highest angle used by sweep/all/wave")
    p.add_argument("--center", type=float, default=90, help="rest / center angle")
    p.add_argument("--step", type=float, default=2, help="degrees per ramp step")
    p.add_argument("--delay", type=float, default=0.02, help="seconds between ramp steps")
    p.add_argument("--cycles", type=int, default=1, help="repeats for sweep/all")
    p.add_argument("--hold", type=float, default=0,
                   help="seconds to run center/wave (0 = center holds forever, wave runs 10 s)")
    p.add_argument("--backend", choices=["auto", "pigpio", "lgpio", "default"], default="auto",
                   help="GPIO library; auto tries pigpio, then lgpio")
    p.add_argument("--no-detach", action="store_true",
                   help="keep holding position on exit instead of going limp")
    p.add_argument("--dry-run", action="store_true",
                   help="use mock pins, no hardware needed")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    if not 1 <= len(args.pins) <= 4:
        p.error("give between 1 and 4 pins")
    if len(set(args.pins)) != len(args.pins):
        p.error("pins must be unique")
    if not 0 <= args.min_angle < args.max_angle <= 180:
        p.error("need 0 <= --min-angle < --max-angle <= 180")
    if not 0 <= args.center <= 180:
        p.error("--center must be within 0-180")
    if not 400 <= args.min_pulse < args.max_pulse <= 2600:
        p.error("need 400 <= --min-pulse < --max-pulse <= 2600")
    if args.step <= 0:
        p.error("--step must be positive")
    return args


def main():
    args = parse_args()
    backend = setup_pin_factory(args.backend, args.dry_run)

    print(f"GPIO backend : {backend}")
    print(f"Servo pins   : " + ", ".join(f"{i}=GPIO{pin}" for i, pin in enumerate(args.pins)))
    print(f"Pulse range  : {args.min_pulse:.0f}-{args.max_pulse:.0f} us for 0-180 deg")
    print(f"Mode         : {args.mode}")

    try:
        bank = ServoBank(args.pins, args.min_pulse, args.max_pulse, args.verbose)
    except Exception as exc:
        sys.exit(f"Failed to open GPIO pins {args.pins}: {exc}\n"
                 "Are you on a Raspberry Pi? Try 'sudo' or add your user to the 'gpio' group.")

    try:
        MODES[args.mode](bank, args)
        print("\nDone.")
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        print(f"Returning servos to {args.center} deg...")
        bank.verbose = False
        bank.set_all(args.center)
        time.sleep(0.6)
        if not args.no_detach:
            bank.detach()
        bank.close()


if __name__ == "__main__":
    main()
