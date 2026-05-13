"""
Prudentia Observatory — application entry point.

Run with:
    python -m prudentia_observatory.app.main

Or after pip install:
    prudentia
"""

from __future__ import annotations

import logging
import os
import sys


def _configure_logging() -> None:
    log_dir = os.path.join(os.path.expanduser("~"), "PrudentiaObservatory", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "prudentia_app.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )
    # Silence very chatty third-party loggers
    logging.getLogger("astropy").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("watchdog").setLevel(logging.WARNING)


def main() -> None:
    _configure_logging()
    log = logging.getLogger(__name__)
    log.info("Starting Prudentia Observatory v%s", _get_version())

    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt

    app = QApplication(sys.argv)
    app.setApplicationName("Prudentia Observatory")
    app.setOrganizationName("Prudentia Observatory")
    app.setApplicationVersion(_get_version())

    # High-DPI support
    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        app.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, "AA_UseHighDpiPixmaps"):
        app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    from .ui.main_window import MainWindow
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


def _get_version() -> str:
    try:
        from prudentia_observatory import __version__
        return __version__
    except ImportError:
        return "0.1.0"


if __name__ == "__main__":
    main()
