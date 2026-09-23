#!/usr/bin/env python3

import time
import board
import busio
from adafruit_pca9685 import PCA9685
from adafruit_motor import servo

def main():
    # Initialize I2C bus
    i2c = busio.I2C(board.SCL, board.SDA)

    # Initialize two PCA9685 boards
    pca1 = PCA9685(i2c, address=0x40)
    pca2 = PCA9685(i2c, address=0x41)

    # Set the PWM frequency to 50hz
    pca1.frequency = 50
    pca2.frequency = 50

    servos = []
    
    # 16 servos on board 1
    for i in range(16):
        servos.append(servo.Servo(pca1.channels[i], min_pulse=500, max_pulse=2500))
        
    # 1 servo on board 2
    servos.append(servo.Servo(pca2.channels[0], min_pulse=500, max_pulse=2500))

    # Define leg assignments 
    left_leg_indices = [0, 1, 2, 3]
    right_leg_indices = [4, 5, 6, 7]

    def set_leg_positions(indices, angles):
        for idx, angle in zip(indices, angles):
            clamped_angle = max(0, min(180, angle))
            servos[idx].angle = clamped_angle

    print("Initializing jumping sequence...")

    home_position = [90, 90, 90, 90]
    
    # Crouch position (bend knees and hips)
    # Adjust these values based on actual servo mapping to achieve a crouch
    crouch_position = [90, 90, 50, 130] 
    
    # Explode position (straighten legs rapidly)
    explode_position = [90, 90, 110, 70]

    set_leg_positions(left_leg_indices, home_position)
    set_leg_positions(right_leg_indices, home_position)
    time.sleep(2)

    try:
        while True:
            print("Crouching...")
            set_leg_positions(left_leg_indices, crouch_position)
            set_leg_positions(right_leg_indices, crouch_position)
            time.sleep(0.5) # Hold crouch

            print("Jumping!")
            set_leg_positions(left_leg_indices, explode_position)
            set_leg_positions(right_leg_indices, explode_position)
            time.sleep(0.3) # Airborne / explode phase

            print("Landing...")
            set_leg_positions(left_leg_indices, crouch_position)
            set_leg_positions(right_leg_indices, crouch_position)
            time.sleep(0.3) # Absorb impact

            print("Resetting...")
            set_leg_positions(left_leg_indices, home_position)
            set_leg_positions(right_leg_indices, home_position)
            time.sleep(1.0) # Rest before next jump

    except KeyboardInterrupt:
        print("Stopping robot and returning to home position...")
        set_leg_positions(left_leg_indices, home_position)
        set_leg_positions(right_leg_indices, home_position)
        time.sleep(1)

        pca1.deinit()
        pca2.deinit()

if __name__ == "__main__":
    main()
