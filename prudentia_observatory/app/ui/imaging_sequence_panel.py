"""
Imaging sequence panel — build, run, pause, and abort a multi-frame sequence.

Runs the sequence in a background QThread so the UI stays responsive.
Each frame is captured by the camera backend, then metadata is written to the
session log.
"""

from __future__ import annotations

import logging
import os
import datetime
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..cameras.base_camera import BaseCamera, CameraError
from ..core.models import (
    ImagingSequence,
    MountStatus,
    ObserverLocation,
    SequenceFrame,
    SequenceState,
    SessionMetadata,
    SkyCoordinate,
)
from ..core.session_logger import SessionLogger
from .styles import STATUS_LED_CSS

log = logging.getLogger(__name__)


class _SequenceWorker(QThread):
    """Runs all frames in an ImagingSequence on a background thread."""

    frame_started = Signal(int)          # frame index
    frame_complete = Signal(int, str)    # frame index, image path
    frame_failed = Signal(int, str)      # frame index, error message
    sequence_complete = Signal(bool)     # aborted?
    log_message = Signal(str)

    def __init__(
        self,
        sequence: ImagingSequence,
        camera: BaseCamera,
        session_log: SessionLogger,
        mount_status_fn,
        observer: ObserverLocation,
    ) -> None:
        super().__init__()
        self._seq = sequence
        self._camera = camera
        self._log = session_log
        self._get_mount_status = mount_status_fn
        self._observer = observer
        self._abort_requested = False

    def request_abort(self) -> None:
        self._abort_requested = True
        try:
            self._camera.abort()
        except Exception:
            pass

    def run(self) -> None:
        import time
        self._seq.state = SequenceState.RUNNING
        self._log.log_sequence_start(
            self._seq.target_name,
            self._seq.num_lights,
            self._seq.exposure_seconds,
            self._seq.iso,
        )

        for i, frame in enumerate(self._seq.frames):
            if self._abort_requested:
                break

            while self._seq.state == SequenceState.PAUSED:
                time.sleep(0.5)
                if self._abort_requested:
                    break

            if self._abort_requested:
                break

            self.frame_started.emit(i)
            self.log_message.emit(f"Frame {i + 1}/{len(self._seq.frames)} started.")

            try:
                self._camera.set_exposure(frame.exposure_seconds)
                self._camera.set_iso(frame.iso)
                path = self._camera.capture(frame.filename)
                frame.filename = path
                frame.completed = True
                self._seq.current_frame_index = i + 1
                self.frame_complete.emit(i, path)
                self.log_message.emit(f"Frame {i + 1} saved: {path}")

                # Write session metadata
                mst = self._get_mount_status()
                meta = SessionMetadata(
                    target_name=self._seq.target_name,
                    ra_hours=mst.ra_hours if mst else 0.0,
                    dec_degrees=mst.dec_degrees if mst else 0.0,
                    altitude_degrees=mst.altitude_degrees if mst else 0.0,
                    azimuth_degrees=mst.azimuth_degrees if mst else 0.0,
                    exposure_seconds=frame.exposure_seconds,
                    iso=frame.iso,
                    observer_latitude=self._observer.latitude_degrees,
                    observer_longitude=self._observer.longitude_degrees,
                    observer_elevation=self._observer.elevation_meters,
                    utc_datetime=datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
                    software="Prudentia Observatory",
                )
                self._log.log_capture(meta, path)

            except CameraError as exc:
                log.error("Frame %d failed: %s", i + 1, exc)
                self.frame_failed.emit(i, str(exc))
                self.log_message.emit(f"Frame {i + 1} FAILED: {exc}")

            if i < len(self._seq.frames) - 1:
                time.sleep(self._seq.delay_seconds)

        aborted = self._abort_requested
        self._seq.state = SequenceState.ABORTED if aborted else SequenceState.COMPLETED
        done_count = sum(1 for f in self._seq.frames if f.completed)
        self._log.log_sequence_end(self._seq.target_name, done_count, aborted)
        self.sequence_complete.emit(aborted)


