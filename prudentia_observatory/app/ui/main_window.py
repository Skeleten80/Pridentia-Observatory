"""
Prudentia Observatory main application window.

Wires together all panels, manages device backends, and coordinates the
guided imaging workflow.  The night-vision toggle, emergency stop, and status
bar are always accessible regardless of which tab is active.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QCloseEvent, QFont, QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..cameras.base_camera import BaseCamera
from ..cameras.simulator_camera import SimulatorCamera
from ..core.models import CelestialObject, ObserverLocation, SkyCoordinate
from ..core.object_database import ObjectDatabase
from ..core.session_logger import SessionLogger
from ..mounts.base_mount import BaseMount
from ..mounts.simulator_mount import SimulatorMount
from ..platesolve.base_solver import BaseSolver
from ..platesolve.simulator_solver import SimulatorSolver
from .camera_panel import CameraPanel
from .imaging_sequence_panel import ImagingSequencePanel
from .object_search import ObjectSearchPanel
from .platesolve_panel import PlateSolvePanel
from .settings_panel import SettingsPanel, load_settings
from .sky_map import SkyMapPanel
from .styles import DARK_THEME, NIGHT_VISION_THEME, STATUS_LED_CSS
from .telescope_panel import TelescopePanel

log = logging.getLogger(__name__)


def _make_mount(settings: dict) -> BaseMount:
    backend = settings.get("mount", {}).get("backend", "simulator")
    if backend == "ascom_alpaca":
        from ..mounts.ascom_alpaca_mount import ASCOMAlpacaMount
        mnt = settings["mount"]
        return ASCOMAlpacaMount(
            host=mnt.get("alpaca_host", "localhost"),
            port=mnt.get("alpaca_port", 11111),
            device_number=mnt.get("alpaca_device", 0),
        )
    if backend == "indi":
        from ..mounts.indi_mount import INDIMount
        mnt = settings["mount"]
        return INDIMount(
            host=mnt.get("indi_host", "localhost"),
            port=mnt.get("indi_port", 7624),
            driver_name=mnt.get("indi_driver", "EQMod Mount"),
        )
    return SimulatorMount()


def _make_camera(settings: dict) -> BaseCamera:
    backend = settings.get("camera", {}).get("backend", "simulator")
    if backend == "gphoto2":
        from ..cameras.gphoto_camera import GPhoto2Camera
        return GPhoto2Camera()
    if backend == "indi":
        from ..cameras.indi_camera import INDICamera
        cam = settings["mount"]  # reuse INDI host
        return INDICamera(host=cam.get("indi_host", "localhost"))
    if backend == "folder_watch":
        from ..cameras.folder_watch_camera import FolderWatchCamera
        return FolderWatchCamera(watch_dir=settings["camera"].get("watch_dir"))
    fast = settings.get("camera", {}).get("fast_sim", False)
    return SimulatorCamera(fast_mode=fast)


def _make_solver(settings: dict) -> BaseSolver:
    backend = settings.get("solver", {}).get("backend", "simulator")
    if backend == "astrometry_local":
        from ..platesolve.astrometry_local_solver import AstrometryLocalSolver
        return AstrometryLocalSolver()
    if backend == "astrometry_remote":
        from ..platesolve.astrometry_remote_solver import AstrometryRemoteSolver
        return AstrometryRemoteSolver(
            api_key=settings["solver"].get("astrometry_api_key", "")
        )
    return SimulatorSolver()


class MainWindow(QMainWindow):
    """Primary application window for Prudentia Observatory."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Prudentia Observatory")
        self.setMinimumSize(1280, 800)
        self.resize(1440, 900)

        self._settings = load_settings()
        self._night_vision = self._settings.get("ui", {}).get("night_vision", False)
        self._session_log: Optional[SessionLogger] = None

        self._init_devices()
        self._init_database()
        self._build_ui()
        self._wire_signals()
        self._apply_theme()
        self._seed_database_if_needed()

        # Periodic status refresh
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._refresh_statusbar)
        self._status_timer.start(2000)

    # ─────────────────────────────────────────────────────────────────────────
    # Initialisation
    # ─────────────────────────────────────────────────────────────────────────

    def _init_devices(self) -> None:
        self._mount: BaseMount = _make_mount(self._settings)
        self._camera: BaseCamera = _make_camera(self._settings)
        self._solver: BaseSolver = _make_solver(self._settings)

    def _init_database(self) -> None:
        self._db = ObjectDatabase()

    def _seed_database_if_needed(self) -> None:
        if self._db.count() == 0:
            log.info("Empty catalogue detected — seeding database…")
            from ..data.seed_catalogs import seed
            seed(self._db)
            # Reload objects into panels
            objects = self._db.all_objects(limit=2000)
            self._sky_map.set_objects(objects)
            log.info("Database seeded: %d objects", len(objects))

    # ─────────────────────────────────────────────────────────────────────────
    # UI build
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._build_toolbar())
        outer.addWidget(self._build_tabs(), stretch=1)

        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._refresh_statusbar()

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(52)
        bar.setStyleSheet("background-color: #0d1929; border-bottom: 1px solid #30363d;")
        hl = QHBoxLayout(bar)
        hl.setContentsMargins(16, 8, 16, 8)

        # Brand name
        brand = QLabel("Prudentia Observatory")
        brand.setFont(QFont("Arial", 15, QFont.Weight.Bold))
        brand.setStyleSheet("color: #58a6ff; background: transparent; border: none;")
        hl.addWidget(brand)

        hl.addStretch()

        # UTC clock
        self._lbl_clock = QLabel("UTC 00:00:00")
        self._lbl_clock.setStyleSheet("color: #8b949e; background: transparent; border: none; font-family: monospace;")
        hl.addWidget(self._lbl_clock)

        # Night vision toggle
        self._btn_nv = QPushButton("🔴  Night Vision")
        self._btn_nv.setCheckable(True)
        self._btn_nv.setChecked(self._night_vision)
        self._btn_nv.setFixedHeight(32)
        self._btn_nv.clicked.connect(self._toggle_night_vision)
        hl.addWidget(self._btn_nv)

        # Status LEDs
        for label, attr in [("Mount", "_mount_led"), ("Camera", "_camera_led"), ("Solver", "_solver_led")]:
            row = QHBoxLayout()
            led = QLabel()
            led.setStyleSheet(STATUS_LED_CSS["off"])
            setattr(self, attr, led)
            row.addWidget(led)
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #8b949e; background: transparent; border: none; font-size: 11px;")
            row.addWidget(lbl)
            hl.addLayout(row)

        # Emergency stop — always visible
        estop = QPushButton("⬛ STOP")
        estop.setProperty("role", "danger")
        estop.setFixedHeight(36)
        estop.setToolTip("Emergency Stop — immediately halts all mount motion")
        estop.clicked.connect(self._emergency_stop)
        hl.addWidget(estop)

        # Clock update timer
        clock_timer = QTimer(self)
        clock_timer.timeout.connect(self._update_clock)
        clock_timer.start(1000)

        return bar

    def _build_tabs(self) -> QTabWidget:
        tabs = QTabWidget()
        tabs.setTabPosition(QTabWidget.TabPosition.West)

        # ── Sky Map ──────────────────────────────────────────────────────────
        self._sky_map = SkyMapPanel()
        tabs.addTab(self._sky_map, "Sky Map")

        # ── Object Search ────────────────────────────────────────────────────
        self._object_search = ObjectSearchPanel(self._db)
        tabs.addTab(self._object_search, "Object Search")

        # ── Telescope ────────────────────────────────────────────────────────
        self._telescope = TelescopePanel()
        self._telescope.set_mount(self._mount)
        tabs.addTab(self._telescope, "Telescope")

        # ── Camera ───────────────────────────────────────────────────────────
        self._camera_panel = CameraPanel()
        self._camera_panel.set_camera(self._camera)
        self._camera_panel.set_save_dir(
            self._settings.get("ui", {}).get("save_dir",
            os.path.join(os.path.expanduser("~"), "PrudentiaObservatory", "images"))
        )
        tabs.addTab(self._camera_panel, "Camera")

        # ── Imaging Sequence ─────────────────────────────────────────────────
        self._sequence_panel = ImagingSequencePanel()
        self._sequence_panel.set_camera(self._camera)
        tabs.addTab(self._sequence_panel, "Sequence")

        # ── Plate Solver ─────────────────────────────────────────────────────
        self._solver_panel = PlateSolvePanel()
        self._solver_panel.set_solver(self._solver)
        tabs.addTab(self._solver_panel, "Plate Solver")

        # ── Session Log ──────────────────────────────────────────────────────
        self._log_widget = self._build_log_widget()
        tabs.addTab(self._log_widget, "Session Log")

        # ── Settings ─────────────────────────────────────────────────────────
        self._settings_panel = SettingsPanel()
        tabs.addTab(self._settings_panel, "Settings")

        return tabs

    def _build_log_widget(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)

        title = QLabel("Session Log")
        title.setProperty("role", "title")
        layout.addWidget(title)

        from PySide6.QtWidgets import QPlainTextEdit
        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setFont(QFont("Consolas", 10))
        self._log_view.setMaximumBlockCount(5000)
        layout.addWidget(self._log_view, stretch=1)

        btn_row = QHBoxLayout()
        btn_new = QPushButton("New Session Log")
        btn_new.clicked.connect(self._start_new_session_log)
        btn_row.addWidget(btn_new)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        return w

    # ─────────────────────────────────────────────────────────────────────────
    # Signal wiring
    # ─────────────────────────────────────────────────────────────────────────

    def _wire_signals(self) -> None:
        # Object search → telescope slew
        self._object_search.slew_to_target.connect(self._on_slew_to_object)
        self._object_search.target_selected.connect(self._on_target_selected)

        # Sky map → object search and telescope
        self._sky_map.target_selected.connect(self._on_slew_to_object)

        # Camera capture → plate solver
        self._camera_panel.capture_complete.connect(self._solver_panel.set_image)

        # Plate solver sync → mount
        self._solver_panel.sync_mount.connect(self._telescope.set_slew_target)

        # Settings changed → restart devices
        self._settings_panel.settings_changed.connect(self._on_settings_changed)

        # Telescope mount connected → update UI LEDs
        self._telescope.mount_connected.connect(self._on_mount_connected)
        self._camera_panel.camera_connected.connect(self._on_camera_connected)

        # Sequence → log
        self._sequence_panel.sequence_started.connect(lambda: self._log_append("Sequence started."))
        self._sequence_panel.sequence_finished.connect(
            lambda ab: self._log_append("Sequence " + ("aborted." if ab else "complete."))
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Slots
    # ─────────────────────────────────────────────────────────────────────────

    def _on_slew_to_object(self, obj: CelestialObject) -> None:
        coord = obj.coordinate
        self._telescope.set_slew_target(coord, obj.display_name)
        if self._session_log:
            self._session_log.log_slew(obj.display_name, coord.ra_hours, coord.dec_degrees)
        self._log_append(f"Target set: {obj.display_name}")
        # Update sky map target marker
        from ..core.astronomy_engine import altaz_from_radec
        try:
            loc = self._settings_panel.get_observer_location()
            altaz = altaz_from_radec(coord.ra_hours, coord.dec_degrees, loc)
            self._sky_map.set_target_altaz(altaz.altitude_degrees, altaz.azimuth_degrees)
        except Exception:
            pass
        # Pre-fill sequence target
        self._sequence_panel.set_target(obj.display_name, coord)
        # Pre-fill solver hint
        self._solver_panel.set_hint(coord)

    def _on_target_selected(self, obj: CelestialObject) -> None:
        pass  # future: highlight on sky map

    def _on_mount_connected(self, connected: bool) -> None:
        self._mount_led.setStyleSheet(STATUS_LED_CSS["ok" if connected else "off"])
        if connected and self._session_log is None:
            self._start_new_session_log()
        if connected:
            self._log_append("Mount connected.")

    def _on_camera_connected(self, connected: bool) -> None:
        self._camera_led.setStyleSheet(STATUS_LED_CSS["ok" if connected else "off"])
        if connected:
            self._log_append("Camera connected.")

    def _on_settings_changed(self, settings: dict) -> None:
        self._settings = settings
        self._night_vision = settings.get("ui", {}).get("night_vision", False)
        self._apply_theme()
        # Update observer location across all panels
        loc = self._settings_panel.get_observer_location()
        self._object_search.set_observer(loc)
        self._sky_map.set_observer(loc)
        self._sequence_panel.set_observer(loc)
        self._sequence_panel.set_save_dir(
            settings.get("ui", {}).get("save_dir",
            os.path.join(os.path.expanduser("~"), "PrudentiaObservatory", "images"))
        )
        # Re-create device backends with new config
        self._mount = _make_mount(settings)
        self._camera = _make_camera(settings)
        self._solver = _make_solver(settings)
        self._telescope.set_mount(self._mount)
        self._camera_panel.set_camera(self._camera)
        self._sequence_panel.set_camera(self._camera)
        self._solver_panel.set_solver(self._solver)
        self._log_append("Settings applied — devices re-initialised.")

    def _emergency_stop(self) -> None:
        log.warning("Emergency stop triggered from toolbar")
        self._mount.emergency_stop()
        self._log_append("⚠ EMERGENCY STOP")
        if self._session_log:
            self._session_log.warning("EMERGENCY STOP triggered by user")

    def _toggle_night_vision(self, checked: bool) -> None:
        self._night_vision = checked
        self._apply_theme()
        self._sky_map.set_night_vision(checked)
        if self._settings_panel:
            self._settings_panel._night_vision.setChecked(checked)

    def _start_new_session_log(self) -> None:
        if self._session_log:
            self._session_log.close()
        self._session_log = SessionLogger()
        self._session_log.info("Session started. Prudentia Observatory ready.")
        self._sequence_panel.set_session_log(self._session_log)
        loc = self._settings_panel.get_observer_location()
        self._session_log.info(
            f"Observer: {loc.name} ({loc.latitude_degrees:.4f}°, "
            f"{loc.longitude_degrees:.4f}°, {loc.elevation_meters:.0f}m)"
        )
        self._log_append(f"Session log: {self._session_log.log_path}")

    # ─────────────────────────────────────────────────────────────────────────
    # Timer callbacks
    # ─────────────────────────────────────────────────────────────────────────

    def _update_clock(self) -> None:
        now = datetime.now(tz=timezone.utc)
        self._lbl_clock.setText(now.strftime("UTC %H:%M:%S"))

    def _refresh_statusbar(self) -> None:
        loc = self._settings_panel.get_observer_location()
        mount_state = "Disconnected"
        if self._mount.is_connected:
            try:
                st = self._mount.get_status()
                mount_state = st.state.value
                self._sky_map.set_mount_status(st)
                # Update sky map mount position
            except Exception:
                pass
        cam_state = "Disconnected"
        if self._camera.is_connected:
            try:
                cs = self._camera.get_status()
                cam_state = cs.state.value
            except Exception:
                pass
        self._statusbar.showMessage(
            f"  {loc.name}  |  Mount: {mount_state}  |  Camera: {cam_state}  "
            f"|  DB: {self._db.count()} objects"
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Theme
    # ─────────────────────────────────────────────────────────────────────────

    def _apply_theme(self) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.instance().setStyleSheet(
            NIGHT_VISION_THEME if self._night_vision else DARK_THEME
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Log helper
    # ─────────────────────────────────────────────────────────────────────────

    def _log_append(self, text: str) -> None:
        ts = datetime.now(tz=timezone.utc).strftime("%H:%M:%S")
        self._log_view.appendPlainText(f"[{ts}] {text}")

    # ─────────────────────────────────────────────────────────────────────────
    # Close
    # ─────────────────────────────────────────────────────────────────────────

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._session_log:
            self._session_log.close()
        if self._mount.is_connected:
            self._mount.disconnect()
        if self._camera.is_connected:
            self._camera.disconnect()
        event.accept()
