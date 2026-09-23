#!/usr/bin/env python3

import time
import math
import board
import busio
from adafruit_pca9685 import PCA9685
from adafruit_motor import servo

def main():
    # Initialize I2C bus
    i2c = busio.I2C(board.SCL, board.SDA)

    # Initialize two PCA9685 boards
    # Assuming addresses are 0x40 and 0x41. Change if your wiring differs.
    pca1 = PCA9685(i2c, address=0x40)
    pca2 = PCA9685(i2c, address=0x41)

    # Set the PWM frequency to 50hz for standard servos
    pca1.frequency = 50
    pca2.frequency = 50

    # Initialize servo objects on the two boards
    # Assuming servos 0-15 on pca1 and servos 0-15 on pca2.
    # Total 17 servos, so we will use 16 on pca1 and 1 on pca2, or split them.
    # For this script, let's create a list of all 17 servos across the two boards.
    servos = []
    
    # 16 servos on board 1
    for i in range(16):
        servos.append(servo.Servo(pca1.channels[i], min_pulse=500, max_pulse=2500))
        
    # 1 servo on board 2 (giving 17 total)
    servos.append(servo.Servo(pca2.channels[0], min_pulse=500, max_pulse=2500))

    # Define leg assignments based on user description
    # 4 servos for left leg, 4 servos for right leg
    # (Adjust these indices to match your actual hardware wiring)
    left_leg_indices = [0, 1, 2, 3]   # Example indices: Hip yaw, Hip roll, Hip pitch, Knee
    right_leg_indices = [4, 5, 6, 7]  # Example indices: Hip yaw, Hip roll, Hip pitch, Knee

    # Helper function to set leg positions safely
    def set_leg_positions(indices, angles):
        for idx, angle in zip(indices, angles):
            # Clamp angles between 0 and 180
            clamped_angle = max(0, min(180, angle))
            servos[idx].angle = clamped_angle

    print("Initializing running sequence...")

    # Default standing position (approx 90 degrees for all leg servos)
    home_position = [90, 90, 90, 90]
    set_leg_positions(left_leg_indices, home_position)
    set_leg_positions(right_leg_indices, home_position)
    time.sleep(2)

    # Basic Running Gait Parameters
    # Higher amplitude and speed compared to walking
    amplitude = 35 # degrees
    speed = 5.0    # speed multiplier

    try:
        t = 0
        while True:
            # Calculate oscillatory angles for walking
            # Left leg cycle
            left_hip_pitch = 90 + amplitude * math.sin(t)
            left_knee      = 90 + amplitude * math.sin(t + math.pi/4)
            left_hip_roll  = 90 + (amplitude/2) * math.sin(t + math.pi/2)
            
            # Right leg cycle (out of phase)
            right_hip_pitch = 90 + amplitude * math.sin(t + math.pi)
            right_knee      = 90 + amplitude * math.sin(t + math.pi + math.pi/4)
            right_hip_roll  = 90 + (amplitude/2) * math.sin(t + math.pi + math.pi/2)

            # Assign computed angles to the legs (assuming indices: Yaw=0, Roll=1, Pitch=2, Knee=3)
            # You may need to invert some angles based on servo mounting orientation
            left_angles = [90, left_hip_roll, left_hip_pitch, left_knee]
            right_angles = [90, right_hip_roll, right_hip_pitch, right_knee]

            set_leg_positions(left_leg_indices, left_angles)
            set_leg_positions(right_leg_indices, right_angles)

            t += 0.1 * speed
            time.sleep(0.05)

    except KeyboardInterrupt:
        print("Stopping robot and returning to home position...")
        set_leg_positions(left_leg_indices, home_position)
        set_leg_positions(right_leg_indices, home_position)
        time.sleep(1)

        # Deinitialize boards
        pca1.deinit()
        pca2.deinit()

if __name__ == "__main__":
    main()
