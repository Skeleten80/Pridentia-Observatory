"""
Settings panel — observer location, device configuration, and application preferences.

Settings are persisted to ~/PrudentiaObservatory/prudentia_observatory_settings.json
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..core.models import ObserverLocation

log = logging.getLogger(__name__)

_SETTINGS_PATH = os.path.join(
    os.path.expanduser("~"), "PrudentiaObservatory", "prudentia_observatory_settings.json"
)

_PRESET_SITES: list[dict] = [
    {"name": "Custom", "lat": 0.0, "lon": 0.0, "elev": 0.0},
    {"name": "Mauna Kea, HI", "lat": 19.8207, "lon": -155.4681, "elev": 4205.0},
    {"name": "La Palma, Canary Islands", "lat": 28.7623, "lon": -17.8825, "elev": 2396.0},
    {"name": "Cerro Paranal, Chile", "lat": -24.6272, "lon": -70.4048, "elev": 2635.0},
    {"name": "Kitt Peak, AZ", "lat": 31.9583, "lon": -111.5967, "elev": 2096.0},
    {"name": "New York, NY", "lat": 40.7128, "lon": -74.0060, "elev": 10.0},
    {"name": "London, UK", "lat": 51.5074, "lon": -0.1278, "elev": 11.0},
    {"name": "Sydney, AU", "lat": -33.8688, "lon": 151.2093, "elev": 58.0},
    {"name": "Tokyo, JP", "lat": 35.6762, "lon": 139.6503, "elev": 40.0},
]


def load_settings() -> dict:
    """Load settings from disk, returning defaults if the file does not exist."""
    defaults: dict = {
        "observer": {
            "name": "My Observatory",
            "latitude": 0.0,
            "longitude": 0.0,
            "elevation": 0.0,
            "timezone": "UTC",
        },
        "mount": {
            "backend": "simulator",
            "alpaca_host": "localhost",
            "alpaca_port": 11111,
            "alpaca_device": 0,
            "indi_host": "localhost",
            "indi_port": 7624,
            "indi_driver": "EQMod Mount",
        },
        "camera": {
            "backend": "simulator",
            "fast_sim": False,
            "watch_dir": os.path.expanduser("~/Pictures/Tethered"),
        },
        "solver": {
            "backend": "simulator",
            "astrometry_api_key": "",
            "hint_radius": 15.0,
        },
        "ui": {
            "night_vision": False,
            "horizon_limit": 10.0,
            "save_dir": os.path.join(os.path.expanduser("~"), "PrudentiaObservatory", "images"),
        },
    }
    if os.path.isfile(_SETTINGS_PATH):
        try:
            with open(_SETTINGS_PATH, encoding="utf-8") as f:
                saved = json.load(f)
            # Deep-merge saved into defaults
            for section, vals in saved.items():
                if section in defaults and isinstance(vals, dict):
                    defaults[section].update(vals)
                else:
                    defaults[section] = vals
        except (OSError, json.JSONDecodeError):
            log.warning("Could not read settings from %s; using defaults.", _SETTINGS_PATH)
    return defaults


def save_settings(settings: dict) -> None:
    os.makedirs(os.path.dirname(_SETTINGS_PATH), exist_ok=True)
    with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
    log.info("Settings saved to %s", _SETTINGS_PATH)


class SettingsPanel(QWidget):
    """
    Settings panel widget displayed in the Settings tab.

    Emits settings_changed when the user clicks Save.
    """

    settings_changed = Signal(dict)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._settings = load_settings()
        self._build_ui()
        self._populate()

    # ─────────────────────────────────────────────────────────────────────────
    # UI construction
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        vbox = QVBoxLayout(inner)
        vbox.setSpacing(16)
        vbox.setContentsMargins(16, 16, 16, 16)

        vbox.addWidget(self._build_observer_group())
        vbox.addWidget(self._build_mount_group())
        vbox.addWidget(self._build_camera_group())
        vbox.addWidget(self._build_solver_group())
        vbox.addWidget(self._build_ui_group())
        vbox.addStretch()

        save_btn = QPushButton("Save Settings")
        save_btn.setProperty("role", "primary")
        save_btn.setFixedHeight(38)
        save_btn.clicked.connect(self._save)
        vbox.addWidget(save_btn)

        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _build_observer_group(self) -> QGroupBox:
        grp = QGroupBox("Observer Location")
        form = QFormLayout(grp)
        form.setSpacing(8)

        self._site_combo = QComboBox()
        for s in _PRESET_SITES:
            self._site_combo.addItem(s["name"])
        self._site_combo.currentIndexChanged.connect(self._on_preset_changed)
        form.addRow("Preset Site:", self._site_combo)

        self._obs_name = QLineEdit()
        form.addRow("Site Name:", self._obs_name)

        self._lat = QDoubleSpinBox()
        self._lat.setRange(-90.0, 90.0)
        self._lat.setDecimals(6)
        self._lat.setSuffix("°")
        form.addRow("Latitude:", self._lat)

        self._lon = QDoubleSpinBox()
        self._lon.setRange(-180.0, 180.0)
        self._lon.setDecimals(6)
        self._lon.setSuffix("°")
        form.addRow("Longitude:", self._lon)

        self._elev = QDoubleSpinBox()
        self._elev.setRange(-400.0, 9000.0)
        self._elev.setDecimals(1)
        self._elev.setSuffix(" m")
        form.addRow("Elevation:", self._elev)

        self._tz = QLineEdit()
        self._tz.setPlaceholderText("UTC, America/New_York, Europe/London …")
        form.addRow("Time Zone:", self._tz)

        return grp

    def _build_mount_group(self) -> QGroupBox:
        grp = QGroupBox("Telescope Mount")
        form = QFormLayout(grp)
        form.setSpacing(8)

        self._mount_backend = QComboBox()
        self._mount_backend.addItems(["simulator", "ascom_alpaca", "indi"])
        form.addRow("Backend:", self._mount_backend)

        self._alpaca_host = QLineEdit()
        form.addRow("Alpaca Host:", self._alpaca_host)

        self._alpaca_port = QSpinBox()
        self._alpaca_port.setRange(1, 65535)
        form.addRow("Alpaca Port:", self._alpaca_port)

        self._alpaca_device = QSpinBox()
        self._alpaca_device.setRange(0, 99)
        form.addRow("Alpaca Device #:", self._alpaca_device)

        self._indi_host = QLineEdit()
        form.addRow("INDI Host:", self._indi_host)

        self._indi_port = QSpinBox()
        self._indi_port.setRange(1, 65535)
        form.addRow("INDI Port:", self._indi_port)

        self._indi_driver = QLineEdit()
        form.addRow("INDI Driver:", self._indi_driver)

        return grp

    def _build_camera_group(self) -> QGroupBox:
        grp = QGroupBox("Camera")
        form = QFormLayout(grp)
        form.setSpacing(8)

        self._cam_backend = QComboBox()
        self._cam_backend.addItems(["simulator", "gphoto2", "indi", "folder_watch"])
        form.addRow("Backend:", self._cam_backend)

        self._cam_fast_sim = QCheckBox("Fast simulation (instant exposures)")
        form.addRow("", self._cam_fast_sim)

        self._cam_watch_dir = QLineEdit()
        form.addRow("Watch Directory:", self._cam_watch_dir)

        self._save_dir = QLineEdit()
        form.addRow("Image Save Directory:", self._save_dir)

        return grp

    def _build_solver_group(self) -> QGroupBox:
        grp = QGroupBox("Plate Solver")
        form = QFormLayout(grp)
        form.setSpacing(8)

        self._solver_backend = QComboBox()
        self._solver_backend.addItems(["simulator", "astrometry_local", "astrometry_remote"])
        form.addRow("Backend:", self._solver_backend)

        self._astro_api_key = QLineEdit()
        self._astro_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._astro_api_key.setPlaceholderText("nova.astrometry.net API key")
        form.addRow("API Key:", self._astro_api_key)

        self._hint_radius = QDoubleSpinBox()
        self._hint_radius.setRange(0.5, 180.0)
        self._hint_radius.setDecimals(1)
        self._hint_radius.setSuffix("°")
        form.addRow("Hint Radius:", self._hint_radius)

        return grp

    def _build_ui_group(self) -> QGroupBox:
        grp = QGroupBox("Interface")
        form = QFormLayout(grp)
        form.setSpacing(8)

        self._night_vision = QCheckBox("Enable Night Vision Mode (red UI)")
        form.addRow("", self._night_vision)

        self._horizon_limit = QDoubleSpinBox()
        self._horizon_limit.setRange(0.0, 45.0)
        self._horizon_limit.setDecimals(1)
        self._horizon_limit.setSuffix("°")
        form.addRow("Horizon Limit:", self._horizon_limit)

        return grp

    # ─────────────────────────────────────────────────────────────────────────
    # Data ↔ Widget
    # ─────────────────────────────────────────────────────────────────────────

    def _populate(self) -> None:
        s = self._settings
        obs = s["observer"]
        self._obs_name.setText(obs.get("name", "My Observatory"))
        self._lat.setValue(obs.get("latitude", 0.0))
        self._lon.setValue(obs.get("longitude", 0.0))
        self._elev.setValue(obs.get("elevation", 0.0))
        self._tz.setText(obs.get("timezone", "UTC"))

        mnt = s["mount"]
        idx = self._mount_backend.findText(mnt.get("backend", "simulator"))
        if idx >= 0:
            self._mount_backend.setCurrentIndex(idx)
        self._alpaca_host.setText(mnt.get("alpaca_host", "localhost"))
        self._alpaca_port.setValue(mnt.get("alpaca_port", 11111))
        self._alpaca_device.setValue(mnt.get("alpaca_device", 0))
        self._indi_host.setText(mnt.get("indi_host", "localhost"))
        self._indi_port.setValue(mnt.get("indi_port", 7624))
        self._indi_driver.setText(mnt.get("indi_driver", "EQMod Mount"))

        cam = s["camera"]
        idx = self._cam_backend.findText(cam.get("backend", "simulator"))
        if idx >= 0:
            self._cam_backend.setCurrentIndex(idx)
        self._cam_fast_sim.setChecked(cam.get("fast_sim", False))
        self._cam_watch_dir.setText(cam.get("watch_dir", ""))
        self._save_dir.setText(s["ui"].get("save_dir", ""))

        sol = s["solver"]
        idx = self._solver_backend.findText(sol.get("backend", "simulator"))
        if idx >= 0:
            self._solver_backend.setCurrentIndex(idx)
        self._astro_api_key.setText(sol.get("astrometry_api_key", ""))
        self._hint_radius.setValue(sol.get("hint_radius", 15.0))

        ui = s["ui"]
        self._night_vision.setChecked(ui.get("night_vision", False))
        self._horizon_limit.setValue(ui.get("horizon_limit", 10.0))

    def _collect(self) -> dict:
        return {
            "observer": {
                "name": self._obs_name.text(),
                "latitude": self._lat.value(),
                "longitude": self._lon.value(),
                "elevation": self._elev.value(),
                "timezone": self._tz.text() or "UTC",
            },
            "mount": {
                "backend": self._mount_backend.currentText(),
                "alpaca_host": self._alpaca_host.text(),
                "alpaca_port": self._alpaca_port.value(),
                "alpaca_device": self._alpaca_device.value(),
                "indi_host": self._indi_host.text(),
                "indi_port": self._indi_port.value(),
                "indi_driver": self._indi_driver.text(),
            },
            "camera": {
                "backend": self._cam_backend.currentText(),
                "fast_sim": self._cam_fast_sim.isChecked(),
                "watch_dir": self._cam_watch_dir.text(),
            },
            "solver": {
                "backend": self._solver_backend.currentText(),
                "astrometry_api_key": self._astro_api_key.text(),
                "hint_radius": self._hint_radius.value(),
            },
            "ui": {
                "night_vision": self._night_vision.isChecked(),
                "horizon_limit": self._horizon_limit.value(),
                "save_dir": self._save_dir.text(),
            },
        }

    def _save(self) -> None:
        self._settings = self._collect()
        save_settings(self._settings)
        self.settings_changed.emit(self._settings)
        QMessageBox.information(self, "Settings Saved",
                                "Settings have been saved successfully.")

    def _on_preset_changed(self, index: int) -> None:
        if index == 0:
            return
        site = _PRESET_SITES[index]
        self._obs_name.setText(site["name"])
        self._lat.setValue(site["lat"])
        self._lon.setValue(site["lon"])
        self._elev.setValue(site["elev"])

    def get_observer_location(self) -> ObserverLocation:
        obs = self._settings["observer"]
        return ObserverLocation(
            name=obs.get("name", "My Observatory"),
            latitude_degrees=obs.get("latitude", 0.0),
            longitude_degrees=obs.get("longitude", 0.0),
            elevation_meters=obs.get("elevation", 0.0),
            timezone=obs.get("timezone", "UTC"),
        )

    def get_settings(self) -> dict:
        return self._settings
