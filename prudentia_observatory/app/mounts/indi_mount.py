"""
INDI mount adapter (optional backend).

INDI (Instrument-Neutral Distributed Interface) is an open-source astronomy
device protocol primarily used on Linux/macOS systems.  This adapter connects
to an INDI server using the PyIndi client library.

Installation:
    pip install pyindi-client   # or build from source

The INDI server must be running before connecting:
    indiserver -v indi_eqmod_telescope

Reference: https://indilib.org/

⚠ WARNING: This adapter commands real hardware.  Always test with the
SimulatorMount first.

Note: This module is a structural scaffold.  Full PyIndi integration requires
installing the indi Python bindings and running an INDI server.  The class
raises NotImplementedError for unimplemented methods so you can extend it
incrementally without breaking the application.
"""

from __future__ import annotations

import logging
from typing import Optional

from ..core.models import MountState, MountStatus, SkyCoordinate
from .base_mount import BaseMount, MountError

log = logging.getLogger(__name__)

try:
    import PyIndi  # type: ignore[import-untyped]
    _PYINDI_AVAILABLE = True
except ImportError:
    _PYINDI_AVAILABLE = False
    log.info("PyIndi not installed — INDI mount adapter disabled.")


class INDIMount(BaseMount):
    """
    INDI telescope mount adapter.

    Extend this class or implement the methods below once PyIndi is available
    in your environment.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 7624,
        driver_name: str = "EQMod Mount",
        name: str = "INDI Mount",
    ) -> None:
        super().__init__(name)
        if not _PYINDI_AVAILABLE:
            log.warning("PyIndi is not installed. INDIMount will not function.")
        self._host = host
        self._port = port
        self._driver_name = driver_name
        self._client: Optional[object] = None  # will be PyIndi.BaseClient instance

    def connect(self) -> None:
        if not _PYINDI_AVAILABLE:
            raise MountError("PyIndi is not installed. Install pyindi-client to use this adapter.")
        # TODO: implement full PyIndi connection sequence
        # client = PyIndi.BaseClient()
        # client.setServer(self._host, self._port)
        # client.connectServer()
        # client.connectDevice(self._driver_name)
        raise NotImplementedError("Full INDI mount connection not yet implemented.")

    def disconnect(self) -> None:
        if self._client is not None:
            # TODO: client.disconnectServer()
            self._client = None
        self._status.state = MountState.DISCONNECTED

    def get_status(self) -> MountStatus:
        # TODO: query COORD property for RA/DEC, TELESCOPE_TRACK_STATE, etc.
        raise NotImplementedError("INDI get_status not yet implemented.")

    def slew_to_radec(self, coord: SkyCoordinate, target_name: str = "") -> None:
        # TODO: set EQUATORIAL_EOD_COORD property
        raise NotImplementedError("INDI slew_to_radec not yet implemented.")

    def abort_slew(self) -> None:
        # TODO: set TELESCOPE_ABORT_MOTION property
        raise NotImplementedError("INDI abort_slew not yet implemented.")

    def set_tracking(self, enabled: bool) -> None:
        # TODO: set TELESCOPE_TRACK_STATE property
        raise NotImplementedError("INDI set_tracking not yet implemented.")

    def sync_to_radec(self, coord: SkyCoordinate) -> None:
        # TODO: set ON_COORD_SET to SYNC, then set EQUATORIAL_EOD_COORD
        raise NotImplementedError("INDI sync_to_radec not yet implemented.")

    def park(self) -> None:
        # TODO: set TELESCOPE_PARK property
        raise NotImplementedError("INDI park not yet implemented.")

    def unpark(self) -> None:
        # TODO: set TELESCOPE_PARK property to UNPARK
        raise NotImplementedError("INDI unpark not yet implemented.")
