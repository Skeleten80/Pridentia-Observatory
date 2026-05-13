"""
Local SQLite object database for Prudentia Observatory.

Provides fast offline lookup for Messier, NGC, IC, Caldwell, bright stars,
planets, and other common objects.  All writes happen through seed_catalogs.py
at first launch; this module is read-only at runtime.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from typing import Optional

from .models import CelestialObject, ObjectType

log = logging.getLogger(__name__)

_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "catalogs.sqlite")


def _get_db_path() -> str:
    return os.path.abspath(_DB_PATH)


def _row_to_object(row: sqlite3.Row) -> CelestialObject:
    catalogue_ids = [c.strip() for c in (row["catalogue_ids"] or "").split(",") if c.strip()]
    common_names = [c.strip() for c in (row["common_names"] or "").split("|") if c.strip()]
    try:
        obj_type = ObjectType(row["object_type"])
    except ValueError:
        obj_type = ObjectType.UNKNOWN
    return CelestialObject(
        id=row["id"],
        name=row["name"],
        catalogue_ids=catalogue_ids,
        object_type=obj_type,
        ra_hours=row["ra_hours"],
        dec_degrees=row["dec_degrees"],
        magnitude=row["magnitude"],
        angular_size_arcmin=row["angular_size_arcmin"],
        constellation=row["constellation"] or "",
        description=row["description"] or "",
        common_names=common_names,
    )


class ObjectDatabase:
    """Thread-safe read-only interface to the local object catalogue."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = db_path or _get_db_path()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        """Create the table if it does not yet exist (seed script populates it)."""
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS objects (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    name                TEXT NOT NULL,
                    catalogue_ids       TEXT,
                    common_names        TEXT,
                    object_type         TEXT NOT NULL,
                    ra_hours            REAL NOT NULL,
                    dec_degrees         REAL NOT NULL,
                    magnitude           REAL,
                    angular_size_arcmin REAL,
                    constellation       TEXT,
                    description         TEXT
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_name ON objects (name COLLATE NOCASE)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_type ON objects (object_type)"
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Query methods
    # ─────────────────────────────────────────────────────────────────────────

    def count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM objects").fetchone()[0]

    def get_by_id(self, obj_id: int) -> Optional[CelestialObject]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM objects WHERE id=?", (obj_id,)).fetchone()
            return _row_to_object(row) if row else None

    def search(
        self,
        query: str = "",
        object_types: Optional[list[str]] = None,
        min_magnitude: Optional[float] = None,
        max_magnitude: Optional[float] = None,
        constellation: Optional[str] = None,
        limit: int = 200,
    ) -> list[CelestialObject]:
        """
        Full-text search across name, catalogue_ids, and common_names fields.
        Additional filters narrow by type, magnitude range, and constellation.
        """
        sql = "SELECT * FROM objects WHERE 1=1"
        params: list = []

        if query:
            term = f"%{query}%"
            sql += (
                " AND (name LIKE ? OR catalogue_ids LIKE ?"
                " OR common_names LIKE ? OR description LIKE ?)"
            )
            params.extend([term, term, term, term])

        if object_types:
            placeholders = ",".join("?" * len(object_types))
            sql += f" AND object_type IN ({placeholders})"
            params.extend(object_types)

        if min_magnitude is not None:
            sql += " AND (magnitude IS NULL OR magnitude >= ?)"
            params.append(min_magnitude)

        if max_magnitude is not None:
            sql += " AND (magnitude IS NULL OR magnitude <= ?)"
            params.append(max_magnitude)

        if constellation:
            sql += " AND constellation LIKE ?"
            params.append(f"%{constellation}%")

        sql += " ORDER BY magnitude ASC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_row_to_object(r) for r in rows]

    def get_by_catalogue_id(self, cat_id: str) -> Optional[CelestialObject]:
        """Look up an object by e.g. 'M31', 'NGC 224', 'IC 1805'."""
        normalised = cat_id.strip().upper().replace("  ", " ")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM objects WHERE catalogue_ids LIKE ?",
                (f"%{normalised}%",),
            ).fetchone()
        return _row_to_object(row) if row else None

    def get_planets(self) -> list[CelestialObject]:
        return self.search(object_types=[ObjectType.PLANET.value, ObjectType.SUN.value,
                                         ObjectType.MOON.value])

    def get_messier_objects(self) -> list[CelestialObject]:
        return self.search(query="M", limit=500)

    def all_objects(self, limit: int = 5000) -> list[CelestialObject]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM objects ORDER BY magnitude ASC LIMIT ?", (limit,)
            ).fetchall()
        return [_row_to_object(r) for r in rows]

    # ─────────────────────────────────────────────────────────────────────────
    # Write methods (used by seed script only)
    # ─────────────────────────────────────────────────────────────────────────

    def insert_object(self, obj: CelestialObject) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO objects
                    (name, catalogue_ids, common_names, object_type,
                     ra_hours, dec_degrees, magnitude, angular_size_arcmin,
                     constellation, description)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    obj.name,
                    ",".join(obj.catalogue_ids),
                    "|".join(obj.common_names),
                    obj.object_type.value,
                    obj.ra_hours,
                    obj.dec_degrees,
                    obj.magnitude,
                    obj.angular_size_arcmin,
                    obj.constellation,
                    obj.description,
                ),
            )
        return cursor.lastrowid or 0

    def clear_all(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM objects")
