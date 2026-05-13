"""Unit tests for the simulated telescope mount."""

from __future__ import annotations

import time
import threading

import pytest

from prudentia_observatory.app.core.models import MountState, SkyCoordinate
from prudentia_observatory.app.mounts.base_mount import MountError
from prudentia_observatory.app.mounts.simulator_mount import SimulatorMount


@pytest.fixture
def mount() -> SimulatorMount:
    m = SimulatorMount()
    return m


@pytest.fixture
def connected_mount(mount) -> SimulatorMount:
    mount.connect()
    mount.unpark()
    return mount


class TestConnection:
    def test_initial_state(self, mount):
        assert not mount.is_connected

    def test_connect(self, mount):
        mount.connect()
        assert mount.is_connected

    def test_disconnect(self, connected_mount):
        connected_mount.disconnect()
        assert not connected_mount.is_connected

    def test_connect_idempotent(self, mount):
        mount.connect()
        mount.connect()  # should not raise
        assert mount.is_connected


class TestStatus:
    def test_status_connected(self, connected_mount):
        status = connected_mount.get_status()
        assert status.state != MountState.DISCONNECTED

    def test_initial_position(self, connected_mount):
        status = connected_mount.get_status()
        assert 0 <= status.ra_hours < 24
        assert -90 <= status.dec_degrees <= 90


class TestTracking:
    def test_start_tracking(self, connected_mount):
        connected_mount.set_tracking(True)
        status = connected_mount.get_status()
        assert status.is_tracking

    def test_stop_tracking(self, connected_mount):
        connected_mount.set_tracking(True)
        connected_mount.set_tracking(False)
        status = connected_mount.get_status()
        assert not status.is_tracking

    def test_tracking_requires_connection(self, mount):
        with pytest.raises(MountError):
            mount.set_tracking(True)


class TestSlew:
    def test_slew_updates_position(self):
        # Use a fast-slew mount and sync to near-target first to keep test short
        fast_mount = SimulatorMount(slew_rate_deg_s=30.0)
        fast_mount.connect()
        fast_mount.unpark()
        # Pre-position mount close to target so the slew is short
        fast_mount.sync_to_radec(SkyCoordinate(ra_hours=5.5, dec_degrees=-5.0))
        target = SkyCoordinate(ra_hours=5.588, dec_degrees=-5.39)
        fast_mount.slew_to_radec(target, "Orion Nebula")
        # Wait for slew to complete
        timeout = 15.0
        t0 = time.time()
        while time.time() - t0 < timeout:
            st = fast_mount.get_status()
            if st.state == MountState.TRACKING:
                break
            time.sleep(0.2)
        st = fast_mount.get_status()
        assert abs(st.ra_hours - target.ra_hours) < 0.01
        assert abs(st.dec_degrees - target.dec_degrees) < 0.1
        fast_mount.disconnect()

    def test_slew_requires_connection(self, mount):
        with pytest.raises(MountError):
            mount.slew_to_radec(SkyCoordinate(5.0, 0.0))

    def test_slew_requires_unpark(self, mount):
        mount.connect()  # parked by default
        with pytest.raises(MountError):
            mount.slew_to_radec(SkyCoordinate(5.0, 0.0))

    def test_abort_slew(self, connected_mount):
        target = SkyCoordinate(ra_hours=12.0, dec_degrees=45.0)
        connected_mount.slew_to_radec(target)
        time.sleep(0.1)
        connected_mount.abort_slew()
        st = connected_mount.get_status()
        # After abort, should be idle
        assert st.state in (MountState.IDLE, MountState.TRACKING)


class TestSync:
    def test_sync_updates_position(self, connected_mount):
        new_coord = SkyCoordinate(ra_hours=10.0, dec_degrees=30.0)
        connected_mount.sync_to_radec(new_coord)
        st = connected_mount.get_status()
        assert abs(st.ra_hours - 10.0) < 0.01
        assert abs(st.dec_degrees - 30.0) < 0.01

    def test_sync_requires_connection(self, mount):
        with pytest.raises(MountError):
            mount.sync_to_radec(SkyCoordinate(10.0, 30.0))


class TestParkUnpark:
    def test_park(self, connected_mount):
        connected_mount.park()
        st = connected_mount.get_status()
        assert st.is_parked
        assert st.state == MountState.PARKED

    def test_unpark(self, connected_mount):
        connected_mount.park()
        connected_mount.unpark()
        st = connected_mount.get_status()
        assert not st.is_parked

    def test_emergency_stop(self, connected_mount):
        target = SkyCoordinate(12.0, 45.0)
        connected_mount.slew_to_radec(target)
        time.sleep(0.1)
        connected_mount.emergency_stop()
        st = connected_mount.get_status()
        assert st.state != MountState.SLEWING
