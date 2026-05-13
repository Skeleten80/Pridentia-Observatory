"""Shared data models used across all Prudentia Observatory modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Optional


class ObjectType(str, Enum):
    GALAXY = "Galaxy"
    NEBULA = "Nebula"
    OPEN_CLUSTER = "Open Cluster"
    GLOBULAR_CLUSTER = "Globular Cluster"
    PLANETARY_NEBULA = "Planetary Nebula"
    SUPERNOVA_REMNANT = "Supernova Remnant"
    DOUBLE_STAR = "Double Star"
    STAR = "Star"
    PLANET = "Planet"
    DWARF_PLANET = "Dwarf Planet"
    MOON = "Moon"
    SUN = "Sun"
    COMET = "Comet"
    ASTEROID = "Asteroid"
    UNKNOWN = "Unknown"


class MountState(str, Enum):
    DISCONNECTED = "Disconnected"
    CONNECTED = "Connected"
    SLEWING = "Slewing"
    TRACKING = "Tracking"
    PARKED = "Parked"
    IDLE = "Idle"
    ERROR = "Error"


class CameraState(str, Enum):
    DISCONNECTED = "Disconnected"
    CONNECTED = "Connected"
    IDLE = "Idle"
    EXPOSING = "Exposing"
    DOWNLOADING = "Downloading"
    ERROR = "Error"


class SolverState(str, Enum):
    IDLE = "Idle"
    SOLVING = "Solving"
    SOLVED = "Solved"
    FAILED = "Failed"


class SequenceState(str, Enum):
    IDLE = "Idle"
    RUNNING = "Running"
    PAUSED = "Paused"
    COMPLETED = "Completed"
    ABORTED = "Aborted"


@dataclass
class SkyCoordinate:
    """Equatorial coordinate pair (J2000 epoch)."""
    ra_hours: float   # Right Ascension in decimal hours [0, 24)
    dec_degrees: float  # Declination in decimal degrees [-90, +90]

    @property
    def ra_degrees(self) -> float:
        return self.ra_hours * 15.0

    def __str__(self) -> str:
        ra_h = int(self.ra_hours)
        ra_m = int((self.ra_hours - ra_h) * 60)
        ra_s = ((self.ra_hours - ra_h) * 60 - ra_m) * 60
        sign = "+" if self.dec_degrees >= 0 else "-"
        dec_abs = abs(self.dec_degrees)
        dec_d = int(dec_abs)
        dec_m = int((dec_abs - dec_d) * 60)
        dec_s = ((dec_abs - dec_d) * 60 - dec_m) * 60
        return f"RA {ra_h:02d}h{ra_m:02d}m{ra_s:05.2f}s  Dec {sign}{dec_d:02d}°{dec_m:02d}'{dec_s:04.1f}\""


@dataclass
class HorizonCoordinate:
    """Horizontal (Alt/Az) coordinate pair."""
    altitude_degrees: float   # Above horizon [-90, +90]
    azimuth_degrees: float    # North=0, East=90, South=180, West=270 [0, 360)

    def is_above_horizon(self, min_alt: float = 0.0) -> bool:
        return self.altitude_degrees >= min_alt


@dataclass
class ObserverLocation:
    """Observer geographic position and timezone."""
    name: str = "My Observatory"
    latitude_degrees: float = 0.0
    longitude_degrees: float = 0.0
    elevation_meters: float = 0.0
    timezone: str = "UTC"

    def is_valid(self) -> bool:
        return -90.0 <= self.latitude_degrees <= 90.0 and -180.0 <= self.longitude_degrees <= 180.0


@dataclass
class CelestialObject:
    """An entry from the object catalogue."""
    id: int = 0
    name: str = ""
    catalogue_ids: list[str] = field(default_factory=list)
    object_type: ObjectType = ObjectType.UNKNOWN
    ra_hours: float = 0.0
    dec_degrees: float = 0.0
    magnitude: Optional[float] = None
    angular_size_arcmin: Optional[float] = None
    constellation: str = ""
    description: str = ""
    common_names: list[str] = field(default_factory=list)

    @property
    def coordinate(self) -> SkyCoordinate:
        return SkyCoordinate(self.ra_hours, self.dec_degrees)

    @property
    def display_name(self) -> str:
        if self.common_names:
            return self.common_names[0]
        if self.catalogue_ids:
            return self.catalogue_ids[0]
        return self.name

    def is_solar_system_body(self) -> bool:
        return self.object_type in (
            ObjectType.PLANET, ObjectType.DWARF_PLANET,
            ObjectType.MOON, ObjectType.SUN, ObjectType.COMET, ObjectType.ASTEROID,
        )


@dataclass
class TargetInfo:
    """Computed visibility and imaging data for an object at a given time/location."""
    obj: CelestialObject
    altaz: HorizonCoordinate
    airmass: float
    moon_separation_degrees: float
    transit_time: Optional[datetime]
    rise_time: Optional[datetime]
    set_time: Optional[datetime]
    imaging_score: float  # 0–10, higher is better


@dataclass
class MountStatus:
    state: MountState = MountState.DISCONNECTED
    ra_hours: float = 0.0
    dec_degrees: float = 0.0
    altitude_degrees: float = 0.0
    azimuth_degrees: float = 0.0
    is_tracking: bool = False
    is_parked: bool = False
    slew_rate: float = 1.0
    pier_side: str = "Unknown"
    error_message: str = ""


@dataclass
class CameraStatus:
    state: CameraState = CameraState.DISCONNECTED
    model: str = "Unknown"
    current_iso: int = 1600
    current_exposure_seconds: float = 60.0
    aperture: str = "N/A"
    image_format: str = "RAW"
    progress_percent: float = 0.0
    last_image_path: str = ""
    error_message: str = ""


@dataclass
class SolveResult:
    """Result from a plate-solving attempt."""
    success: bool
    ra_hours: float = 0.0
    dec_degrees: float = 0.0
    rotation_degrees: float = 0.0
    pixel_scale_arcsec: float = 0.0
    ra_error_arcmin: float = 0.0
    dec_error_arcmin: float = 0.0
    total_error_arcmin: float = 0.0
    solver_time_seconds: float = 0.0
    message: str = ""


@dataclass
class SequenceFrame:
    """One frame in an imaging sequence."""
    index: int
    exposure_seconds: float
    iso: int
    frame_type: str = "Light"  # Light, Dark, Flat, Bias
    filename: str = ""
    completed: bool = False
    solve_result: Optional[SolveResult] = None


@dataclass
class ImagingSequence:
    """A complete imaging sequence definition."""
    target_name: str = ""
    target_coord: Optional[SkyCoordinate] = None
    num_lights: int = 10
    exposure_seconds: float = 120.0
    iso: int = 1600
    delay_seconds: float = 2.0
    dither_every: int = 0  # 0 = disabled
    save_directory: str = ""
    filename_template: str = "{target}_{date}_{index:04d}"
    frames: list[SequenceFrame] = field(default_factory=list)
    state: SequenceState = SequenceState.IDLE
    current_frame_index: int = 0


@dataclass
class SessionMetadata:
    """Header metadata saved with each captured image."""
    target_name: str = ""
    ra_hours: float = 0.0
    dec_degrees: float = 0.0
    altitude_degrees: float = 0.0
    azimuth_degrees: float = 0.0
    exposure_seconds: float = 0.0
    iso: int = 0
    camera_model: str = ""
    telescope_info: str = ""
    mount_info: str = ""
    observer_latitude: float = 0.0
    observer_longitude: float = 0.0
    observer_elevation: float = 0.0
    utc_datetime: str = ""
    local_datetime: str = ""
    airmass: float = 1.0
    moon_separation_degrees: float = 0.0
    software: str = "Prudentia Observatory"
