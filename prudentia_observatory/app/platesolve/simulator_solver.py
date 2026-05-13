"""
Simulated plate solver backend.

Returns a synthetic SolveResult for development and testing.  By default it
succeeds immediately with a small random pointing error, simulating a real
plate solve that found a match close to the hint coordinates.
"""

from __future__ import annotations

import logging
import math
import random
import time
from typing import Optional

from ..core.models import SkyCoordinate, SolveResult
from .base_solver import BaseSolver

log = logging.getLogger(__name__)

_DEFAULT_ERROR_ARCMIN = 3.0   # typical pointing error before sync
_DEFAULT_SOLVE_TIME_S = 2.5   # simulated solve duration


class SimulatorSolver(BaseSolver):
    """Software-simulated plate solver for development and testing."""

    def __init__(
        self,
        name: str = "Simulator Solver",
        always_succeed: bool = True,
        simulated_error_arcmin: float = _DEFAULT_ERROR_ARCMIN,
        simulated_solve_time_s: float = _DEFAULT_SOLVE_TIME_S,
    ) -> None:
        super().__init__(name)
        self._always_succeed = always_succeed
        self._error_arcmin = simulated_error_arcmin
        self._solve_time = simulated_solve_time_s

    def solve(
        self,
        image_path: str,
        hint_coord: Optional[SkyCoordinate] = None,
        hint_radius_degrees: float = 15.0,
        downsample: int = 2,
    ) -> SolveResult:
        log.info("SimulatorSolver: solving %s", image_path)
        time.sleep(self._solve_time)

        if not self._always_succeed:
            if random.random() < 0.15:
                log.warning("SimulatorSolver: simulated solve failure")
                return SolveResult(
                    success=False,
                    message="Simulated solve failure (15% failure rate active).",
                    solver_time_seconds=self._solve_time,
                )

        # Base position: use hint if given, otherwise a default sky position
        if hint_coord:
            base_ra = hint_coord.ra_hours
            base_dec = hint_coord.dec_degrees
        else:
            base_ra = 5.588  # near Orion Nebula
            base_dec = -5.39

        # Add a small random pointing error
        angle = random.uniform(0, 2 * math.pi)
        err_mag = random.gauss(self._error_arcmin, self._error_arcmin * 0.3)
        err_mag = max(0.1, err_mag)
        ra_err = err_mag * math.cos(angle) / 60 / 15  # convert arcmin → hours
        dec_err = err_mag * math.sin(angle) / 60

        solved_ra = base_ra + ra_err
        solved_dec = base_dec + dec_err

        result = SolveResult(
            success=True,
            ra_hours=solved_ra % 24,
            dec_degrees=max(-90.0, min(90.0, solved_dec)),
            rotation_degrees=random.uniform(-5, 5),
            pixel_scale_arcsec=random.uniform(0.8, 2.5),
            ra_error_arcmin=ra_err * 15 * 60,
            dec_error_arcmin=dec_err * 60,
            total_error_arcmin=err_mag,
            solver_time_seconds=self._solve_time,
            message="Simulated solve successful.",
        )
        log.info(
            "SimulatorSolver: solved RA=%.4fh Dec=%+.3f° error=%.1f'",
            result.ra_hours,
            result.dec_degrees,
            result.total_error_arcmin,
        )
        return result
