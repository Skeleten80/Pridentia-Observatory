"""
Folder-watch / import camera backend.

For users who shoot tethered using vendor software (Canon EOS Utility,
Nikon Camera Control Pro, Capture One, etc.) that saves files to a local
directory.  Prudentia watches the folder and imports images as they appear.

Supports RAW (CR2, CR3, NEF, ARW, ORF, RW2, DNG) and JPEG files.
"""

from __future__ import annotations

import logging
import os
import time
import threading
from pathlib import Path
from typing import Optional, Callable

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent

from ..core.models import CameraState, CameraStatus
from .base_camera import BaseCamera, CameraError

log = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {
    ".cr2", ".cr3", ".nef", ".arw", ".orf", ".rw2", ".dng",
    ".jpg", ".jpeg", ".fits", ".tiff", ".tif",
}


class _ImageArrivalHandler(FileSystemEventHandler):
    """Watchdog handler that calls a callback when a new image file appears."""

    def __init__(self, callback: Callable[[str], None]) -> None:
        super().__init__()
        self._callback = callback

    def on_created(self, event: FileCreatedEvent) -> None:
        if not event.is_directory:
            ext = Path(event.src_path).suffix.lower()
            if ext in _SUPPORTED_EXTENSIONS:
                log.info("FolderWatchCamera: new image detected: %s", event.src_path)
                self._callback(event.src_path)


class FolderWatchCamera(BaseCamera):
    """
    Watches a directory for newly-saved images from tethered shooting software.

    Usage:
        cam = FolderWatchCamera(watch_dir="/path/to/tethered/folder")
        cam.connect()
        # vendor software saves files → cam.capture() returns the next arrived file
    """

    def __init__(
        self,
        watch_dir: Optional[str] = None,
        timeout_seconds: float = 120.0,
        name: str = "Folder Watch Camera",
    ) -> None:
        super().__init__(name)
        self._watch_dir = watch_dir or os.path.expanduser("~/Pictures/Tethered")
        self._timeout = timeout_seconds
        self._observer: Optional[Observer] = None
        self._pending_image: Optional[str] = None
        self._image_event = threading.Event()
        self._abort_event = threading.Event()
        self._exposure = 60.0
        self._iso = 1600

    def connect(self) -> None:
        os.makedirs(self._watch_dir, exist_ok=True)
        handler = _ImageArrivalHandler(self._on_image_arrived)
        self._observer = Observer()
        self._observer.schedule(handler, self._watch_dir, recursive=False)
        self._observer.start()
        self._status.state = CameraState.IDLE
        self._status.model = f"Folder Watch → {self._watch_dir}"
        log.info("FolderWatchCamera: watching %s", self._watch_dir)

    def disconnect(self) -> None:
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
        self._status.state = CameraState.DISCONNECTED

    def get_status(self) -> CameraStatus:
        return CameraStatus(
            state=self._status.state,
            model=self._status.model,
            current_iso=self._iso,
            current_exposure_seconds=self._exposure,
            last_image_path=self._status.last_image_path,
        )

    def set_exposure(self, seconds: float) -> None:
        self._exposure = seconds  # informational only — vendor software controls shutter

    def set_iso(self, iso: int) -> None:
        self._iso = iso  # informational only

    def capture(self, save_path: str) -> str:
        """
        Wait for the next image to appear in the watch directory.

        The vendor tethering software must be configured to save files there.
        Returns the path of the detected image (not save_path, which is ignored).
        """
        if not self.is_connected:
            raise CameraError("Camera is not connected.")
        self._abort_event.clear()
        self._image_event.clear()
        self._pending_image = None
        self._status.state = CameraState.EXPOSING

        log.info("FolderWatchCamera: waiting for image in %s", self._watch_dir)
        arrived = self._image_event.wait(timeout=self._timeout)

        if self._abort_event.is_set():
            self._status.state = CameraState.IDLE
            raise CameraError("Capture aborted.")

        if not arrived or self._pending_image is None:
            self._status.state = CameraState.IDLE
            raise CameraError(
                f"No image appeared in {self._timeout:.0f}s."
                "  Check that your tethering software is saving to: "
                f"{self._watch_dir}"
            )

        self._status.state = CameraState.IDLE
        self._status.last_image_path = self._pending_image
        return self._pending_image

    def abort(self) -> None:
        self._abort_event.set()
        self._image_event.set()  # unblock the wait
        self._status.state = CameraState.IDLE

    # ─────────────────────────────────────────────────────────────────────────
    # Internal
    # ─────────────────────────────────────────────────────────────────────────

    def _on_image_arrived(self, path: str) -> None:
        # Wait briefly for the file to finish writing before reporting it
        time.sleep(0.5)
        self._pending_image = path
        self._status.state = CameraState.DOWNLOADING
        self._image_event.set()
