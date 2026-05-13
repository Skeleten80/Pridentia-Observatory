"""
Astronomy engine — coordinate transforms, ephemerides, and target calculations.

Uses Astropy for all coordinate math and Skyfield for high-precision solar-system
ephemerides where needed.  All public methods are pure-ish functions that take an
ObserverLocation and a UTC datetime; no global state is mutated.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Optional

from astropy import units as u
from astropy.coordinates import (
    AltAz,
    EarthLocation,
    SkyCoord,
    get_body,
    solar_system_ephemeris,
)
from astropy.time import Time

from .models import (
    CelestialObject,
    HorizonCoordinate,
    ObserverLocation,
    ObjectType,
    SkyCoordinate,
    TargetInfo,
)

log = logging.getLogger(__name__)

# Solar-system bodies accessible via astropy.coordinates.get_body
_ASTROPY_SOLAR_BODIES = {
    "sun", "moon", "mercury", "venus", "mars",
    "jupiter", "saturn", "uranus", "neptune",
    "pluto",
}

# ─────────────────────────────────────────────────────────────────────────────
# Public helper functions
# ─────────────────────────────────────────────────────────────────────────────

def make_earth_location(loc: ObserverLocation) -> EarthLocation:
    return EarthLocation(
        lat=loc.latitude_degrees * u.deg,
        lon=loc.longitude_degrees * u.deg,
        height=loc.elevation_meters * u.m,
    )


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def local_sidereal_time(loc: ObserverLocation, dt: Optional[datetime] = None) -> float:
    """Return Local Sidereal Time in decimal hours."""
    if dt is None:
        dt = utcnow()
    t = Time(dt)
    earth_loc = make_earth_location(loc)
    lst = t.sidereal_time("apparent", longitude=earth_loc.lon)
    return float(lst.hour)


def hour_angle(ra_hours: float, lst_hours: float) -> float:
    """Return hour angle in decimal hours, range [-12, +12]."""
    ha = lst_hours - ra_hours
    # normalise to [-12, 12]
    ha = ha % 24
    if ha > 12:
        ha -= 24
    return ha


def altaz_from_radec(
    ra_hours: float,
    dec_degrees: float,
    loc: ObserverLocation,
    dt: Optional[datetime] = None,
) -> HorizonCoordinate:
    """Convert equatorial RA/Dec (J2000) to horizon Alt/Az for given location and time."""
    if dt is None:
        dt = utcnow()
    t = Time(dt)
    earth_loc = make_earth_location(loc)
    frame = AltAz(obstime=t, location=earth_loc)
    coord = SkyCoord(ra=ra_hours * 15 * u.deg, dec=dec_degrees * u.deg, frame="icrs")
    altaz = coord.transform_to(frame)
    return HorizonCoordinate(
        altitude_degrees=float(altaz.alt.deg),
        azimuth_degrees=float(altaz.az.deg),
    )


def solar_system_radec(
    body_name: str,
    loc: ObserverLocation,
    dt: Optional[datetime] = None,
) -> Optional[SkyCoordinate]:
    """Return current RA/Dec for a named solar-system body using Astropy built-in ephemeris."""
    if dt is None:
        dt = utcnow()
    key = body_name.lower()
    if key not in _ASTROPY_SOLAR_BODIES:
        return None
    try:
        t = Time(dt)
        earth_loc = make_earth_location(loc)
        with solar_system_ephemeris.set("builtin"):
            body = get_body(key, t, earth_loc)
        icrs = body.icrs
        return SkyCoordinate(
            ra_hours=float(icrs.ra.hour),
            dec_degrees=float(icrs.dec.deg),
        )
    except Exception:
        log.exception("Failed to compute solar-system coordinates for %s", body_name)
        return None


def airmass(altitude_degrees: float) -> float:
    """Pickering (2002) airmass approximation; returns float('inf') below horizon."""
    if altitude_degrees <= 0:
        return float("inf")
    # Formula works in degrees throughout; convert the final sum to radians
    alt_corr = altitude_degrees + 244.0 / (165.0 + 47.0 * altitude_degrees**1.1)
    return 1.0 / math.sin(math.radians(alt_corr))


def moon_separation(
    ra_hours: float,
    dec_degrees: float,
    loc: ObserverLocation,
    dt: Optional[datetime] = None,
) -> float:
    """Return angular separation in degrees between target and the Moon."""
    if dt is None:
        dt = utcnow()
    moon_coord = solar_system_radec("moon", loc, dt)
    if moon_coord is None:
        return 180.0
    c1 = SkyCoord(ra=ra_hours * 15 * u.deg, dec=dec_degrees * u.deg, frame="icrs")
    c2 = SkyCoord(
        ra=moon_coord.ra_hours * 15 * u.deg,
        dec=moon_coord.dec_degrees * u.deg,
        frame="icrs",
    )
    return float(c1.separation(c2).deg)


def imaging_score(
    altitude_deg: float,
    moon_sep_deg: float,
    target_mag: Optional[float],
) -> float:
    """
    Heuristic 0–10 score representing tonight's imaging suitability.
    Higher altitude, larger moon separation, and brighter targets score better.
    """
    if altitude_deg < 10:
        return 0.0
    alt_score = min(altitude_deg / 90.0, 1.0) * 4.0
    moon_score = min(moon_sep_deg / 90.0, 1.0) * 4.0
    mag_score = 0.0
    if target_mag is not None:
        if target_mag <= 6:
            mag_score = 2.0
        elif target_mag <= 10:
            mag_score = 1.0
    return round(alt_score + moon_score + mag_score, 1)


def transit_rise_set(
    ra_hours: float,
    dec_degrees: float,
    loc: ObserverLocation,
    dt: Optional[datetime] = None,
    horizon_deg: float = 10.0,
) -> tuple[Optional[datetime], Optional[datetime], Optional[datetime]]:
    """
    Approximate transit, rise, and set times for a fixed RA/Dec object.

    Returns (transit_utc, rise_utc, set_utc).  All values may be None if the
    object is circumpolar below or above the horizon all night.
    """
    if dt is None:
        dt = utcnow()

    # Sample the next 24 hours in 5-minute steps
    samples: list[tuple[datetime, float]] = []
    for minutes in range(0, 24 * 60, 5):
        sample_time = dt + timedelta(minutes=minutes)
        altaz = altaz_from_radec(ra_hours, dec_degrees, loc, sample_time)
        samples.append((sample_time, altaz.altitude_degrees))

    # Find transit (max altitude)
    transit_time, _ = max(samples, key=lambda s: s[1])

    # Find rise and set around the max
    rise_time: Optional[datetime] = None
    set_time: Optional[datetime] = None

    for i in range(1, len(samples)):
        prev_t, prev_alt = samples[i - 1]
        cur_t, cur_alt = samples[i]
        if prev_alt < horizon_deg <= cur_alt:
            rise_time = prev_t
        if prev_alt >= horizon_deg > cur_alt:
            set_time = cur_t

    return transit_time, rise_time, set_time


def compute_target_info(
    obj: CelestialObject,
    loc: ObserverLocation,
    dt: Optional[datetime] = None,
) -> TargetInfo:
    """
    Compute a full TargetInfo for a CelestialObject at the given observer/time.

    For solar-system bodies the RA/Dec is fetched live; for deep-sky objects the
    catalogue coordinates are used.
    """
    if dt is None:
        dt = utcnow()

    ra_h = obj.ra_hours
    dec_d = obj.dec_degrees

    # Override catalogue coordinates for solar-system bodies
    if obj.is_solar_system_body():
        live = solar_system_radec(obj.display_name, loc, dt)
        if live is None:
            # Try using catalogue name fields
            for alias in [obj.name, *obj.common_names, *obj.catalogue_ids]:
                live = solar_system_radec(alias, loc, dt)
                if live:
                    break
        if live:
            ra_h, dec_d = live.ra_hours, live.dec_degrees

    altaz = altaz_from_radec(ra_h, dec_d, loc, dt)
    am = airmass(altaz.altitude_degrees)
    moon_sep = moon_separation(ra_h, dec_d, loc, dt)
    transit, rise, set_ = transit_rise_set(ra_h, dec_d, loc, dt)
    score = imaging_score(altaz.altitude_degrees, moon_sep, obj.magnitude)

    return TargetInfo(
        obj=obj,
        altaz=altaz,
        airmass=am,
        moon_separation_degrees=moon_sep,
        transit_time=transit,
        rise_time=rise,
        set_time=set_,
        imaging_score=score,
    )


def degrees_to_hms(degrees: float) -> str:
    """Format decimal degrees as RA HH:MM:SS string."""
    hours = degrees / 15.0
    h = int(hours)
    m = int((hours - h) * 60)
    s = ((hours - h) * 60 - m) * 60
    return f"{h:02d}:{m:02d}:{s:05.2f}"


def degrees_to_dms(degrees: float) -> str:
    """Format decimal degrees as Dec ±DD:MM:SS string."""
    sign = "+" if degrees >= 0 else "-"
    d_abs = abs(degrees)
    d = int(d_abs)
    m = int((d_abs - d) * 60)
    s = ((d_abs - d) * 60 - m) * 60
    return f"{sign}{d:02d}:{m:02d}:{s:04.1f}"


def parse_ra_hms(text: str) -> Optional[float]:
    """Parse 'HH:MM:SS' or 'HH MM SS' into decimal hours. Returns None on failure."""
    try:
        parts = text.replace(":", " ").split()
        if len(parts) == 3:
            h, m, s = float(parts[0]), float(parts[1]), float(parts[2])
            return h + m / 60 + s / 3600
        if len(parts) == 1:
            return float(parts[0])
    except ValueError:
        pass
    return None


def parse_dec_dms(text: str) -> Optional[float]:
    """Parse '±DD:MM:SS' or '±DD MM SS' into decimal degrees. Returns None on failure."""
    try:
        clean = text.strip()
        negative = clean.startswith("-")
        clean = clean.lstrip("+-")
        parts = clean.replace(":", " ").split()
        if len(parts) == 3:
            d, m, s = float(parts[0]), float(parts[1]), float(parts[2])
            val = d + m / 60 + s / 3600
            return -val if negative else val
        if len(parts) == 1:
            val = float(parts[0])
            return -val if negative else val
    except ValueError:
        pass
    return None
