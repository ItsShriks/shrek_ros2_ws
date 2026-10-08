import time
import busio
from board import SCL, SDA
from adafruit_pca9685 import PCA9685
from adafruit_motor import servo

def main():
    # 1. Initialize I2C bus and PCA9685 module
    print("Initializing I2C bus and PCA9685...")
    i2c = busio.I2C(SCL, SDA)
    pca = PCA9685(i2c)

    # Standard 50Hz frequency for analog/digital hobby servos
    pca.frequency = 50

    # 2. Configure Servo on Channel 0
    # min_pulse and max_pulse in microseconds (standard range is usually 500-2500us or 750-2250us)
    servo_channel = 0
    test_servo = servo.Servo(pca.channels[servo_channel], min_pulse=500, max_pulse=2500)

    print(f"\n--- Testing Servo on PCA9685 Channel {servo_channel} ---")
    print("Press Ctrl+C to stop.")

    try:
        while True:
            # Move to 0 degrees
            print("Position: 0°")
            test_servo.angle = 0
            time.sleep(1.5)

            # Move to 90 degrees (Center)
            print("Position: 90° (Center)")
            test_servo.angle = 90
            time.sleep(1.5)

            # Move to 180 degrees
            print("Position: 180°")
            test_servo.angle = 180
            time.sleep(1.5)

            # Smooth sweep from 180 back to 0 degrees
            print("Sweeping smoothly from 180° back to 0°...")
            for angle in range(180, -1, -5):
                test_servo.angle = angle
                time.sleep(0.05)

            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping test...")
    finally:
        # Turn off signal to channel 0 to stop sending pulses/holding torque
        pca.channels[servo_channel].duty_cycle = 0
        pca.deinit()
        print("PCA9685 connection closed cleanly.")

if __name__ == "__main__":
    main()
