#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Raspberry Pi 5 CCTV Hub
========================
Aggregates multiple ESP32-S3 MJPEG streams and motion statuses
into one web dashboard. Optionally records motion events.

Features:
- Multi-camera live streaming dashboard
- Motion detection monitoring
- Automatic snapshot recording on motion
- Optional video recording
- Health monitoring for each camera
- RESTful API for camera status
"""

import os
import sys
import json
import time
import logging
import threading
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

import cv2
import requests
from flask import Flask, Response, render_template_string, jsonify, request

# ------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------
CONFIG_FILE = os.getenv("CCTV_CONFIG", "config.json")
DEFAULT_CONFIG = {
    "cameras": [
        {"name": "FrontDoor", "ip": "192.168.1.101", "enabled": True},
        {"name": "Garage", "ip": "192.168.1.102", "enabled": True},
        {"name": "BackYard", "ip": "192.168.1.103", "enabled": True},
    ],
    "recording": {
        "enabled": True,
        "snapshot_on_motion": True,
        "video_on_motion": False,
        "video_duration": 30,  # seconds
        "recordings_dir": "recordings"
    },
    "server": {
        "host": "0.0.0.0",
        "port": 8080,
        "debug": False
    },
    "polling": {
        "motion_interval": 1.5,  # seconds
        "health_check_interval": 10,  # seconds
        "timeout": 2  # seconds
    },
    "stream": {
        "width": 640,
        "height": 480,
        "quality": 85
    }
}

# ------------------------------------------------------------------
# LOGGING
# ------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('cctv_hub.log')
    ]
)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# FLASK APP
# ------------------------------------------------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

# Global state
config: Dict = {}
motion_state: Dict[str, bool] = {}
camera_health: Dict[str, Dict] = {}
active_recordings: Dict[str, Optional[cv2.VideoWriter]] = {}

# ------------------------------------------------------------------
# HTML DASHBOARD TEMPLATE
# ------------------------------------------------------------------
DASHBOARD_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>ESP32 CCTV Hub - Multi-Camera Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: linear-gradient(135deg, #0b0d10 0%, #1a1d24 100%);
            color: #e0e0e0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            min-height: 100vh;
        }
        header {
            background: rgba(20, 25, 35, 0.95);
            padding: 1rem 2rem;
            border-bottom: 2px solid #2a3040;
            backdrop-filter: blur(10px);
            position: sticky;
            top: 0;
            z-index: 100;
        }
        h1 {
            font-size: 1.8rem;
            font-weight: 600;
            color: #4a9eff;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .status-bar {
            display: flex;
            gap: 1rem;
            margin-top: 0.5rem;
            font-size: 0.9rem;
        }
        .status-item {
            padding: 0.25rem 0.75rem;
            background: rgba(40, 50, 70, 0.6);
            border-radius: 12px;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #4a9eff;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 1.5rem;
            padding: 2rem;
            max-width: 1600px;
            margin: 0 auto;
        }
        .cam {
            background: rgba(20, 25, 35, 0.8);
            padding: 1rem;
            border-radius: 16px;
            border: 2px solid #2a3040;
            transition: all 0.3s ease;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }
        .cam:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 12px rgba(0, 0, 0, 0.4);
        }
        .cam.motion {
            border-color: #ff4444;
            box-shadow: 0 0 20px rgba(255, 68, 68, 0.3);
            animation: alertPulse 1s infinite;
        }
        @keyframes alertPulse {
            0%, 100% { border-color: #ff4444; }
            50% { border-color: #ff8888; }
        }
        .cam.offline {
            border-color: #666;
            opacity: 0.6;
        }
        .cam-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.75rem;
        }
        .cam-header h3 {
            font-size: 1.2rem;
            font-weight: 500;
            color: #ffffff;
        }
        .cam-status {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.25rem 0.75rem;
            border-radius: 12px;
            font-size: 0.85rem;
            font-weight: 500;
        }
        .cam-status.idle {
            background: rgba(74, 158, 255, 0.2);
            color: #4a9eff;
        }
        .cam-status.motion {
            background: rgba(255, 68, 68, 0.2);
            color: #ff4444;
        }
        .cam-status.offline {
            background: rgba(128, 128, 128, 0.2);
            color: #999;
        }
        .stream-container {
            position: relative;
            background: #000;
            border-radius: 12px;
            overflow: hidden;
            aspect-ratio: 4/3;
        }
        .stream-container img {
            width: 100%;
            height: 100%;
            object-fit: contain;
            display: block;
        }
        .loading {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            color: #666;
            font-size: 0.9rem;
        }
        .cam-info {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 0.5rem;
            margin-top: 0.75rem;
            font-size: 0.85rem;
        }
        .info-item {
            background: rgba(40, 50, 70, 0.4);
            padding: 0.5rem;
            border-radius: 8px;
        }
        .info-label {
            color: #888;
            font-size: 0.75rem;
            margin-bottom: 0.25rem;
        }
        .info-value {
            color: #e0e0e0;
            font-weight: 500;
        }
        footer {
            text-align: center;
            padding: 2rem;
            color: #666;
            font-size: 0.9rem;
        }
        @media (max-width: 768px) {
            .grid {
                grid-template-columns: 1fr;
                padding: 1rem;
            }
            header {
                padding: 1rem;
            }
            h1 {
                font-size: 1.4rem;
            }
            .status-bar {
                flex-wrap: wrap;
            }
        }
    </style>
</head>
<body>
    <header>
        <h1>
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <circle cx="12" cy="12" r="3"/>
                <line x1="12" y1="2" x2="12" y2="4"/>
                <line x1="12" y1="20" x2="12" y2="22"/>
                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
                <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
            </svg>
            ESP32 CCTV Hub
        </h1>
        <div class="status-bar">
            <div class="status-item">
                <div class="status-dot"></div>
                <span id="camera-count">Loading...</span>
            </div>
            <div class="status-item">
                <span id="recording-status">Recording: Enabled</span>
            </div>
        </div>
    </header>

    <div class="grid" id="cameras"></div>

    <footer>
        <p>ESP32-S3 CCTV Hub | Raspberry Pi 5 | Last update: <span id="last-update">--:--:--</span></p>
    </footer>

    <script>
        const cameras = {{ cameras|tojson }};
        const gridEl = document.getElementById('cameras');
        const cameraCountEl = document.getElementById('camera-count');
        const lastUpdateEl = document.getElementById('last-update');

        // Initialize camera cards
        cameras.forEach(cam => {
            const card = document.createElement('div');
            card.className = 'cam';
            card.id = 'cam-' + cam.name;
            card.innerHTML = `
                <div class="cam-header">
                    <h3>${cam.name}</h3>
                    <div class="cam-status idle" id="status-${cam.name}">
                        <span id="status-text-${cam.name}">Loading...</span>
                    </div>
                </div>
                <div class="stream-container">
                    <img src="/stream/${cam.name}" alt="${cam.name} stream" onerror="handleImageError(this)">
                    <div class="loading">Connecting...</div>
                </div>
                <div class="cam-info">
                    <div class="info-item">
                        <div class="info-label">IP Address</div>
                        <div class="info-value">${cam.ip}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Last Motion</div>
                        <div class="info-value" id="last-motion-${cam.name}">None</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Health</div>
                        <div class="info-value" id="health-${cam.name}">Unknown</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Uptime</div>
                        <div class="info-value" id="uptime-${cam.name}">--</div>
                    </div>
                </div>
            `;
            gridEl.appendChild(card);
        });

        function handleImageError(img) {
            img.style.display = 'none';
        }

        // Poll status for all cameras
        async function pollStatus() {
            const now = new Date();
            lastUpdateEl.textContent = now.toLocaleTimeString();

            let onlineCount = 0;
            let motionCount = 0;

            for (const cam of cameras) {
                try {
                    const response = await fetch('/status/' + cam.name);
                    const data = await response.json();

                    const cardEl = document.getElementById('cam-' + cam.name);
                    const statusEl = document.getElementById('status-' + cam.name);
                    const statusTextEl = document.getElementById('status-text-' + cam.name);
                    const healthEl = document.getElementById('health-' + cam.name);

                    if (data.health && data.health.online) {
                        onlineCount++;
                        cardEl.classList.remove('offline');

                        if (data.motion) {
                            motionCount++;
                            cardEl.classList.add('motion');
                            statusEl.className = 'cam-status motion';
                            statusTextEl.textContent = '⚠ Motion Detected';

                            if (data.last_motion) {
                                document.getElementById('last-motion-' + cam.name).textContent =
                                    new Date(data.last_motion * 1000).toLocaleTimeString();
                            }
                        } else {
                            cardEl.classList.remove('motion');
                            statusEl.className = 'cam-status idle';
                            statusTextEl.textContent = '✓ Idle';
                        }

                        healthEl.textContent = '✓ Online';
                        healthEl.style.color = '#4a9eff';
                    } else {
                        cardEl.classList.add('offline');
                        cardEl.classList.remove('motion');
                        statusEl.className = 'cam-status offline';
                        statusTextEl.textContent = '✗ Offline';
                        healthEl.textContent = '✗ Offline';
                        healthEl.style.color = '#999';
                    }
                } catch (error) {
                    console.error('Error polling ' + cam.name + ':', error);
                    const cardEl = document.getElementById('cam-' + cam.name);
                    cardEl.classList.add('offline');
                    document.getElementById('status-text-' + cam.name).textContent = '✗ Error';
                    document.getElementById('health-' + cam.name).textContent = '✗ Error';
                }
            }

            cameraCountEl.textContent = `${onlineCount}/${cameras.length} cameras online`;
            if (motionCount > 0) {
                cameraCountEl.textContent += ` | ${motionCount} detecting motion`;
            }
        }

        // Initial poll and setup interval
        pollStatus();
        setInterval(pollStatus, 2000);
    </script>
</body>
</html>
"""

