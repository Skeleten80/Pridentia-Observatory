"""
Simulated telescope mount backend.

Provides a fully functional mount that slews in software, suitable for
development, unit testing, and UI demos without physical hardware.

Slewing is animated over a configurable duration using a background thread.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from typing import Optional

from ..core.models import MountState, MountStatus, SkyCoordinate
from .base_mount import BaseMount, MountError

log = logging.getLogger(__name__)

_DEFAULT_SLEW_RATE_DEG_S = 3.0   # degrees per second
_TRACKING_NOISE_ARCSEC = 2.0     # RMS tracking error simulation


class SimulatorMount(BaseMount):
    """
    Software-simulated telescope mount.

    Thread safety: all state is protected by a threading.Lock.
    """

    def __init__(
        self,
        name: str = "Simulator Mount",
        slew_rate_deg_s: float = _DEFAULT_SLEW_RATE_DEG_S,
    ) -> None:
        super().__init__(name)
        self._slew_rate = slew_rate_deg_s
        self._lock = threading.Lock()
        self._slew_thread: Optional[threading.Thread] = None
        self._abort_event = threading.Event()

        # Initial parked position
        self._ra_hours: float = 0.0
        self._dec_degrees: float = 90.0  # pointing at the pole
        self._is_tracking: bool = False
        self._is_parked: bool = True

    # ─────────────────────────────────────────────────────────────────────────
    # Connection
    # ─────────────────────────────────────────────────────────────────────────

    def connect(self) -> None:
        with self._lock:
            if self._status.state == MountState.CONNECTED:
                return
            log.info("SimulatorMount: connecting")
            self._status.state = MountState.PARKED
            self._status.is_parked = True
        log.info("SimulatorMount: connected")

    def disconnect(self) -> None:
        self.abort_slew()
        with self._lock:
            self._status.state = MountState.DISCONNECTED
            self._is_tracking = False
        log.info("SimulatorMount: disconnected")

    # ─────────────────────────────────────────────────────────────────────────
    # Status
    # ─────────────────────────────────────────────────────────────────────────

    def get_status(self) -> MountStatus:
        with self._lock:
            # Add tiny noise to RA if tracking (simulates mount drift)
            ra = self._ra_hours
            dec = self._dec_degrees
            if self._is_tracking and self._status.state == MountState.TRACKING:
                import random
                noise = random.gauss(0, _TRACKING_NOISE_ARCSEC / 3600 / 15)
                ra += noise

            self._status.ra_hours = ra
            self._status.dec_degrees = dec
            self._status.is_tracking = self._is_tracking
            self._status.is_parked = self._is_parked
            return MountStatus(
                state=self._status.state,
                ra_hours=ra,
                dec_degrees=dec,
                altitude_degrees=self._status.altitude_degrees,
                azimuth_degrees=self._status.azimuth_degrees,
                is_tracking=self._is_tracking,
                is_parked=self._is_parked,
                slew_rate=self._slew_rate,
                pier_side=self._status.pier_side,
                error_message=self._status.error_message,
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Motion
    # ─────────────────────────────────────────────────────────────────────────

    def slew_to_radec(self, coord: SkyCoordinate, target_name: str = "") -> None:
        if not self.is_connected:
            raise MountError("Mount is not connected.")
        if self._is_parked:
            raise MountError("Mount is parked; unpark before slewing.")

        self.abort_slew()
        self._abort_event.clear()

        log.info("SimulatorMount: slewing to %s (%s)", target_name or "target", coord)

        def _slew() -> None:
            with self._lock:
                self._status.state = MountState.SLEWING
                start_ra = self._ra_hours
                start_dec = self._dec_degrees

            ra_diff = coord.ra_hours - start_ra
            # Normalise RA difference to [-12, 12]
            if ra_diff > 12:
                ra_diff -= 24
            if ra_diff < -12:
                ra_diff += 24

            dec_diff = coord.dec_degrees - start_dec
            dist_deg = math.sqrt((ra_diff * 15) ** 2 + dec_diff ** 2)
            duration = max(1.0, dist_deg / self._slew_rate)

            steps = max(20, int(duration * 20))
            for i in range(steps + 1):
                if self._abort_event.is_set():
                    log.warning("SimulatorMount: slew aborted")
                    with self._lock:
                        self._status.state = MountState.IDLE
                    return
                t = i / steps
                cur_ra = start_ra + ra_diff * t
                cur_dec = start_dec + dec_diff * t
                with self._lock:
                    self._ra_hours = cur_ra % 24
                    self._dec_degrees = max(-90.0, min(90.0, cur_dec))
                time.sleep(duration / steps)

            with self._lock:
                self._ra_hours = coord.ra_hours % 24
                self._dec_degrees = max(-90.0, min(90.0, coord.dec_degrees))
                self._is_tracking = True
                self._status.state = MountState.TRACKING
                log.info("SimulatorMount: slew complete, tracking")

        self._slew_thread = threading.Thread(target=_slew, daemon=True, name="mount-slew")
        self._slew_thread.start()

    def abort_slew(self) -> None:
        self._abort_event.set()
        if self._slew_thread and self._slew_thread.is_alive():
            self._slew_thread.join(timeout=2.0)
        with self._lock:
            if self._status.state == MountState.SLEWING:
                self._status.state = MountState.IDLE

    def set_tracking(self, enabled: bool) -> None:
        if not self.is_connected:
            raise MountError("Mount is not connected.")
        with self._lock:
            self._is_tracking = enabled
            if enabled:
                self._status.state = MountState.TRACKING
            else:
                self._status.state = MountState.IDLE
        log.info("SimulatorMount: tracking %s", "ON" if enabled else "OFF")

    def sync_to_radec(self, coord: SkyCoordinate) -> None:
        if not self.is_connected:
            raise MountError("Mount is not connected.")
        with self._lock:
            self._ra_hours = coord.ra_hours
            self._dec_degrees = coord.dec_degrees
        log.info("SimulatorMount: synced to %s", coord)

    def park(self) -> None:
        self.abort_slew()
        with self._lock:
            self._ra_hours = 0.0
            self._dec_degrees = 90.0
            self._is_tracking = False
            self._is_parked = True
            self._status.state = MountState.PARKED
        log.info("SimulatorMount: parked")

    def unpark(self) -> None:
        with self._lock:
            if not self.is_connected:
                raise MountError("Mount is not connected.")
            self._is_parked = False
            self._status.state = MountState.IDLE
        log.info("SimulatorMount: unparked")
