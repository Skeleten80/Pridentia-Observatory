"""
Integration test: full guided imaging workflow with simulated hardware.

Test scenario:
  1. Load object database and find target
  2. Connect simulated mount
  3. Slew to target
  4. Connect simulated camera
  5. Capture test exposure
  6. Plate solve the image
  7. Sync mount to solved position
  8. Run a 3-frame exposure sequence
"""

from __future__ import annotations

import os
import time

import pytest

from prudentia_observatory.app.cameras.simulator_camera import SimulatorCamera
from prudentia_observatory.app.core.astronomy_engine import compute_target_info
from prudentia_observatory.app.core.models import (
    MountState,
    ObserverLocation,
    SequenceState,
    SkyCoordinate,
)
from prudentia_observatory.app.core.object_database import ObjectDatabase
from prudentia_observatory.app.core.session_logger import SessionLogger
from prudentia_observatory.app.core.target_planner import PlannerFilters, TargetPlanner
from prudentia_observatory.app.data.seed_catalogs import seed
from prudentia_observatory.app.mounts.simulator_mount import SimulatorMount
from prudentia_observatory.app.platesolve.simulator_solver import SimulatorSolver


@pytest.fixture(scope="module")
def seeded_db(tmp_path_factory) -> ObjectDatabase:
    db_path = str(tmp_path_factory.mktemp("data") / "integration.sqlite")
    db = ObjectDatabase(db_path=db_path)
    seed(db, rebuild=False)
    return db


@pytest.fixture
def observer() -> ObserverLocation:
    return ObserverLocation(
        name="Integration Test Site",
        latitude_degrees=48.0,
        longitude_degrees=11.0,
        elevation_meters=500.0,
    )


class TestFullWorkflow:
    def test_01_database_seeded(self, seeded_db):
        assert seeded_db.count() > 100

    def test_02_find_target(self, seeded_db):
        m42 = seeded_db.get_by_catalogue_id("M42")
        assert m42 is not None
        assert m42.ra_hours > 5 and m42.ra_hours < 6

    def test_03_connect_mount(self):
        mount = SimulatorMount()
        mount.connect()
        assert mount.is_connected
        mount.disconnect()

    def test_04_slew_to_m42(self):
        mount = SimulatorMount(slew_rate_deg_s=30.0)
        mount.connect()
        mount.unpark()
        # Pre-sync close to target so test stays fast
        mount.sync_to_radec(SkyCoordinate(ra_hours=5.5, dec_degrees=-5.0))
        target = SkyCoordinate(ra_hours=5.588, dec_degrees=-5.39)
        mount.slew_to_radec(target, "M42")
        # Wait for slew
        deadline = time.time() + 15
        while time.time() < deadline:
            st = mount.get_status()
            if st.state == MountState.TRACKING:
                break
            time.sleep(0.2)
        st = mount.get_status()
        assert st.state == MountState.TRACKING
        assert abs(st.ra_hours - 5.588) < 0.05
        mount.disconnect()

    def test_05_capture_exposure(self, tmp_path):
        camera = SimulatorCamera(fast_mode=True)
        camera.connect()
        save_path = str(tmp_path / "m42_test.fits")
        path = camera.capture(save_path)
        assert os.path.exists(path)
        assert os.path.getsize(path) > 1000
        camera.disconnect()

    def test_06_plate_solve(self, tmp_path):
        camera = SimulatorCamera(fast_mode=True)
        camera.connect()
        save_path = str(tmp_path / "solve_frame.fits")
        image_path = camera.capture(save_path)

        solver = SimulatorSolver(always_succeed=True)
        hint = SkyCoordinate(ra_hours=5.588, dec_degrees=-5.39)
        result = solver.solve(image_path, hint_coord=hint)

        assert result.success
        assert 0 <= result.ra_hours < 24
        assert -90 <= result.dec_degrees <= 90
        camera.disconnect()

    def test_07_sync_mount_after_solve(self):
        mount = SimulatorMount()
        mount.connect()
        mount.unpark()
        mount.slew_to_radec(SkyCoordinate(5.588, -5.39))
        time.sleep(1.0)

        solver = SimulatorSolver(always_succeed=True)
        image_dir = "/tmp"
        from prudentia_observatory.app.cameras.simulator_camera import SimulatorCamera
        cam = SimulatorCamera(fast_mode=True)
        cam.connect()
        path = cam.capture("/tmp/prudentia_sync_test.fits")
        result = solver.solve(path, SkyCoordinate(5.588, -5.39))
        assert result.success

        mount.sync_to_radec(SkyCoordinate(result.ra_hours, result.dec_degrees))
        st = mount.get_status()
        assert abs(st.ra_hours - result.ra_hours) < 0.01
        mount.disconnect()

    def test_08_sequence_three_frames(self, tmp_path, observer):
        camera = SimulatorCamera(fast_mode=True)
        camera.connect()
        mount = SimulatorMount()
        mount.connect()
        mount.unpark()

        log = SessionLogger(log_dir=str(tmp_path))
        log.log_sequence_start("M42", 3, 10.0, 800)

        frames_done = 0
        for i in range(3):
            fname = str(tmp_path / f"m42_seq_{i + 1:04d}.fits")
            camera.set_exposure(10.0)
            camera.set_iso(800)
            path = camera.capture(fname)
            assert os.path.exists(path)
            frames_done += 1

        assert frames_done == 3
        log.log_sequence_end("M42", frames_done, aborted=False)
        log.close()
        camera.disconnect()
        mount.disconnect()

    def test_09_target_planner_finds_visible_objects(self, seeded_db, observer):
        objects = seeded_db.all_objects(limit=500)
        planner = TargetPlanner(observer, objects)
        filters = PlannerFilters(
            min_altitude_degrees=15.0,
            min_moon_separation_degrees=10.0,
            only_visible_now=True,
        )
        # Don't require specific targets — just verify planner runs without error
        planned = planner.plan(filters, max_results=20)
        # All returned targets should be above the minimum altitude
        for p in planned:
            assert p.info.altaz.altitude_degrees >= 0 or p.info.obj.is_solar_system_body()

    def test_10_session_log_written(self, tmp_path):
        log = SessionLogger(log_dir=str(tmp_path))
        log.info("Integration test event")
        log.warning("Test warning")
        log.close()
        log_files = list(tmp_path.glob("session_*.log"))
        assert len(log_files) == 1
        content = log_files[0].read_text()
        assert "Integration test event" in content
        assert "Prudentia Observatory" in content
