"""System tray icon — the only way to control the overlay since the window
is click-through."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon, QWidget

from . import __version__
from .config import user_config_path, example_user_config


def _make_icon() -> QIcon:
    """Generate a simple tray icon at runtime so we don't need a bundled .ico file."""
    pm = QPixmap(32, 32)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(Qt.GlobalColor.darkMagenta)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(2, 2, 28, 28, 6, 6)
    p.setPen(Qt.GlobalColor.white)
    f = p.font()
    f.setBold(True)
    f.setPixelSize(18)
    p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "N")
    p.end()
    return QIcon(pm)


class TrayIcon(QSystemTrayIcon):
    def __init__(self, overlay: QWidget, parent=None) -> None:
        super().__init__(_make_icon(), parent)
        self._overlay = overlay
        self.setToolTip(f"Nullscape Overlay {__version__} — Duo Standard")

        menu = QMenu()

        self._toggle = QAction("Hide overlay")
        self._toggle.triggered.connect(self._on_toggle)
        menu.addAction(self._toggle)

        menu.addSeparator()

        about = QAction("About…")
        about.triggered.connect(self._on_about)
        menu.addAction(about)

        config = QAction("Show config path")
        config.triggered.connect(self._on_config)
        menu.addAction(config)

        menu.addSeparator()

        quit_act = QAction("Quit")
        quit_act.triggered.connect(QApplication.instance().quit)  # type: ignore[union-attr]
        menu.addAction(quit_act)

        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)

    def _on_toggle(self) -> None:
        if self._overlay.isVisible():
            self._overlay.hide()
            self._toggle.setText("Show overlay")
        else:
            self._overlay.show()
            self._toggle.setText("Hide overlay")

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._on_toggle()

    def _on_about(self) -> None:
        QMessageBox.information(
            None,
            "Nullscape Overlay",
            (
                f"Nullscape Overlay v{__version__}\n"
                "Tuned for: Duo Standard\n\n"
                "Shows recommended upgrades for each shop level (3, 5, 8, 10, 13, 15).\n"
                "The overlay is click-through — use this tray icon to hide or quit.\n\n"
                "Detection uses pixel template matching on the on-screen level digit.\n"
                "If the level isn't detected, check that Nullscape is running at a\n"
                "supported resolution (1080p / 1440p / 4K) and the HUD is visible."
            ),
        )

    def _on_config(self) -> None:
        path = user_config_path()
        QMessageBox.information(
            None,
            "User config",
            (
                f"Optional config override file (create this to tweak level region coords):\n\n"
                f"  {path}\n\n"
                f"Expected JSON shape:\n\n{example_user_config()}"
            ),
        )
