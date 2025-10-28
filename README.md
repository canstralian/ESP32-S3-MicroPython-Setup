# ESP32-S3 Camera Streaming with MicroPython and Thonny

This guide walks you through preparing an ESP32-S3 board with an onboard camera to run MicroPython firmware that includes the
camera driver, then deploying a streaming server script with Thonny. The instructions reflect the community-maintained
firmware builds that currently provide camera support for the ESP32-S3.

## Prerequisites

* ESP32-S3 development board with an integrated camera module (e.g., ESP32-S3-EYE, ESP32-S3 CAM, or equivalent)
* USB data cable
* Python 3.9 or later on your workstation
* `pip` and `esptool.py`
* Thonny IDE 4.1 or later
* A Wi-Fi network (2.4 GHz) that the board can join

## 1. Install `esptool.py`

Install the flashing utility globally or in a virtual environment:

```sh
pip install --upgrade esptool
```

> **Tip:** On Linux and macOS you may need to prepend `python3 -m` if `pip` is not mapped to Python 3.

## 2. Download a Camera-Enabled MicroPython Firmware

The upstream MicroPython builds do not yet ship with ESP32-S3 camera support. Use a community firmware image that bundles the
`esp32-camera` driver, such as the [Loboris MicroPython fork](https://github.com/loboris/MicroPython_ESP32_psRAM_LoBo) or the
[Silabs/Unicore community builds](https://github.com/silabs-MicroPython/micropython-esp32-s3/releases). Download the latest
`.bin` image that explicitly mentions **ESP32-S3** and **camera support**.

Save the firmware file to a known location on your workstation. The examples below assume the file is named
`micropython-esp32s3-camera.bin`.

## 3. Put the ESP32-S3 into Bootloader Mode

1. Connect the board to your computer with the USB cable.
2. Hold the **BOOT** (or `IO0`) button.
3. Press and release the **RESET** button.
4. Release the **BOOT** button.

## 4. Erase and Flash the Firmware

Identify the serial port the board exposes:

* Windows: `COMx` (e.g., `COM5`)
* Linux: `/dev/ttyUSB0` or `/dev/ttyACM0`
* macOS: `/dev/tty.usbserial-XXXX`

Erase the flash (recommended when moving between firmware families):

```sh
esptool.py --chip esp32s3 --port <PORT> erase_flash
```

Flash the camera-enabled firmware:

```sh
esptool.py --chip esp32s3 --port <PORT> --baud 460800 \
  write_flash -z 0x0000 micropython-esp32s3-camera.bin
```

Replace `<PORT>` with the path from the previous step.

## 5. Confirm the Firmware Booted

Open a serial terminal (Thonny, PuTTY, `screen`, etc.) at **115200 baud**. You should see the MicroPython REPL prompt (`>>>`).
If you receive a `ModuleNotFoundError` for `camera` in later steps, the firmware you flashed does not include the driver—repeat
step 2 with a confirmed camera build.

## 6. Prepare Thonny for the ESP32-S3

1. Launch Thonny.
2. Open **Tools ▸ Options ▸ Interpreter**.
3. Select **MicroPython (ESP32)** as the interpreter.
4. Choose the same serial port you used for `esptool.py`.
5. Click **OK**, then open the REPL (bottom shell) to verify you can run simple commands like `import machine`.

## 7. Upload the Camera Streaming Script

1. Copy the `main.py` script from this repository (or create a new file in Thonny with the contents below).
2. Update the Wi-Fi SSID and password constants so the board can join your network.
3. In Thonny, choose **File ▸ Save As…**, pick **MicroPython device**, and save the script as `main.py`.
4. Press **Ctrl+D** or reset the board; MicroPython will automatically execute `main.py` on boot.

## Example: MJPEG Streaming Server (`main.py`)

```python
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
    station = network.WLAN(network.STA_IF)
    if not station.active():
        station.active(True)
    if not station.isconnected():
        station.connect(ssid, password)
        while not station.isconnected():
            time.sleep(0.2)


def configure_camera() -> None:
    camera.deinit()
    camera.init(0, format=camera.JPEG)
    camera.framesize(camera.FRAME_QVGA)
    camera.quality(10)
    camera.flip(0)
    camera.mirror(0)


def stream_frames(client: socket.socket) -> None:
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
    connect_wifi(WIFI_SSID, WIFI_PASSWORD)
    configure_camera()
    start_server()


if __name__ == "__main__":
    try:
        main()
    finally:
        camera.deinit()
```

Visit `http://<board-ip-address>:8080/` from a browser on the same network to view the MJPEG stream.

## Deployment Considerations

* **Power:** Camera streaming draws more current than simple GPIO workloads. Use a stable 5 V supply capable of at least 1 A.
* **Heat:** Long streaming sessions can warm the ESP32-S3. Provide airflow or attach a small heatsink if you enclose the board.
* **Security:** The sample server is unencrypted and unauthenticated. Place the board on a trusted LAN or extend the script with
  HTTPS termination on an upstream proxy and HTTP basic authentication or API tokens.
* **Resilience:** For remote deployments, consider adding a watchdog timer and persisting Wi-Fi credentials in NVS to ensure the
  device recovers gracefully after brownouts.

## Troubleshooting

| Symptom | Cause | Resolution |
| --- | --- | --- |
| `ModuleNotFoundError: camera` | Firmware lacks camera driver | Flash a community build that bundles `esp32-camera` support. |
| Continuous reboot cycle | Brownout due to insufficient power | Use a shorter cable and a power source rated for 1 A or more. |
| Stream is blank or green | Sensor not initialized | Call `camera.deinit()` before `camera.init()` and double-check pin mapping if using a custom board. |
| Browser does not show video | Network isolation or firewall | Ensure the viewing device is on the same subnet and that port 8080 is open. |

## Next Steps

* Add authentication and TLS (e.g., by proxying through Nginx or ESP32 SSL sockets).
* Capture still images on demand by exposing additional HTTP endpoints.
* Integrate with Home Assistant by wrapping the MJPEG stream in a camera entity.
