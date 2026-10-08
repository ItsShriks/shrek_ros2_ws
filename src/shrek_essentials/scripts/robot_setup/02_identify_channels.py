#!/usr/bin/env python3
"""
Step 2: find out which PCA channel / GPIO pin drives which joint.

Each output is wiggled a few degrees around its neutral angle, one at a time,
and you type the joint that moved. The result is saved to servo_config.yaml.

Lay the robot on its back with the limbs free (or hang it up). The first
pulse moves a servo from wherever it is to its neutral angle, which can be
a big jump.

    python3 02_identify_channels.py                 # configured joints only
    python3 02_identify_channels.py --all-channels  # every channel of every board + GPIO joints
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shrek_servos as ss  # noqa: E402


def outputs_to_test(cfg, all_channels):
    """List of (key, spec, current_name) where spec is the joint dict minus calibration."""
    by_key = {}
    for name, j in cfg["joints"].items():
        key = ("gpio", j["gpio"]) if "gpio" in j else (j["board"], j["channel"])
        by_key[key] = name
    keys = list(by_key)
    if all_channels:
        for addr in cfg["hardware"]["pca9685_addresses"]:
            for ch in range(16):
                if (addr, ch) not in by_key:
                    keys.append((addr, ch))
    keys.sort(key=lambda k: (1, k[1]) if k[0] == "gpio" else (0, k[0], k[1]))
    out = []
    for key in keys:
        spec = {"gpio": key[1]} if key[0] == "gpio" else {"board": key[0], "channel": key[1]}
        out.append((key, spec, by_key.get(key)))
    return out


def wiggle(robot, name, amplitude, times=2):
    j = robot.joints[name]
    base = j["neutral"]
    robot.set_servo_angle(name, base)
    time.sleep(0.6)
    for _ in range(times):
        robot.set_servo_angle(name, base + amplitude)
        time.sleep(0.35)
        robot.set_servo_angle(name, base - amplitude)
        time.sleep(0.35)
    robot.set_servo_angle(name, base)
    time.sleep(0.3)


def print_choices():
    print("\nJoint names (type the name or its number):")
    for i, name in enumerate(ss.KNOWN_JOINTS):
        end = "\n" if i % 3 == 2 else ""
        print(f"  {i:2d} {name:<18}", end=end)
    print("\n")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ss.add_common_args(p)
    p.add_argument("--all-channels", action="store_true",
                   help="also test PCA channels that aren't in the config yet")
    p.add_argument("--amplitude", type=float, default=15, help="wiggle size in degrees")
    p.add_argument("--keep-on", action="store_true",
                   help="leave each servo holding neutral instead of relaxing it after the wiggle")
    args = p.parse_args()

    cfg = ss.load_config(args.config)
    targets = outputs_to_test(cfg, args.all_channels)

    # One temporary joint per output so the Robot class can drive it.
    temp = {}
    for key, spec, current in targets:
        base = dict(cfg["joints"][current]) if current else {**spec, **ss.JOINT_DEFAULTS}
        temp[f"out_{len(temp)}"] = base
    robot_cfg = dict(cfg, joints=temp)
    robot = ss.Robot(robot_cfg, dry_run=args.dry_run, verbose=args.verbose)

    print(__doc__)
    if not ss.confirm("Robot lying down / hanging with limbs free, servo power ON. Start?"):
        return
    print_choices()

    assignments = {}  # key -> new joint name (None = nothing attached)
    try:
        for (key, spec, current), tmp_name in zip(targets, temp):
            while True:
                print(f"--- {ss.fmt_output(spec)}  (currently: {current or 'unassigned'})")
                wiggle(robot, tmp_name, args.amplitude)
                if not args.keep_on:
                    robot.relax([tmp_name])
                hint = f"Enter=keep '{current}'" if current else "Enter=skip"
                try:
                    ans = input(f"Which joint moved? [{hint} | name/number | n=nothing | r=repeat | q=stop] ").strip()
                except EOFError:
                    ans = "q"
                if ans == "r":
                    continue
                break
            if ans == "q":
                break
            if ans == "":
                if current:
                    assignments[key] = current
                continue
            if ans == "n":
                assignments[key] = None
                continue
            if ans.isdigit() and int(ans) < len(ss.KNOWN_JOINTS):
                ans = ss.KNOWN_JOINTS[int(ans)]
            if ans not in ss.KNOWN_JOINTS:
                print(f"  '{ans}' is not a standard joint name; using it anyway.")
            for k, v in list(assignments.items()):
                if v == ans and k != key:
                    print(f"  note: {ans} was on {k}, moving it here")
                    assignments[k] = None
            assignments[key] = ans
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        if not args.keep_on:
            robot.relax()
        robot.close(hold=args.keep_on)

    if not assignments:
        print("Nothing changed.")
        return

    # Build the new joint table: keep calibration of joints that stay on the same output.
    old_by_name = cfg["joints"]
    new_joints = {}
    tested = set(assignments)
    for name, j in old_by_name.items():
        key = ("gpio", j["gpio"]) if "gpio" in j else (j["board"], j["channel"])
        if key not in tested:
            new_joints[name] = j  # not tested this run, keep as is
    for (key, spec, current) in targets:
        if key not in assignments or assignments[key] is None:
            continue
        name = assignments[key]
        if name in new_joints:
            print(f"  warning: {name} also kept on an untested output; the new one wins")
        if name in old_by_name:
            # Calibration belongs to the joint (servo + horn), so it moves with it to the new output.
            calib = {k: v for k, v in old_by_name[name].items() if k not in ("board", "channel", "gpio")}
            new_joints[name] = {**spec, **calib}
        else:
            new_joints[name] = {**spec, **ss.JOINT_DEFAULTS}

    print("\nNew mapping:")
    for name in ss.ordered_joints(new_joints):
        print(f"  {name:<18} {ss.fmt_output(new_joints[name])}"
              + ("" if new_joints[name]["calibrated"] else "  (needs calibration)"))
    removed = sorted(set(old_by_name) - set(new_joints))
    if removed:
        print("Removed from config: " + ", ".join(removed))
    missing = [n for n in ss.KNOWN_JOINTS if n not in new_joints and ss.group_of(n) == "leg"]
    if missing:
        print("Leg joints with no servo (fine if your legs don't have them): " + ", ".join(missing))

    if not ss.can_save(cfg, args.dry_run):
        return
    if ss.confirm(f"Save to {cfg['_path']}?"):
        cfg["joints"] = new_joints
        ss.save_config(cfg)
        print("Saved. Next: python3 03_calibrate.py")


if __name__ == "__main__":
    main()
