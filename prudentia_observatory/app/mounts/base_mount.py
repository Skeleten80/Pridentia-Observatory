"""
Abstract base class for all telescope mount backends.

Real hardware adapters (ASCOM Alpaca, INDI) subclass this and implement
every abstract method.  The simulator_mount.py provides a working reference
implementation for development and testing without physical hardware.

⚠ WARNING: Real telescope movement can damage equipment if commanded to invalid
positions.  Always implement and respect horizon/meridian limits.  Never slew
to the Sun without a certified solar filter and explicit Solar Safety Mode.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional

from ..core.models import MountState, MountStatus, SkyCoordinate

log = logging.getLogger(__name__)


class MountError(Exception):
    """Raised when a mount operation fails."""


class BaseMount(ABC):
    """
    Abstract interface for telescope mount control.

    Implementations must be thread-safe because the UI calls methods from both
    the main Qt thread and background worker threads.
    """

    def __init__(self, name: str = "Mount") -> None:
        self.name = name
        self._status = MountStatus()

    # ─────────────────────────────────────────────────────────────────────────
    # Connection lifecycle
    # ─────────────────────────────────────────────────────────────────────────

    @abstractmethod
    def connect(self) -> None:
        """Connect to the mount hardware/driver."""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the mount hardware/driver."""
        ...

    @property
    def is_connected(self) -> bool:
        return self._status.state not in (MountState.DISCONNECTED, MountState.ERROR)

    # ─────────────────────────────────────────────────────────────────────────
    # Status
    # ─────────────────────────────────────────────────────────────────────────

    @abstractmethod
    def get_status(self) -> MountStatus:
        """Return current mount state including position and tracking flag."""
        ...

    # ─────────────────────────────────────────────────────────────────────────
    # Motion control
    # ─────────────────────────────────────────────────────────────────────────

    @abstractmethod
    def slew_to_radec(self, coord: SkyCoordinate, target_name: str = "") -> None:
        """
        Slew the mount to the given equatorial coordinates.

        Implementations should validate that the target is above the configured
        horizon limit before issuing the slew command.
        """
        ...

    @abstractmethod
    def abort_slew(self) -> None:
        """Immediately stop all mount motion. Must be instantaneous."""
        ...

    @abstractmethod
    def set_tracking(self, enabled: bool) -> None:
        """Enable or disable sidereal tracking."""
        ...

    @abstractmethod
    def sync_to_radec(self, coord: SkyCoordinate) -> None:
        """
        Sync the mount model to the given coordinates (plate-solve correction).

        This adjusts the mount's internal pointing model to treat the current
        position as the given RA/Dec.
        """
        ...

    @abstractmethod
    def park(self) -> None:
        """Move the mount to its park position."""
        ...

    @abstractmethod
    def unpark(self) -> None:
        """Wake the mount from the parked state."""
        ...

    # ─────────────────────────────────────────────────────────────────────────
    # Safety helpers — implementations may override
    # ─────────────────────────────────────────────────────────────────────────

    def is_safe_target(
        self,
        coord: SkyCoordinate,
        min_altitude_degrees: float = 5.0,
    ) -> tuple[bool, str]:
        """
        Return (is_safe, reason_string).

        Base implementation always returns True; real adapters should check
        horizon and meridian limits using the observer location.
        """
        return True, "OK"

    def emergency_stop(self) -> None:
        """
        Alias for abort_slew() with extra logging.

        The UI emergency-stop button always calls this method.
        """
        log.warning("EMERGENCY STOP issued on %s", self.name)
        self.abort_slew()

    # ─────────────────────────────────────────────────────────────────────────
    # String representation
    # ─────────────────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"
