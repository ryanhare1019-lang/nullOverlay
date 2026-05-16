"""System tray icon. Hosts overlay show/hide, About, config-path info,
detection diagnostics, and Quit."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon, QWidget

from . import __version__
from .config import diagnostics_dir, example_user_config, user_config_path


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


def _open_in_file_manager(path: Path) -> None:
    """Open the given directory in the OS file manager."""
    path.mkdir(parents=True, exist_ok=True)
    if sys.platform.startswith("win"):
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


class TrayIcon(QSystemTrayIcon):
    def __init__(self, overlay: QWidget, detector=None, parent=None) -> None:
        super().__init__(_make_icon(), parent)
        self._overlay = overlay
        self._detector = detector
        self.setToolTip(f"Nullscape Overlay {__version__} — Duo Standard")

        menu = QMenu()

        self._toggle = QAction("Hide overlay")
        self._toggle.triggered.connect(self._on_toggle)
        menu.addAction(self._toggle)

        menu.addSeparator()

        if detector is not None:
            snap_act = QAction("Save detection snapshot")
            snap_act.triggered.connect(self._on_snapshot)
            menu.addAction(snap_act)

            open_diag = QAction("Open diagnostics folder")
            open_diag.triggered.connect(self._on_open_diagnostics)
            menu.addAction(open_diag)

            detector.diagnostic_saved.connect(self._on_diagnostic_saved)

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

    def _on_snapshot(self) -> None:
        if self._detector is None:
            return
        self._detector.request_snapshot()
        self.showMessage(
            "Nullscape Overlay",
            "Saving detection snapshot on the next polling tick…",
            QSystemTrayIcon.MessageIcon.Information,
            2000,
        )

    def _on_diagnostic_saved(self, path: str) -> None:
        self.showMessage(
            "Nullscape Overlay",
            f"Snapshot saved → {Path(path).name}",
            QSystemTrayIcon.MessageIcon.Information,
            3000,
        )

    def _on_open_diagnostics(self) -> None:
        _open_in_file_manager(diagnostics_dir())

    def _on_about(self) -> None:
        QMessageBox.information(
            None,
            "Nullscape Overlay",
            (
                f"Nullscape Overlay v{__version__}\n"
                "Tuned for: Duo Standard\n\n"
                "Shows recommended upgrades for each shop level "
                "(3, 5, 8, 10, 13, 15).\n\n"
                "If level detection is wrong, click 'Save detection snapshot'\n"
                "while the wrong level is showing — it dumps the captured\n"
                "region + match scores so the template set can be fixed."
            ),
        )

    def _on_config(self) -> None:
        path = user_config_path()
        QMessageBox.information(
            None,
            "User config",
            (
                f"Optional config override file (create this to tweak level "
                f"region coords):\n\n  {path}\n\n"
                f"Expected JSON shape:\n\n{example_user_config()}"
            ),
        )