class ImagingSequencePanel(QWidget):
    """Full imaging sequence builder and runner panel."""

    sequence_started = Signal()
    sequence_finished = Signal(bool)   # aborted?

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._camera: Optional[BaseCamera] = None
        self._session_log: Optional[SessionLogger] = None
        self._observer = ObserverLocation()
        self._get_mount_status = lambda: None
        self._save_dir = os.path.join(os.path.expanduser("~"), "PrudentiaObservatory", "images")
        self._worker: Optional[_SequenceWorker] = None
        self._current_sequence: Optional[ImagingSequence] = None
        self._build_ui()

    # ─────────────────────────────────────────────────────────────────────────
    # UI construction
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)

        title = QLabel("Imaging Sequence")
        title.setProperty("role", "title")
        layout.addWidget(title)

        # ── Target ──────────────────────────────────────────────────────────
        tgt_grp = QGroupBox("Target")
        tgt_form = QFormLayout(tgt_grp)

        self._input_target = QLineEdit()
        self._input_target.setPlaceholderText("e.g. Orion Nebula / M42")
        tgt_form.addRow("Target Name:", self._input_target)

        layout.addWidget(tgt_grp)

        # ── Sequence parameters ──────────────────────────────────────────────
        seq_grp = QGroupBox("Sequence Parameters")
        seq_form = QFormLayout(seq_grp)

        self._spin_frames = QSpinBox()
        self._spin_frames.setRange(1, 9999)
        self._spin_frames.setValue(10)
        seq_form.addRow("Number of Lights:", self._spin_frames)

        self._spin_exp = QDoubleSpinBox()
        self._spin_exp.setRange(0.1, 3600.0)
        self._spin_exp.setDecimals(1)
        self._spin_exp.setValue(120.0)
        self._spin_exp.setSuffix(" s")
        seq_form.addRow("Exposure:", self._spin_exp)

        self._spin_iso = QSpinBox()
        self._spin_iso.setRange(50, 102400)
        self._spin_iso.setValue(1600)
        self._spin_iso.setSingleStep(100)
        seq_form.addRow("ISO:", self._spin_iso)

        self._spin_delay = QDoubleSpinBox()
        self._spin_delay.setRange(0.0, 60.0)
        self._spin_delay.setDecimals(1)
        self._spin_delay.setValue(2.0)
        self._spin_delay.setSuffix(" s")
        seq_form.addRow("Delay Between Frames:", self._spin_delay)

        self._chk_dither = QCheckBox("Dither (placeholder — requires guider)")
        seq_form.addRow("", self._chk_dither)

        layout.addWidget(seq_grp)

        # ── Progress ─────────────────────────────────────────────────────────
        prog_grp = QGroupBox("Progress")
        prog_layout = QVBoxLayout(prog_grp)

        self._lbl_progress = QLabel("Idle")
        prog_layout.addWidget(self._lbl_progress)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        prog_layout.addWidget(self._progress_bar)

        layout.addWidget(prog_grp)

        # ── Frame log table ──────────────────────────────────────────────────
        self._frame_table = QTableWidget(0, 4)
        self._frame_table.setHorizontalHeaderLabels(["#", "Exp (s)", "ISO", "Status"])
        self._frame_table.horizontalHeader().setStretchLastSection(True)
        self._frame_table.setMaximumHeight(180)
        layout.addWidget(self._frame_table)

        # ── Log output ────────────────────────────────────────────────────────
        from PySide6.QtWidgets import QPlainTextEdit
        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumBlockCount(200)
        self._log_view.setMaximumHeight(120)
        self._log_view.setPlaceholderText("Sequence log…")
        layout.addWidget(self._log_view)

        # ── Control buttons ───────────────────────────────────────────────────
        btn_row = QHBoxLayout()

        self._btn_start = QPushButton("▶  Start Sequence")
        self._btn_start.setProperty("role", "primary")
        self._btn_start.setFixedHeight(38)
        self._btn_start.clicked.connect(self._on_start)
        btn_row.addWidget(self._btn_start)

        self._btn_pause = QPushButton("⏸  Pause")
        self._btn_pause.clicked.connect(self._on_pause)
        self._btn_pause.setEnabled(False)
        btn_row.addWidget(self._btn_pause)

        self._btn_abort = QPushButton("⏹  Abort")
        self._btn_abort.setProperty("role", "danger")
        self._btn_abort.clicked.connect(self._on_abort)
        self._btn_abort.setEnabled(False)
        btn_row.addWidget(self._btn_abort)

        layout.addLayout(btn_row)

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def set_camera(self, camera: BaseCamera) -> None:
        self._camera = camera

    def set_session_log(self, log: SessionLogger) -> None:
        self._session_log = log

    def set_observer(self, observer: ObserverLocation) -> None:
        self._observer = observer

    def set_mount_status_fn(self, fn) -> None:
        self._get_mount_status = fn

    def set_save_dir(self, directory: str) -> None:
        self._save_dir = directory

    def set_target(self, name: str, coord: Optional[SkyCoordinate] = None) -> None:
        self._input_target.setText(name)

    # ─────────────────────────────────────────────────────────────────────────
    # Sequence control
    # ─────────────────────────────────────────────────────────────────────────

    def _on_start(self) -> None:
        if self._camera is None or not self._camera.is_connected:
            self._log_append("Camera is not connected.")
            return

        n = self._spin_frames.value()
        exp = self._spin_exp.value()
        iso = self._spin_iso.value()
        delay = self._spin_delay.value()
        target = self._input_target.text().strip() or "Target"

        os.makedirs(self._save_dir, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")

        frames = []
        self._frame_table.setRowCount(n)
        for i in range(n):
            fname = os.path.join(
                self._save_dir,
                f"{target.replace(' ', '_')}_{ts}_{i + 1:04d}.fits",
            )
            frames.append(SequenceFrame(index=i, exposure_seconds=exp, iso=iso, filename=fname))
            self._frame_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self._frame_table.setItem(i, 1, QTableWidgetItem(str(exp)))
            self._frame_table.setItem(i, 2, QTableWidgetItem(str(iso)))
            self._frame_table.setItem(i, 3, QTableWidgetItem("Pending"))

        seq = ImagingSequence(
            target_name=target,
            num_lights=n,
            exposure_seconds=exp,
            iso=iso,
            delay_seconds=delay,
            save_directory=self._save_dir,
            frames=frames,
        )
        self._current_sequence = seq

        if self._session_log is None:
            from ..core.session_logger import SessionLogger
            self._session_log = SessionLogger()

        self._worker = _SequenceWorker(
            seq, self._camera, self._session_log,
            self._get_mount_status, self._observer,
        )
        self._worker.frame_started.connect(self._on_frame_started)
        self._worker.frame_complete.connect(self._on_frame_complete)
        self._worker.frame_failed.connect(self._on_frame_failed)
        self._worker.sequence_complete.connect(self._on_sequence_complete)
        self._worker.log_message.connect(self._log_append)
        self._worker.start()

        self._btn_start.setEnabled(False)
        self._btn_pause.setEnabled(True)
        self._btn_abort.setEnabled(True)
        self.sequence_started.emit()
        self._log_append(f"Sequence started: {n} × {exp}s @ ISO {iso}")

    def _on_pause(self) -> None:
        if self._current_sequence is None:
            return
        if self._current_sequence.state == SequenceState.RUNNING:
            self._current_sequence.state = SequenceState.PAUSED
            self._btn_pause.setText("▶  Resume")
            self._log_append("Sequence paused.")
        else:
            self._current_sequence.state = SequenceState.RUNNING
            self._btn_pause.setText("⏸  Pause")
            self._log_append("Sequence resumed.")

    def _on_abort(self) -> None:
        if self._worker:
            self._worker.request_abort()
        self._log_append("Abort requested…")

    @Slot(int)
    def _on_frame_started(self, index: int) -> None:
        self._frame_table.setItem(index, 3, QTableWidgetItem("Exposing…"))
        done = index
        total = self._current_sequence.num_lights if self._current_sequence else 1
        self._progress_bar.setValue(int(done / total * 100))
        self._lbl_progress.setText(f"Frame {index + 1} of {total}")

    @Slot(int, str)
    def _on_frame_complete(self, index: int, path: str) -> None:
        self._frame_table.setItem(index, 3, QTableWidgetItem("✓ Done"))
        total = self._current_sequence.num_lights if self._current_sequence else 1
        self._progress_bar.setValue(int((index + 1) / total * 100))

    @Slot(int, str)
    def _on_frame_failed(self, index: int, msg: str) -> None:
        self._frame_table.setItem(index, 3, QTableWidgetItem(f"✗ {msg[:30]}"))

    @Slot(bool)
    def _on_sequence_complete(self, aborted: bool) -> None:
        self._btn_start.setEnabled(True)
        self._btn_pause.setEnabled(False)
        self._btn_abort.setEnabled(False)
        self._btn_pause.setText("⏸  Pause")
        msg = "Sequence aborted." if aborted else "Sequence complete!"
        self._lbl_progress.setText(msg)
        self._log_append(msg)
        self.sequence_finished.emit(aborted)

    def _log_append(self, text: str) -> None:
        self._log_view.appendPlainText(text)
