#!/usr/bin/env bash
# Install what servo_gpio_test.py needs on Raspberry Pi OS / Ubuntu for Pi.
set -e

echo "Installing gpiozero + lgpio..."
sudo apt-get update
sudo apt-get install -y python3-gpiozero python3-lgpio || \
    pip3 install --break-system-packages gpiozero lgpio

# pigpio gives jitter-free servo pulses but does not support the Pi 5.
MODEL=$(tr -d '\0' < /proc/device-tree/model 2>/dev/null || echo unknown)
echo "Board: $MODEL"
if [[ "$MODEL" == *"Raspberry Pi 5"* ]]; then
    echo "Pi 5 detected: skipping pigpio, the script will use lgpio."
else
    if sudo apt-get install -y pigpio python3-pigpio; then
        sudo systemctl enable --now pigpiod
        echo "pigpiod running: servos will use jitter-free DMA timing."
    else
        echo "pigpio not available from apt, the script will use lgpio instead."
    fi
fi

sudo usermod -aG gpio "$USER" || true
echo
echo "Done. Log out and back in if this was your first time joining the 'gpio' group."
echo "Then run: python3 servo_gpio_test.py"
