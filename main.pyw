"""Application entry point."""

from __future__ import annotations

import os
import sys

from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QApplication

from config import SCRIPT_DIR
from ui import ModernRadioApp
from utils import ensure_runtime_directories, load_persisted_station_order


APP_ID = "coleman.radio.player.v3"


def _build_fallback_icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#000000"))
    painter.setPen(QPen(QColor("#45f3ff"), 3))
    painter.drawRoundedRect(2, 2, 60, 60, 12, 12)
    painter.setPen(QPen(QColor("#ffffff"), 2))
    painter.drawText(QRect(0, 0, 64, 64), Qt.AlignmentFlag.AlignCenter, "R")
    painter.end()
    return QIcon(pixmap)


def _load_app_icon() -> QIcon:
    icon_ico_path = os.path.join(SCRIPT_DIR, "icon.ico")
    icon_png_path = os.path.join(SCRIPT_DIR, "icon.png")
    if os.path.exists(icon_ico_path):
        return QIcon(icon_ico_path)
    if os.path.exists(icon_png_path):
        return QIcon(icon_png_path)
    return _build_fallback_icon()


def run() -> int:
    ensure_runtime_directories()
    load_persisted_station_order()

    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except Exception as exc:
            print(f"Taskbar grouping optimization failure: {exc}")

    app = QApplication(sys.argv)
    app.setWindowIcon(_load_app_icon())

    window = ModernRadioApp()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())

