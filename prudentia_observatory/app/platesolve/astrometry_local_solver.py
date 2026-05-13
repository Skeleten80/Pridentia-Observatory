"""
Local Astrometry.net command-line plate solver.

Wraps the `solve-field` command-line tool from the astrometry.net package.

Installation:
    macOS:   brew install astrometry-net
    Ubuntu:  apt install astrometry.net astrometry-data-tycho2
    Arch:    pacman -S astrometry.net

Index files must be downloaded separately.
See: http://data.astrometry.net/

⚠ Solving can take 10–120 seconds depending on the image size, index files,
and whether a hint coordinate is supplied.
"""

from __future__ import annotations

import glob
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from ..core.models import SkyCoordinate, SolveResult
from .base_solver import BaseSolver, SolverError

log = logging.getLogger(__name__)


def _find_solve_field() -> Optional[str]:
    """Return the path to the solve-field executable, or None if not found."""
    return shutil.which("solve-field")


def _parse_wcs_fits(wcs_path: str) -> Optional[dict]:
    """Parse the WCS FITS header written by solve-field for RA/Dec/rotation."""
    try:
        with open(wcs_path, "rb") as f:
            raw = f.read(2880 * 10).decode("ascii", errors="replace")
    except OSError:
        return None

    result: dict = {}
    for i in range(0, len(raw), 80):
        card = raw[i:i + 80]
        if card.startswith("CRVAL1"):
            result["ra"] = float(card.split("=")[1].split("/")[0].strip())
        elif card.startswith("CRVAL2"):
            result["dec"] = float(card.split("=")[1].split("/")[0].strip())
        elif card.startswith("CROTA2"):
            result["rotation"] = float(card.split("=")[1].split("/")[0].strip())
        elif card.startswith("PIXSCALE") or card.startswith("SCALE"):
            try:
                result["pixel_scale"] = float(card.split("=")[1].split("/")[0].strip())
            except (ValueError, IndexError):
                pass
    return result if "ra" in result and "dec" in result else None


class AstrometryLocalSolver(BaseSolver):
    """
    Plate solver using the local Astrometry.net `solve-field` binary.

    Requires astrometry.net and appropriate index files to be installed.
    """

    def __init__(
        self,
        solve_field_path: Optional[str] = None,
        extra_args: Optional[list[str]] = None,
        name: str = "Astrometry.net Local",
        timeout_seconds: float = 120.0,
    ) -> None:
        super().__init__(name)
        self._solve_field = solve_field_path or _find_solve_field()
        self._extra_args = extra_args or []
        self._timeout = timeout_seconds

    def solve(
        self,
        image_path: str,
        hint_coord: Optional[SkyCoordinate] = None,
        hint_radius_degrees: float = 15.0,
        downsample: int = 2,
    ) -> SolveResult:
        if not self._solve_field:
            return SolveResult(
                success=False,
                message="solve-field not found. Install astrometry.net.",
            )

        if not os.path.isfile(image_path):
            return SolveResult(success=False, message=f"Image not found: {image_path}")

        with tempfile.TemporaryDirectory(prefix="prudentia_solve_") as tmpdir:
            cmd = [
                self._solve_field,
                "--no-plots",
                "--overwrite",
                "--dir", tmpdir,
                "--downsample", str(downsample),
                "--new-fits", "none",
                *self._extra_args,
            ]
            if hint_coord:
                cmd += [
                    "--ra", str(hint_coord.ra_degrees),
                    "--dec", str(hint_coord.dec_degrees),
                    "--radius", str(hint_radius_degrees),
                ]
            cmd.append(image_path)

            log.info("AstrometryLocalSolver: running %s", " ".join(cmd))
            import time
            t0 = time.monotonic()
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self._timeout,
                )
            except subprocess.TimeoutExpired:
                return SolveResult(
                    success=False,
                    message=f"Solve timed out after {self._timeout:.0f}s.",
                )
            elapsed = time.monotonic() - t0

            stem = Path(image_path).stem
            wcs_path = os.path.join(tmpdir, f"{stem}.wcs")

            if proc.returncode != 0 or not os.path.exists(wcs_path):
                log.warning("AstrometryLocalSolver: solve failed\n%s", proc.stderr[-1000:])
                return SolveResult(
                    success=False,
                    message="solve-field reported no match.",
                    solver_time_seconds=elapsed,
                )

            parsed = _parse_wcs_fits(wcs_path)
            if not parsed:
                return SolveResult(
                    success=False,
                    message="Could not parse WCS FITS output.",
                    solver_time_seconds=elapsed,
                )

            ra_hours = parsed["ra"] / 15.0
            dec_degrees = parsed["dec"]
            result = SolveResult(
                success=True,
                ra_hours=ra_hours,
                dec_degrees=dec_degrees,
                rotation_degrees=parsed.get("rotation", 0.0),
                pixel_scale_arcsec=parsed.get("pixel_scale", 0.0),
                solver_time_seconds=elapsed,
                message="Solved by local Astrometry.net",
            )
            if hint_coord:
                ra_e, dec_e, total = self.pointing_error(result, hint_coord)
                result.ra_error_arcmin = ra_e
                result.dec_error_arcmin = dec_e
                result.total_error_arcmin = total

            log.info(
                "AstrometryLocalSolver: solved RA=%.4fh Dec=%+.3f° in %.1fs",
                ra_hours, dec_degrees, elapsed,
            )
            return result
