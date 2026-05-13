"""
Plate solver panel UI — trigger a solve, display results, and sync the mount.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QThread, Signal, Slot
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.models import SkyCoordinate, SolveResult
from ..platesolve.base_solver import BaseSolver
from .styles import STATUS_LED_CSS

log = logging.getLogger(__name__)


class _SolveThread(QThread):
    solve_complete = Signal(object)   # SolveResult

    def __init__(self, solver: BaseSolver, image_path: str, hint: Optional[SkyCoordinate]) -> None:
        super().__init__()
        self._solver = solver
        self._image_path = image_path
        self._hint = hint

    def run(self) -> None:
        result = self._solver.solve(self._image_path, self._hint)
        self.solve_complete.emit(result)


class PlateSolvePanel(QWidget):
    """Plate solve panel — solve an image and optionally sync the mount."""

    sync_mount = Signal(object)   # SkyCoordinate

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._solver: Optional[BaseSolver] = None
        self._last_image: str = ""
        self._hint_coord: Optional[SkyCoordinate] = None
        self._solve_thread: Optional[_SolveThread] = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel("Plate Solver")
        title.setProperty("role", "title")
        hdr.addWidget(title)
        hdr.addStretch()
        self._led = QLabel()
        self._led.setStyleSheet(STATUS_LED_CSS["off"])
        hdr.addWidget(self._led)
        self._status_lbl = QLabel("Idle")
        hdr.addWidget(self._status_lbl)
        layout.addLayout(hdr)

        # ── Input ─────────────────────────────────────────────────────────────
        in_grp = QGroupBox("Input")
        in_form = QFormLayout(in_grp)

        self._input_image = QLineEdit()
        self._input_image.setPlaceholderText("Path to FITS / JPEG image…")
        in_form.addRow("Image:", self._input_image)

        self._input_hint_ra = QLineEdit()
        self._input_hint_ra.setPlaceholderText("HH:MM:SS (optional)")
        in_form.addRow("Hint RA:", self._input_hint_ra)

        self._input_hint_dec = QLineEdit()
        self._input_hint_dec.setPlaceholderText("±DD:MM:SS (optional)")
        in_form.addRow("Hint Dec:", self._input_hint_dec)

        layout.addWidget(in_grp)

        # ── Result ────────────────────────────────────────────────────────────
        res_grp = QGroupBox("Solve Result")
        res_form = QFormLayout(res_grp)
        self._res: dict[str, QLabel] = {}
        for key in ["Solved RA", "Solved Dec", "Rotation", "Pixel Scale",
                    "RA Error", "Dec Error", "Total Error", "Solve Time"]:
            lbl = QLabel("--")
            lbl.setProperty("role", "value")
            res_form.addRow(f"{key}:", lbl)
            self._res[key] = lbl
        layout.addWidget(res_grp)

        # ── Actions ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        self._btn_solve = QPushButton("Plate Solve")
        self._btn_solve.setProperty("role", "primary")
        self._btn_solve.clicked.connect(self._on_solve)
        btn_row.addWidget(self._btn_solve)

        self._btn_sync = QPushButton("Sync Mount to Solve")
        self._btn_sync.clicked.connect(self._on_sync)
        self._btn_sync.setEnabled(False)
        btn_row.addWidget(self._btn_sync)
        layout.addLayout(btn_row)

        layout.addStretch()

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def set_solver(self, solver: BaseSolver) -> None:
        self._solver = solver

    def set_image(self, path: str) -> None:
        self._last_image = path
        self._input_image.setText(path)

    def set_hint(self, coord: SkyCoordinate) -> None:
        self._hint_coord = coord
        from ..core.astronomy_engine import degrees_to_hms, degrees_to_dms
        self._input_hint_ra.setText(degrees_to_hms(coord.ra_degrees))
        self._input_hint_dec.setText(degrees_to_dms(coord.dec_degrees))

    # ─────────────────────────────────────────────────────────────────────────
    # Slots
    # ─────────────────────────────────────────────────────────────────────────

    def _on_solve(self) -> None:
        if self._solver is None:
            self._status_lbl.setText("No solver configured.")
            return
        image_path = self._input_image.text().strip()
        if not image_path:
            self._status_lbl.setText("Provide an image path.")
            return

        hint: Optional[SkyCoordinate] = None
        from ..core.astronomy_engine import parse_ra_hms, parse_dec_dms
        ra_h = parse_ra_hms(self._input_hint_ra.text().strip())
        dec_d = parse_dec_dms(self._input_hint_dec.text().strip())
        if ra_h is not None and dec_d is not None:
            hint = SkyCoordinate(ra_h, dec_d)

        self._led.setStyleSheet(STATUS_LED_CSS["blue"])
        self._status_lbl.setText("Solving…")
        self._btn_solve.setEnabled(False)
        self._btn_sync.setEnabled(False)

        self._solve_thread = _SolveThread(self._solver, image_path, hint)
        self._solve_thread.solve_complete.connect(self._on_solve_complete)
        self._solve_thread.start()

    @Slot(object)
    def _on_solve_complete(self, result: SolveResult) -> None:
        self._btn_solve.setEnabled(True)
        if result.success:
            self._led.setStyleSheet(STATUS_LED_CSS["ok"])
            self._status_lbl.setText("Solved!")
            from ..core.astronomy_engine import degrees_to_hms, degrees_to_dms
            self._res["Solved RA"].setText(degrees_to_hms(result.ra_hours * 15))
            self._res["Solved Dec"].setText(degrees_to_dms(result.dec_degrees))
            self._res["Rotation"].setText(f"{result.rotation_degrees:.2f}°")
            self._res["Pixel Scale"].setText(
                f"{result.pixel_scale_arcsec:.2f}\"/px" if result.pixel_scale_arcsec else "--"
            )
            self._res["RA Error"].setText(f"{result.ra_error_arcmin:.1f}'")
            self._res["Dec Error"].setText(f"{result.dec_error_arcmin:.1f}'")
            self._res["Total Error"].setText(f"{result.total_error_arcmin:.1f}'")
            self._res["Solve Time"].setText(f"{result.solver_time_seconds:.1f}s")
            self._btn_sync.setEnabled(True)
            self._last_solve_result = result
        else:
            self._led.setStyleSheet(STATUS_LED_CSS["error"])
            self._status_lbl.setText(f"Failed: {result.message}")

    def _on_sync(self) -> None:
        if hasattr(self, "_last_solve_result"):
            coord = SkyCoordinate(
                self._last_solve_result.ra_hours,
                self._last_solve_result.dec_degrees,
            )
            self.sync_mount.emit(coord)
            self._status_lbl.setText("Sync requested.")
