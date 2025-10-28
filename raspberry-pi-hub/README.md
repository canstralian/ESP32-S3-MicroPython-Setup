# ESP32-S3 CCTV Hub for Raspberry Pi 5

A powerful, multi-camera CCTV aggregation system that runs on Raspberry Pi 5, designed to work with ESP32-S3 camera modules. This hub provides centralized video streaming, motion detection monitoring, recording capabilities, and a beautiful web dashboard for managing multiple camera feeds.

## Overview

```
[ESP32-S3 Cam #1] ─┐
[ESP32-S3 Cam #2] ─┤── Wi-Fi LAN ──> [Raspberry Pi 5 CCTV Hub]
[ESP32-S3 Cam #3] ─┘                  │
                                      ├─ Flask web server (multi-camera dashboard)
                                      ├─ Motion event listener & recorder
                                      └─ Health monitoring & alerts
```

### Key Features

- **Multi-Camera Dashboard**: Live view of all connected ESP32-S3 cameras in a responsive web interface
- **Motion Detection**: Real-time monitoring with automatic snapshot/video recording
- **Health Monitoring**: Continuous camera health checks and status reporting
- **Automatic Recording**: Configurable snapshot and video recording on motion events
- **RESTful API**: JSON API for integration with other systems
- **Auto-Start**: Systemd service for running on boot
- **Low Latency**: Optimized streaming with minimal delay
- **Scalable**: Support for multiple cameras with easy configuration

## Prerequisites

### Hardware
- Raspberry Pi 5 (4GB or 8GB recommended)
- MicroSD card (32GB+ recommended)
- Power supply (5V/5A for Raspberry Pi 5)
- One or more ESP32-S3 camera modules (configured with the MicroPython streaming firmware)
- Local network (2.4GHz Wi-Fi or Ethernet)

### Software
- Raspberry Pi OS (64-bit, Bookworm or later recommended)
- Python 3.9 or later
- Git

## Quick Start

### 1. Clone the Repository

```bash
cd ~
git clone https://github.com/canstralian/ESP32-S3-MicroPython-Setup.git
cd ESP32-S3-MicroPython-Setup/raspberry-pi-hub
```

### 2. Run the Setup Script

```bash
chmod +x setup.sh
./setup.sh
```

The setup script will:
- Install all system dependencies (OpenCV, FFmpeg, etc.)
- Create a Python virtual environment
- Install Python packages
- Create necessary directories
- Generate a default configuration file

### 3. Configure Your Cameras

Edit `config.json` to add your ESP32-S3 camera IP addresses:

```bash
nano config.json
```

Update the camera list with your actual IP addresses:

```json
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
    }
  ]
}
```

### 4. Start the CCTV Hub

```bash
source venv/bin/activate
python3 cctv_hub.py
```

### 5. Access the Dashboard

Open your web browser and navigate to:

```
http://<raspberry-pi-ip>:8080
```

You can find your Raspberry Pi's IP address with:

```bash
hostname -I
```

## Configuration

### Configuration File Structure

The `config.json` file controls all aspects of the CCTV hub:

```json
{
  "cameras": [
    {
      "name": "CameraName",       // Unique identifier for the camera
      "ip": "192.168.1.101",      // IP address of the ESP32-S3
      "enabled": true             // Enable/disable this camera
    }
  ],
  "recording": {
    "enabled": true,              // Enable/disable all recording
    "snapshot_on_motion": true,   // Save JPG snapshots when motion detected
    "video_on_motion": false,     // Save MP4 videos when motion detected
    "video_duration": 30,         // Video length in seconds
    "recordings_dir": "recordings" // Directory for saved recordings
  },
  "server": {
    "host": "0.0.0.0",           // Listen address (0.0.0.0 = all interfaces)
    "port": 8080,                // Web server port
    "debug": false               // Enable Flask debug mode
  },
  "polling": {
    "motion_interval": 1.5,      // How often to check for motion (seconds)
    "health_check_interval": 10, // How often to check camera health (seconds)
    "timeout": 2                 // Request timeout (seconds)
  },
  "stream": {
    "width": 640,                // Stream frame width
    "height": 480,               // Stream frame height
    "quality": 85                // JPEG quality (0-100)
  }
}
```