# ------------------------------------------------------------------
# CONFIGURATION MANAGEMENT
# ------------------------------------------------------------------
def load_config() -> Dict:
    """Load configuration from file or create default."""
    global config

    config_path = Path(CONFIG_FILE)
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                logger.info(f"Loaded configuration from {CONFIG_FILE}")
                return config
        except Exception as e:
            logger.error(f"Error loading config: {e}. Using defaults.")

    # Create default config
    config = DEFAULT_CONFIG.copy()
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        logger.info(f"Created default configuration at {CONFIG_FILE}")
    except Exception as e:
        logger.error(f"Could not save default config: {e}")

    return config

def save_config():
    """Save current configuration to file."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        logger.info("Configuration saved")
    except Exception as e:
        logger.error(f"Error saving config: {e}")

# ------------------------------------------------------------------
# CAMERA STREAM GENERATOR
# ------------------------------------------------------------------
def gen_frames(camera_ip: str, camera_name: str):
    """Generate frames from camera MJPEG stream."""
    stream_url = f"http://{camera_ip}:8080/stream"
    cap = None
    retry_count = 0
    max_retries = 3

    while True:
        try:
            if cap is None or not cap.isOpened():
                logger.info(f"Connecting to {camera_name} at {stream_url}")
                cap = cv2.VideoCapture(stream_url)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize latency
                retry_count = 0

            ret, frame = cap.read()
            if not ret:
                retry_count += 1
                if retry_count > max_retries:
                    logger.warning(f"Failed to read from {camera_name}, reconnecting...")
                    if cap:
                        cap.release()
                    cap = None
                    time.sleep(1)
                continue

            # Resize if needed
            target_width = config['stream']['width']
            target_height = config['stream']['height']
            if frame.shape[1] != target_width or frame.shape[0] != target_height:
                frame = cv2.resize(frame, (target_width, target_height))

            # Encode frame
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), config['stream']['quality']]
            ret, buffer = cv2.imencode('.jpg', frame, encode_param)
            if not ret:
                continue

            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

        except Exception as e:
            logger.error(f"Error streaming {camera_name}: {e}")
            if cap:
                cap.release()
            cap = None
            time.sleep(2)

# ------------------------------------------------------------------
# MOTION DETECTION & RECORDING
# ------------------------------------------------------------------
def poll_motion():
    """Poll /motion endpoint from each camera and handle recording."""
    global motion_state

    recordings_dir = Path(config['recording']['recordings_dir'])
    recordings_dir.mkdir(exist_ok=True)

    while True:
        try:
            for cam in config['cameras']:
                if not cam.get('enabled', True):
                    continue

                name = cam['name']
                ip = cam['ip']

                try:
                    # Check motion endpoint
                    motion_url = f"http://{ip}:8080/motion"
                    response = requests.get(motion_url, timeout=config['polling']['timeout'])
                    data = response.json()

                    is_motion = data.get('motion', False)
                    prev_motion = motion_state.get(name, False)
                    motion_state[name] = is_motion

                    # Update last motion time
                    if is_motion:
                        if 'last_motion' not in camera_health[name]:
                            camera_health[name]['last_motion'] = time.time()
                            logger.info(f"Motion detected on {name}")
                        camera_health[name]['last_motion'] = time.time()

                    # Handle recording
                    if config['recording']['enabled'] and is_motion:
                        if config['recording']['snapshot_on_motion'] and not prev_motion:
                            # Save snapshot on motion start
                            snapshot_url = f"http://{ip}:8080/snapshot"
                            try:
                                img_data = requests.get(snapshot_url, timeout=config['polling']['timeout']).content
                                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                                filename = recordings_dir / f"{name}_{timestamp}.jpg"
                                filename.write_bytes(img_data)
                                logger.info(f"Saved snapshot: {filename}")
                            except Exception as e:
                                logger.error(f"Error saving snapshot for {name}: {e}")

                except requests.RequestException as e:
                    logger.debug(f"Could not poll motion from {name}: {e}")
                    motion_state[name] = False
                except Exception as e:
                    logger.error(f"Error polling {name}: {e}")
                    motion_state[name] = False

            time.sleep(config['polling']['motion_interval'])

        except Exception as e:
            logger.error(f"Error in motion polling thread: {e}")
            time.sleep(5)

def health_check():
    """Perform periodic health checks on all cameras."""
    global camera_health

    while True:
        try:
            for cam in config['cameras']:
                if not cam.get('enabled', True):
                    continue

                name = cam['name']
                ip = cam['ip']

                # Initialize health dict if needed
                if name not in camera_health:
                    camera_health[name] = {
                        'online': False,
                        'last_check': 0,
                        'uptime': 0
                    }

                try:
                    # Try to connect to stream
                    url = f"http://{ip}:8080/stream"
                    response = requests.get(url, timeout=config['polling']['timeout'], stream=True)

                    camera_health[name]['online'] = response.status_code == 200
                    camera_health[name]['last_check'] = time.time()

                    if camera_health[name]['online']:
                        camera_health[name]['uptime'] = camera_health[name].get('uptime', 0) + \
                                                         config['polling']['health_check_interval']

                except Exception:
                    camera_health[name]['online'] = False
                    camera_health[name]['uptime'] = 0

            time.sleep(config['polling']['health_check_interval'])

        except Exception as e:
            logger.error(f"Error in health check thread: {e}")
            time.sleep(10)

# ------------------------------------------------------------------
# FLASK ROUTES
# ------------------------------------------------------------------
@app.route('/')
def index():
    """Main dashboard page."""
    enabled_cameras = [c for c in config['cameras'] if c.get('enabled', True)]
    return render_template_string(DASHBOARD_TEMPLATE, cameras=enabled_cameras)

@app.route('/status/<name>')
def status(name):
    """Get status for a specific camera."""
    return jsonify({
        'motion': motion_state.get(name, False),
        'health': camera_health.get(name, {'online': False}),
        'last_motion': camera_health.get(name, {}).get('last_motion')
    })

@app.route('/stream/<name>')
def stream(name):
    """Proxy MJPEG stream from a specific camera."""
    cam = next((c for c in config['cameras'] if c['name'] == name), None)
    if not cam:
        return jsonify({'error': 'Camera not found'}), 404

    return Response(
        gen_frames(cam['ip'], name),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

@app.route('/api/cameras')
def api_cameras():
    """Get list of all cameras and their status."""
    cameras_data = []
    for cam in config['cameras']:
        if not cam.get('enabled', True):
            continue
        cameras_data.append({
            'name': cam['name'],
            'ip': cam['ip'],
            'motion': motion_state.get(cam['name'], False),
            'health': camera_health.get(cam['name'], {'online': False})
        })
    return jsonify(cameras_data)

@app.route('/api/health')
def api_health():
    """Health check endpoint for the hub itself."""
    return jsonify({
        'status': 'ok',
        'cameras_count': len([c for c in config['cameras'] if c.get('enabled', True)]),
        'cameras_online': sum(1 for h in camera_health.values() if h.get('online', False)),
        'recording_enabled': config['recording']['enabled']
    })

# ------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------
def main():
    """Initialize and start the CCTV hub."""
    logger.info("=" * 60)
    logger.info("ESP32-S3 CCTV Hub - Raspberry Pi 5")
    logger.info("=" * 60)

    # Load configuration
    load_config()

    # Initialize state
    for cam in config['cameras']:
        if cam.get('enabled', True):
            motion_state[cam['name']] = False
            camera_health[cam['name']] = {'online': False, 'last_check': 0}

    # Create recordings directory
    recordings_dir = Path(config['recording']['recordings_dir'])
    recordings_dir.mkdir(exist_ok=True)
    logger.info(f"Recordings directory: {recordings_dir.absolute()}")

    # Start background threads
    logger.info("Starting background threads...")

    motion_thread = threading.Thread(target=poll_motion, daemon=True, name="MotionPoller")
    motion_thread.start()
    logger.info("✓ Motion detection thread started")

    health_thread = threading.Thread(target=health_check, daemon=True, name="HealthCheck")
    health_thread.start()
    logger.info("✓ Health check thread started")

    # Start Flask server
    host = config['server']['host']
    port = config['server']['port']
    debug = config['server']['debug']

    logger.info("=" * 60)
    logger.info(f"Starting web server on http://{host}:{port}")
    logger.info(f"Dashboard: http://{host}:{port}/")
    logger.info(f"API Health: http://{host}:{port}/api/health")
    logger.info("=" * 60)

    try:
        app.run(host=host, port=port, debug=debug, threaded=True, use_reloader=False)
    except KeyboardInterrupt:
        logger.info("\nShutting down gracefully...")
    except Exception as e:
        logger.error(f"Server error: {e}")
        return 1

    return 0

if __name__ == '__main__':
    sys.exit(main())
