"""Tests for the ESP32-S3 camera streaming server."""

import sys
import types
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Bootstrap MicroPython stubs so ``import main`` works on desktop Python.
# ---------------------------------------------------------------------------

_camera = types.ModuleType("camera")
_camera.JPEG = 0
_camera.FRAME_QVGA = 0
_camera.init = MagicMock()
_camera.deinit = MagicMock()
_camera.capture = MagicMock(return_value=b"\xff\xd8fake-jpeg")
_camera.framesize = MagicMock()
_camera.quality = MagicMock()
_camera.flip = MagicMock()
_camera.mirror = MagicMock()
sys.modules["camera"] = _camera

_network = types.ModuleType("network")
_network.STA_IF = 0
_wlan_instance = MagicMock()
_wlan_instance.active.return_value = True
_wlan_instance.isconnected.return_value = True
_wlan_instance.ifconfig.return_value = (
    "192.168.1.100",
    "255.255.255.0",
    "192.168.1.1",
    "8.8.8.8",
)
_network.WLAN = MagicMock(return_value=_wlan_instance)
sys.modules["network"] = _network

# Remove cached config to ensure main.py falls back to defaults
sys.modules.pop("config", None)

import main  # noqa: E402, I001


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestConnectWifi:
    """Tests for connect_wifi()."""

    def test_returns_ip_when_already_connected(self):
        _wlan_instance.isconnected.return_value = True
        _wlan_instance.ifconfig.return_value = ("10.0.0.5", "", "", "")
        ip = main.connect_wifi("ssid", "pass")
        assert ip == "10.0.0.5"

    def test_raises_on_timeout(self):
        _wlan_instance.isconnected.return_value = False
        _wlan_instance.active.return_value = False

        with (
            patch.object(main.time, "time") as mock_time,
            patch.object(main.time, "sleep"),
        ):
            # First call sets deadline, subsequent calls exceed it
            mock_time.side_effect = [0, 0, 100]
            with pytest.raises(OSError, match="timed out"):
                main.connect_wifi("bad_ssid", "bad_pass")

    def test_connects_successfully(self):
        call_count = 0

        def fake_isconnected():
            nonlocal call_count
            call_count += 1
            return call_count > 2

        _wlan_instance.isconnected.side_effect = fake_isconnected
        _wlan_instance.active.return_value = False
        _wlan_instance.ifconfig.return_value = ("192.168.0.42", "", "", "")

        with (
            patch.object(main.time, "time", return_value=0),
            patch.object(main.time, "sleep"),
        ):
            ip = main.connect_wifi("my_ssid", "my_pass")
        assert ip == "192.168.0.42"
        _wlan_instance.isconnected.side_effect = None
        _wlan_instance.isconnected.return_value = True


class TestConfigureCamera:
    """Tests for configure_camera()."""

    def test_calls_init_with_jpeg(self):
        _camera.deinit.reset_mock()
        _camera.init.reset_mock()
        main.configure_camera()
        _camera.init.assert_called_once_with(0, format=_camera.JPEG)
        _camera.framesize.assert_called_with(_camera.FRAME_QVGA)
        _camera.quality.assert_called_with(10)

    def test_handles_deinit_exception(self):
        _camera.deinit.side_effect = RuntimeError("not initialized")
        main.configure_camera()  # should not raise
        _camera.deinit.side_effect = None


class TestStreamFrames:
    """Tests for stream_frames()."""

    def test_writes_http_headers(self):
        mock_client = MagicMock()
        _camera.capture.return_value = b"\xff\xd8jpeg-data"
        call_count = 0

        def write_side_effect(_data):
            nonlocal call_count
            call_count += 1
            if call_count > 10:
                raise OSError("client disconnected")

        mock_client.write.side_effect = write_side_effect

        with pytest.raises(OSError), patch.object(main.time, "sleep"):
            main.stream_frames(mock_client)

        # Check HTTP status line was written first
        first_call = mock_client.write.call_args_list[0]
        assert b"HTTP/1.1 200 OK" in first_call[0][0]

    def test_breaks_after_max_retries(self):
        mock_client = MagicMock()
        _camera.capture.return_value = None  # always fail

        with patch.object(main.time, "sleep"):
            main.stream_frames(mock_client)

        # Should have written headers then stopped
        _camera.capture.return_value = b"\xff\xd8fake-jpeg"


class TestStartServer:
    """Tests for start_server()."""

    def test_binds_and_listens(self):
        mock_sock = MagicMock()
        mock_client = MagicMock()
        mock_sock.accept.side_effect = [
            (mock_client, ("127.0.0.1", 9999)),
            KeyboardInterrupt,
        ]
        addr_info = [
            (None, None, None, None, ("0.0.0.0", 8080)),
        ]

        with (
            patch.object(
                main.socket,
                "getaddrinfo",
                return_value=addr_info,
            ),
            patch.object(
                main.socket,
                "socket",
                return_value=mock_sock,
            ),
            patch.object(
                main,
                "stream_frames",
                side_effect=OSError("disconnect"),
            ),
            pytest.raises(KeyboardInterrupt),
        ):
            main.start_server()

        mock_sock.bind.assert_called_once()
        mock_sock.listen.assert_called_once_with(2)
        mock_client.close.assert_called_once()


class TestMain:
    """Tests for main()."""

    def test_calls_functions_in_order(self):
        with (
            patch.object(main, "connect_wifi", return_value="10.0.0.1") as mock_wifi,
            patch.object(main, "configure_camera") as mock_cam,
            patch.object(main, "start_server") as mock_server,
        ):
            main.main()

        mock_wifi.assert_called_once()
        mock_cam.assert_called_once()
        mock_server.assert_called_once()
