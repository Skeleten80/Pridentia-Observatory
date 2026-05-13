"""Unit tests for the object database and seed data."""

from __future__ import annotations

import os
import tempfile

import pytest

from prudentia_observatory.app.core.models import CelestialObject, ObjectType
from prudentia_observatory.app.core.object_database import ObjectDatabase
from prudentia_observatory.app.data.seed_catalogs import seed


@pytest.fixture
def db(tmp_path) -> ObjectDatabase:
    """Return an empty in-memory database backed by a temp file."""
    db_path = str(tmp_path / "test_catalogs.sqlite")
    return ObjectDatabase(db_path=db_path)


@pytest.fixture
def seeded_db(db) -> ObjectDatabase:
    seed(db, rebuild=False)
    return db


class TestDatabaseSetup:
    def test_empty_on_creation(self, db):
        assert db.count() == 0

    def test_schema_created(self, db):
        import sqlite3
        conn = sqlite3.connect(db._db_path)
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        assert "objects" in tables


class TestSeedData:
    def test_seed_populates_objects(self, seeded_db):
        assert seeded_db.count() > 100

    def test_messier_objects_present(self, seeded_db):
        m42 = seeded_db.get_by_catalogue_id("M42")
        assert m42 is not None
        assert "Orion Nebula" in m42.common_names or "M42" in m42.catalogue_ids

    def test_m31_andromeda(self, seeded_db):
        m31 = seeded_db.get_by_catalogue_id("M31")
        assert m31 is not None
        assert m31.object_type == ObjectType.GALAXY
        assert m31.magnitude is not None and m31.magnitude < 5

    def test_planets_present(self, seeded_db):
        planets = seeded_db.get_planets()
        names = [p.name for p in planets]
        assert "Jupiter" in names
        assert "Saturn" in names
        assert "Moon" in names

    def test_sun_present(self, seeded_db):
        results = seeded_db.search(query="Sun", object_types=[ObjectType.SUN.value])
        assert len(results) > 0

    def test_bright_stars_present(self, seeded_db):
        sirius = seeded_db.get_by_catalogue_id("Sirius")
        assert sirius is not None
        assert sirius.magnitude is not None
        assert sirius.magnitude < 0  # Sirius is mag -1.46

    def test_rebuild_replaces_data(self, seeded_db):
        count_before = seeded_db.count()
        seed(seeded_db, rebuild=True)
        count_after = seeded_db.count()
        assert count_before == count_after  # same data re-seeded


class TestSearch:
    def test_search_by_name(self, seeded_db):
        results = seeded_db.search(query="Orion")
        assert any("Orion" in (r.description + " ".join(r.common_names)) for r in results)

    def test_search_by_type(self, seeded_db):
        galaxies = seeded_db.search(object_types=[ObjectType.GALAXY.value])
        for g in galaxies:
            assert g.object_type == ObjectType.GALAXY

    def test_search_by_magnitude(self, seeded_db):
        bright = seeded_db.search(max_magnitude=5.0)
        for obj in bright:
            if obj.magnitude is not None:
                assert obj.magnitude <= 5.0

    def test_search_limit(self, seeded_db):
        results = seeded_db.search(limit=10)
        assert len(results) <= 10

    def test_search_empty_query_returns_objects(self, seeded_db):
        results = seeded_db.search(query="")
        assert len(results) > 0

    def test_get_by_catalogue_id_m13(self, seeded_db):
        m13 = seeded_db.get_by_catalogue_id("M13")
        assert m13 is not None
        assert m13.object_type == ObjectType.GLOBULAR_CLUSTER

    def test_search_case_insensitive(self, seeded_db):
        lower = seeded_db.search(query="m42")
        upper = seeded_db.search(query="M42")
        assert len(lower) > 0
        assert len(upper) > 0


class TestInsert:
    def test_insert_and_retrieve(self, db):
        obj = CelestialObject(
            name="Test Object",
            catalogue_ids=["TEST 1"],
            common_names=["My Test Galaxy"],
            object_type=ObjectType.GALAXY,
            ra_hours=10.0,
            dec_degrees=20.0,
            magnitude=9.0,
        )
        new_id = db.insert_object(obj)
        assert new_id > 0
        retrieved = db.get_by_id(new_id)
        assert retrieved is not None
        assert retrieved.name == "Test Object"
        assert ObjectType.GALAXY == retrieved.object_type

    def test_clear_all(self, seeded_db):
        seeded_db.clear_all()
        assert seeded_db.count() == 0
