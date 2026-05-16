"""Entry point. Wires QApplication, level detector, overlay, and tray together."""
from __future__ import annotations

import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from .config import load_preset
from .detector import LevelDetector
from .overlay import OverlayWindow
from .tray import TrayIcon


def main() -> int:
    # High-DPI screens — make sure pixel math lines up.
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(
            None,
            "Nullscape Overlay",
            "No system tray available. The overlay needs the tray to be controllable.",
        )
        return 1

    screen = QGuiApplication.primaryScreen()
    if screen is None:
        QMessageBox.critical(None, "Nullscape Overlay", "No primary screen detected.")
        return 1
    size = screen.size()
    preset = load_preset(size.width(), size.height())

    overlay = OverlayWindow(preset)
    overlay.show()

    from .config import diagnostics_dir
    detector = LevelDetector(
        preset.level_region,
        preset.digit_height,
        diagnostics_dir=diagnostics_dir(),
    )
    detector.level_changed.connect(overlay.set_level, type=Qt.ConnectionType.QueuedConnection)
    detector.start()

    tray = TrayIcon(overlay, detector=detector)
    tray.show()

    exit_code = app.exec()
    detector.stop()
    detector.wait(2000)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
