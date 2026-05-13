"""Abstract base class for plate-solving backends."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional

from ..core.models import SkyCoordinate, SolveResult

log = logging.getLogger(__name__)


class SolverError(Exception):
    """Raised when a plate-solving operation fails."""


class BaseSolver(ABC):
    """
    Abstract interface for plate-solving backends.

    Implementations receive a path to an image file (FITS, JPEG, PNG) and
    optionally a hint RA/Dec and field-of-view radius, then return a SolveResult.
    """

    def __init__(self, name: str = "Solver") -> None:
        self.name = name

    @abstractmethod
    def solve(
        self,
        image_path: str,
        hint_coord: Optional[SkyCoordinate] = None,
        hint_radius_degrees: float = 15.0,
        downsample: int = 2,
    ) -> SolveResult:
        """
        Attempt to plate-solve the image at image_path.

        Parameters
        ----------
        image_path:
            Path to the image file to solve.
        hint_coord:
            Optional approximate RA/Dec to speed up the blind-solve search.
        hint_radius_degrees:
            Search radius around hint_coord (ignored if hint_coord is None).
        downsample:
            Downsample factor for the solver (1 = full resolution, 2 = half).

        Returns
        -------
        SolveResult with success=True if the solve succeeded, False otherwise.
        """
        ...

    def pointing_error(
        self,
        solved: SolveResult,
        target: SkyCoordinate,
    ) -> tuple[float, float, float]:
        """
        Compute (ra_error_arcmin, dec_error_arcmin, total_error_arcmin) between
        the solved position and the intended target.
        """
        import math
        ra_err = (solved.ra_hours - target.ra_hours) * 60 * 15  # arcmin
        dec_err = (solved.dec_degrees - target.dec_degrees) * 60  # arcmin
        total = math.sqrt(ra_err**2 + dec_err**2)
        return ra_err, dec_err, total

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"