### Adding Cameras

To add a new camera:

1. Configure the ESP32-S3 with the MicroPython streaming firmware (see main README)
2. Note its IP address
3. Add an entry to the `cameras` array in `config.json`
4. Restart the CCTV hub

### Recordings

Recordings are saved in the `recordings/` directory with the format:

```
recordings/
├── FrontDoor_20250128_143052.jpg
├── Garage_20250128_143105.jpg
└── BackYard_20250128_143210.jpg
```

## Running as a System Service

To run the CCTV hub automatically on boot:

### 1. Edit the Service File

Update the paths in `cctv-hub.service` to match your installation:

```bash
nano cctv-hub.service
```

Change `/home/pi/cctv-hub` to your actual installation path.

### 2. Install the Service

```bash
sudo cp cctv-hub.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable cctv-hub.service
sudo systemctl start cctv-hub.service
```

### 3. Check Status

```bash
sudo systemctl status cctv-hub.service
```

### 4. View Logs

```bash
sudo journalctl -u cctv-hub.service -f
```

### 5. Control the Service

```bash
# Stop the service
sudo systemctl stop cctv-hub.service

# Restart the service
sudo systemctl restart cctv-hub.service

# Disable auto-start
sudo systemctl disable cctv-hub.service
```

## API Endpoints

The CCTV hub provides a RESTful API:

### Dashboard
```
GET /
```
Returns the main web dashboard.

### Camera Stream
```
GET /stream/<camera_name>
```
Returns MJPEG stream from the specified camera.

### Camera Status
```
GET /status/<camera_name>
```
Returns JSON with motion and health status:
```json
{
  "motion": false,
  "health": {
    "online": true,
    "last_check": 1706454123,
    "uptime": 3600
  },
  "last_motion": 1706454100
}
```

### All Cameras
```
GET /api/cameras
```
Returns array of all cameras with their status.

### Hub Health
```
GET /api/health
```
Returns hub system health:
```json
{
  "status": "ok",
  "cameras_count": 3,
  "cameras_online": 3,
  "recording_enabled": true
}
```

## Troubleshooting

### Camera Shows "Offline"

**Possible causes:**
- ESP32-S3 is not powered on or not connected to Wi-Fi
- Incorrect IP address in `config.json`
- Network connectivity issues
- ESP32-S3 firmware not running

**Solutions:**
1. Check ESP32-S3 power and Wi-Fi connection
2. Verify IP address with `ping <camera-ip>`
3. Check ESP32-S3 serial output for errors
4. Ensure firewall allows port 8080

### Stream Shows Black Screen

**Possible causes:**
- Camera sensor not initialized
- Poor lighting conditions
- Camera hardware issue

**Solutions:**
1. Restart the ESP32-S3
2. Check camera initialization in ESP32-S3 logs
3. Improve lighting in camera view
4. Test camera with direct browser access: `http://<esp32-ip>:8080/stream`

### High CPU Usage

**Possible causes:**
- Too many cameras streaming simultaneously
- High resolution settings
- Insufficient Raspberry Pi resources

**Solutions:**
1. Reduce stream resolution in `config.json`
2. Lower JPEG quality setting
3. Disable unused cameras
4. Consider upgrading to Raspberry Pi 5 with more RAM

### Recording Not Working

**Possible causes:**
- Recording disabled in config
- Insufficient disk space
- Permissions issue on recordings directory

**Solutions:**
1. Check `recording.enabled` in `config.json`
2. Verify disk space: `df -h`
3. Check directory permissions: `ls -la recordings/`
4. Ensure recordings directory exists

### Service Won't Start

**Possible causes:**
- Incorrect paths in service file
- Python virtual environment not activated
- Missing dependencies

