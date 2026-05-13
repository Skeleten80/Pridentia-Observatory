"""
Camera control panel UI — connect, set exposure/ISO, capture single frame.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..cameras.base_camera import BaseCamera, CameraError
from ..core.models import CameraState, CameraStatus
from .styles import STATUS_LED_CSS

log = logging.getLogger(__name__)


class _CaptureThread(QThread):
    """Run a single capture in a background thread."""

    capture_done = Signal(str)
    capture_failed = Signal(str)

    def __init__(self, camera: BaseCamera, save_path: str) -> None:
        super().__init__()
        self._camera = camera
        self._save_path = save_path

    def run(self) -> None:
        try:
            path = self._camera.capture(self._save_path)
            self.capture_done.emit(path)
        except CameraError as exc:
            self.capture_failed.emit(str(exc))
        except Exception as exc:
            self.capture_failed.emit(f"Unexpected error: {exc}")


class CameraPanel(QWidget):
    """Single-frame camera control panel."""

    capture_complete = Signal(str)    # image path
    camera_connected = Signal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._camera: Optional[BaseCamera] = None
        self._capture_thread: Optional[_CaptureThread] = None
        self._save_dir: str = ""
        self._frame_counter = 0
        self._build_ui()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_status)
        self._refresh_timer.start(500)

    # ─────────────────────────────────────────────────────────────────────────
    # UI construction
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel("Camera Control")
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

        # ── Connection ────────────────────────────────────────────────────────
        conn_row = QHBoxLayout()
        self._btn_connect = QPushButton("Connect Camera")
        self._btn_connect.setProperty("role", "primary")
        self._btn_connect.clicked.connect(self._on_connect)
        conn_row.addWidget(self._btn_connect)

        self._btn_disconnect = QPushButton("Disconnect")
        self._btn_disconnect.clicked.connect(self._on_disconnect)
        self._btn_disconnect.setEnabled(False)
        conn_row.addWidget(self._btn_disconnect)
        layout.addLayout(conn_row)

        # ── Camera info ───────────────────────────────────────────────────────
        info_grp = QGroupBox("Camera Info")
        info_form = QFormLayout(info_grp)

        self._lbl_model = QLabel("--")
        self._lbl_model.setProperty("role", "value")
        info_form.addRow("Model:", self._lbl_model)

        self._lbl_format = QLabel("--")
        self._lbl_format.setProperty("role", "value")
        info_form.addRow("Format:", self._lbl_format)

        self._lbl_last_image = QLabel("(none)")
        self._lbl_last_image.setProperty("role", "value")
        self._lbl_last_image.setWordWrap(True)
        info_form.addRow("Last Image:", self._lbl_last_image)

        layout.addWidget(info_grp)

        # ── Settings ──────────────────────────────────────────────────────────
        cfg_grp = QGroupBox("Exposure Settings")
        cfg_form = QFormLayout(cfg_grp)

        self._spin_exposure = QDoubleSpinBox()
        self._spin_exposure.setRange(0.001, 3600.0)
        self._spin_exposure.setDecimals(1)
        self._spin_exposure.setValue(60.0)
        self._spin_exposure.setSuffix(" s")
        self._spin_exposure.valueChanged.connect(self._on_exposure_changed)
        cfg_form.addRow("Exposure:", self._spin_exposure)

        self._combo_iso = QComboBox()
        for iso in [100, 200, 400, 800, 1600, 3200, 6400, 12800, 25600]:
            self._combo_iso.addItem(str(iso), iso)
        self._combo_iso.setCurrentIndex(4)  # 1600
        self._combo_iso.currentIndexChanged.connect(self._on_iso_changed)
        cfg_form.addRow("ISO:", self._combo_iso)

        layout.addWidget(cfg_grp)

        # ── Capture ───────────────────────────────────────────────────────────
        cap_grp = QGroupBox("Capture")
        cap_layout = QVBoxLayout(cap_grp)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(True)
        self._progress.setFormat("Ready")
        cap_layout.addWidget(self._progress)

        cap_btn_row = QHBoxLayout()
        self._btn_capture = QPushButton("Capture Frame")
        self._btn_capture.setProperty("role", "primary")
        self._btn_capture.clicked.connect(self._on_capture)
        self._btn_capture.setEnabled(False)
        cap_btn_row.addWidget(self._btn_capture)

        self._btn_abort = QPushButton("Abort")
        self._btn_abort.setProperty("role", "danger")
        self._btn_abort.clicked.connect(self._on_abort)
        self._btn_abort.setEnabled(False)
        cap_btn_row.addWidget(self._btn_abort)

        cap_layout.addLayout(cap_btn_row)
        layout.addWidget(cap_grp)
        layout.addStretch()

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def set_camera(self, camera: BaseCamera) -> None:
        self._camera = camera

    def set_save_dir(self, directory: str) -> None:
        self._save_dir = directory

    def get_exposure(self) -> float:
        return self._spin_exposure.value()

    def get_iso(self) -> int:
        return self._combo_iso.currentData()

    # ─────────────────────────────────────────────────────────────────────────
    # Event handlers
    # ─────────────────────────────────────────────────────────────────────────

    def _on_connect(self) -> None:
        if self._camera is None:
            return
        try:
            self._camera.connect()
            self._btn_connect.setEnabled(False)
            self._btn_disconnect.setEnabled(True)
            self._btn_capture.setEnabled(True)
            self.camera_connected.emit(True)
        except CameraError as exc:
            log.error("Camera connect failed: %s", exc)
            self._status_label.setText(f"Error: {exc}")

    def _on_disconnect(self) -> None:
        if self._camera:
            self._camera.disconnect()
        self._btn_connect.setEnabled(True)
        self._btn_disconnect.setEnabled(False)
        self._btn_capture.setEnabled(False)
        self.camera_connected.emit(False)

    def _on_exposure_changed(self, value: float) -> None:
        if self._camera and self._camera.is_connected:
            try:
                self._camera.set_exposure(value)
            except CameraError:
                pass

    def _on_iso_changed(self, _index: int) -> None:
        if self._camera and self._camera.is_connected:
            try:
                self._camera.set_iso(self._combo_iso.currentData())
            except CameraError:
                pass

    def _on_capture(self) -> None:
        if self._camera is None or not self._camera.is_connected:
            return
        import os
        import datetime
        os.makedirs(self._save_dir or ".", exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
        self._frame_counter += 1
        fname = f"frame_{ts}_{self._frame_counter:04d}.fits"
        save_path = os.path.join(self._save_dir or ".", fname)

        self._camera.set_exposure(self._spin_exposure.value())
        self._camera.set_iso(self._combo_iso.currentData())

        self._btn_capture.setEnabled(False)
        self._btn_abort.setEnabled(True)
        self._progress.setFormat("Exposing…")

        self._capture_thread = _CaptureThread(self._camera, save_path)
        self._capture_thread.capture_done.connect(self._on_capture_done)
        self._capture_thread.capture_failed.connect(self._on_capture_failed)
        self._capture_thread.start()

    def _on_abort(self) -> None:
        if self._camera:
            self._camera.abort()
        self._btn_abort.setEnabled(False)
        self._btn_capture.setEnabled(True)
        self._progress.setValue(0)
        self._progress.setFormat("Aborted")

    def _on_capture_done(self, path: str) -> None:
        self._btn_capture.setEnabled(True)
        self._btn_abort.setEnabled(False)
        self._progress.setValue(100)
        self._progress.setFormat("Done")
        self._lbl_last_image.setText(path)
        self.capture_complete.emit(path)

    def _on_capture_failed(self, msg: str) -> None:
        log.error("Capture failed: %s", msg)
        self._btn_capture.setEnabled(True)
        self._btn_abort.setEnabled(False)
        self._progress.setValue(0)
        self._progress.setFormat(f"Error: {msg[:40]}")

    def _refresh_status(self) -> None:
        if self._camera is None or not self._camera.is_connected:
            self._led.setStyleSheet(STATUS_LED_CSS["off"])
            self._status_label.setText("Disconnected")
            return

        try:
            st: CameraStatus = self._camera.get_status()
        except Exception:
            return

        self._lbl_model.setText(st.model)
        self._lbl_format.setText(st.image_format)
        if st.last_image_path:
            self._lbl_last_image.setText(st.last_image_path)

        led_map = {
            CameraState.IDLE: "ok",
            CameraState.EXPOSING: "blue",
            CameraState.DOWNLOADING: "warn",
            CameraState.ERROR: "error",
        }
        self._led.setStyleSheet(STATUS_LED_CSS.get(led_map.get(st.state, "off"), STATUS_LED_CSS["off"]))
        self._status_label.setText(st.state.value)

        if st.state == CameraState.EXPOSING:
            self._progress.setValue(int(st.progress_percent))
            self._progress.setFormat(f"Exposing… {st.progress_percent:.0f}%")
