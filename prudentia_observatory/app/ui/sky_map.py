"""
Interactive sky map panel — renders an azimuthal equidistant projection of the sky.

Shows:
  - Horizon circle and cardinal directions
  - Altitude grid rings (30°, 60° rings)
  - Current telescope position (reticle)
  - Target position (crosshair)
  - Loaded catalogue objects (colour-coded by type)
  - Tonight's best targets list

Rendering uses Qt's QPainter; no external graphics engine is required.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Optional

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..core.astronomy_engine import altaz_from_radec, compute_target_info
from ..core.models import CelestialObject, MountStatus, ObserverLocation, ObjectType

log = logging.getLogger(__name__)

# Colour by object type
_TYPE_COLORS = {
    ObjectType.GALAXY: "#c678dd",
    ObjectType.NEBULA: "#56b6c2",
    ObjectType.OPEN_CLUSTER: "#e5c07b",
    ObjectType.GLOBULAR_CLUSTER: "#d19a66",
    ObjectType.PLANETARY_NEBULA: "#98c379",
    ObjectType.SUPERNOVA_REMNANT: "#e06c75",
    ObjectType.STAR: "#abb2bf",
    ObjectType.DOUBLE_STAR: "#61afef",
    ObjectType.PLANET: "#f9c74f",
    ObjectType.MOON: "#adb5bd",
    ObjectType.SUN: "#ffd60a",
    ObjectType.UNKNOWN: "#6c757d",
}


def _altaz_to_xy(
    alt: float, az: float, radius: float, cx: float, cy: float
) -> QPointF:
    """Map an alt/az pair to pixel coordinates in an azimuthal projection."""
    # r = 0 at zenith (alt 90°), r = radius at horizon (alt 0°)
    r = radius * (90.0 - alt) / 90.0
    az_rad = math.radians(az)
    x = cx + r * math.sin(az_rad)
    y = cy - r * math.cos(az_rad)
    return QPointF(x, y)


class SkyCanvas(QWidget):
    """The actual painted sky-map widget."""

    object_clicked = Signal(object)   # CelestialObject

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(400, 400)
        self._observer = ObserverLocation()
        self._objects: list[CelestialObject] = []
        self._mount_status: Optional[MountStatus] = None
        self._target_coord: Optional[tuple[float, float]] = None  # (alt, az)
        self._night_vision = False

    def set_observer(self, observer: ObserverLocation) -> None:
        self._observer = observer
        self.update()

    def set_objects(self, objects: list[CelestialObject]) -> None:
        self._objects = objects
        self.update()

    def set_mount_status(self, status: Optional[MountStatus]) -> None:
        self._mount_status = status
        self.update()

    def set_target(self, alt: float, az: float) -> None:
        self._target_coord = (alt, az)
        self.update()

    def set_night_vision(self, enabled: bool) -> None:
        self._night_vision = enabled
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        radius = min(w, h) / 2 - 20

        bg = QColor("#050a0f") if not self._night_vision else QColor("#0a0000")
        painter.fillRect(0, 0, w, h, bg)

        self._draw_grid(painter, cx, cy, radius)
        self._draw_objects(painter, cx, cy, radius)
        self._draw_target(painter, cx, cy, radius)
        self._draw_mount(painter, cx, cy, radius)
        self._draw_labels(painter, cx, cy, radius)

    def _draw_grid(self, p: QPainter, cx: float, cy: float, r: float) -> None:
        nv = self._night_vision
        grid_color = QColor("#220000" if nv else "#1a2433")
        horizon_color = QColor("#441100" if nv else "#1f6feb")
        label_color = QColor("#cc3300" if nv else "#8b949e")

        # Altitude rings
        for alt in [0, 30, 60]:
            ring_r = r * (90 - alt) / 90
            p.setPen(QPen(horizon_color if alt == 0 else grid_color, 1 if alt > 0 else 2))
            p.drawEllipse(QPointF(cx, cy), ring_r, ring_r)
            if alt > 0:
                p.setPen(QPen(label_color))
                p.drawText(QPointF(cx + 4, cy - ring_r + 14), f"{alt}°")

        # Cardinal directions
        p.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        p.setPen(QPen(QColor("#cc3300" if nv else "#58a6ff")))
        for label, az in [("N", 0), ("E", 90), ("S", 180), ("W", 270)]:
            pt = _altaz_to_xy(0, az, r, cx, cy)
            p.drawText(QPointF(pt.x() - 5, pt.y() + 5), label)

    def _draw_objects(self, p: QPainter, cx: float, cy: float, r: float) -> None:
        now = datetime.now(tz=timezone.utc)
        for obj in self._objects:
            try:
                altaz = altaz_from_radec(obj.ra_hours, obj.dec_degrees, self._observer, now)
            except Exception:
                continue
            if altaz.altitude_degrees < -5:
                continue

            pt = _altaz_to_xy(altaz.altitude_degrees, altaz.azimuth_degrees, r, cx, cy)
            color = QColor(_TYPE_COLORS.get(obj.object_type, "#6c757d"))
            if self._night_vision:
                color = QColor("#cc3300")

            mag = obj.magnitude or 10.0
            dot_r = max(2.0, min(6.0, 8.0 - mag * 0.5))

            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(color))
            p.drawEllipse(pt, dot_r, dot_r)

    def _draw_target(self, p: QPainter, cx: float, cy: float, r: float) -> None:
        if self._target_coord is None:
            return
        alt, az = self._target_coord
        if alt < 0:
            return
        pt = _altaz_to_xy(alt, az, r, cx, cy)
        color = QColor("#ff4400" if self._night_vision else "#56e36c")
        p.setPen(QPen(color, 2))
        size = 12
        p.drawLine(QPointF(pt.x() - size, pt.y()), QPointF(pt.x() + size, pt.y()))
        p.drawLine(QPointF(pt.x(), pt.y() - size), QPointF(pt.x(), pt.y() + size))
        p.drawEllipse(pt, size / 2, size / 2)

    def _draw_mount(self, p: QPainter, cx: float, cy: float, r: float) -> None:
        if self._mount_status is None or not self._mount_status.ra_hours:
            return
        try:
            from ..core.astronomy_engine import altaz_from_radec
            altaz = altaz_from_radec(
                self._mount_status.ra_hours,
                self._mount_status.dec_degrees,
                self._observer,
                datetime.now(tz=timezone.utc),
            )
        except Exception:
            return
        pt = _altaz_to_xy(altaz.altitude_degrees, altaz.azimuth_degrees, r, cx, cy)
        color = QColor("#880000" if self._night_vision else "#f0a500")
        p.setPen(QPen(color, 2))
        size = 10
        p.drawLine(QPointF(pt.x() - size, pt.y() - size), QPointF(pt.x() + size, pt.y() + size))
        p.drawLine(QPointF(pt.x() + size, pt.y() - size), QPointF(pt.x() - size, pt.y() + size))

    def _draw_labels(self, p: QPainter, cx: float, cy: float, r: float) -> None:
        p.setFont(QFont("Arial", 8))
        color = QColor("#cc3300" if self._night_vision else "#58a6ff")
        p.setPen(QPen(color))
        p.drawText(QRectF(cx - r, cy - r, r * 2, 20), Qt.AlignmentFlag.AlignHCenter, "Zenith")


class SkyMapPanel(QWidget):
    """Full sky map panel with canvas and Tonight's Best Targets sidebar."""

    target_selected = Signal(object)     # CelestialObject

    def __init__(
        self,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._observer = ObserverLocation()
        self._objects: list[CelestialObject] = []
        self._build_ui()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._update_best_targets)
        self._refresh_timer.start(60_000)  # refresh best targets every minute

    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Sky canvas ───────────────────────────────────────────────────────
        self._canvas = SkyCanvas()
        splitter.addWidget(self._canvas)

        # ── Sidebar: best targets ─────────────────────────────────────────────
        sidebar = QWidget()
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(8, 8, 8, 8)
        sb_layout.setSpacing(8)

        sb_title = QLabel("Tonight's Best Targets")
        sb_title.setProperty("role", "title")
        sb_layout.addWidget(sb_title)

        self._best_list = QListWidget()
        self._best_list.setAlternatingRowColors(True)
        self._best_list.itemDoubleClicked.connect(self._on_best_item_clicked)
        sb_layout.addWidget(self._best_list, stretch=1)

        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self._update_best_targets)
        sb_layout.addWidget(btn_refresh)

        splitter.addWidget(sidebar)
        splitter.setSizes([600, 240])

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(splitter)

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def set_observer(self, observer: ObserverLocation) -> None:
        self._observer = observer
        self._canvas.set_observer(observer)
        self._update_best_targets()

    def set_objects(self, objects: list[CelestialObject]) -> None:
        self._objects = objects
        self._canvas.set_objects(objects)
        self._update_best_targets()

    def set_mount_status(self, status: Optional[MountStatus]) -> None:
        self._canvas.set_mount_status(status)

    def set_target_altaz(self, alt: float, az: float) -> None:
        self._canvas.set_target(alt, az)

    def set_night_vision(self, enabled: bool) -> None:
        self._canvas.set_night_vision(enabled)

    # ─────────────────────────────────────────────────────────────────────────
    # Internal
    # ─────────────────────────────────────────────────────────────────────────

    def _update_best_targets(self) -> None:
        self._best_list.clear()
        now = datetime.now(tz=timezone.utc)
        scored: list[tuple[float, CelestialObject]] = []
        for obj in self._objects[:300]:
            if obj.object_type == ObjectType.SUN:
                continue
            try:
                info = compute_target_info(obj, self._observer, now)
                if info.altaz.altitude_degrees >= 15:
                    scored.append((info.imaging_score, obj))
            except Exception:
                pass
        scored.sort(reverse=True, key=lambda x: x[0])
        for score, obj in scored[:30]:
            mag = f"  V={obj.magnitude:.1f}" if obj.magnitude is not None else ""
            label = f"{obj.display_name}  [{obj.object_type.value}]{mag}  ★{score:.1f}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, obj)
            self._best_list.addItem(item)

    def _on_best_item_clicked(self, item: QListWidgetItem) -> None:
        obj: CelestialObject = item.data(Qt.ItemDataRole.UserRole)
        if obj:
            self.target_selected.emit(obj)
