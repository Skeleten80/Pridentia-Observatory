"""
Abstract base class for all DSLR/camera backends.

Real hardware adapters (gPhoto2, INDI) subclass this and implement every
abstract method.  The simulator_camera.py provides a working reference
implementation for development and testing without real hardware.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional

from ..core.models import CameraState, CameraStatus

log = logging.getLogger(__name__)


class CameraError(Exception):
    """Raised when a camera operation fails."""


class BaseCamera(ABC):
    """
    Abstract interface for camera control.

    Implementations should be thread-safe as exposure capture runs in a
    background thread.
    """

    def __init__(self, name: str = "Camera") -> None:
        self.name = name
        self._status = CameraStatus()

    # ─────────────────────────────────────────────────────────────────────────
    # Connection lifecycle
    # ─────────────────────────────────────────────────────────────────────────

    @abstractmethod
    def connect(self) -> None:
        """Detect and connect to the camera."""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Release the camera and clean up resources."""
        ...

    @property
    def is_connected(self) -> bool:
        return self._status.state not in (CameraState.DISCONNECTED, CameraState.ERROR)

    # ─────────────────────────────────────────────────────────────────────────
    # Status
    # ─────────────────────────────────────────────────────────────────────────

    @abstractmethod
    def get_status(self) -> CameraStatus:
        """Return current camera status including state and settings."""
        ...

    # ─────────────────────────────────────────────────────────────────────────
    # Settings
    # ─────────────────────────────────────────────────────────────────────────

    @abstractmethod
    def set_exposure(self, seconds: float) -> None:
        """Set exposure duration in seconds."""
        ...

    @abstractmethod
    def set_iso(self, iso: int) -> None:
        """Set ISO sensitivity."""
        ...

    def set_aperture(self, aperture: str) -> None:
        """
        Set aperture f-stop (e.g. '5.6').
        Default implementation is a no-op for cameras where aperture is fixed.
        """
        log.debug("%s: aperture control not supported", self.name)

    # ─────────────────────────────────────────────────────────────────────────
    # Capture
    # ─────────────────────────────────────────────────────────────────────────

    @abstractmethod
    def capture(self, save_path: str) -> str:
        """
        Trigger one exposure and download the image.

        Blocks until the image is downloaded.  Returns the path of the saved file.
        """
        ...

    @abstractmethod
    def abort(self) -> None:
        """Abort the current exposure immediately."""
        ...

    # ─────────────────────────────────────────────────────────────────────────
    # String representation
    # ─────────────────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"
