"""
Simulated DSLR camera backend.

Generates synthetic star-field FITS images for development, testing, and
workflow demos without physical hardware.  Exposure timing is simulated in
real time (or accelerated with fast_mode=True).
"""

from __future__ import annotations

import logging
import math
import os
import random
import struct
import threading
import time
from typing import Optional

import numpy as np

from ..core.models import CameraState, CameraStatus
from .base_camera import BaseCamera, CameraError

log = logging.getLogger(__name__)


def _make_fits_header(
    width: int,
    height: int,
    exposure: float,
    iso: int,
    target: str = "",
) -> bytes:
    """Build a minimal FITS primary HDU header block (multiple of 2880 bytes)."""
    cards = [
        ("SIMPLE", "T", ""),
        ("BITPIX", "16", ""),
        ("NAXIS", "2", ""),
        (f"NAXIS1", str(width), ""),
        (f"NAXIS2", str(height), ""),
        ("BSCALE", "1", ""),
        ("BZERO", "32768", ""),
        ("EXPTIME", str(exposure), "Exposure time in seconds"),
        ("ISOSPEED", str(iso), "ISO sensitivity"),
        ("OBJECT", f"'{target[:68]}'", "Target name"),
        ("INSTRUME", "'Prudentia Sim'", "Simulated camera"),
        ("SWCREATE", "'Prudentia Observatory'", ""),
        ("END", "", ""),
    ]
    raw = b""
    for key, val, comm in cards:
        card = f"{key:<8}= {val:<20} / {comm}"
        raw += card[:80].encode("ascii").ljust(80)
    # Pad to 2880-byte block
    while len(raw) % 2880 != 0:
        raw += b" " * 80
    return raw


def _generate_star_field(
    width: int = 640,
    height: int = 480,
    num_stars: int = 150,
    sky_bg: int = 300,
    exposure: float = 60.0,
) -> np.ndarray:
    """Generate a synthetic 16-bit star-field array."""
    rng = np.random.default_rng()
    img = rng.normal(sky_bg, 15, (height, width)).astype(np.float32)
    scale = min(1.0, exposure / 30.0)

    for _ in range(num_stars):
        cx = rng.integers(10, width - 10)
        cy = rng.integers(10, height - 10)
        flux = rng.uniform(500, 60000) * scale
        sigma = rng.uniform(1.2, 2.5)
        for dy in range(-6, 7):
            for dx in range(-6, 7):
                py, px = cy + dy, cx + dx
                if 0 <= py < height and 0 <= px < width:
                    img[py, px] += flux * math.exp(-(dx**2 + dy**2) / (2 * sigma**2))

    return np.clip(img, 0, 65535).astype(np.uint16)


def _write_fits(path: str, data: np.ndarray, exposure: float, iso: int, target: str) -> None:
    """Write a minimal FITS file without requiring the full astropy.io.fits module."""
    h, w = data.shape
    header = _make_fits_header(w, h, exposure, iso, target)
    # FITS data is big-endian; subtract 32768 offset per BZERO convention
    fits_data = (data.astype(np.int32) - 32768).astype(np.int16)
    raw_data = fits_data.byteswap().tobytes()
    # Pad data to 2880-byte block
    remainder = len(raw_data) % 2880
    if remainder:
        raw_data += b"\x00" * (2880 - remainder)
    with open(path, "wb") as f:
        f.write(header)
        f.write(raw_data)


class SimulatorCamera(BaseCamera):
    """
    Software-simulated DSLR camera.

    Generates small synthetic FITS images.  Exposures are timed in real time
    by default; set fast_mode=True to complete instantly.
    """

    def __init__(
        self,
        name: str = "Simulator Camera",
        fast_mode: bool = False,
    ) -> None:
        super().__init__(name)
        self._fast_mode = fast_mode
        self._exposure = 60.0
        self._iso = 1600
        self._abort_event = threading.Event()
        self._capture_thread: Optional[threading.Thread] = None
        self._current_target: str = ""
        self._progress: float = 0.0

    # ─────────────────────────────────────────────────────────────────────────
    # Connection
    # ─────────────────────────────────────────────────────────────────────────

    def connect(self) -> None:
        self._status.state = CameraState.IDLE
        self._status.model = "Prudentia Simulated DSLR"
        self._status.current_iso = self._iso
        self._status.current_exposure_seconds = self._exposure
        self._status.image_format = "FITS"
        log.info("SimulatorCamera: connected")

    def disconnect(self) -> None:
        self.abort()
        self._status.state = CameraState.DISCONNECTED
        log.info("SimulatorCamera: disconnected")

    # ─────────────────────────────────────────────────────────────────────────
    # Status
    # ─────────────────────────────────────────────────────────────────────────

    def get_status(self) -> CameraStatus:
        self._status.progress_percent = self._progress
        self._status.current_exposure_seconds = self._exposure
        self._status.current_iso = self._iso
        return CameraStatus(
            state=self._status.state,
            model=self._status.model,
            current_iso=self._iso,
            current_exposure_seconds=self._exposure,
            aperture=self._status.aperture,
            image_format=self._status.image_format,
            progress_percent=self._progress,
            last_image_path=self._status.last_image_path,
            error_message=self._status.error_message,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Settings
    # ─────────────────────────────────────────────────────────────────────────

    def set_exposure(self, seconds: float) -> None:
        if seconds <= 0:
            raise CameraError("Exposure must be > 0 seconds.")
        self._exposure = seconds

    def set_iso(self, iso: int) -> None:
        self._iso = iso

    def set_target(self, target: str) -> None:
        self._current_target = target

    # ─────────────────────────────────────────────────────────────────────────
    # Capture
    # ─────────────────────────────────────────────────────────────────────────

    def capture(self, save_path: str) -> str:
        if not self.is_connected:
            raise CameraError("Camera is not connected.")
        if self._status.state == CameraState.EXPOSING:
            raise CameraError("Exposure already in progress.")

        os.makedirs(os.path.dirname(save_path) if os.path.dirname(save_path) else ".", exist_ok=True)

        self._abort_event.clear()
        self._status.state = CameraState.EXPOSING
        self._progress = 0.0

        duration = self._exposure if not self._fast_mode else 0.05
        steps = max(10, int(duration * 10))

        for i in range(steps):
            if self._abort_event.is_set():
                self._status.state = CameraState.IDLE
                self._progress = 0.0
                raise CameraError("Exposure aborted.")
            self._progress = (i + 1) / steps * 100.0
            time.sleep(duration / steps)

        self._status.state = CameraState.DOWNLOADING
        self._progress = 100.0

        # Generate and save the synthetic image
        data = _generate_star_field(exposure=self._exposure)
        if not save_path.lower().endswith(".fits"):
            save_path = save_path.rsplit(".", 1)[0] + ".fits"
        _write_fits(save_path, data, self._exposure, self._iso, self._current_target)

        self._status.state = CameraState.IDLE
        self._status.last_image_path = save_path
        self._progress = 0.0
        log.info("SimulatorCamera: captured %s", save_path)
        return save_path

    def abort(self) -> None:
        self._abort_event.set()
        self._status.state = CameraState.IDLE
        self._progress = 0.0
        log.info("SimulatorCamera: exposure aborted")
