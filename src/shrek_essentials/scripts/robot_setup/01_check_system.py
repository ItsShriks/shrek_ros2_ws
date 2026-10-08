#!/usr/bin/env python3
"""
Step 1: check the Pi, libraries, I2C wiring, PCA9685 and config. Nothing moves.

    python3 01_check_system.py
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shrek_servos as ss  # noqa: E402

results = []


def report(status, what, detail=""):
    results.append(status)
    mark = {"PASS": "\033[32mPASS\033[0m", "WARN": "\033[33mWARN\033[0m", "FAIL": "\033[31mFAIL\033[0m",
            "INFO": "INFO"}[status]
    print(f"[{mark}] {what}" + (f"\n       {detail}" if detail else ""))


def check_board():
    try:
        with open("/proc/device-tree/model") as f:
            model = f.read().strip("\x00\n")
        report("INFO", f"Board: {model}")
        return model
    except OSError:
        report("WARN", "Not running on a Raspberry Pi (no /proc/device-tree/model)")
        return ""


def check_power():
    """The Pi's own under-voltage flags. Servos sharing the Pi's supply show up here."""
    if not shutil.which("vcgencmd"):
        report("INFO", "vcgencmd not found, skipping Pi power check")
        return
    try:
        out = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True, timeout=3).stdout
        flags = int(out.strip().split("=")[1], 16)
    except Exception as exc:
        report("WARN", f"Could not read throttle flags: {exc}")
        return
    now = {0: "under-voltage NOW", 1: "CPU frequency capped NOW", 2: "throttled NOW", 3: "temperature limit NOW"}
    past = {16: "under-voltage", 17: "frequency capping", 18: "throttling", 19: "temperature limit"}
    active = [t for b, t in now.items() if flags & (1 << b)]
    seen = [t for b, t in past.items() if flags & (1 << b)]
    if active:
        report("FAIL", "Pi power problem: " + ", ".join(active),
               "Use the official Pi power supply. Do NOT power the Pi from the servo supply.")
    elif seen:
        report("WARN", "Since boot the Pi has had: " + ", ".join(seen),
               "Often caused by servos pulling the Pi's 5 V down. Keep Pi and servo power separate.")
    else:
        report("PASS", "Pi power OK (no under-voltage since boot)")


def check_libraries(cfg):
    need_pca = any("board" in j for j in cfg["joints"].values())
    need_gpio = any("gpio" in j for j in cfg["joints"].values())
    mods = [("yaml", "python3-yaml")]
    if need_pca:
        mods += [("board", "adafruit-blinka"), ("busio", "adafruit-blinka"),
                 ("adafruit_pca9685", "adafruit-circuitpython-pca9685")]
    if need_gpio:
        mods += [("gpiozero", "python3-gpiozero")]
    ok = True
    for mod, pkg in mods:
        try:
            __import__(mod)
        except Exception as exc:
            ok = False
            report("FAIL", f"Python module '{mod}' missing ({pkg})", f"{exc}. Run setup_pi.sh")
    if ok:
        report("PASS", "Python libraries installed")
    return ok


def check_i2c(cfg):
    buses = sorted(glob.glob("/dev/i2c-*"))
    if "/dev/i2c-1" not in buses:
        report("FAIL", "I2C bus /dev/i2c-1 not found",
               "Enable I2C: sudo raspi-config nonint do_i2c 0  (then reboot)")
        return None
    report("PASS", "I2C enabled (/dev/i2c-1)")
    try:
        import board
        import busio
        i2c = busio.I2C(board.SCL, board.SDA)
        while not i2c.try_lock():
            pass
        try:
            found = i2c.scan()
        finally:
            i2c.unlock()
    except Exception as exc:
        report("FAIL", f"I2C scan failed: {exc}",
               "Check: is your user in the 'i2c' group? Try with sudo.")
        return None
    pretty = ", ".join(f"0x{a:02x}" for a in found) or "nothing"
    report("INFO", f"I2C devices found: {pretty}  (0x70 is the PCA9685 'all call' address, ignore it)")
    wanted = cfg["hardware"]["pca9685_addresses"]
    for addr in wanted:
        if addr in found:
            report("PASS", f"PCA9685 answers at 0x{addr:02x}")
        else:
            report("FAIL", f"No PCA9685 at 0x{addr:02x}",
                   "Wiring PCA -> Pi: VCC->pin 1 (3.3V), SDA->pin 3, SCL->pin 5, GND->pin 6. "
                   "OE unconnected. Board LED 'POWER' must be lit (it shows VCC, not servo power).")
    extra = [a for a in found if 0x40 <= a <= 0x7F and a != 0x70 and a not in wanted]
    if extra:
        report("WARN", "Possible PCA9685 boards not in config: " + ", ".join(f"0x{a:02x}" for a in extra),
               "Add them to hardware.pca9685_addresses if you're using them.")
    return found


def check_pca_registers(cfg, found):
    """Read MODE1 and PRESCALE without resetting the chip (creating a PCA9685 object would)."""
    try:
        import board
        import busio
    except Exception:
        return
    i2c = busio.I2C(board.SCL, board.SDA)
    for addr in cfg["hardware"]["pca9685_addresses"]:
        if found is None or addr not in found:
            continue
        buf = bytearray(1)
        try:
            while not i2c.try_lock():
                pass
            try:
                i2c.writeto_then_readfrom(addr, bytes([0x00]), buf)
                mode1 = buf[0]
                i2c.writeto_then_readfrom(addr, bytes([0xFE]), buf)
                prescale = buf[0]
            finally:
                i2c.unlock()
        except Exception as exc:
            report("WARN", f"Could not read PCA 0x{addr:02x} registers: {exc}")
            continue
        freq = cfg["hardware"]["pca_reference_clock"] / 4096 / (prescale + 1)
        state = "sleeping (outputs off)" if mode1 & 0x10 else "running (outputs may be active)"
        report("INFO", f"PCA 0x{addr:02x}: prescale={prescale} (~{freq:.0f} Hz), {state}")


def check_gpio(cfg):
    pins = [j["gpio"] for j in cfg["joints"].values() if "gpio" in j]
    if not pins:
        return
    pigpio_up = False
    try:
        import socket
        socket.create_connection(("localhost", 8888), timeout=0.5).close()
        pigpio_up = True
    except OSError:
        pass
    if pigpio_up:
        report("PASS", f"pigpiod running: clean pulses for GPIO servo(s) on {pins}")
    else:
        report("INFO", f"GPIO servo(s) on {pins} will use lgpio (software PWM): small jitter is normal. "
                       "Pi 3/4: sudo systemctl start pigpiod for clean pulses.")


def check_config(cfg):
    errors, warnings = ss.validate_config(cfg)
    n = len(cfg["joints"])
    for e in errors:
        report("FAIL", f"config: {e}")
    uncal = [w for w in warnings if w.endswith("not calibrated yet")]
    for w in warnings:
        if w not in uncal:
            report("WARN", f"config: {w}")
    if uncal:
        names = ", ".join(w.split(":")[0] for w in uncal)
        report("WARN", f"{len(uncal)}/{n} joints not calibrated: {names}",
               "Run 03_calibrate.py before standing.")
    if not errors:
        report("PASS", f"config OK: {n} joints, poses: {', '.join(cfg['poses'])}")
    pca_n = sum("board" in j for j in cfg["joints"].values())
    gpio_n = n - pca_n
    report("INFO", f"{pca_n} servos on PCA9685, {gpio_n} on Pi GPIO")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default=ss.DEFAULT_CONFIG)
    args = p.parse_args()

    print(f"Config: {args.config}\n")
    cfg = ss.load_config(args.config)
    check_board()
    check_power()
    check_config(cfg)
    libs_ok = check_libraries(cfg)
    if libs_ok and any("board" in j for j in cfg["joints"].values()):
        found = check_i2c(cfg)
        check_pca_registers(cfg, found)
    check_gpio(cfg)

    print("\nThings this script cannot check, do them by hand:")
    print("  - Servo supply: 5 V measured at the PCA's green terminal while servos hold a pose (>= 4.8 V).")
    print("  - Servo plugs: brown wire on the GND row (board edge), orange on the yellow PWM row.")
    print("  - Pi and servo supply share ground (it does via the PCA's GND header pin).")

    fails = results.count("FAIL")
    warns = results.count("WARN")
    print(f"\nSummary: {fails} fail, {warns} warn")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
