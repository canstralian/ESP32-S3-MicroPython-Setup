#!/bin/bash
# ESP32-S3 CCTV Hub Setup Script for Raspberry Pi 5
# This script installs all dependencies and sets up the CCTV hub

set -e  # Exit on error

echo "=========================================="
echo "ESP32-S3 CCTV Hub Setup"
echo "Raspberry Pi 5 Installation"
echo "=========================================="
echo ""

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo "⚠ Warning: This doesn't appear to be a Raspberry Pi"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check for root/sudo
if [ "$EUID" -eq 0 ]; then
    echo "⚠ Please run without sudo. The script will ask for sudo when needed."
    exit 1
fi

echo "Step 1: Updating system packages..."
sudo apt update

echo ""
echo "Step 2: Installing system dependencies..."
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-opencv \
    ffmpeg \
    libopencv-dev \
    libatlas-base-dev \
    libjpeg-dev \
    libtiff-dev \
    libpng-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    libxvidcore-dev \
    libx264-dev

echo ""
echo "Step 3: Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

echo ""
echo "Step 4: Activating virtual environment and installing Python packages..."
source venv/bin/activate
pip install --upgrade pip wheel setuptools
pip install -r requirements.txt

echo ""
echo "Step 5: Creating directories..."
mkdir -p recordings
mkdir -p logs
echo "✓ Directories created"

echo ""
echo "Step 6: Creating default configuration..."
if [ ! -f "config.json" ]; then
    cat > config.json << 'EOF'
{
  "cameras": [
    {
      "name": "FrontDoor",
      "ip": "192.168.1.101",
      "enabled": true
    },
    {
      "name": "Garage",
      "ip": "192.168.1.102",
      "enabled": true
    },
    {
      "name": "BackYard",
      "ip": "192.168.1.103",
      "enabled": true
    }
  ],
  "recording": {
    "enabled": true,
    "snapshot_on_motion": true,
    "video_on_motion": false,
    "video_duration": 30,
    "recordings_dir": "recordings"
  },
  "server": {
    "host": "0.0.0.0",
    "port": 8080,
    "debug": false
  },
  "polling": {
    "motion_interval": 1.5,
    "health_check_interval": 10,
    "timeout": 2
  },
  "stream": {
    "width": 640,
    "height": 480,
    "quality": 85
  }
}
EOF
    echo "✓ Default config.json created"
    echo "⚠ IMPORTANT: Edit config.json to set your camera IP addresses!"
else
    echo "✓ config.json already exists (not overwriting)"
fi

echo ""
echo "Step 7: Making scripts executable..."
chmod +x cctv_hub.py
chmod +x setup.sh
echo "✓ Scripts are executable"

echo ""
echo "=========================================="
echo "✓ Installation Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Edit config.json with your camera IP addresses:"
echo "   nano config.json"
echo ""
echo "2. Start the CCTV hub:"
echo "   source venv/bin/activate"
echo "   python3 cctv_hub.py"
echo ""
echo "3. Access the dashboard at:"
echo "   http://$(hostname -I | awk '{print $1}'):8080"
echo ""
echo "4. (Optional) Set up as a system service:"
echo "   sudo cp cctv-hub.service /etc/systemd/system/"
echo "   sudo systemctl daemon-reload"
echo "   sudo systemctl enable cctv-hub.service"
echo "   sudo systemctl start cctv-hub.service"
echo ""
echo "For more information, see README.md"
echo ""
