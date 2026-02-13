"""ESP32-S3 camera streaming server script for MicroPython."""

import socket
import time

import camera
import network

try:
    from config import CAPTURE_INTERVAL, SERVER_PORT, WIFI_PASSWORD, WIFI_SSID
except ImportError:
    WIFI_SSID = "YOUR_WIFI_SSID"
    WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"
    SERVER_PORT = 8080
    CAPTURE_INTERVAL = 0.2

BOUNDARY = b"--frame"
CONTENT_TYPE = b"multipart/x-mixed-replace; boundary=--frame"
WIFI_CONNECT_TIMEOUT = 15
MAX_CAPTURE_RETRIES = 5


def connect_wifi(ssid: str, password: str) -> str:
    """Connect to the configured Wi-Fi network.

    Returns the assigned IP address.
    Raises OSError if connection times out.
    """
    station = network.WLAN(network.STA_IF)
    if not station.active():
        station.active(True)
    if station.isconnected():
        ip_address = station.ifconfig()[0]
        print("Already connected, IP:", ip_address)
        return ip_address

    print("Connecting to Wi-Fi:", ssid)
    station.connect(ssid, password)
    deadline = time.time() + WIFI_CONNECT_TIMEOUT
    while not station.isconnected():
        if time.time() > deadline:
            station.active(False)
            msg = "Wi-Fi connection timed out after {}s"
            raise OSError(msg.format(WIFI_CONNECT_TIMEOUT))
        time.sleep(0.5)

    ip_address = station.ifconfig()[0]
    print("Connected, IP:", ip_address)
    return ip_address


def configure_camera() -> None:
    """Initialise the camera sensor with JPEG output."""
    try:  # noqa: SIM105
        camera.deinit()
    except Exception:  # noqa: BLE001
        pass
    camera.init(0, format=camera.JPEG)
    camera.framesize(camera.FRAME_QVGA)
    camera.quality(10)
    camera.flip(0)
    camera.mirror(0)
    print("Camera initialised")


def stream_frames(client: socket.socket) -> None:
    """Send an endless MJPEG stream to the connected client."""
    client.write(b"HTTP/1.1 200 OK\r\n")
    client.write(b"Content-Type: " + CONTENT_TYPE + b"\r\n")
    client.write(b"Connection: close\r\n\r\n")
    retries = 0
    while True:
        frame = camera.capture()
        if frame is None:
            retries += 1
            if retries >= MAX_CAPTURE_RETRIES:
                print(
                    "Camera capture failed after",
                    MAX_CAPTURE_RETRIES,
                    "retries",
                )
                break
            time.sleep(0.1)
            continue
        retries = 0
        client.write(BOUNDARY + b"\r\n")
        client.write(b"Content-Type: image/jpeg\r\n")
        client.write(b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n")
        client.write(frame)
        client.write(b"\r\n")
        time.sleep(CAPTURE_INTERVAL)


def start_server(host: str = "0.0.0.0", port: int = SERVER_PORT) -> None:
    """Start a blocking socket server that streams camera frames."""
    address_info = socket.getaddrinfo(host, port)[0][-1]
    server_socket = socket.socket()
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(address_info)
    server_socket.listen(2)
    print("Streaming server started on port", port)
    try:
        while True:
            client, addr = server_socket.accept()
            print("Client connected:", addr)
            try:
                stream_frames(client)
            except OSError as e:
                print("Client disconnected:", e)
            finally:
                client.close()
    finally:
        server_socket.close()


def main() -> None:
    """Entry point: connect Wi-Fi, configure camera, start streaming."""
    ip_address = connect_wifi(WIFI_SSID, WIFI_PASSWORD)
    configure_camera()
    print("View stream at http://{}:{}/".format(ip_address, SERVER_PORT))
    start_server()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        try:  # noqa: SIM105
            camera.deinit()
        except Exception:  # noqa: BLE001
            pass
