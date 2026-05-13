"""
INDI camera adapter (optional backend).

Controls cameras exposed as INDI CCD devices (e.g., ZWO, QHY, Canon via INDI
driver, etc.).

Prerequisites:
    pip install pyindi-client
    indiserver -v indi_asi_ccd   # or appropriate driver

Note: This is a structural scaffold.  Methods raise NotImplementedError until
the full PyIndi integration is implemented.
"""

from __future__ import annotations

import logging
from typing import Optional

from ..core.models import CameraState, CameraStatus
from .base_camera import BaseCamera, CameraError

log = logging.getLogger(__name__)

try:
    import PyIndi  # type: ignore[import-untyped]
    _PYINDI_AVAILABLE = True
except ImportError:
    _PYINDI_AVAILABLE = False


class INDICamera(BaseCamera):
    """INDI CCD/camera adapter."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 7624,
        driver_name: str = "ZWO CCD",
        name: str = "INDI Camera",
    ) -> None:
        super().__init__(name)
        self._host = host
        self._port = port
        self._driver_name = driver_name
        self._client: Optional[object] = None
        self._exposure = 60.0
        self._iso = 1600

    def connect(self) -> None:
        if not _PYINDI_AVAILABLE:
            raise CameraError(
                "PyIndi not installed.  Install pyindi-client to use this adapter."
            )
        # TODO: connect to INDI server and enable CCD driver
        raise NotImplementedError("Full INDI camera connection not yet implemented.")

    def disconnect(self) -> None:
        self._client = None
        self._status.state = CameraState.DISCONNECTED

    def get_status(self) -> CameraStatus:
        raise NotImplementedError("INDI camera get_status not yet implemented.")

    def set_exposure(self, seconds: float) -> None:
        self._exposure = seconds
        # TODO: set CCD_EXPOSURE property

    def set_iso(self, iso: int) -> None:
        self._iso = iso
        # TODO: set CCD_ISO property

    def capture(self, save_path: str) -> str:
        # TODO: set CCD_EXPOSURE_VALUE and wait for CCD_FRAME_TYPE BLOB
        raise NotImplementedError("INDI camera capture not yet implemented.")

    def abort(self) -> None:
        # TODO: set CCD_ABORT_EXPOSURE
        raise NotImplementedError("INDI camera abort not yet implemented.")
