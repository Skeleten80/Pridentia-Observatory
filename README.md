# Prudentia Observatory

**Intelligent Telescope Tracking & Astrophotography Platform**

Prudentia Observatory is a production-quality cross-platform desktop application for amateur astronomers, astrophotographers, and small private observatories.  The name "Prudentia" reflects the application's design philosophy: precision, careful planning, and intelligent automation.

---

## Features

| Feature | Status |
|---|---|
| Cross-platform (macOS + Windows) | ✅ MVP |
| Simulated telescope mount | ✅ MVP |
| Simulated DSLR camera | ✅ MVP |
| Simulated plate solver | ✅ MVP |
| Astropy coordinate engine | ✅ MVP |
| Local object database (Messier + 200+ objects) | ✅ MVP |
| Interactive sky map | ✅ MVP |
| Object search panel | ✅ MVP |
| Imaging sequence builder | ✅ MVP |
| Session logger | ✅ MVP |
| Night Vision Mode (red UI) | ✅ MVP |
| ASCOM Alpaca mount adapter | ✅ Real HW |
| INDI mount adapter | 🔧 Scaffold |
| gPhoto2 DSLR adapter | 🔧 Scaffold |
| INDI camera adapter | 🔧 Scaffold |
| Local Astrometry.net solver | ✅ Real HW |
| Remote Astrometry.net solver | ✅ Real HW |
| Folder-watch tethering camera | ✅ Real HW |

---

## ⚠ Safety Warnings

> **Real telescope movement can damage equipment if commanded to invalid positions.**
> Always use the simulated backend first.  Test all hardware connections carefully.
>
> **NEVER slew to or image the Sun without a certified solar filter.**
> Permanent eye damage or equipment destruction can result.
>
> Prudentia Observatory disables Sun slewing by default unless Solar Safety Mode
> is explicitly enabled in settings.

---

## Quick Start

### Prerequisites

- Python 3.12 or later
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/skeleten80/pridentia-observatory.git
cd pridentia-observatory

# Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate       # macOS / Linux
.venv\Scripts\activate.bat      # Windows

# Install dependencies
pip install -r requirements.txt

# Or install as a package
pip install -e .
```

### Run the application

```bash
python -m prudentia_observatory.app.main
```

Or after `pip install -e .`:

```bash
prudentia
```

The application opens with all devices in **Simulator** mode — no hardware required.

### First launch

On first launch, Prudentia Observatory automatically seeds its local SQLite
catalogue with:

- All 110 Messier objects
- 48 bright stars (Yale BSC subset, V < 2.5)
- 20 notable NGC/IC objects
- 9 solar system bodies (planets, Moon, Sun)

---

## Project Structure

```
prudentia_observatory/
  app/
    main.py                     ← Entry point
    ui/                         ← PySide6 UI panels
      main_window.py
      sky_map.py
      object_search.py
      telescope_panel.py
      camera_panel.py
      imaging_sequence_panel.py
      platesolve_panel.py
      settings_panel.py
      styles.py
    core/                       ← Astronomy engine and data models
      models.py
      astronomy_engine.py
      object_database.py
      target_planner.py
      session_logger.py
    mounts/                     ← Mount backends
      base_mount.py
      simulator_mount.py
      ascom_alpaca_mount.py
      indi_mount.py
    cameras/                    ← Camera backends
      base_camera.py
      simulator_camera.py
      gphoto_camera.py
      indi_camera.py
      folder_watch_camera.py
    platesolve/                 ← Plate solver backends
      base_solver.py
      simulator_solver.py
      astrometry_local_solver.py
      astrometry_remote_solver.py
    data/
      seed_catalogs.py          ← Catalogue seed data
      catalogs.sqlite           ← Local SQLite database (auto-created)
  tests/
    test_astronomy_engine.py
    test_object_database.py
    test_mount_simulator.py
    test_camera_simulator.py
    test_integration_workflow.py
  docs/
    HARDWARE_SETUP.md
    USER_GUIDE.md
    DEVELOPER_GUIDE.md
```

---

## Running Tests

```bash
pip install pytest pytest-cov
pytest prudentia_observatory/tests/ -v
```

Or with coverage:

```bash
pytest prudentia_observatory/tests/ --cov=prudentia_observatory --cov-report=html
```

---

## Packaging

### macOS

```bash
pip install pyinstaller
pyinstaller --windowed --name "Prudentia Observatory" \
  --add-data "prudentia_observatory/app/data:prudentia_observatory/app/data" \
  prudentia_observatory/app/main.py
```

### Windows

```powershell
pip install pyinstaller
pyinstaller --windowed --name "Prudentia Observatory" `
  --add-data "prudentia_observatory\app\data;prudentia_observatory\app\data" `
  prudentia_observatory\app\main.py
```

---

## Data Sources

The bundled catalogue uses authoritative published values.  The application
**does not** claim to ingest data from observatory networks directly.

| Data | Source |
|---|---|
| Messier catalogue | IAU / SEDS published values |
| Bright stars | Yale Bright Star Catalogue (BSC5) subset |
| NGC / IC objects | Published NGC/IC coordinates |
| Planets / solar system | JPL DE432 via Astropy built-in ephemeris |
| Online lookups (future) | SIMBAD / VizieR / CDS REST APIs |
| Plate solving | Astrometry.net (local or nova.astrometry.net) |

---

## Contributing

See [docs/DEVELOPER_GUIDE.md](prudentia_observatory/docs/DEVELOPER_GUIDE.md).

## License

MIT License.  See LICENSE file.
