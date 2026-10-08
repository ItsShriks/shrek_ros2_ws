#!/usr/bin/env python3
"""
Step 4: make the robot stand, then trim its balance live.

  1. Hold the robot in the air by the torso (feet off the table).
  2. The servos switch on one at a time, straight into the stand pose.
  3. Lower it onto its feet, let go carefully, and trim with the keys.
  4. 'p' saves your trims into the pose so next time it stands the same way.

    python3 04_stand.py                 # pose 'stand' (straight legs)
    python3 04_stand.py --pose ready    # slightly bent knees, usually more stable
    python3 04_stand.py --yes --no-tune # just stand up and exit (PCA keeps holding)
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shrek_servos as ss  # noqa: E402

KEYS = """
  w / s   lean forward / back        a / d   shift weight to robot's left / right
  c / v   crouch more / less         0       clear all trims
  g       go to another pose         i       show joint angles
  p       save trims into the pose   x       sit down, then relax (hold the robot!)
  q       quit, servos keep holding  h       this help
"""

TRIM_LIMIT = 25.0


def present(robot, *names):
    return [n for n in names if n in robot.joints]


def add(trims, robot, changes):
    for name, delta in changes.items():
        if name in robot.joints:
            trims[name] = max(-TRIM_LIMIT, min(TRIM_LIMIT, trims.get(name, 0.0) + delta))


def lean_forward(robot, trims, step):
    # Feet planted: toes-up at the ankle tips the shins (and body) forward.
    if present(robot, "l_ankle_pitch", "r_ankle_pitch"):
        add(trims, robot, {"l_ankle_pitch": step, "r_ankle_pitch": step})
    else:
        add(trims, robot, {"l_hip_pitch": -step, "r_hip_pitch": -step})


def shift_left(robot, trims, step):
    # Hips move left over the feet: left leg in, right leg out; ankles keep the feet flat.
    add(trims, robot, {"l_hip_roll": -step, "r_hip_roll": step,
                       "l_ankle_roll": step, "r_ankle_roll": -step})


def crouch(robot, trims, step):
    # Thigh forward, knee bends twice as much, ankle follows: torso stays upright over the feet.
    add(trims, robot, {"l_hip_pitch": step, "r_hip_pitch": step,
                       "l_knee": 2 * step, "r_knee": 2 * step,
                       "l_ankle_pitch": step, "r_ankle_pitch": step})


def show_angles(robot):
    for n in ss.ordered_joints(robot.joints):
        if n in robot.current:
            a = robot.current[n]
            print(f"  {n:<18} joint {robot.servo_to_joint(n, a):+6.1f}   servo {a:5.1f}")
        else:
            print(f"  {n:<18} off")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ss.add_common_args(p)
    p.add_argument("--pose", default="stand", help="pose to stand in")
    p.add_argument("--gap", type=float, default=None, help="seconds between switching on each servo")
    p.add_argument("--yes", action="store_true", help="don't ask for confirmation")
    p.add_argument("--no-tune", action="store_true", help="stand up and exit, servos keep holding")
    args = p.parse_args()

    cfg = ss.load_config(args.config)
    errors, _ = ss.validate_config(cfg)
    if errors:
        sys.exit("Config errors, run 01_check_system.py:\n  " + "\n  ".join(errors))
    uncal = [n for n, j in cfg["joints"].items() if not j["calibrated"] and ss.group_of(n) == "leg"]
    if uncal:
        print("WARNING: leg joints not calibrated: " + ", ".join(uncal))
        print("Neutral 90 deg is a guess, so the legs may not be straight. Run 03_calibrate.py first.")
        if not ss.confirm("Continue anyway?", args.yes):
            return

    robot = ss.Robot(cfg, dry_run=args.dry_run, verbose=args.verbose)
    pose = args.pose
    trims = {}
    robot.pose(pose)  # exits early if the pose doesn't exist

    print(f"\nPose '{pose}'. Hold the robot in the AIR by the torso, feet not touching anything.")
    if not ss.confirm("Servo power on and robot held up. Switch servos on?", args.yes):
        return

    hold = True
    try:
        robot.enable_staggered(robot.pose(pose), gap=args.gap)
        print("\nAll servos on. Lower the robot onto its feet and let go slowly.")
        if args.no_tune:
            return
        print(KEYS)
        while True:
            key = ss.read_key(f"[{pose}] > ")
            if key == "w":
                lean_forward(robot, trims, 1)
            elif key == "s":
                lean_forward(robot, trims, -1)
            elif key == "a":
                shift_left(robot, trims, 1)
            elif key == "d":
                shift_left(robot, trims, -1)
            elif key == "c":
                crouch(robot, trims, 2)
            elif key == "v":
                crouch(robot, trims, -2)
            elif key == "0":
                trims.clear()
            elif key == "i":
                show_angles(robot)
                continue
            elif key == "g":
                name = input(f"  pose ({', '.join(cfg['poses'])}): ").strip()
                if name not in cfg["poses"]:
                    print("  unknown pose")
                    continue
                if trims and not ss.confirm("  drop unsaved trims?"):
                    continue
                pose, trims = name, {}
                robot.move_to(robot.pose(pose), duration=1.5)
                continue
            elif key == "p":
                if not ss.can_save(cfg, args.dry_run):
                    continue
                base = cfg["poses"][pose]
                for n, v in trims.items():
                    base[n] = round(float(base.get(n, 0.0)) + v, 1)
                trims.clear()
                ss.save_config(cfg)
                print(f"  saved into pose '{pose}': {base}")
                continue
            elif key == "x":
                if "sit" in cfg["poses"]:
                    print("  sitting down...")
                    robot.move_to(robot.pose("sit"), duration=2.5)
                if ss.confirm("  Holding the robot? Relax all servos now?"):
                    hold = False
                    return
                continue
            elif key == "q":
                return
            elif key in ("h", "?"):
                print(KEYS)
                continue
            elif key:
                print("  unknown key, 'h' for help")
                continue
            else:
                continue
            robot.move_to(robot.pose(pose, trims), duration=0.15)
            if trims:
                print("  trims: " + ", ".join(f"{n} {v:+.0f}" for n, v in trims.items() if v))
    except (KeyboardInterrupt, EOFError):
        print()
    finally:
        robot.close(hold=hold)
        if hold:
            print("Servos on the PCA keep holding the pose. To let go: python3 relax.py "
                  "(hold the robot first).")
            if any("gpio" in j for j in cfg["joints"].values()):
                print("Servos on Pi GPIO pins stop when this script exits.")
        else:
            print("All servos relaxed.")


if __name__ == "__main__":
    main()
