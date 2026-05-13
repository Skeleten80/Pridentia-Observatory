"""Unit tests for the simulated camera backend."""

from __future__ import annotations

import os
import tempfile

import pytest

from prudentia_observatory.app.cameras.base_camera import CameraError
from prudentia_observatory.app.cameras.simulator_camera import SimulatorCamera
from prudentia_observatory.app.core.models import CameraState


@pytest.fixture
def camera(tmp_path) -> SimulatorCamera:
    return SimulatorCamera(fast_mode=True)


@pytest.fixture
def connected_camera(camera) -> SimulatorCamera:
    camera.connect()
    return camera


class TestConnection:
    def test_initial_disconnected(self, camera):
        assert not camera.is_connected

    def test_connect(self, camera):
        camera.connect()
        assert camera.is_connected

    def test_disconnect(self, connected_camera):
        connected_camera.disconnect()
        assert not connected_camera.is_connected

    def test_status_after_connect(self, connected_camera):
        st = connected_camera.get_status()
        assert st.state == CameraState.IDLE
        assert "Simulated" in st.model or "Prudentia" in st.model


class TestSettings:
    def test_set_exposure(self, connected_camera):
        connected_camera.set_exposure(120.0)
        st = connected_camera.get_status()
        assert st.current_exposure_seconds == 120.0

    def test_set_iso(self, connected_camera):
        connected_camera.set_iso(3200)
        st = connected_camera.get_status()
        assert st.current_iso == 3200

    def test_set_exposure_invalid(self, connected_camera):
        with pytest.raises(CameraError):
            connected_camera.set_exposure(-1.0)

    def test_set_exposure_zero(self, connected_camera):
        with pytest.raises(CameraError):
            connected_camera.set_exposure(0.0)


class TestCapture:
    def test_capture_creates_file(self, connected_camera, tmp_path):
        save_path = str(tmp_path / "test_frame.fits")
        result_path = connected_camera.capture(save_path)
        assert os.path.exists(result_path)
        assert os.path.getsize(result_path) > 0

    def test_capture_fits_header(self, connected_camera, tmp_path):
        """Verify the FITS file has a valid SIMPLE=T header."""
        save_path = str(tmp_path / "test_header.fits")
        connected_camera.capture(save_path)
        with open(save_path, "rb") as f:
            header = f.read(80).decode("ascii", errors="replace")
        assert "SIMPLE" in header

    def test_capture_requires_connection(self, camera, tmp_path):
        save_path = str(tmp_path / "no_connect.fits")
        with pytest.raises(CameraError):
            camera.capture(save_path)

    def test_capture_updates_last_image(self, connected_camera, tmp_path):
        save_path = str(tmp_path / "last.fits")
        connected_camera.capture(save_path)
        st = connected_camera.get_status()
        assert st.last_image_path != ""

    def test_abort_capture(self, tmp_path):
        # Use slow camera for abort test
        slow_cam = SimulatorCamera(fast_mode=False)
        slow_cam.connect()
        slow_cam.set_exposure(10.0)

        import threading
        result = {}

        def _capture():
            try:
                p = slow_cam.capture(str(tmp_path / "abort_test.fits"))
                result["path"] = p
            except CameraError as e:
                result["error"] = str(e)

        t = threading.Thread(target=_capture, daemon=True)
        t.start()

        import time
        time.sleep(0.3)
        slow_cam.abort()
        t.join(timeout=5.0)

        assert "error" in result
        assert "abort" in result["error"].lower()


class TestSequentialCaptures:
    def test_multiple_captures(self, connected_camera, tmp_path):
        paths = []
        for i in range(3):
            path = connected_camera.capture(str(tmp_path / f"frame_{i:04d}.fits"))
            paths.append(path)
        assert len(paths) == 3
        for p in paths:
            assert os.path.exists(p)
