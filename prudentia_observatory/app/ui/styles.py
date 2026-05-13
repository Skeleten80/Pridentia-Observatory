"""
Qt style sheets for Prudentia Observatory's dark astronomy UI.

Two themes are provided:
  - DARK_THEME: Navy/black professional observatory look.
  - NIGHT_VISION_THEME: Deep red mode to preserve dark adaptation.
"""

DARK_THEME = """
QMainWindow, QDialog, QWidget {
    background-color: #0d1117;
    color: #c9d1d9;
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

QFrame {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
}

QGroupBox {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 8px;
    color: #8b949e;
    font-size: 11px;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 1px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    color: #58a6ff;
}

QLabel {
    color: #c9d1d9;
    background-color: transparent;
    border: none;
}

QLabel[role="title"] {
    font-size: 18px;
    font-weight: bold;
    color: #58a6ff;
}

QLabel[role="subtitle"] {
    font-size: 11px;
    color: #8b949e;
}

QLabel[role="value"] {
    color: #e6edf3;
    font-family: "Consolas", "Courier New", monospace;
}

QLabel[role="status-ok"] { color: #3fb950; }
QLabel[role="status-warn"] { color: #d29922; }
QLabel[role="status-error"] { color: #f85149; }

QPushButton {
    background-color: #21262d;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 16px;
    font-size: 13px;
}

QPushButton:hover {
    background-color: #30363d;
    border-color: #58a6ff;
    color: #e6edf3;
}

QPushButton:pressed {
    background-color: #1f6feb;
    border-color: #388bfd;
    color: #ffffff;
}

QPushButton:disabled {
    background-color: #161b22;
    color: #484f58;
    border-color: #21262d;
}

QPushButton[role="primary"] {
    background-color: #1f6feb;
    color: #ffffff;
    border-color: #388bfd;
    font-weight: bold;
}

QPushButton[role="primary"]:hover {
    background-color: #388bfd;
}

QPushButton[role="danger"] {
    background-color: #b91c1c;
    color: #ffffff;
    border-color: #ef4444;
    font-weight: bold;
    font-size: 14px;
}

QPushButton[role="danger"]:hover {
    background-color: #dc2626;
}

QPushButton[role="success"] {
    background-color: #1a7f37;
    color: #ffffff;
    border-color: #3fb950;
}

QPushButton[role="success"]:hover {
    background-color: #2ea043;
}

QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #0d1117;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 4px 8px;
    selection-background-color: #1f6feb;
}

QLineEdit:focus, QTextEdit:focus {
    border-color: #58a6ff;
}

QComboBox {
    background-color: #21262d;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 4px 8px;
    min-width: 80px;
}

QComboBox:hover { border-color: #58a6ff; }

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox QAbstractItemView {
    background-color: #161b22;
    color: #c9d1d9;
    border: 1px solid #30363d;
    selection-background-color: #1f6feb;
}

QSpinBox, QDoubleSpinBox {
    background-color: #21262d;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 4px;
}

QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #58a6ff;
}

QSlider::groove:horizontal {
    background: #30363d;
    height: 4px;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: #58a6ff;
    width: 14px;
    height: 14px;
    border-radius: 7px;
    margin: -5px 0;
}

QProgressBar {
    background-color: #21262d;
    border: 1px solid #30363d;
    border-radius: 4px;
    text-align: center;
    color: #c9d1d9;
    font-size: 11px;
}

QProgressBar::chunk {
    background-color: #1f6feb;
    border-radius: 3px;
}

QTabWidget::pane {
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-radius: 6px;
}

QTabBar::tab {
    background-color: #161b22;
    color: #8b949e;
    border: 1px solid #30363d;
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}

QTabBar::tab:selected {
    background-color: #0d1117;
    color: #58a6ff;
    border-bottom-color: #0d1117;
}

QTabBar::tab:hover {
    background-color: #21262d;
    color: #c9d1d9;
}

QListWidget, QTreeWidget, QTableWidget {
    background-color: #0d1117;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    alternate-background-color: #161b22;
    gridline-color: #21262d;
}

QListWidget::item, QTreeWidget::item, QTableWidget::item {
    padding: 4px;
}

QListWidget::item:selected, QTreeWidget::item:selected, QTableWidget::item:selected {
    background-color: #1f6feb;
    color: #ffffff;
}

QListWidget::item:hover, QTreeWidget::item:hover, QTableWidget::item:hover {
    background-color: #21262d;
}

QHeaderView::section {
    background-color: #161b22;
    color: #8b949e;
    border: none;
    border-bottom: 1px solid #30363d;
    padding: 6px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

QScrollBar:vertical {
    background: #161b22;
    width: 8px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #484f58;
    border-radius: 4px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover { background: #8b949e; }

QScrollBar:horizontal {
    background: #161b22;
    height: 8px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal {
    background: #484f58;
    border-radius: 4px;
    min-width: 30px;
}

QScrollBar::add-line, QScrollBar::sub-line { background: none; }

QSplitter::handle {
    background-color: #30363d;
    width: 4px;
    height: 4px;
}

QMenuBar {
    background-color: #161b22;
    color: #c9d1d9;
    border-bottom: 1px solid #30363d;
}

QMenuBar::item:selected { background-color: #21262d; }

QMenu {
    background-color: #161b22;
    color: #c9d1d9;
    border: 1px solid #30363d;
}

QMenu::item:selected { background-color: #1f6feb; }

QStatusBar {
    background-color: #161b22;
    color: #8b949e;
    border-top: 1px solid #30363d;
    font-size: 11px;
}

QToolTip {
    background-color: #161b22;
    color: #c9d1d9;
    border: 1px solid #30363d;
    padding: 4px;
}

QCheckBox {
    color: #c9d1d9;
    spacing: 6px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #484f58;
    border-radius: 3px;
    background: #0d1117;
}

QCheckBox::indicator:checked {
    background: #1f6feb;
    border-color: #388bfd;
}

QRadioButton {
    color: #c9d1d9;
    spacing: 6px;
}
"""

NIGHT_VISION_THEME = DARK_THEME.replace(
    "#58a6ff", "#cc3300"
).replace(
    "#1f6feb", "#990000"
).replace(
    "#388bfd", "#cc2200"
).replace(
    "#3fb950", "#882200"
).replace(
    "#c9d1d9", "#cc4400"
).replace(
    "#e6edf3", "#dd5500"
).replace(
    "#8b949e", "#993300"
).replace(
    "#0d1117", "#0a0000"
).replace(
    "#161b22", "#120000"
).replace(
    "#21262d", "#1a0000"
).replace(
    "#30363d", "#330000"
).replace(
    "#484f58", "#441100"
)

STATUS_LED_CSS = {
    "ok":      "background-color: #3fb950; border-radius: 6px; min-width: 12px; min-height: 12px; max-width: 12px; max-height: 12px;",
    "warn":    "background-color: #d29922; border-radius: 6px; min-width: 12px; min-height: 12px; max-width: 12px; max-height: 12px;",
    "error":   "background-color: #f85149; border-radius: 6px; min-width: 12px; min-height: 12px; max-width: 12px; max-height: 12px;",
    "off":     "background-color: #484f58; border-radius: 6px; min-width: 12px; min-height: 12px; max-width: 12px; max-height: 12px;",
    "blue":    "background-color: #58a6ff; border-radius: 6px; min-width: 12px; min-height: 12px; max-width: 12px; max-height: 12px;",
}
