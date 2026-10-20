# Changelog

All notable changes to Prudentia Observatory are documented here.

## [0.1.0] — 2026-05-14

### Added — MVP Release

#### Core engine
- `astronomy_engine.py` — Astropy-powered Alt/Az transforms, Pickering airmass,
  moon separation, rise/set/transit times, imaging suitability score (0–10)
- `object_database.py` — SQLite catalogue with full-text search, type/magnitude filters
- `seed_catalogs.py` — 200+ objects: 110 Messier, 48 bright stars, 20 NGC/IC, 9 solar system bodies
- `target_planner.py` — nightly best-target ranking with imaging window estimates
- `session_logger.py` — timestamped `.log` + `_events.json` per session

#### Mount backends
- `SimulatorMount` — thread-safe animated slewing and tracking simulation
- `ASCOMAlpacaMount` — full ASCOM Alpaca HTTP/REST adapter
- `INDIMount` — structural scaffold ready for PyIndi implementation

#### Camera backends
- `SimulatorCamera` — generates synthetic 16-bit FITS star-field images
- `FolderWatchCamera` — watchdog-based tethered shooting import
- `GPhoto2Camera` — scaffold for libgphoto2 (Canon/Nikon/Sony DSLRs)
- `INDICamera` — scaffold for INDI CCD devices

#### Plate solver backends
- `SimulatorSolver` — realistic Gaussian pointing errors for testing
- `AstrometryLocalSolver` — wraps the `solve-field` command-line tool
- `AstrometryRemoteSolver` — nova.astrometry.net REST API adapter

#### PySide6 UI
- Dark astronomy theme with Night Vision Mode (red/dim)
- Sky Map — azimuthal equidistant projection, live mount and target markers,
  Tonight's Best Targets sidebar
- Object Search — full-text + type/magnitude filters, live Alt/Az and imaging notes
- Telescope Control — connect/slew/sync/park, always-visible Emergency Stop
- Camera Control — single-frame capture with progress bar
- Imaging Sequence — multi-frame builder with pause/resume/abort
- Plate Solver — solve any image, display results, one-click mount sync
- Session Log — live event viewer
- Settings — observer location presets, device backends, Night Vision toggle

#### Safety
- Emergency Stop button always visible in toolbar
- Sun slewing disabled by default
- Horizon and meridian limit placeholders in mount base class

#### Tests
- 84 passing unit and integration tests covering coordinate math, database CRUD,
  mount simulator, camera simulator, and full end-to-end imaging workflow

#### Documentation
- `README.md` with install, run, and packaging instructions
- `HARDWARE_SETUP.md` — mount/camera/solver hardware guide
- `USER_GUIDE.md` — step-by-step night session walkthrough
- `DEVELOPER_GUIDE.md` — plugin/extension architecture guide
