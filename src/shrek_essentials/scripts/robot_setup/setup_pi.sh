#!/usr/bin/env bash
# One-time Raspberry Pi setup for the Shrek servo tools.
#   bash setup_pi.sh
set -e

echo "== Enabling I2C =="
if command -v raspi-config >/dev/null; then
    sudo raspi-config nonint do_i2c 0
else
    echo "raspi-config not found: enable I2C by hand (dtparam=i2c_arm=on in /boot/firmware/config.txt)"
fi

echo "== System packages =="
sudo apt-get update
sudo apt-get install -y python3-yaml python3-gpiozero python3-pip python3-venv i2c-tools
sudo apt-get install -y python3-lgpio || echo "(python3-lgpio not available, GPIO servos fall back to gpiozero default)"

echo "== Adafruit PCA9685 library =="
if python3 -c "import board, busio, adafruit_pca9685" 2>/dev/null; then
    echo "Already installed for system python3."
    PY=python3
else
    VENV="$HOME/shrek_venv"
    python3 -m venv --system-site-packages "$VENV"
    "$VENV/bin/pip" install --upgrade adafruit-blinka adafruit-circuitpython-pca9685 adafruit-circuitpython-motor
    PY="$VENV/bin/python3"
    echo
    echo "Installed into $VENV. Before running the tools:  source $VENV/bin/activate"
fi

echo "== Permissions =="
sudo usermod -aG i2c,gpio "$USER" || true

echo
echo "== I2C scan (PCA9685 should show as 40) =="
sudo i2cdetect -y 1 || echo "i2cdetect failed: reboot so I2C becomes active, then run it again"

echo
echo "Done. If this was the first run: reboot (I2C + group membership), then"
echo "  $PY 01_check_system.py"
