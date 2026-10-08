#!/usr/bin/env python3
"""
Step 3: calibrate each joint (neutral, direction, limits).

For every joint you:
  1. jog the servo until the joint is in its STRAIGHT standing position
     (legs straight and vertical, feet flat, arms hanging down, head forward)
     and press 'n' to store that as neutral,
  2. press 't' to test the direction, and 'r' if it moved the wrong way,
  3. optionally jog to each end of the safe range and press ',' / '.' for min / max,
  4. press 'c' to mark it calibrated.

Hang the robot up (or hold it) so the legs move freely.

    python3 03_calibrate.py               # pick joints from a list
    python3 03_calibrate.py l_knee r_knee # go straight to these joints
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shrek_servos as ss  # noqa: E402

JOG_HELP = """
  + / -   jog 1 deg          ] / [   jog 5 deg
  n       set NEUTRAL here    t       test direction (+15 deg and back)
  r       reverse direction   0       go to neutral
  ,       set MIN limit here  .       set MAX limit here
  x       relax this servo    c       mark calibrated, next joint
  q       back to joint list  h       this help
"""


def show_joint(robot, name):
    j = robot.joints[name]
    print(f"\n=== {name}  ({ss.fmt_output(j)}) ===")
    print(f"Positive direction should be: {ss.describe(name)}")
    print(f"neutral={j['neutral']:.1f}  direction={j['direction']:+d}  "
          f"min={j['min']:.0f}  max={j['max']:.0f}  calibrated={j['calibrated']}")
    print(JOG_HELP)


def calibrate_joint(robot, name):
    """Returns True if the user wants to move to the next joint, False to go back to the list."""
    j = robot.joints[name]
    show_joint(robot, name)
    angle = robot.current.get(name, j["neutral"])
    angle = robot.set_servo_angle(name, angle, respect_limits=False)
    while True:
        try:
            key = ss.read_key(f"[{name}] servo {angle:5.1f} deg (joint {robot.servo_to_joint(name, angle):+5.1f}) > ")
        except EOFError:
            return False
        step = {"+": 1, "=": 1, "-": -1, "_": -1, "]": 5, "[": -5}.get(key)
        if step is not None:
            angle = robot.set_servo_angle(name, angle + step, respect_limits=False)
        elif key == "0":
            angle = robot.set_servo_angle(name, j["neutral"], respect_limits=False)
        elif key == "n":
            j["neutral"] = round(angle, 1)
            j["min"] = min(j["min"], j["neutral"])
            j["max"] = max(j["max"], j["neutral"])
            print(f"  neutral = {j['neutral']:.1f}")
            if abs(j["neutral"] - 90) > 30:
                print("  ! far from 90: the joint will run out of range on one side. "
                      "Consider moving the horn by one spline tooth.")
        elif key == "t":
            print(f"  moving +15 deg: should be '{ss.describe(name)}'")
            robot.set_servo_angle(name, robot.joint_to_servo(name, 15), respect_limits=False)
            time.sleep(1.0)
            angle = robot.set_servo_angle(name, j["neutral"], respect_limits=False)
            print("  wrong way? press 'r'")
        elif key == "r":
            j["direction"] *= -1
            print(f"  direction = {j['direction']:+d} (press 't' to check)")
        elif key == ",":
            if angle >= j["neutral"]:
                print("  min must be below neutral")
            else:
                j["min"] = round(angle, 1)
                print(f"  min = {j['min']:.1f}")
        elif key == ".":
            if angle <= j["neutral"]:
                print("  max must be above neutral")
            else:
                j["max"] = round(angle, 1)
                print(f"  max = {j['max']:.1f}")
        elif key == "x":
            robot.relax([name])
            print("  relaxed (any jog key re-enables)")
        elif key == "c":
            j["calibrated"] = True
            robot.set_servo_angle(name, j["neutral"], respect_limits=False)
            print(f"  {name} calibrated")
            return True
        elif key == "q":
            return False
        elif key in ("h", "?"):
            show_joint(robot, name)
        elif key:
            print("  unknown key, 'h' for help")


def list_joints(robot, names):
    print("\nJoints:")
    for i, n in enumerate(names):
        j = robot.joints[n]
        mark = "ok " if j["calibrated"] else "-- "
        print(f"  {i:2d} [{mark}] {n:<18} {ss.fmt_output(j):<16} neutral {j['neutral']:5.1f} dir {j['direction']:+d}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ss.add_common_args(p)
    p.add_argument("joints", nargs="*", help="joint names to calibrate in order")
    args = p.parse_args()

    cfg = ss.load_config(args.config)
    robot = ss.Robot(cfg, dry_run=args.dry_run, verbose=args.verbose)
    names = ss.ordered_joints(cfg["joints"])
    for n in args.joints:
        if n not in cfg["joints"]:
            sys.exit(f"Unknown joint '{n}'. Known: {', '.join(names)}")

    print(__doc__)
    dirty = False
    try:
        queue = list(args.joints)
        while True:
            if queue:
                name = queue.pop(0)
            else:
                list_joints(robot, names)
                try:
                    ans = input("\nJoint number/name, 'a' = next uncalibrated, 's' = save, 'q' = quit: ").strip()
                except EOFError:
                    ans = "q"
                if ans == "q":
                    break
                if ans == "s":
                    if not ss.can_save(cfg, args.dry_run):
                        continue
                    ss.save_config(cfg)
                    dirty = False
                    print(f"Saved {cfg['_path']}")
                    continue
                if ans == "a":
                    queue = [n for n in names if not cfg["joints"][n]["calibrated"]]
                    if not queue:
                        print("All joints calibrated.")
                    continue
                if ans.isdigit() and int(ans) < len(names):
                    name = names[int(ans)]
                elif ans in cfg["joints"]:
                    name = ans
                else:
                    print("?")
                    continue
            dirty = True
            if not calibrate_joint(robot, name):
                queue = []
    except KeyboardInterrupt:
        print()
    finally:
        if dirty and ss.can_save(cfg, args.dry_run) and ss.confirm("Save changes?"):
            ss.save_config(cfg)
            print(f"Saved {cfg['_path']}")
        robot.close(hold=True)
        print("Servos on the PCA keep holding. Run relax.py to let them go limp.")


if __name__ == "__main__":
    main()
