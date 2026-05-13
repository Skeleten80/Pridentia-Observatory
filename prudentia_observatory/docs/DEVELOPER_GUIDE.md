# Developer Guide — Prudentia Observatory

## Architecture Overview

Prudentia Observatory is built with a deliberately modular architecture.
Each subsystem is isolated behind an abstract base class so that different
hardware backends, UI frameworks, or data sources can be plugged in without
touching unrelated code.

```
┌───────────────────────────────────────────────────────────────────────┐
│                        PySide6 UI Layer                               │
│  MainWindow → Tabs: SkyMap, ObjectSearch, Telescope, Camera, …        │
└──────────┬──────────┬──────────┬──────────┬──────────────────────────┘
           │          │          │          │
    ┌──────▼──┐  ┌────▼───┐  ┌──▼──────┐  ┌▼──────────────┐
    │ Core    │  │ Mount  │  │ Camera  │  │ PlateSolve     │
    │ Engine  │  │ Backend│  │ Backend │  │ Backend        │
    │ (Astropy│  │ (ASCOM │  │ (gPhoto2│  │ (Astrometry.  │
    │  based) │  │  INDI  │  │  INDI   │  │  net / Sim)   │
    └──────┬──┘  │  Sim)  │  │  Sim    │  └────────────────┘
           │     └────────┘  └─────────┘
    ┌──────▼──┐
    │ SQLite  │
    │ Catalogue│
    └─────────┘
```

---

## Module Descriptions

### `app/core/models.py`

Shared dataclasses and enums used everywhere:
- `SkyCoordinate` — equatorial RA/Dec pair
- `HorizonCoordinate` — Alt/Az pair
- `CelestialObject` — catalogue entry
- `MountStatus`, `CameraStatus`, `SolveResult`
- `ImagingSequence`, `SessionMetadata`

All models are pure data; they have no side effects.

### `app/core/astronomy_engine.py`

All coordinate math, wrapped around Astropy.  Pure functions.

Key functions:
- `altaz_from_radec(ra, dec, location, dt)` — equatorial → horizon
- `solar_system_radec(body, location, dt)` — live planet/moon coords
- `transit_rise_set(ra, dec, location, dt)` — event times
- `airmass(altitude)` — Pickering formula
- `imaging_score(alt, moon_sep, mag)` — 0–10 suitability score
- `compute_target_info(obj, location, dt)` — full `TargetInfo` struct

### `app/core/object_database.py`

Read-only SQLite interface.  All writes go through `seed_catalogs.py`.
Thread-safe (each call opens and closes its own connection).

### `app/core/target_planner.py`

`TargetPlanner.plan(filters)` returns a sorted list of `PlannedTarget`
objects with imaging windows and exposure notes.

### `app/core/session_logger.py`

Writes `.log` (human-readable) and `_events.json` (machine-readable) files
to `~/PrudentiaObservatory/logs/`.

---

## Adding a New Mount Backend

1. Create `app/mounts/my_new_mount.py`.
2. Subclass `BaseMount` and implement all abstract methods:
   - `connect()`, `disconnect()`
   - `get_status() → MountStatus`
   - `slew_to_radec(coord, target_name)`
   - `abort_slew()`
   - `set_tracking(enabled)`
   - `sync_to_radec(coord)`
   - `park()`, `unpark()`
3. Register the backend in `app/ui/main_window.py` → `_make_mount()`:

```python
if backend == "my_new_mount":
    from ..mounts.my_new_mount import MyNewMount
    return MyNewMount(host=..., port=...)
```

4. Add it to the backend dropdown in `app/ui/settings_panel.py`:

```python
self._mount_backend.addItems([..., "my_new_mount"])
```

---

## Adding a New Camera Backend

Same pattern — subclass `BaseCamera` from `app/cameras/base_camera.py`,
implement `connect`, `disconnect`, `get_status`, `set_exposure`, `set_iso`,
`capture`, `abort`.  Register in `_make_camera()`.

---

## Adding a New Plate Solver

Subclass `BaseSolver` from `app/platesolve/base_solver.py`, implement `solve()`.
Register in `_make_solver()`.

---

## Adding Catalogue Data

Open `app/data/seed_catalogs.py` and add entries to the appropriate list:
- `SOLAR_SYSTEM` — planets and moons
- `MESSIER` — Messier objects
- `BRIGHT_STARS` — bright stars
- `NOTABLE_NGC_IC` — NGC/IC objects

Then run:
```bash
python -m prudentia_observatory.app.data.seed_catalogs --rebuild
```

For large catalogues (Gaia, full NGC, IC, Tycho-2), consider a separate loader
that imports a CSV or FITS file directly into the SQLite database.

---

## Adding Online Catalogue Lookup (SIMBAD/VizieR)

The `ObjectDatabase` is intentionally local-only for MVP.  To add online
lookup:

1. Create `app/core/simbad_client.py` with an async `lookup(query)` function
   using `aiohttp` and the CDS SIMBAD TAP endpoint.
2. Add a "Search SIMBAD" button to `ObjectSearchPanel`.
3. On response, create a `CelestialObject` and optionally cache it in the
   local database.

CDS SIMBAD TAP URL:
```
https://simbad.u-strasbg.fr/simbad/sim-tap/sync?REQUEST=doQuery&LANG=ADQL&FORMAT=json&QUERY=...
```

---

## Testing

All test files live in `prudentia_observatory/tests/`.

```bash
# Run all tests
pytest prudentia_observatory/tests/ -v

# Run only the integration workflow
pytest prudentia_observatory/tests/test_integration_workflow.py -v

# With coverage
pytest --cov=prudentia_observatory --cov-report=html
```

No Qt/GUI is required for the unit tests — they test the core engine, database,
mount simulator, and camera simulator directly.

---

## Code Style

- Python 3.12+ syntax and type hints throughout.
- `dataclasses` for structured data (or `pydantic` for validation-heavy models).
- `logging` instead of `print`.
- Error handling at hardware boundaries only; let exceptions propagate from pure functions.
- No global mutable state (except the Qt application singleton).
- One file per class/module; no mega-files.

---

## Settings File

User settings are persisted to:

```
~/PrudentiaObservatory/prudentia_observatory_settings.json
```

The schema is defined in `app/ui/settings_panel.py` → `load_settings()`.
All keys have defaults so missing keys are gracefully handled.

---

## Packaging

### PyInstaller (macOS / Windows)

```bash
pip install pyinstaller
pyinstaller prudentia_observatory/app/main.py \
  --name "Prudentia Observatory" \
  --windowed \
  --add-data "prudentia_observatory/app/data:prudentia_observatory/app/data"
```

The SQLite catalogue is bundled as a data file.  On first launch in the
bundled app, `seed_catalogs.py` creates the database in the user's home directory.

### Briefcase (alternative)

```bash
pip install briefcase
briefcase new    # configure pyproject.toml [tool.briefcase]
briefcase build
briefcase run
```

---

## Future Roadmap

- [ ] PHD2/PHD Guiding 2 integration for autoguiding
- [ ] FITS header writer (full WCS and metadata)
- [ ] Sequence dithering via guider commands
- [ ] SIMBAD/VizieR online lookup adapter
- [ ] Gaia DR3 proper motion corrections
- [ ] Focuser control (ASCOM Alpaca / INDI)
- [ ] Filter wheel control
- [ ] All-sky camera integration
- [ ] Weather station / cloud sensor integration
- [ ] Mobile companion app (future)
