"""
Telescope control panel UI — mount connection, slew, tracking, and emergency stop.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.models import MountState, MountStatus, SkyCoordinate
from ..core.astronomy_engine import degrees_to_hms, degrees_to_dms, parse_ra_hms, parse_dec_dms
from ..mounts.base_mount import BaseMount, MountError
from .styles import STATUS_LED_CSS

log = logging.getLogger(__name__)


class TelescopePanel(QWidget):
    """
    Mount control panel.

    Signals
    -------
    slew_requested(SkyCoordinate, str) — emitted when user clicks Slew
    sync_requested(SkyCoordinate)      — emitted when user clicks Sync
    """

    slew_requested = Signal(object, str)   # (SkyCoordinate, target_name)
    sync_requested = Signal(object)        # SkyCoordinate
    mount_connected = Signal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._mount: Optional[BaseMount] = None
        self._build_ui()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_status)
        self._refresh_timer.start(1000)

    # ─────────────────────────────────────────────────────────────────────────
    # UI construction
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel("Telescope Control")
        title.setProperty("role", "title")
        hdr.addWidget(title)
        hdr.addStretch()
        self._led = QLabel()
        self._led.setStyleSheet(STATUS_LED_CSS["off"])
        hdr.addWidget(self._led)
        self._status_label = QLabel("Disconnected")
        self._status_label.setProperty("role", "status-error")
        hdr.addWidget(self._status_label)
        layout.addLayout(hdr)

        # ── Connection buttons ─────────────────────────────────────────────
        conn_row = QHBoxLayout()
        self._btn_connect = QPushButton("Connect Mount")
        self._btn_connect.setProperty("role", "primary")
        self._btn_connect.clicked.connect(self._on_connect)
        conn_row.addWidget(self._btn_connect)

        self._btn_disconnect = QPushButton("Disconnect")
        self._btn_disconnect.clicked.connect(self._on_disconnect)
        self._btn_disconnect.setEnabled(False)
        conn_row.addWidget(self._btn_disconnect)
        layout.addLayout(conn_row)

        # ── Current position ──────────────────────────────────────────────
        pos_grp = QGroupBox("Current Position")
        pos_form = QFormLayout(pos_grp)

        self._lbl_ra = QLabel("--:--:--")
        self._lbl_ra.setProperty("role", "value")
        pos_form.addRow("RA (J2000):", self._lbl_ra)

        self._lbl_dec = QLabel("+--:--:--")
        self._lbl_dec.setProperty("role", "value")
        pos_form.addRow("Dec (J2000):", self._lbl_dec)

        self._lbl_alt = QLabel("---°")
        self._lbl_alt.setProperty("role", "value")
        pos_form.addRow("Altitude:", self._lbl_alt)

        self._lbl_az = QLabel("---°")
        self._lbl_az.setProperty("role", "value")
        pos_form.addRow("Azimuth:", self._lbl_az)

        self._lbl_tracking = QLabel("Not tracking")
        pos_form.addRow("Tracking:", self._lbl_tracking)

        layout.addWidget(pos_grp)

        # ── Slew target ───────────────────────────────────────────────────
        slew_grp = QGroupBox("Slew to Target")
        slew_form = QFormLayout(slew_grp)

        self._input_target = QLineEdit()
        self._input_target.setPlaceholderText("Target name (optional)")
        slew_form.addRow("Target:", self._input_target)

        self._input_ra = QLineEdit()
        self._input_ra.setPlaceholderText("HH:MM:SS  e.g. 05:34:32")
        slew_form.addRow("RA:", self._input_ra)

        self._input_dec = QLineEdit()
        self._input_dec.setPlaceholderText("±DD:MM:SS  e.g. +22:00:52")
        slew_form.addRow("Dec:", self._input_dec)

        slew_row = QHBoxLayout()
        self._btn_slew = QPushButton("Slew to Target")
        self._btn_slew.setProperty("role", "primary")
        self._btn_slew.clicked.connect(self._on_slew)
        self._btn_slew.setEnabled(False)
        slew_row.addWidget(self._btn_slew)

        self._btn_sync = QPushButton("Sync Here")
        self._btn_sync.clicked.connect(self._on_sync)
        self._btn_sync.setEnabled(False)
        slew_row.addWidget(self._btn_sync)
        slew_form.addRow("", slew_row)

        layout.addWidget(slew_grp)

        # ── Tracking and park ─────────────────────────────────────────────
        ctrl_grp = QGroupBox("Mount Control")
        ctrl_row = QHBoxLayout(ctrl_grp)

        self._btn_track_on = QPushButton("Start Tracking")
        self._btn_track_on.setProperty("role", "success")
        self._btn_track_on.clicked.connect(lambda: self._on_tracking(True))
        self._btn_track_on.setEnabled(False)
        ctrl_row.addWidget(self._btn_track_on)

        self._btn_track_off = QPushButton("Stop Tracking")
        self._btn_track_off.clicked.connect(lambda: self._on_tracking(False))
        self._btn_track_off.setEnabled(False)
        ctrl_row.addWidget(self._btn_track_off)

        self._btn_park = QPushButton("Park")
        self._btn_park.clicked.connect(self._on_park)
        self._btn_park.setEnabled(False)
        ctrl_row.addWidget(self._btn_park)

        self._btn_unpark = QPushButton("Unpark")
        self._btn_unpark.clicked.connect(self._on_unpark)
        self._btn_unpark.setEnabled(False)
        ctrl_row.addWidget(self._btn_unpark)

        layout.addWidget(ctrl_grp)

        # ── EMERGENCY STOP ────────────────────────────────────────────────
        self._btn_estop = QPushButton("⬛  EMERGENCY STOP")
        self._btn_estop.setProperty("role", "danger")
        self._btn_estop.setFixedHeight(48)
        self._btn_estop.clicked.connect(self._on_emergency_stop)
        layout.addWidget(self._btn_estop)

        layout.addStretch()

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def set_mount(self, mount: BaseMount) -> None:
        self._mount = mount

    def set_slew_target(self, coord: SkyCoordinate, name: str = "") -> None:
        """Pre-fill the slew target fields from an external source (e.g. object search)."""
        self._input_ra.setText(degrees_to_hms(coord.ra_degrees))
        self._input_dec.setText(degrees_to_dms(coord.dec_degrees))
        self._input_target.setText(name)

    # ─────────────────────────────────────────────────────────────────────────
    # Event handlers
    # ─────────────────────────────────────────────────────────────────────────

    def _on_connect(self) -> None:
        if self._mount is None:
            return
        try:
            self._mount.connect()
            self._btn_connect.setEnabled(False)
            self._btn_disconnect.setEnabled(True)
            self._btn_slew.setEnabled(True)
            self._btn_sync.setEnabled(True)
            self._btn_track_on.setEnabled(True)
            self._btn_track_off.setEnabled(True)
            self._btn_park.setEnabled(True)
            self._btn_unpark.setEnabled(True)
            self.mount_connected.emit(True)
        except MountError as exc:
            log.error("Mount connect failed: %s", exc)
            self._status_label.setText(f"Error: {exc}")

    def _on_disconnect(self) -> None:
        if self._mount:
            self._mount.disconnect()
        self._btn_connect.setEnabled(True)
        self._btn_disconnect.setEnabled(False)
        self._btn_slew.setEnabled(False)
        self._btn_sync.setEnabled(False)
        self._btn_track_on.setEnabled(False)
        self._btn_track_off.setEnabled(False)
        self._btn_park.setEnabled(False)
        self._btn_unpark.setEnabled(False)
        self.mount_connected.emit(False)

    def _on_slew(self) -> None:
        coord = self._parse_coord_inputs()
        if coord is None:
            return
        target_name = self._input_target.text().strip()
        self.slew_requested.emit(coord, target_name)
        if self._mount and self._mount.is_connected:
            try:
                self._mount.slew_to_radec(coord, target_name)
            except MountError as exc:
                log.error("Slew failed: %s", exc)

    def _on_sync(self) -> None:
        coord = self._parse_coord_inputs()
        if coord is None:
            return
        self.sync_requested.emit(coord)
        if self._mount and self._mount.is_connected:
            try:
                self._mount.sync_to_radec(coord)
            except MountError as exc:
                log.error("Sync failed: %s", exc)

    def _on_tracking(self, enabled: bool) -> None:
        if self._mount and self._mount.is_connected:
            try:
                self._mount.set_tracking(enabled)
            except MountError as exc:
                log.error("Tracking change failed: %s", exc)

    def _on_park(self) -> None:
        if self._mount and self._mount.is_connected:
            try:
                self._mount.park()
            except MountError as exc:
                log.error("Park failed: %s", exc)

    def _on_unpark(self) -> None:
        if self._mount and self._mount.is_connected:
            try:
                self._mount.unpark()
            except MountError as exc:
                log.error("Unpark failed: %s", exc)

    def _on_emergency_stop(self) -> None:
        log.warning("Emergency stop triggered from UI")
        if self._mount:
            self._mount.emergency_stop()

    def _parse_coord_inputs(self) -> Optional[SkyCoordinate]:
        ra_text = self._input_ra.text().strip()
        dec_text = self._input_dec.text().strip()
        ra_h = parse_ra_hms(ra_text)
        dec_d = parse_dec_dms(dec_text)
        if ra_h is None or dec_d is None:
            self._status_label.setText("Invalid RA/Dec — use HH:MM:SS and ±DD:MM:SS")
            return None
        return SkyCoordinate(ra_hours=ra_h, dec_degrees=dec_d)

    def _refresh_status(self) -> None:
        if self._mount is None or not self._mount.is_connected:
            self._led.setStyleSheet(STATUS_LED_CSS["off"])
            self._status_label.setText("Disconnected")
            self._status_label.setProperty("role", "status-error")
            self._lbl_ra.setText("--:--:--")
            self._lbl_dec.setText("+--:--:--")
            return

        try:
            st: MountStatus = self._mount.get_status()
        except Exception:
            return

        self._lbl_ra.setText(degrees_to_hms(st.ra_hours * 15))
        self._lbl_dec.setText(degrees_to_dms(st.dec_degrees))
        self._lbl_alt.setText(f"{st.altitude_degrees:.2f}°")
        self._lbl_az.setText(f"{st.azimuth_degrees:.2f}°")
        self._lbl_tracking.setText("Tracking ✓" if st.is_tracking else "Not tracking")

        led_map = {
            MountState.TRACKING: "ok",
            MountState.SLEWING: "blue",
            MountState.PARKED: "warn",
            MountState.IDLE: "warn",
            MountState.ERROR: "error",
        }
        led = led_map.get(st.state, "off")
        self._led.setStyleSheet(STATUS_LED_CSS[led])
        self._status_label.setText(st.state.value)
        self._status_label.setProperty(
            "role",
            "status-ok" if st.state == MountState.TRACKING else "status-warn",
        )
        self._status_label.style().unpolish(self._status_label)
        self._status_label.style().polish(self._status_label)
