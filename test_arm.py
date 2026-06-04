#!/usr/bin/env python3
import time
from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig

def main():
    print("Initializing SO-101 Follower Arm configuration...")
    
    # Configure the robot with your port and calibration ID
    config = SO101FollowerConfig(
        port="/dev/ttyACM0",
        id="my_follower",
    )
    
    # Create the robot instance and connect (this will automatically load your calibration file)
    robot = SO101Follower(config)
    
    print("Connecting to the arm and loading calibration...")
    robot.connect()
    print("Successfully connected.")
    
    try:
        # Move the arm to its zero/neutral vertical state first
        print("Moving to home position (straight up, gripper half-open)...")
        home_action = {
            "shoulder_pan.pos": 0.0,
            "shoulder_lift.pos": 0.0,
            "elbow_flex.pos": 0.0,
            "wrist_flex.pos": 0.0,
            "wrist_roll.pos": 0.0,
            "gripper.pos": 50.0,
        }
        robot.send_action(home_action)
        time.sleep(2)
        
        # Test 1: Close gripper
        print("Testing gripper: Closing...")
        robot.send_action({**home_action, "gripper.pos": 0.0})
        time.sleep(1.5)
        
        # Test 2: Open gripper
        print("Testing gripper: Opening fully...")
        robot.send_action({**home_action, "gripper.pos": 100.0})
        time.sleep(1.5)
        
        # Return gripper to half-open
        print("Testing gripper: Returning to half-open...")
        robot.send_action(home_action)
        time.sleep(1)

        # Test 3: Wave wrist
        print("Testing wrist: Tilting forward...")
        robot.send_action({**home_action, "wrist_flex.pos": 30.0})
        time.sleep(1.5)
        
        print("Testing wrist: Tilting backward...")
        robot.send_action({**home_action, "wrist_flex.pos": -30.0})
        time.sleep(1.5)
        
        # Return to home
        print("Returning to home position...")
        robot.send_action(home_action)
        time.sleep(1.5)
        
        print("Tests completed successfully.")
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user.")
    finally:
        # Always disconnect to cleanly disable torque and avoid burning out the motors
        print("Disconnecting and disabling torque...")
        robot.disconnect()
        print("Disconnected safely.")

if __name__ == "__main__":
    main()
