"""
Remote Astrometry.net API plate solver adapter.

Submits images to the online Astrometry.net service at nova.astrometry.net.
Requires an API key: sign up free at https://nova.astrometry.net/

Internet access required. Solves take 20–300 seconds depending on server load.

Reference: http://nova.astrometry.net/api_help
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Optional

import requests

from ..core.models import SkyCoordinate, SolveResult
from .base_solver import BaseSolver, SolverError

log = logging.getLogger(__name__)

_API_URL = "http://nova.astrometry.net/api/"
_POLL_INTERVAL_S = 10.0
_DEFAULT_TIMEOUT_S = 300.0


class AstrometryRemoteSolver(BaseSolver):
    """
    Plate solver using the nova.astrometry.net online service.

    Usage:
        solver = AstrometryRemoteSolver(api_key="your_key_here")
        result = solver.solve("/path/to/image.fits", hint_coord=coord)
    """

    def __init__(
        self,
        api_key: str = "",
        name: str = "Astrometry.net Remote",
        timeout_seconds: float = _DEFAULT_TIMEOUT_S,
    ) -> None:
        super().__init__(name)
        self._api_key = api_key or os.environ.get("ASTROMETRY_API_KEY", "")
        self._timeout = timeout_seconds
        self._session: Optional[str] = None

    # ─────────────────────────────────────────────────────────────────────────
    # Public
    # ─────────────────────────────────────────────────────────────────────────

    def solve(
        self,
        image_path: str,
        hint_coord: Optional[SkyCoordinate] = None,
        hint_radius_degrees: float = 15.0,
        downsample: int = 2,
    ) -> SolveResult:
        if not self._api_key:
            return SolveResult(
                success=False,
                message="No Astrometry.net API key configured.",
            )
        if not os.path.isfile(image_path):
            return SolveResult(success=False, message=f"Image not found: {image_path}")

        t0 = time.monotonic()
        try:
            session = self._login()
            sub_id = self._upload(session, image_path, hint_coord, hint_radius_degrees)
            job_id = self._wait_for_job(sub_id)
            if job_id is None:
                return SolveResult(
                    success=False,
                    message="Astrometry.net: submission did not produce a job.",
                    solver_time_seconds=time.monotonic() - t0,
                )
            result = self._fetch_result(job_id, t0)
            return result
        except (requests.RequestException, SolverError) as exc:
            return SolveResult(
                success=False,
                message=str(exc),
                solver_time_seconds=time.monotonic() - t0,
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _login(self) -> str:
        resp = requests.post(
            f"{_API_URL}login",
            data={"request-json": json.dumps({"apikey": self._api_key})},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "success":
            raise SolverError(f"Astrometry.net login failed: {data.get('errormessage','')}")
        return data["session"]

    def _upload(
        self,
        session: str,
        image_path: str,
        hint_coord: Optional[SkyCoordinate],
        radius_deg: float,
    ) -> int:
        args: dict = {"session": session, "publicly_visible": "n", "allow_modifications": "n"}
        if hint_coord:
            args["center_ra"] = hint_coord.ra_degrees
            args["center_dec"] = hint_coord.dec_degrees
            args["radius"] = radius_deg

        with open(image_path, "rb") as f:
            resp = requests.post(
                f"{_API_URL}upload",
                files={"file": f},
                data={"request-json": json.dumps(args)},
                timeout=60,
            )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "success":
            raise SolverError(f"Astrometry.net upload failed: {data.get('errormessage','')}")
        return data["subid"]

    def _wait_for_job(self, sub_id: int) -> Optional[int]:
        deadline = time.monotonic() + self._timeout
        while time.monotonic() < deadline:
            resp = requests.get(
                f"{_API_URL}submissions/{sub_id}", timeout=30
            )
            resp.raise_for_status()
            data = resp.json()
            jobs = data.get("jobs", [])
            if jobs and jobs[0] is not None:
                return jobs[0]
            time.sleep(_POLL_INTERVAL_S)
        return None

    def _fetch_result(self, job_id: int, t0: float) -> SolveResult:
        deadline = time.monotonic() + self._timeout
        while time.monotonic() < deadline:
            resp = requests.get(f"{_API_URL}jobs/{job_id}", timeout=30)
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status", "")
            if status == "success":
                info_resp = requests.get(f"{_API_URL}jobs/{job_id}/calibration/", timeout=30)
                info_resp.raise_for_status()
                cal = info_resp.json()
                return SolveResult(
                    success=True,
                    ra_hours=cal.get("ra", 0.0) / 15.0,
                    dec_degrees=cal.get("dec", 0.0),
                    rotation_degrees=cal.get("orientation", 0.0),
                    pixel_scale_arcsec=cal.get("pixscale", 0.0),
                    solver_time_seconds=time.monotonic() - t0,
                    message="Solved by nova.astrometry.net",
                )
            if status == "failure":
                return SolveResult(
                    success=False,
                    message="Astrometry.net reported solve failure.",
                    solver_time_seconds=time.monotonic() - t0,
                )
            time.sleep(_POLL_INTERVAL_S)
        return SolveResult(
            success=False,
            message=f"Astrometry.net solve timed out after {self._timeout:.0f}s.",
            solver_time_seconds=time.monotonic() - t0,
        )
