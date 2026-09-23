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

    # Define indices based on total 17 servos
    left_arm_indices = [8, 9, 10, 11]
    right_arm_indices = [12, 13, 14, 15]
    head_index = 16

    def set_arm_positions(indices, angles):
        for idx, angle in zip(indices, angles):
            clamped_angle = max(0, min(180, angle))
            servos[idx].angle = clamped_angle

    def set_head_position(angle):
        servos[head_index].angle = max(0, min(180, angle))

    print("Initializing waving sequence...")

    home_arm_position = [90, 90, 90, 90]
    
    # Bring right arm up to wave position
    # (assuming index 12 is shoulder pitch, 13 is shoulder roll, etc.)
    # Adjust these to raise the arm properly
    wave_base_position = [150, 90, 90, 120] 

    set_arm_positions(left_arm_indices, home_arm_position)
    set_arm_positions(right_arm_indices, home_arm_position)
    set_head_position(90) # Looking forward
    time.sleep(1)

    try:
        # Move arm up and look towards the right arm
        set_arm_positions(right_arm_indices, wave_base_position)
        set_head_position(120) # Turn head right
        time.sleep(0.5)

        t = 0
        while True:
            # Oscillate the wrist/elbow for a wave
            # We'll just oscillate the last two servos in the arm chain
            wave_angle_1 = 90 + 30 * math.sin(t)
            wave_angle_2 = 120 + 20 * math.cos(t)

            wave_current_position = [150, 90, wave_angle_1, wave_angle_2]
            set_arm_positions(right_arm_indices, wave_current_position)
            
            # Slightly nod/bob head during wave
            set_head_position(120 + 10 * math.sin(t/2))

            t += 0.5
            time.sleep(0.05)

    except KeyboardInterrupt:
        print("Stopping robot and returning to home position...")
        set_arm_positions(left_arm_indices, home_arm_position)
        set_arm_positions(right_arm_indices, home_arm_position)
        set_head_position(90)
        time.sleep(1)

        pca1.deinit()
        pca2.deinit()

if __name__ == "__main__":
    main()
