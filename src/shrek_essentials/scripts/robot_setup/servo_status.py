#!/usr/bin/env python3
"""
Show the angle every servo is currently being driven to. Nothing moves.

Reads the PCA9685's output registers directly (without resetting the chip),
so it works while 04_stand.py is running or after it exited and the PCA is
still holding the pose.

Hobby servos like the MG996R have no position feedback: this is the
COMMANDED angle. It equals the real angle unless the servo is blocked,
overloaded or under-powered.

    python3 servo_status.py           # one snapshot
    python3 servo_status.py --watch   # refresh twice a second
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shrek_servos as ss  # noqa: E402

MODE1, PRESCALE, LED0 = 0x00, 0xFE, 0x06


def decode_channel(regs):
    """regs = [ON_L, ON_H, OFF_L, OFF_H] -> ('off'|'full-on'|'pwm', pulse ticks out of 4096)."""
    on_l, on_h, off_l, off_h = regs
    if off_h & 0x10:
        return "off", 0
    if on_h & 0x10:
        return "full-on", 4096
    on = ((on_h & 0x0F) << 8) | on_l
    off = ((off_h & 0x0F) << 8) | off_l
    ticks = (off - on) % 4096
    return ("off", 0) if ticks == 0 else ("pwm", ticks)


class PcaReader:
    def __init__(self):
        import board
        import busio
        self.i2c = busio.I2C(board.SCL, board.SDA)

    def read(self, addr, reg, n=1):
        buf = bytearray(1)
        out = []
        while not self.i2c.try_lock():
            pass
        try:
            # One byte at a time: works whether or not auto-increment is enabled.
            for r in range(reg, reg + n):
                self.i2c.writeto_then_readfrom(addr, bytes([r]), buf)
                out.append(buf[0])
        finally:
            self.i2c.unlock()
        return out


def gpio_pulse_us(pin):
    """GPIO servos can only be read back while pigpiod is driving them."""
    try:
        import pigpio
        pi = pigpio.pi()
        if not pi.connected:
            return None
        try:
            return pi.get_servo_pulsewidth(pin)
        finally:
            pi.stop()
    except Exception:
        return None


def snapshot(cfg, reader, show_unmapped):
    hw = cfg["hardware"]
    lo, hi = hw["min_pulse_us"], hw["max_pulse_us"]
    by_output = {}
    for name, j in cfg["joints"].items():
        key = ("gpio", j["gpio"]) if "gpio" in j else (j["board"], j["channel"])
        by_output[key] = name

    rows = []
    for addr in hw["pca9685_addresses"]:
        try:
            mode1 = reader.read(addr, MODE1)[0]
            prescale = reader.read(addr, PRESCALE)[0]
            regs = reader.read(addr, LED0, 64)
        except Exception as exc:
            print(f"PCA 0x{addr:02x}: not readable ({exc})")
            continue
        freq = hw["pca_reference_clock"] / 4096 / (prescale + 1)
        period_us = 1e6 / freq
        asleep = bool(mode1 & 0x10)
        print(f"PCA 0x{addr:02x}: {freq:.1f} Hz, {'SLEEPING - all outputs off' if asleep else 'running'}")
        for ch in range(16):
            name = by_output.get((addr, ch))
            if name is None and not show_unmapped:
                continue
            state, ticks = decode_channel(regs[ch * 4: ch * 4 + 4])
            if asleep:
                state = "off"
            rows.append((name or "-", f"0x{addr:02x} ch{ch:<2}", state,
                         ticks * period_us / 4096 if state == "pwm" else None))

    for (kind, pin), name in by_output.items():
        if kind != "gpio":
            continue
        us = gpio_pulse_us(pin)
        if us is None:
            rows.append((name, f"GPIO{pin}", "unknown", None))
        else:
            rows.append((name, f"GPIO{pin}", "pwm" if us else "off", us or None))

    print(f"\n{'joint':<18} {'output':<12} {'pulse':>8} {'servo':>8} {'joint':>8}  note")
    for name, where, state, us in rows:
        if us is None:
            note = {"off": "limp (no pulses)", "full-on": "output stuck high, not a servo signal",
                    "unknown": "can't read back (only with pigpiod)"}.get(state, state)
            print(f"{name:<18} {where:<12} {'-':>8} {'-':>8} {'-':>8}  {note}")
            continue
        servo = (us - lo) / (hi - lo) * 180.0
        note = ""
        if not lo - 20 <= us <= hi + 20:
            note = "outside the configured pulse range"
        joint = "-"
        if name in cfg["joints"]:
            j = cfg["joints"][name]
            rel = (servo - j["neutral"]) * j["direction"]
            joint = f"{rel:+.1f}"
            if not j["calibrated"]:
                note = note or "uncalibrated (joint angle assumes neutral 90)"
        print(f"{name:<18} {where:<12} {us:6.0f}us {servo:7.1f}° {joint:>8}  {note}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default=ss.DEFAULT_CONFIG)
    p.add_argument("--watch", action="store_true", help="refresh until Ctrl+C")
    p.add_argument("--interval", type=float, default=0.5)
    p.add_argument("--unmapped", action="store_true", help="also show PCA channels not in the config")
    args = p.parse_args()

    cfg = ss.load_config(args.config)
    try:
        reader = PcaReader()
    except Exception as exc:
        sys.exit(f"Can't open I2C ({exc}). Run 01_check_system.py.")
    print("servo = commanded servo angle (0-180), joint = angle relative to calibrated neutral\n")
    try:
        while True:
            if args.watch:
                print("\033[2J\033[H", end="")
            snapshot(cfg, reader, args.unmapped)
            if not args.watch:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
