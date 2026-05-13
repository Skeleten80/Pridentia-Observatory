"""
Object search panel — search the local catalogue and view detailed target info.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..core.astronomy_engine import compute_target_info, degrees_to_dms, degrees_to_hms
from ..core.models import CelestialObject, ObjectType, ObserverLocation, TargetInfo
from ..core.object_database import ObjectDatabase

log = logging.getLogger(__name__)


class _SearchThread(QThread):
    results_ready = Signal(list)

    def __init__(self, db: ObjectDatabase, query: str, types: list[str], max_mag: Optional[float]) -> None:
        super().__init__()
        self._db = db
        self._query = query
        self._types = types
        self._max_mag = max_mag

    def run(self) -> None:
        results = self._db.search(
            query=self._query,
            object_types=self._types or None,
            max_magnitude=self._max_mag,
            limit=200,
        )
        self.results_ready.emit(results)


class ObjectSearchPanel(QWidget):
    """
    Object search and detail panel.

    Signals
    -------
    slew_to_target(CelestialObject) — user clicked "Slew to Target"
    target_selected(CelestialObject) — user selected an object in the list
    """

    slew_to_target = Signal(object)     # CelestialObject
    target_selected = Signal(object)    # CelestialObject

    def __init__(
        self,
        db: ObjectDatabase,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._db = db
        self._observer = ObserverLocation()
        self._search_thread: Optional[_SearchThread] = None
        self._selected_object: Optional[CelestialObject] = None
        self._build_ui()

    # ─────────────────────────────────────────────────────────────────────────
    # UI
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Left: search controls ────────────────────────────────────────────
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(12, 12, 8, 12)
        left_layout.setSpacing(8)

        title = QLabel("Object Search")
        title.setProperty("role", "title")
        left_layout.addWidget(title)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search by name, catalogue ID…")
        self._search_input.textChanged.connect(self._trigger_search)
        left_layout.addWidget(self._search_input)

        # Type filter
        type_grp = QGroupBox("Filter by Type")
        type_col = QVBoxLayout(type_grp)
        self._type_checks: dict[str, QCheckBox] = {}
        for obj_type in [
            ObjectType.GALAXY, ObjectType.NEBULA, ObjectType.OPEN_CLUSTER,
            ObjectType.GLOBULAR_CLUSTER, ObjectType.PLANETARY_NEBULA,
            ObjectType.STAR, ObjectType.DOUBLE_STAR,
            ObjectType.PLANET, ObjectType.MOON, ObjectType.SUN,
        ]:
            cb = QCheckBox(obj_type.value)
            self._type_checks[obj_type.value] = cb
            type_col.addWidget(cb)
            cb.stateChanged.connect(self._trigger_search)

        left_layout.addWidget(type_grp)

        # Magnitude filter
        mag_grp = QGroupBox("Max Magnitude")
        mag_row = QHBoxLayout(mag_grp)
        self._chk_mag = QCheckBox()
        self._spin_mag = QDoubleSpinBox()
        self._spin_mag.setRange(-30.0, 30.0)
        self._spin_mag.setValue(12.0)
        self._spin_mag.setDecimals(1)
        self._chk_mag.stateChanged.connect(self._trigger_search)
        self._spin_mag.valueChanged.connect(self._trigger_search)
        mag_row.addWidget(self._chk_mag)
        mag_row.addWidget(self._spin_mag)
        left_layout.addWidget(mag_grp)

        # Results list
        self._results_list = QListWidget()
        self._results_list.currentItemChanged.connect(self._on_item_selected)
        left_layout.addWidget(self._results_list, stretch=1)

        self._lbl_count = QLabel("0 objects found")
        self._lbl_count.setProperty("role", "subtitle")
        left_layout.addWidget(self._lbl_count)

        # Populate on start
        btn_all = QPushButton("Show All Objects")
        btn_all.clicked.connect(self._show_all)
        left_layout.addWidget(btn_all)

        # ── Right: object detail ──────────────────────────────────────────────
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 12, 12, 12)
        right_layout.setSpacing(8)

        detail_title = QLabel("Object Details")
        detail_title.setProperty("role", "title")
        right_layout.addWidget(detail_title)

        detail_grp = QGroupBox("Catalogue Information")
        detail_form = QFormLayout(detail_grp)
        self._det: dict[str, QLabel] = {}
        for key in ["Name", "Type", "Catalogue IDs", "RA (J2000)", "Dec (J2000)",
                    "Magnitude", "Angular Size", "Constellation", "Description"]:
            lbl = QLabel("--")
            lbl.setProperty("role", "value")
            lbl.setWordWrap(True)
            detail_form.addRow(f"{key}:", lbl)
            self._det[key] = lbl
        right_layout.addWidget(detail_grp)

        sky_grp = QGroupBox("Sky Position (Now)")
        sky_form = QFormLayout(sky_grp)
        for key in ["Altitude", "Azimuth", "Airmass", "Moon Separation",
                    "Transit Time", "Rise Time", "Set Time", "Imaging Score"]:
            lbl = QLabel("--")
            lbl.setProperty("role", "value")
            sky_form.addRow(f"{key}:", lbl)
            self._det[key] = lbl
        right_layout.addWidget(sky_grp)

        note_grp = QGroupBox("Imaging Notes")
        note_layout = QVBoxLayout(note_grp)
        self._lbl_note = QLabel("Select an object to see imaging recommendations.")
        self._lbl_note.setWordWrap(True)
        note_layout.addWidget(self._lbl_note)
        right_layout.addWidget(note_grp)

        self._btn_slew = QPushButton("Slew to This Target")
        self._btn_slew.setProperty("role", "primary")
        self._btn_slew.setFixedHeight(38)
        self._btn_slew.setEnabled(False)
        self._btn_slew.clicked.connect(self._on_slew_clicked)
        right_layout.addWidget(self._btn_slew)

        right_layout.addStretch()

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([340, 460])

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(splitter)

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def set_observer(self, observer: ObserverLocation) -> None:
        self._observer = observer

    # ─────────────────────────────────────────────────────────────────────────
    # Slots
    # ─────────────────────────────────────────────────────────────────────────

    def _trigger_search(self) -> None:
        query = self._search_input.text().strip()
        active_types = [t for t, cb in self._type_checks.items() if cb.isChecked()]
        max_mag = self._spin_mag.value() if self._chk_mag.isChecked() else None

        if self._search_thread and self._search_thread.isRunning():
            self._search_thread.quit()

        self._search_thread = _SearchThread(self._db, query, active_types, max_mag)
        self._search_thread.results_ready.connect(self._on_results_ready)
        self._search_thread.start()

    def _show_all(self) -> None:
        self._search_input.clear()
        for cb in self._type_checks.values():
            cb.setChecked(False)
        self._chk_mag.setChecked(False)
        self._trigger_search()

    @Slot(list)
    def _on_results_ready(self, objects: list[CelestialObject]) -> None:
        self._results_list.clear()
        for obj in objects:
            mag_str = f"  V={obj.magnitude:.1f}" if obj.magnitude is not None else ""
            label = f"{obj.display_name}  [{obj.object_type.value}]{mag_str}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, obj)
            self._results_list.addItem(item)
        self._lbl_count.setText(f"{len(objects)} objects found")

    def _on_item_selected(self, current: Optional[QListWidgetItem], _prev) -> None:
        if current is None:
            return
        obj: CelestialObject = current.data(Qt.ItemDataRole.UserRole)
        if obj is None:
            return
        self._selected_object = obj
        self._populate_detail(obj)
        self._btn_slew.setEnabled(True)
        self.target_selected.emit(obj)

    def _populate_detail(self, obj: CelestialObject) -> None:
        self._det["Name"].setText(obj.display_name)
        self._det["Type"].setText(obj.object_type.value)
        self._det["Catalogue IDs"].setText(", ".join(obj.catalogue_ids) or "--")
        self._det["RA (J2000)"].setText(degrees_to_hms(obj.ra_hours * 15))
        self._det["Dec (J2000)"].setText(degrees_to_dms(obj.dec_degrees))
        self._det["Magnitude"].setText(f"{obj.magnitude:.2f}" if obj.magnitude is not None else "N/A")
        self._det["Angular Size"].setText(f"{obj.angular_size_arcmin:.1f}'" if obj.angular_size_arcmin else "N/A")
        self._det["Constellation"].setText(obj.constellation or "--")
        self._det["Description"].setText(obj.description or "--")

        # Compute live sky data
        try:
            info: TargetInfo = compute_target_info(obj, self._observer)
            self._det["Altitude"].setText(f"{info.altaz.altitude_degrees:.2f}°")
            self._det["Azimuth"].setText(f"{info.altaz.azimuth_degrees:.2f}°")
            am = info.airmass
            self._det["Airmass"].setText(f"{am:.2f}" if am < 90 else "Below horizon")
            self._det["Moon Separation"].setText(f"{info.moon_separation_degrees:.1f}°")
            self._det["Transit Time"].setText(
                info.transit_time.strftime("%H:%M UTC") if info.transit_time else "--"
            )
            self._det["Rise Time"].setText(
                info.rise_time.strftime("%H:%M UTC") if info.rise_time else "--"
            )
            self._det["Set Time"].setText(
                info.set_time.strftime("%H:%M UTC") if info.set_time else "--"
            )
            self._det["Imaging Score"].setText(f"{info.imaging_score:.1f} / 10")

            from ..core.target_planner import _exposure_note
            self._lbl_note.setText(_exposure_note(obj))
        except Exception as exc:
            log.debug("Could not compute sky info for %s: %s", obj.display_name, exc)
            for k in ["Altitude", "Azimuth", "Airmass", "Moon Separation",
                      "Transit Time", "Rise Time", "Set Time", "Imaging Score"]:
                self._det[k].setText("--")

    def _on_slew_clicked(self) -> None:
        if self._selected_object:
            self.slew_to_target.emit(self._selected_object)
