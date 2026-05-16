"""Semi-transparent, frameless, click-through overlay shown in the bottom-left
corner of the primary screen. Driven by level updates from LevelDetector.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import (
    QColor,
    QFont,
    QGuiApplication,
    QPainter,
    QPainterPath,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .config import ResolutionPreset, icons_dir
from .shops import Item, SHOPS, is_shop_level, next_shop_target


COLOR_BG = QColor(20, 20, 20, 200)            # rounded backdrop
COLOR_UPGRADE = QColor(60, 180, 75, 165)      # green
COLOR_MAYBE = QColor(230, 200, 40, 165)       # yellow
COLOR_CURSE = QColor(200, 60, 60, 175)        # red
COLOR_CHOICE_HEADER = QColor(70, 70, 90, 180)
COLOR_TEXT = QColor(240, 240, 240)
COLOR_DIM = QColor(170, 170, 170)
COLOR_CURSE_TEXT = QColor(255, 120, 120)

ROW_COLORS = {
    "upgrade": COLOR_UPGRADE,
    "maybe": COLOR_MAYBE,
    "curse": COLOR_CURSE,
}


def _slug(name: str) -> str:
    return name.lower().replace(" ", "_").replace("+", "plus").replace(",", "")


def _placeholder_icon(letter: str, size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(60, 60, 80, 220))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(0, 0, size, size, 6, 6)
    p.setPen(QColor(230, 230, 240))
    font = QFont()
    font.setBold(True)
    font.setPixelSize(int(size * 0.6))
    p.setFont(font)
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, letter.upper())
    p.end()
    return pm


def _load_icon(name: str, size: int) -> QPixmap:
    candidate = icons_dir() / f"{_slug(name)}.png"
    if candidate.exists():
        pm = QPixmap(str(candidate))
        if not pm.isNull():
            return pm.scaled(
                size, size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
    return _placeholder_icon((name or "?")[0], size)


class _ItemRow(QFrame):
    """One row in the upgrade list. Paints its own tinted background."""

    def __init__(self, item: Item, scale: float, indent: bool = False) -> None:
        super().__init__()
        self._color = ROW_COLORS.get(item.type, COLOR_CHOICE_HEADER)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumHeight(int(38 * scale))

        icon_size = int(28 * scale)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            int((22 if indent else 8) * scale), int(4 * scale),
            int(10 * scale), int(4 * scale),
        )
        layout.setSpacing(int(8 * scale))

        icon_label = QLabel()
        icon_label.setPixmap(_load_icon(item.name, icon_size))
        icon_label.setFixedSize(icon_size, icon_size)
        layout.addWidget(icon_label)

        # Yellow background alone signals "maybe" — no text prefix needed.
        name_label = QLabel(item.name)
        name_font = QFont()
        name_font.setPixelSize(int(13 * scale))
        name_font.setBold(True)
        name_label.setFont(name_font)
        name_label.setStyleSheet(f"color: rgba({COLOR_TEXT.red()},{COLOR_TEXT.green()},{COLOR_TEXT.blue()},255);")
        layout.addWidget(name_label, stretch=1)

        if item.type == "curse":
            cost_label = QLabel("(curse)")
            cost_label.setStyleSheet(
                f"color: rgba({COLOR_CURSE_TEXT.red()},{COLOR_CURSE_TEXT.green()},{COLOR_CURSE_TEXT.blue()},255);"
            )
        else:
            cost_label = QLabel(f"{item.cost}" if item.cost is not None else "")
            cost_label.setStyleSheet(
                f"color: rgba({COLOR_TEXT.red()},{COLOR_TEXT.green()},{COLOR_TEXT.blue()},255);"
            )
        cost_font = QFont("Consolas")
        cost_font.setPixelSize(int(13 * scale))
        cost_font.setBold(True)
        cost_label.setFont(cost_font)
        layout.addWidget(cost_label)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self.rect().toRectF(), 6, 6)
        p.fillPath(path, self._color)
        p.end()


class _ChoiceHeader(QLabel):
    def __init__(self, scale: float) -> None:
        super().__init__("Choose one:")
        font = QFont()
        font.setPixelSize(int(11 * scale))
        font.setItalic(True)
        self.setFont(font)
        self.setStyleSheet(
            f"color: rgba({COLOR_DIM.red()},{COLOR_DIM.green()},{COLOR_DIM.blue()},255);"
            f" padding-left: {int(8 * scale)}px; padding-top: {int(4 * scale)}px;"
        )


class OverlayWindow(QWidget):
    def __init__(self, preset: ResolutionPreset) -> None:
        super().__init__()
        self._preset = preset
        self._current_level: int | None = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("Nullscape Overlay")

        scale = preset.scale
        self._width = int(360 * scale)
        self._padding = int(12 * scale)

        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(self._padding, self._padding, self._padding, self._padding)
        self._root.setSpacing(int(6 * scale))

        self._header = QLabel("Waiting for game…")
        header_font = QFont()
        header_font.setPixelSize(int(16 * scale))
        header_font.setBold(True)
        self._header.setFont(header_font)
        self._header.setStyleSheet(
            f"color: rgba({COLOR_TEXT.red()},{COLOR_TEXT.green()},{COLOR_TEXT.blue()},255);"
        )

        self._sub_header = QLabel("")
        sub_font = QFont()
        sub_font.setPixelSize(int(12 * scale))
        self._sub_header.setFont(sub_font)
        self._sub_header.setStyleSheet(
            f"color: rgba({COLOR_DIM.red()},{COLOR_DIM.green()},{COLOR_DIM.blue()},255);"
        )

        self._body = QVBoxLayout()
        self._body.setSpacing(int(4 * scale))

        self._footer = QLabel("Duo Standard")
        footer_font = QFont()
        footer_font.setPixelSize(int(10 * scale))
        footer_font.setItalic(True)
        self._footer.setFont(footer_font)
        self._footer.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._footer.setStyleSheet(
            f"color: rgba({COLOR_DIM.red()},{COLOR_DIM.green()},{COLOR_DIM.blue()},255);"
        )

        self._root.addWidget(self._header)
        self._root.addWidget(self._sub_header)
        self._root.addLayout(self._body)
        self._root.addWidget(self._footer)

        self.setFixedWidth(self._width)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)

        self._render_state()
        self._reposition()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self.rect().toRectF(), 10, 10)
        p.fillPath(path, COLOR_BG)
        p.end()

    def _reposition(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        # Use full screen geometry, not availableGeometry — when Roblox runs
        # fullscreen the taskbar is hidden, but availableGeometry can still
        # report a smaller bottom (or in some DPI configs, the wrong bottom),
        # which clipped the overlay below the visible area.
        geo = screen.geometry()
        left_off, bot_off = self._preset.overlay_pos
        # Force the layout to settle so height() reflects the new contents
        # before we anchor to it.
        self.adjustSize()
        h = max(self.height(), self.sizeHint().height())
        x = geo.left() + left_off
        y = geo.bottom() - h - bot_off
        # Clamp so the overlay can never spill off the top OR bottom of screen.
        y = max(geo.top() + bot_off, y)
        self.move(x, y)

    def set_level(self, level: int) -> None:
        if level == self._current_level:
            return
        self._current_level = level
        self._render_state()
        self._reposition()

    def _clear_body(self) -> None:
        # setParent(None) detaches immediately so re-rendering doesn't show ghost
        # widgets from the previous state (deleteLater alone is async).
        while self._body.count():
            item = self._body.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def _render_state(self) -> None:
        self._clear_body()
        scale = self._preset.scale
        level = self._current_level

        if level is None:
            self._header.setText("Waiting for game…")
            self._sub_header.setText("Make sure Nullscape is visible")
            self.adjustSize()
            return

        if is_shop_level(level):
            shop = SHOPS[level]
            self._header.setText(f"Shop @ Level {level}")
            self._sub_header.setText(f"Need: {shop.total} gifts")
            for item in shop.items:
                if item.type == "choice":
                    self._body.addWidget(_ChoiceHeader(scale))
                    for opt in item.options:
                        self._body.addWidget(_ItemRow(opt, scale, indent=True))
                else:
                    self._body.addWidget(_ItemRow(item, scale))
        else:
            target = next_shop_target(level)
            self._header.setText(f"Good luck!  (Lv {level})")
            if target is not None:
                self._sub_header.setText(f"Target: {target} gifts")
            else:
                self._sub_header.setText("No more shops")
        self.adjustSize()
