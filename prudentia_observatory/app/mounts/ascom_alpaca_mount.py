"""
ASCOM Alpaca HTTP mount adapter.

Communicates with any ASCOM Alpaca-compatible telescope driver running locally
or on the network.  Alpaca is a REST/JSON protocol that works cross-platform —
no COM registration or Windows-only dependencies required.

To use:
  1. Install the ASCOM Platform (Windows) or Alpaca on any OS.
  2. Start the Alpaca Remote Server for your mount driver.
  3. Set host/port/device_number to match the server configuration.

Reference: https://ascom-standards.org/AlpacaDeveloper/Index.htm

⚠ WARNING: This adapter commands real hardware.  Incorrect coordinates or
ignored limits can damage your mount, OTA, or accessories.  Always test with
the simulator backend first.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

import requests

from ..core.models import MountState, MountStatus, SkyCoordinate
from .base_mount import BaseMount, MountError

log = logging.getLogger(__name__)

_TIMEOUT = 5.0  # HTTP request timeout in seconds


class ASCOMAlpacaMount(BaseMount):
    """
    ASCOM Alpaca telescope adapter.

    Implements the Alpaca /api/v1/telescope/{device_number}/* endpoints.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 11111,
        device_number: int = 0,
        name: str = "ASCOM Alpaca Mount",
    ) -> None:
        super().__init__(name)
        self._base = f"http://{host}:{port}/api/v1/telescope/{device_number}"
        self._client_id = 1
        self._txid = 0
        self._lock = threading.Lock()

    # ─────────────────────────────────────────────────────────────────────────
    # Internal HTTP helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _next_txid(self) -> int:
        with self._lock:
            self._txid += 1
            return self._txid

    def _get(self, endpoint: str) -> dict:
        url = f"{self._base}/{endpoint}"
        params = {"ClientID": self._client_id, "ClientTransactionID": self._next_txid()}
        try:
            resp = requests.get(url, params=params, timeout=_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            err = data.get("ErrorNumber", 0)
            if err != 0:
                raise MountError(f"Alpaca error {err}: {data.get('ErrorMessage', '')}")
            return data
        except requests.RequestException as exc:
            raise MountError(f"HTTP error talking to Alpaca mount: {exc}") from exc

    def _put(self, endpoint: str, **kwargs: object) -> dict:
        url = f"{self._base}/{endpoint}"
        data = {
            "ClientID": self._client_id,
            "ClientTransactionID": self._next_txid(),
        }
        data.update({k: v for k, v in kwargs.items()})
        try:
            resp = requests.put(url, data=data, timeout=_TIMEOUT)
            resp.raise_for_status()
            result = resp.json()
            err = result.get("ErrorNumber", 0)
            if err != 0:
                raise MountError(f"Alpaca error {err}: {result.get('ErrorMessage', '')}")
            return result
        except requests.RequestException as exc:
            raise MountError(f"HTTP error talking to Alpaca mount: {exc}") from exc

    # ─────────────────────────────────────────────────────────────────────────
    # Connection
    # ─────────────────────────────────────────────────────────────────────────

    def connect(self) -> None:
        self._put("connected", Connected=True)
        self._status.state = MountState.CONNECTED
        log.info("ASCOMAlpacaMount: connected to %s", self._base)

    def disconnect(self) -> None:
        try:
            self._put("connected", Connected=False)
        except MountError:
            pass
        self._status.state = MountState.DISCONNECTED
        log.info("ASCOMAlpacaMount: disconnected")

    # ─────────────────────────────────────────────────────────────────────────
    # Status
    # ─────────────────────────────────────────────────────────────────────────

    def get_status(self) -> MountStatus:
        try:
            ra = self._get("rightascension")["Value"]
            dec = self._get("declination")["Value"]
            tracking = self._get("tracking")["Value"]
            slewing = self._get("slewing")["Value"]
            at_park = self._get("atpark")["Value"]

            if slewing:
                state = MountState.SLEWING
            elif at_park:
                state = MountState.PARKED
            elif tracking:
                state = MountState.TRACKING
            else:
                state = MountState.IDLE

            self._status = MountStatus(
                state=state,
                ra_hours=ra,
                dec_degrees=dec,
                is_tracking=tracking,
                is_parked=at_park,
            )
        except MountError as exc:
            self._status.error_message = str(exc)
            self._status.state = MountState.ERROR
        return self._status

    # ─────────────────────────────────────────────────────────────────────────
    # Motion
    # ─────────────────────────────────────────────────────────────────────────

    def slew_to_radec(self, coord: SkyCoordinate, target_name: str = "") -> None:
        log.info("ASCOMAlpacaMount: slewing to %s (%s)", target_name, coord)
        # SlewToCoordinatesAsync does not block
        self._put(
            "slewtocoordinatesasync",
            RightAscension=coord.ra_hours,
            Declination=coord.dec_degrees,
        )
        self._status.state = MountState.SLEWING

    def abort_slew(self) -> None:
        try:
            self._put("abortslew")
        except MountError:
            pass
        self._status.state = MountState.IDLE
        log.warning("ASCOMAlpacaMount: slew aborted")

    def set_tracking(self, enabled: bool) -> None:
        self._put("tracking", Tracking=enabled)
        self._status.is_tracking = enabled

    def sync_to_radec(self, coord: SkyCoordinate) -> None:
        self._put(
            "synctocoodinates",
            RightAscension=coord.ra_hours,
            Declination=coord.dec_degrees,
        )
        log.info("ASCOMAlpacaMount: synced to %s", coord)

    def park(self) -> None:
        self._put("park")
        self._status.state = MountState.PARKED
        self._status.is_parked = True

    def unpark(self) -> None:
        self._put("unpark")
        self._status.state = MountState.IDLE
        self._status.is_parked = False
