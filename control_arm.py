#!/usr/bin/env python3
"""
Interactive keyboard controller for the SO-101 Follower Arm.
Uses Python built-in `curses` for reliable key capture in any Linux terminal.

Controls:
  W / S       →  Shoulder Lift  up / down
  A / D       →  Shoulder Pan   left / right
  R / F       →  Elbow Flex     up / down
  T / G       →  Wrist Flex     up / down
  Y / H       →  Wrist Roll     left / right
  O / C       →  Gripper        open / close
  SPACE       →  Home position
  + / -       →  Speed up / down
  Q or ESC    →  Quit safely
"""

import curses
import time

from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig

# Configuration
PORT   = "/dev/ttyACM0"
ARM_ID = "my_follower"
FPS    = 30          # control loop Hz
STEP   = 3.0         # degrees per frame (holding key)

JOINT_NAMES = ["shoulder_pan", "shoulder_lift", "elbow_flex",
               "wrist_flex",   "wrist_roll",    "gripper"]

HOME = {
    "shoulder_pan.pos":  0.0,
    "shoulder_lift.pos": 0.0,
    "elbow_flex.pos":    0.0,
    "wrist_flex.pos":    0.0,
    "wrist_roll.pos":    0.0,
    "gripper.pos":       50.0,
}

JOINT_LIMITS = {
    "shoulder_pan":  (-90,  90),
    "shoulder_lift": (-90,  90),
    "elbow_flex":    (-90,  90),
    "wrist_flex":    (-90,  90),
    "wrist_roll":    (-180, 180),
    "gripper":       (0,    100),
}


def clamp(val, lo, hi):
    return max(lo, min(hi, val))


def nudge(positions, joint, delta):
    lo, hi = JOINT_LIMITS[joint]
    positions[f"{joint}.pos"] = clamp(positions[f"{joint}.pos"] + delta, lo, hi)


def draw(stdscr, positions, speed):
    stdscr.erase()
    w = 58
    stdscr.addstr(0, 0, "═" * w)
    stdscr.addstr(1, 0, f"  SO-101 Controller  │  Speed: {speed:.1f}°/frame  │  FPS: {FPS}")
    stdscr.addstr(2, 0, "═" * w)
    stdscr.addstr(3, 0, f"  {'Joint':<18}│  {'Position':>8}   Bar")
    stdscr.addstr(4, 0, "  " + "─" * 17 + "┼" + "─" * 38)

    for i, name in enumerate(JOINT_NAMES):
        val    = positions[f"{name}.pos"]
        lo, hi = JOINT_LIMITS[name]
        pct    = (val - lo) / (hi - lo)
        bar    = "█" * int(pct * 16) + "░" * (16 - int(pct * 16))
        unit   = "%" if name == "gripper" else "°"
        stdscr.addstr(5 + i, 0, f"  {name:<18}│ {val:+7.1f}{unit}  [{bar}]")

    stdscr.addstr(12, 0, "═" * w)
    stdscr.addstr(13, 0, "  W/S Shoulder Lift  │  A/D Shoulder Pan  │  R/F Elbow")
    stdscr.addstr(14, 0, "  T/G Wrist Flex     │  Y/H Wrist Roll    │  O/C Gripper")
    stdscr.addstr(15, 0, "  SPACE Home  │  +/- Speed  │  Q or ESC Quit")
    stdscr.addstr(16, 0, "═" * w)
    stdscr.refresh()


def run(stdscr, robot):
    global STEP

    # curses setup: non-blocking, no echo, invisible cursor
    curses.curs_set(0)
    stdscr.nodelay(True)   # non-blocking getch()
    stdscr.keypad(True)
    curses.noecho()

    positions = dict(HOME)
    robot.send_action(positions)
    dt = 1.0 / FPS

    while True:
        t0 = time.perf_counter()
        changed = False

        # Drain all pending key events this frame
        while True:
            ch = stdscr.getch()
            if ch == -1:
                break  # no more keys buffered

            # Quit
            if ch in (ord('q'), ord('Q'), 27):   # 27 = ESC
                return

            # Home
            if ch == ord(' '):
                positions = dict(HOME)
                changed = True

            # Speed
            if ch in (ord('+'), ord('=')):
                STEP = min(15.0, STEP + 0.5)
            if ch == ord('-'):
                STEP = max(0.5, STEP - 0.5)

            # Joint nudges (single press per frame registered, but nodelay
            # combined with holding means getch fires rapidly)
            if ch == ord('w'): nudge(positions, "shoulder_lift", +STEP); changed = True
            if ch == ord('s'): nudge(positions, "shoulder_lift", -STEP); changed = True
            if ch == ord('a'): nudge(positions, "shoulder_pan",  +STEP); changed = True
            if ch == ord('d'): nudge(positions, "shoulder_pan",  -STEP); changed = True
            if ch == ord('r'): nudge(positions, "elbow_flex",    +STEP); changed = True
            if ch == ord('f'): nudge(positions, "elbow_flex",    -STEP); changed = True
            if ch == ord('t'): nudge(positions, "wrist_flex",    +STEP); changed = True
            if ch == ord('g'): nudge(positions, "wrist_flex",    -STEP); changed = True
            if ch == ord('y'): nudge(positions, "wrist_roll",    +STEP); changed = True
            if ch == ord('h'): nudge(positions, "wrist_roll",    -STEP); changed = True
            if ch == ord('o'): nudge(positions, "gripper",       +STEP); changed = True
            if ch == ord('c'): nudge(positions, "gripper",       -STEP); changed = True

        if changed:
            robot.send_action(positions)

        draw(stdscr, positions, STEP)

        elapsed = time.perf_counter() - t0
        time.sleep(max(0, dt - elapsed))


def main():
    print("Connecting to arm on /dev/ttyACM0 ...")
    config = SO101FollowerConfig(port=PORT, id=ARM_ID)
    robot  = SO101Follower(config)
    robot.connect()
    print("Connected! Starting controller... (curses window will open)")
    time.sleep(0.5)

    try:
        curses.wrapper(run, robot)
    finally:
        print("Disconnecting arm safely...")
        robot.disconnect()
        print("Done. Goodbye!")


if __name__ == "__main__":
    main()
