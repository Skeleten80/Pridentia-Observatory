"""Unit tests for the astronomy engine — coordinate transforms and helpers."""

from __future__ import annotations

import math
from datetime import datetime, timezone

import pytest

from prudentia_observatory.app.core.astronomy_engine import (
    airmass,
    altaz_from_radec,
    degrees_to_dms,
    degrees_to_hms,
    hour_angle,
    local_sidereal_time,
    moon_separation,
    parse_dec_dms,
    parse_ra_hms,
    solar_system_radec,
    imaging_score,
)
from prudentia_observatory.app.core.models import ObserverLocation


@pytest.fixture
def greenwich() -> ObserverLocation:
    return ObserverLocation(
        name="Greenwich Observatory",
        latitude_degrees=51.4769,
        longitude_degrees=0.0,
        elevation_meters=46.0,
    )


@pytest.fixture
def fixed_time() -> datetime:
    return datetime(2024, 6, 21, 21, 0, 0, tzinfo=timezone.utc)


class TestAirmass:
    def test_zenith(self):
        assert math.isclose(airmass(90.0), 1.0, rel_tol=1e-2)

    def test_below_horizon(self):
        assert math.isinf(airmass(0.0))
        assert math.isinf(airmass(-10.0))

    def test_low_altitude(self):
        am = airmass(30.0)
        assert 1.9 < am < 2.2

    def test_moderate_altitude(self):
        am = airmass(45.0)
        assert 1.3 < am < 1.5


class TestCoordinateConversion:
    def test_altaz_polaris_near_north(self, greenwich, fixed_time):
        """Polaris should be near 51° altitude from Greenwich."""
        altaz = altaz_from_radec(2.5302, 89.2641, greenwich, fixed_time)
        assert 45 < altaz.altitude_degrees < 57
        assert -10 < altaz.azimuth_degrees < 10  # near north

    def test_altaz_below_horizon_possible(self, greenwich, fixed_time):
        """An object with dec well below the observer can be below horizon."""
        # Dec = -80° from Greenwich lat 51° will be below horizon
        altaz = altaz_from_radec(0.0, -80.0, greenwich, fixed_time)
        assert altaz.altitude_degrees < 0

    def test_altaz_returns_valid_range(self, greenwich, fixed_time):
        altaz = altaz_from_radec(5.588, -5.39, greenwich, fixed_time)
        assert -90 <= altaz.altitude_degrees <= 90
        assert 0 <= altaz.azimuth_degrees < 360


class TestHourAngle:
    def test_on_meridian(self):
        assert math.isclose(hour_angle(6.0, 6.0), 0.0)

    def test_negative_ha_east(self):
        ha = hour_angle(8.0, 6.0)
        assert ha == -2.0

    def test_normalisation(self):
        ha = hour_angle(23.0, 1.0)
        assert ha == 2.0  # +2h, not -22h


class TestHmsFormatting:
    def test_round_trip_ra(self):
        for ra in [0.0, 5.588, 23.999]:
            hms = degrees_to_hms(ra * 15)
            parsed = parse_ra_hms(hms.replace(":", " "))
            if parsed is not None:
                assert math.isclose(parsed, ra, abs_tol=0.001)

    def test_round_trip_dec(self):
        for dec in [0.0, -5.39, 89.264, -26.432]:
            dms = degrees_to_dms(dec)
            parsed = parse_dec_dms(dms.replace(":", " "))
            if parsed is not None:
                assert math.isclose(parsed, dec, abs_tol=0.01)

    def test_parse_ra_hms_colons(self):
        val = parse_ra_hms("05:34:32")
        assert val is not None
        assert math.isclose(val, 5 + 34 / 60 + 32 / 3600, abs_tol=1e-4)

    def test_parse_dec_dms_plus(self):
        val = parse_dec_dms("+22:00:52")
        assert val is not None
        assert val > 0

    def test_parse_dec_dms_minus(self):
        val = parse_dec_dms("-05:23:28")
        assert val is not None
        assert val < 0

    def test_parse_ra_invalid(self):
        assert parse_ra_hms("not_a_time") is None

    def test_parse_dec_invalid(self):
        assert parse_dec_dms("xyz") is None


class TestImagingScore:
    def test_high_altitude_high_score(self):
        score = imaging_score(70.0, 80.0, 8.0)
        assert score >= 7.0

    def test_below_horizon_zero(self):
        assert imaging_score(5.0, 80.0, 8.0) == 0.0

    def test_bright_target_bonus(self):
        score_bright = imaging_score(60.0, 60.0, 4.0)
        score_faint = imaging_score(60.0, 60.0, 15.0)
        assert score_bright > score_faint


class TestSolarSystemCoords:
    def test_moon_returns_coord(self, greenwich, fixed_time):
        coord = solar_system_radec("moon", greenwich, fixed_time)
        assert coord is not None
        assert 0 <= coord.ra_hours < 24
        assert -90 <= coord.dec_degrees <= 90

    def test_jupiter_returns_coord(self, greenwich, fixed_time):
        coord = solar_system_radec("jupiter", greenwich, fixed_time)
        assert coord is not None

    def test_invalid_body_returns_none(self, greenwich, fixed_time):
        result = solar_system_radec("bogus_planet", greenwich, fixed_time)
        assert result is None


class TestMoonSeparation:
    def test_moon_separation_from_itself_is_zero(self, greenwich, fixed_time):
        moon = solar_system_radec("moon", greenwich, fixed_time)
        if moon:
            sep = moon_separation(moon.ra_hours, moon.dec_degrees, greenwich, fixed_time)
            assert sep < 1.0

    def test_separation_range(self, greenwich, fixed_time):
        sep = moon_separation(5.588, -5.39, greenwich, fixed_time)
        assert 0 <= sep <= 180
