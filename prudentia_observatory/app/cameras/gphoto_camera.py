"""
gPhoto2 / libgphoto2 camera adapter.

Supports Canon, Nikon, Sony, and other USB-connected DSLRs via the
open-source gPhoto2 library.

Prerequisites:
    macOS:   brew install libgphoto2 gphoto2
    Linux:   apt install gphoto2 libgphoto2-dev
    Python:  pip install gphoto2

⚠ WARNING: This adapter communicates with real camera hardware.

Note: This is a structural scaffold.  Full implementation requires the
gphoto2 Python bindings.  Methods raise NotImplementedError until implemented.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from ..core.models import CameraState, CameraStatus
from .base_camera import BaseCamera, CameraError

log = logging.getLogger(__name__)

try:
    import gphoto2 as gp  # type: ignore[import-untyped]
    _GPHOTO2_AVAILABLE = True
except ImportError:
    _GPHOTO2_AVAILABLE = False
    log.info("gphoto2 Python module not installed — gPhoto2 camera adapter disabled.")


class GPhoto2Camera(BaseCamera):
    """
    DSLR camera adapter using libgphoto2.

    Extend and implement the methods below once gphoto2 is installed.
    """

    def __init__(self, name: str = "gPhoto2 Camera") -> None:
        super().__init__(name)
        self._camera: Optional[object] = None  # gp.Camera instance
        self._context: Optional[object] = None  # gp.Context instance
        self._exposure = 60.0
        self._iso = 1600

    def connect(self) -> None:
        if not _GPHOTO2_AVAILABLE:
            raise CameraError(
                "gphoto2 Python module not installed.  Run: pip install gphoto2"
            )
        # TODO: implement full gPhoto2 connection
        # self._context = gp.Context()
        # self._camera = gp.Camera()
        # self._camera.init(self._context)
        raise NotImplementedError("Full gPhoto2 connection not yet implemented.")

    def disconnect(self) -> None:
        if self._camera is not None:
            # TODO: self._camera.exit(self._context)
            self._camera = None
        self._status.state = CameraState.DISCONNECTED

    def get_status(self) -> CameraStatus:
        # TODO: read camera config for current ISO/shutter speed
        raise NotImplementedError("gPhoto2 get_status not yet implemented.")

    def set_exposure(self, seconds: float) -> None:
        self._exposure = seconds
        # TODO: set shutterspeed in camera config

    def set_iso(self, iso: int) -> None:
        self._iso = iso
        # TODO: set iso in camera config

    def capture(self, save_path: str) -> str:
        if not _GPHOTO2_AVAILABLE:
            raise CameraError("gphoto2 not installed.")
        # TODO:
        # file_path = self._camera.capture(gp.GP_CAPTURE_IMAGE, self._context)
        # camera_file = self._camera.file_get(...)
        # gp.check_result(gp.gp_file_save(camera_file, save_path))
        raise NotImplementedError("gPhoto2 capture not yet implemented.")

    def abort(self) -> None:
        # gPhoto2 does not support mid-exposure abort on most cameras.
        log.warning("GPhoto2Camera: abort not supported on most cameras.")
