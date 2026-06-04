#!/usr/bin/env python3
"""
SO-101 Assembly Helper: Sets each motor to its middle position (encoder 2047 / 0°)
one at a time, so you can assemble each joint at the correct neutral angle.

Usage:
    uv run python set_middle_positions.py --port /dev/ttyACM1   # leader
    uv run python set_middle_positions.py --port /dev/ttyACM2   # follower
"""

import argparse
import time

from lerobot.motors.feetech import FeetechMotorsBus
from lerobot.motors.feetech.feetech import TorqueMode
from lerobot.motors.motors_bus import Motor, MotorNormMode, get_address

# Motor definitions: (name, target_id, model)
MOTORS = [
    ("shoulder_pan",  1, "sts3215"),
    ("shoulder_lift", 2, "sts3215"),
    ("elbow_flex",    3, "sts3215"),
    ("wrist_flex",    4, "sts3215"),
    ("wrist_roll",    5, "sts3215"),
    ("gripper",       6, "sts3215"),
]

MIDDLE_POS = 2047  # Midpoint of 12-bit encoder (0–4095)
SCAN_BAUDRATES = [1_000_000, 500_000, 250_000, 128_000, 115_200, 57_600]
DEFAULT_BAUDRATE = 1_000_000


def set_motor_to_middle(port: str, motor_name: str, target_id: int, model: str) -> bool:
    motor = Motor(target_id, model, MotorNormMode.DEGREES)
    bus = FeetechMotorsBus(port=port, motors={motor_name: motor})
    bus._connect(handshake=False)

    # 1. Scan for the motor across all baudrates
    found_baudrate = None
    found_id = None
    for baudrate in SCAN_BAUDRATES:
        bus.set_baudrate(baudrate)
        ids_models = bus.broadcast_ping()
        if ids_models:
            found_id = list(ids_models.keys())[0]
            found_baudrate = baudrate
            break

    if found_id is None:
        print("  ✗ No motor found! Check the cable connection.")
        bus.port_handler.closePort()
        return False

    print(f"  ✓ Found motor  baudrate={found_baudrate:,}  id={found_id}")

    # 2. Reprogram baud rate if not at default
    if found_baudrate != DEFAULT_BAUDRATE:
        print(f"  ⚠ Setting baudrate {found_baudrate:,} → {DEFAULT_BAUDRATE:,}")
        addr, length = get_address(bus.model_ctrl_table, model, "Baud_Rate")
        baud_val = bus.model_baudrate_table[model][DEFAULT_BAUDRATE]
        bus._write(addr, length, found_id, baud_val, raise_on_error=False)
        bus.set_baudrate(DEFAULT_BAUDRATE)
        time.sleep(0.1)

    # 3. Reprogram ID if incorrect
    if found_id != target_id:
        print(f"  ⚠ Setting ID {found_id} → {target_id}")
        # Disable torque safely
        addr_te, len_te = get_address(bus.model_ctrl_table, model, "Torque_Enable")
        addr_lock, len_lock = get_address(bus.model_ctrl_table, model, "Lock")
        bus._write(addr_te, len_te, found_id, TorqueMode.DISABLED.value, raise_on_error=False)
        bus._write(addr_lock, len_lock, found_id, 0, raise_on_error=False)
        time.sleep(0.1)
        addr, length = get_address(bus.model_ctrl_table, model, "ID")
        bus._write(addr, length, found_id, target_id, raise_on_error=False)
        time.sleep(0.2)

    # 4. Enable torque and move to middle
    addr_te,   len_te   = get_address(bus.model_ctrl_table, model, "Torque_Enable")
    addr_lock, len_lock = get_address(bus.model_ctrl_table, model, "Lock")
    addr_gp,   len_gp   = get_address(bus.model_ctrl_table, model, "Goal_Position")
    addr_pp,   len_pp   = get_address(bus.model_ctrl_table, model, "Present_Position")

    _, err_te = bus._write(addr_te,   len_te,   target_id, TorqueMode.ENABLED.value, raise_on_error=False)
    _, err_lk = bus._write(addr_lock, len_lock, target_id, 1, raise_on_error=False)
    _, err_gp = bus._write(addr_gp,   len_gp,   target_id, MIDDLE_POS, raise_on_error=False)

    for err in [err_te, err_lk, err_gp]:
        if err != 0:
            err_str = bus.packet_handler.getRxPacketError(err)
            print(f"  ⚠ Motor returned a setup packet error: {err_str}")
            if "Overload" in err_str:
                print("  [ACTION REQUIRED] Overload detected! Power-cycle the motor (turn off/on physical power) to clear this.")

    # Wait for motor to reach target
    pos = MIDDLE_POS
    for _ in range(20):
        time.sleep(0.1)
        res_pos, comm, err = bus._read(addr_pp, len_pp, target_id, raise_on_error=False)
        if comm == bus._comm_success:
            pos = res_pos
        if err != 0:
            err_str = bus.packet_handler.getRxPacketError(err)
            print(f"  ⚠ Motor returned a read packet error: {err_str}")
            if "Overload" in err_str:
                print("  [ACTION REQUIRED] Overload detected! Power-cycle the motor (turn off/on physical power) to clear this.")
            break
        if abs(pos - MIDDLE_POS) < 30:
            break
    
    res_pos, comm, _ = bus._read(addr_pp, len_pp, target_id, raise_on_error=False)
    if comm == bus._comm_success:
        pos = res_pos
    error = abs(pos - MIDDLE_POS)
    status = "✓ At middle!" if error < 50 else f"⚠ Off by {error} ticks — check if motor is blocked/overloaded"
    print(f"  Position: {pos} / {MIDDLE_POS}  ({status})")

    # 5. Wait for user to assemble the joint
    input("  → Attach the joint link at this angle, then press Enter to continue...")

    # Disable torque safely
    bus._write(addr_te, len_te, target_id, TorqueMode.DISABLED.value, raise_on_error=False)
    bus._write(addr_lock, len_lock, target_id, 0, raise_on_error=False)
    bus.port_handler.closePort()
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Set SO-101 motor(s) to the neutral middle position for correct assembly."
    )
    parser.add_argument(
        "--port", required=True,
        help="Serial port of the controller board (e.g. /dev/ttyACM1 for leader, /dev/ttyACM2 for follower)"
    )
    parser.add_argument(
        "--id", type=int, choices=[1, 2, 3, 4, 5, 6],
        help="Target ID of a single motor to configure (e.g. 4 for wrist_flex). If omitted, configures all sequential motors."
    )
    args = parser.parse_args()

    print()
    print("=" * 62)
    print("  SO-101  ·  Middle Position Assembly Helper")
    print(f"  Port   : {args.port}")
    if args.id is not None:
        print(f"  Motor ID: {args.id}")
    print(f"  Target : {MIDDLE_POS}  (encoder midpoint = 0° / neutral)")
    print("=" * 62)
    print()
    print("  Procedure for each motor:")
    print("    1. Connect ONLY that single motor to the controller board")
    print("    2. This script moves it to encoder 2047 (neutral angle)")
    print("    3. Physically attach the joint link at this neutral angle")
    print("    4. Press Enter to complete setting the motor")
    print()

    success_count = 0
    active_motors = [m for m in MOTORS if args.id is None or m[1] == args.id]

    for motor_name, target_id, model in active_motors:
        print(f"{'─' * 62}")
        print(f"  [{target_id}/6]  Motor: {motor_name}  (ID: {target_id})")
        print(f"{'─' * 62}")
        input(f"  → Connect ONLY the '{motor_name}' motor, then press Enter...")

        ok = set_motor_to_middle(args.port, motor_name, target_id, model)
        if ok:
            success_count += 1
            print(f"  ✓ '{motor_name}' assembled at neutral position.\n")
        else:
            print(f"  ✗ Skipped '{motor_name}' — check and retry manually.\n")

    print("=" * 62)
    if args.id is not None:
        if success_count == 1:
            print(f"  ✓ Motor {args.id} assembled at neutral position!")
        else:
            print(f"  ⚠ Motor {args.id} setup failed or was skipped.")
    else:
        if success_count == len(MOTORS):
            print("  ✓ All 6 motors assembled at neutral position!")
        else:
            print(f"  ⚠ {success_count}/{len(MOTORS)} motors done — check skipped motors.")
    print()
    print("  Next step — reconnect ALL motors and run calibration:")
    print()
    print("    # For leader:")
    print("    uv run lerobot-calibrate \\")
    print("        --teleop.type=so101_leader \\")
    print(f"        --teleop.port={args.port} \\")
    print("        --teleop.id=my_leader")
    print()
    print("    # For follower:")
    print("    uv run lerobot-calibrate \\")
    print("        --robot.type=so101_follower \\")
    print(f"        --robot.port={args.port} \\")
    print("        --robot.id=my_follower")
    print("=" * 62)


if __name__ == "__main__":
    main()