**Solutions:**
1. Check service logs: `journalctl -u cctv-hub.service -n 50`
2. Verify paths in `/etc/systemd/system/cctv-hub.service`
3. Manually test: `cd /home/pi/cctv-hub && source venv/bin/activate && python3 cctv_hub.py`
4. Reinstall dependencies: `pip install -r requirements.txt`

## Performance Optimization

### For Multiple Cameras (4+)

1. **Increase Buffer Size**: Edit `cctv_hub.py` and increase OpenCV buffer:
   ```python
   cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)  # Increase from 1
   ```

2. **Use Hardware Acceleration**: Install OpenCV with hardware acceleration:
   ```bash
   pip uninstall opencv-python
   pip install opencv-python-headless
   ```

3. **Reduce Resolution**: Lower stream resolution in config:
   ```json
   "stream": {
     "width": 320,
     "height": 240,
     "quality": 70
   }
   ```

4. **Increase Polling Intervals**:
   ```json
   "polling": {
     "motion_interval": 2.5,
     "health_check_interval": 30
   }
   ```

### For Remote Access

If accessing the hub from outside your local network:

1. **Use VPN**: Set up WireGuard or Tailscale for secure access
2. **Reverse Proxy**: Use Nginx with HTTPS:
   ```bash
   sudo apt install nginx certbot
   # Configure reverse proxy to port 8080
   ```

3. **Port Forwarding**: Forward port 8080 on your router (less secure)

## Security Considerations

### Network Security
- Keep the CCTV hub on a trusted network
- Use VPN for remote access instead of port forwarding
- Consider network segmentation for cameras

### Updates
- Keep Raspberry Pi OS updated: `sudo apt update && sudo apt upgrade`
- Update Python packages: `pip install --upgrade -r requirements.txt`

### Authentication
The current version does not include built-in authentication. For production use:
- Run behind Nginx with HTTP basic auth
- Use a VPN for access control
- Implement application-level authentication (requires code modification)

## Advanced Features

### Integration with Home Assistant

Add cameras as MJPEG camera entities:

```yaml
camera:
  - platform: mjpeg
    name: Front Door
    mjpeg_url: http://<pi-ip>:8080/stream/FrontDoor

  - platform: mjpeg
    name: Garage
    mjpeg_url: http://<pi-ip>:8080/stream/Garage
```

### Motion Alerts via Webhook

The hub can be extended to send webhooks on motion detection. Edit `cctv_hub.py` in the `poll_motion()` function to add webhook calls.

### Custom Recording Logic

Modify the `poll_motion()` function to implement custom recording behavior, such as:
- Continuous recording to a circular buffer
- Recording X seconds before and after motion
- Cloud upload of recordings

## File Structure

```
raspberry-pi-hub/
├── cctv_hub.py              # Main application
├── requirements.txt         # Python dependencies
├── config.json             # Configuration (created by setup)
├── config.example.json     # Configuration template
├── setup.sh                # Installation script
├── cctv-hub.service       # Systemd service file
├── README.md              # This file
├── recordings/            # Recorded snapshots/videos
├── logs/                  # Application logs
└── venv/                  # Python virtual environment
```

## Contributing

Contributions are welcome! Please see the main repository for contribution guidelines.

## License

This project is part of the ESP32-S3-MicroPython-Setup repository.

## Support

For issues and questions:
- Open an issue on GitHub
- Check the troubleshooting section above
- Review logs: `cat cctv_hub.log`

## Roadmap

Future enhancements planned:
- [ ] Video recording support
- [ ] Email/SMS notifications on motion
- [ ] Cloud storage integration
- [ ] Motion detection zones
- [ ] PTZ camera support
- [ ] Mobile app
- [ ] Two-way audio
- [ ] Face detection/recognition
- [ ] Time-lapse generation
- [ ] Storage management (auto-cleanup)

## Credits

Built for use with ESP32-S3 camera modules running MicroPython firmware.

---

**Made with ♥ for home security and IoT enthusiasts**
