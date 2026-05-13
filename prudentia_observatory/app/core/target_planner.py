"""
Target planner — builds and scores a list of the best imaging targets for tonight.

Filters objects by altitude, moon separation, magnitude, and object type, then
ranks them by imaging score.  Works entirely offline using the local database
and Astropy ephemerides.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional

from .astronomy_engine import compute_target_info
from .models import CelestialObject, ObserverLocation, ObjectType, TargetInfo

log = logging.getLogger(__name__)


@dataclass
class PlannerFilters:
    min_altitude_degrees: float = 20.0
    max_magnitude: Optional[float] = None
    min_moon_separation_degrees: float = 20.0
    object_types: list[str] = field(default_factory=list)
    only_visible_now: bool = True


@dataclass
class PlannedTarget:
    info: TargetInfo
    imaging_window_minutes: float = 0.0
    recommended_exposure_note: str = ""


def _exposure_note(obj: CelestialObject) -> str:
    """Return a brief imaging recommendation based on object type."""
    notes = {
        ObjectType.GALAXY: "Try 120–300 s subs at ISO 800–1600.",
        ObjectType.NEBULA: "60–300 s subs; consider narrowband filters.",
        ObjectType.PLANETARY_NEBULA: "30–120 s at high focal length.",
        ObjectType.OPEN_CLUSTER: "30–60 s subs, ISO 400–800.",
        ObjectType.GLOBULAR_CLUSTER: "30–120 s subs at ISO 400–800.",
        ObjectType.SUPERNOVA_REMNANT: "Long subs with Ha filter, 180–600 s.",
        ObjectType.DOUBLE_STAR: "Short subs 1–10 s.",
        ObjectType.PLANET: "Video/lucky-imaging, 1–30 ms per frame.",
        ObjectType.MOON: "1/250 s–1 s; use a neutral-density filter.",
        ObjectType.SUN: "⚠ ONLY with certified solar filter. 1/1000 s.",
        ObjectType.STAR: "Short subs 5–30 s.",
    }
    return notes.get(obj.object_type, "Experiment with 60–180 s subs.")


def _imaging_window(info: TargetInfo, min_alt: float = 20.0) -> float:
    """Estimate minutes the object stays above min_alt tonight (rough scan)."""
    if info.rise_time is None or info.set_time is None:
        if info.altaz.altitude_degrees >= min_alt:
            return 240.0  # circumpolar
        return 0.0
    dt = (info.set_time - info.rise_time).total_seconds() / 60.0
    return max(0.0, dt)


class TargetPlanner:
    """
    Plans tonight's best imaging targets.

    Usage:
        planner = TargetPlanner(location, objects)
        best = planner.plan(filters)
    """

    def __init__(
        self,
        location: ObserverLocation,
        objects: list[CelestialObject],
    ) -> None:
        self._location = location
        self._objects = objects

    def plan(
        self,
        filters: Optional[PlannerFilters] = None,
        dt: Optional[datetime] = None,
        max_results: int = 50,
    ) -> list[PlannedTarget]:
        """Return a ranked list of the best imaging targets matching the filters."""
        if filters is None:
            filters = PlannerFilters()
        if dt is None:
            dt = datetime.now(tz=timezone.utc)

        planned: list[PlannedTarget] = []

        for obj in self._objects:
            # Skip the Sun unless explicitly requested
            if obj.object_type == ObjectType.SUN:
                continue

            # Apply type filter
            if filters.object_types and obj.object_type.value not in filters.object_types:
                continue

            # Apply magnitude filter
            if filters.max_magnitude is not None and obj.magnitude is not None:
                if obj.magnitude > filters.max_magnitude:
                    continue

            try:
                info = compute_target_info(obj, self._location, dt)
            except Exception:
                log.debug("Skipping %s — coordinate error", obj.display_name)
                continue

            if filters.only_visible_now and not info.altaz.is_above_horizon(
                filters.min_altitude_degrees
            ):
                continue

            if info.moon_separation_degrees < filters.min_moon_separation_degrees:
                continue

            window = _imaging_window(info, filters.min_altitude_degrees)
            note = _exposure_note(obj)

            planned.append(PlannedTarget(info=info, imaging_window_minutes=window,
                                         recommended_exposure_note=note))

        # Sort by imaging score descending
        planned.sort(key=lambda p: p.info.imaging_score, reverse=True)
        return planned[:max_results]

    def update_location(self, location: ObserverLocation) -> None:
        self._location = location

    def update_objects(self, objects: list[CelestialObject]) -> None:
        self._objects = objects
