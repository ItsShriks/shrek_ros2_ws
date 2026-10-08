#!/usr/bin/env python3
"""
Let servos go limp (stop their pulses). Hold the robot first: it will collapse.

    python3 relax.py             # all servos
    python3 relax.py l_knee      # just some joints
    python3 relax.py --all-channels   # every channel on every PCA, even unmapped ones
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shrek_servos as ss  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ss.add_common_args(p)
    p.add_argument("joints", nargs="*", help="joints to relax (default: all)")
    p.add_argument("--all-channels", action="store_true", help="also switch off unmapped PCA channels")
    p.add_argument("--yes", action="store_true", help="don't ask")
    args = p.parse_args()

    cfg = ss.load_config(args.config)
    for n in args.joints:
        if n not in cfg["joints"]:
            sys.exit(f"Unknown joint '{n}'")
    if args.all_channels:
        mapped = {(j["board"], j["channel"]) for j in cfg["joints"].values() if "board" in j}
        for addr in cfg["hardware"]["pca9685_addresses"]:
            for ch in range(16):
                if (addr, ch) not in mapped:
                    cfg["joints"][f"unmapped_{addr:02x}_{ch}"] = {"board": addr, "channel": ch, **ss.JOINT_DEFAULTS}

    if not ss.confirm("Robot held or lying down? Relax servos now?", args.yes):
        return
    robot = ss.Robot(cfg, dry_run=args.dry_run, verbose=args.verbose)
    robot.relax(args.joints or None)
    robot.close(hold=True)  # nothing left to hold; don't touch channels again
    print("Relaxed: " + (", ".join(args.joints) if args.joints else "all servos"))


if __name__ == "__main__":
    main()
