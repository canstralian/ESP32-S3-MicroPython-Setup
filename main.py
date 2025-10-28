"""ESP32-S3 camera streaming server script for MicroPython."""

import camera
import network
import socket
import time

WIFI_SSID = "YOUR_WIFI_SSID"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"
BOUNDARY = b"--frame"
CONTENT_TYPE = b"multipart/x-mixed-replace; boundary=" + BOUNDARY
CAPTURE_INTERVAL = 0.2


def connect_wifi(ssid: str, password: str) -> None:
    """Connect to the configured Wi-Fi network."""
    station = network.WLAN(network.STA_IF)
    if not station.active():
        station.active(True)
    if not station.isconnected():
        station.connect(ssid, password)
        while not station.isconnected():
            time.sleep(0.2)


def configure_camera() -> None:
    """Initialise the camera sensor with JPEG output."""
    camera.deinit()
    camera.init(0, format=camera.JPEG)
    camera.framesize(camera.FRAME_QVGA)
    camera.quality(10)
    camera.flip(0)
    camera.mirror(0)


def stream_frames(client: socket.socket) -> None:
    """Send an endless MJPEG stream to the connected client."""
    client.write(b"HTTP/1.1 200 OK\r\n")
    client.write(b"Content-Type: " + CONTENT_TYPE + b"\r\n\r\n")
    while True:
        frame = camera.capture()
        if frame is None:
            continue
        client.write(BOUNDARY + b"\r\n")
        client.write(b"Content-Type: image/jpeg\r\n")
        client.write(b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n")
        client.write(frame)
        client.write(b"\r\n")
        time.sleep(CAPTURE_INTERVAL)


def start_server(host: str = "0.0.0.0", port: int = 8080) -> None:
    """Start a blocking socket server that streams camera frames."""
    address_info = socket.getaddrinfo(host, port)[0][-1]
    server_socket = socket.socket()
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(address_info)
    server_socket.listen(2)
    try:
        while True:
            client, _ = server_socket.accept()
            try:
                stream_frames(client)
            except OSError:
                pass
            finally:
                client.close()
    finally:
        server_socket.close()


def main() -> None:
    """Entry point: connect to Wi-Fi, configure the camera, and start streaming."""
    connect_wifi(WIFI_SSID, WIFI_PASSWORD)
    configure_camera()
    start_server()


if __name__ == "__main__":
    try:
        main()
    finally:
        camera.deinit()
