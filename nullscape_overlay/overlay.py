"""Semi-transparent overlay in the bottom-left of the primary screen.

Themed to match Nullscape's mystical look:
  - Cinzel for headers (engraved/classical feel)
  - Cormorant Garamond for body text
  - Teal gem icon next to every price (matches the in-game gift counter)
  - Row backgrounds are translucent so the game shows through

Behavior:
  - Always-on-top, frameless.
  - NOT click-through — user can click + scroll the upgrade list. Clicking
    the overlay will steal focus from Roblox, which is the trade-off we
    accept to make scrolling work.
  - Dragging anywhere on the header bar moves the overlay.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QPoint, QPointF, QSize, Qt
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontDatabase,
    QGuiApplication,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPixmap,
    QPolygonF,
)
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .config import ResolutionPreset, fonts_dir, icons_dir
from .shops import Item, SHOPS, is_shop_level, next_shop_level, next_shop_target


# Theme colors. Backgrounds use moderate alpha so the game shows through.
COLOR_BG_TOP = QColor(18, 12, 28, 230)        # near-black with violet tint
COLOR_BG_BOT = QColor(8, 6, 16, 230)
COLOR_BORDER = QColor(120, 95, 180, 200)      # mystical purple edge
COLOR_UPGRADE = QColor(60, 175, 80, 115)      # green, more transparent
COLOR_MAYBE = QColor(225, 195, 50, 115)       # yellow
COLOR_CURSE = QColor(200, 60, 60, 130)        # red, slightly more opaque
COLOR_CHOICE_HEADER_BG = QColor(70, 60, 95, 110)
COLOR_TEXT = QColor(238, 232, 220)            # parchment
COLOR_DIM = QColor(170, 160, 180)
COLOR_HEADER_GLOW = QColor(180, 140, 240)
COLOR_GEM = QColor(80, 220, 200)              # teal — matches in-game gift counter
COLOR_GEM_HIGHLIGHT = QColor(160, 255, 240)
COLOR_GEM_DARK = QColor(20, 90, 100)
COLOR_PRICE = QColor(120, 235, 215)           # teal price text
COLOR_CURSE_TEXT = QColor(255, 130, 130)

ROW_COLORS = {
    "upgrade": COLOR_UPGRADE,
    "maybe": COLOR_MAYBE,
    "curse": COLOR_CURSE,
}

# Font family names we resolve to once at startup (the QFontDatabase records
# the actual family name embedded in each TTF).
_FONT_HEADER_FAMILY: str | None = None
_FONT_BODY_FAMILY: str | None = None
_FONT_BODY_BOLD_FAMILY: str | None = None


def _register_bundled_fonts() -> None:
    """Load the Cinzel + Cormorant Garamond TTFs into the Qt font database
    so the rest of the overlay can ask for them by family name."""
    global _FONT_HEADER_FAMILY, _FONT_BODY_FAMILY, _FONT_BODY_BOLD_FAMILY
    fonts_path = fonts_dir()
    for filename, slot in (
        ("Cinzel-Bold.ttf", "header"),
        ("CormorantGaramond-Regular.ttf", "body"),
        ("CormorantGaramond-Bold.ttf", "body_bold"),
    ):
        path = fonts_path / filename
        if not path.exists():
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            continue
        families = QFontDatabase.applicationFontFamilies(font_id)
        if not families:
            continue
        family = families[0]
        if slot == "header":
            _FONT_HEADER_FAMILY = family
        elif slot == "body":
            _FONT_BODY_FAMILY = family
        elif slot == "body_bold":
            _FONT_BODY_BOLD_FAMILY = family


def _header_font(px: int) -> QFont:
    f = QFont(_FONT_HEADER_FAMILY or "Georgia")
    f.setPixelSize(px)
    f.setBold(True)
    f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 105.0)
    return f


def _body_font(px: int, bold: bool = False) -> QFont:
    family = _FONT_BODY_BOLD_FAMILY if bold else _FONT_BODY_FAMILY
    f = QFont(family or "Georgia")
    f.setPixelSize(px)
    if bold and not _FONT_BODY_BOLD_FAMILY:
        f.setBold(True)
    return f


def _slug(name: str) -> str:
    return name.lower().replace(" ", "_").replace("+", "plus").replace(",", "")


def _placeholder_icon(letter: str, size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    grad = QLinearGradient(0, 0, 0, size)
    grad.setColorAt(0, QColor(80, 70, 110, 230))
    grad.setColorAt(1, QColor(40, 35, 60, 230))
    p.setBrush(QBrush(grad))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(0, 0, size, size, 8, 8)
    p.setPen(COLOR_TEXT)
    f = _header_font(int(size * 0.55))
    p.setFont(f)
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


_GIFT_PIXMAP_CACHE: dict[int, QPixmap] = {}


def _gift_icon(size: int) -> QPixmap:
    """Golden Gift icon from the Nullscape wiki, scaled to the requested size.

    Cached because every price label re-requests the same size."""
    if size in _GIFT_PIXMAP_CACHE:
        return _GIFT_PIXMAP_CACHE[size]
    path = icons_dir() / "_golden_gift.png"
    if path.exists():
        pm = QPixmap(str(path))
        if not pm.isNull():
            scaled = pm.scaled(
                size, size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            _GIFT_PIXMAP_CACHE[size] = scaled
            return scaled
    # Fallback: a small gold square so the price area never disappears.
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(230, 200, 80, 230))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(2, 2, size - 4, size - 4, 4, 4)
    p.end()
    _GIFT_PIXMAP_CACHE[size] = pm
    return pm


class _ItemRow(QFrame):
    """One row in the upgrade list. Tinted by item type, with a gem next to
    the price."""

    def __init__(self, item: Item, scale: float, indent: bool = False) -> None:
        super().__init__()
        self._color = ROW_COLORS.get(item.type, COLOR_CHOICE_HEADER_BG)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumHeight(int(50 * scale))

        icon_size = int(36 * scale)
        gem_size = int(18 * scale)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            int((28 if indent else 10) * scale), int(6 * scale),
            int(12 * scale), int(6 * scale),
        )
        layout.setSpacing(int(10 * scale))

        icon_label = QLabel()
        icon_label.setPixmap(_load_icon(item.name, icon_size))
        icon_label.setFixedSize(icon_size, icon_size)
        layout.addWidget(icon_label)

        name_label = QLabel(item.name)
        name_label.setFont(_body_font(int(16 * scale), bold=True))
        name_label.setStyleSheet(
            f"color: rgba({COLOR_TEXT.red()},{COLOR_TEXT.green()},{COLOR_TEXT.blue()},255);"
        )
        layout.addWidget(name_label, stretch=1)

        if item.type == "curse":
            cost_label = QLabel("(curse)")
            cost_label.setFont(_body_font(int(14 * scale), bold=True))
            cost_label.setStyleSheet(
                f"color: rgba({COLOR_CURSE_TEXT.red()},{COLOR_CURSE_TEXT.green()},{COLOR_CURSE_TEXT.blue()},255);"
            )
            layout.addWidget(cost_label)
        elif item.cost is not None:
            gift = QLabel()
            gift.setPixmap(_gift_icon(gem_size))
            gift.setFixedSize(gem_size, gem_size)
            layout.addWidget(gift)
            cost_label = QLabel(str(item.cost))
            cost_label.setFont(_body_font(int(15 * scale), bold=True))
            cost_label.setStyleSheet(
                f"color: rgba({COLOR_PRICE.red()},{COLOR_PRICE.green()},{COLOR_PRICE.blue()},255);"
            )
            layout.addWidget(cost_label)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self.rect().toRectF(), 8, 8)
        p.fillPath(path, self._color)
        p.end()


class _ChoiceHeader(QLabel):
    def __init__(self, scale: float) -> None:
        super().__init__("Choose one:")
        f = _body_font(int(13 * scale))
        f.setItalic(True)
        self.setFont(f)
        self.setStyleSheet(
            f"color: rgba({COLOR_DIM.red()},{COLOR_DIM.green()},{COLOR_DIM.blue()},255);"
            f" padding-left: {int(10 * scale)}px; padding-top: {int(4 * scale)}px;"
            f" padding-bottom: {int(2 * scale)}px;"
        )


class OverlayWindow(QWidget):
    def __init__(self, preset: ResolutionPreset) -> None:
        super().__init__()
        self._preset = preset
        self._current_level: int | None = None
        self._drag_anchor: QPoint | None = None

        _register_bundled_fonts()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("Nullscape Overlay")
        self.setMouseTracking(True)

        scale = preset.scale
        self._scale = scale
        self._width = int(400 * scale)
        self._padding = int(14 * scale)
        # Hard upper bound on overlay height — keeps it well below the middle
        # of the screen even on shorter monitors. Content beyond this scrolls.
        self._max_height = int(420 * scale)

        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(self._padding, self._padding, self._padding, self._padding)
        self._root.setSpacing(int(6 * scale))

        self._header = QLabel("Waiting for game…")
        self._header.setFont(_header_font(int(20 * scale)))
        self._header.setStyleSheet(
            f"color: rgba({COLOR_HEADER_GLOW.red()},{COLOR_HEADER_GLOW.green()},{COLOR_HEADER_GLOW.blue()},255);"
        )

        self._sub_header = QLabel("")
        self._sub_header.setFont(_body_font(int(14 * scale)))
        self._sub_header.setStyleSheet(
            f"color: rgba({COLOR_DIM.red()},{COLOR_DIM.green()},{COLOR_DIM.blue()},255);"
        )

        # Scroll area holds the per-shop item rows. The header/sub-header and
        # footer stay pinned outside the scroll area so the player always sees
        # the level + target without scrolling.
        self._body_widget = QWidget()
        self._body_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._body = QVBoxLayout(self._body_widget)
        self._body.setContentsMargins(0, 0, 0, 0)
        self._body.setSpacing(int(5 * scale))

        self._scroll = QScrollArea()
        self._scroll.setWidget(self._body_widget)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._scroll.viewport().setAutoFillBackground(False)
        self._scroll.viewport().setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { background: rgba(40, 30, 60, 100); width: 8px; border-radius: 4px; }"
            "QScrollBar::handle:vertical { background: rgba(180, 140, 240, 180); border-radius: 4px; min-height: 20px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }"
        )

        self._footer = QLabel("Duo Standard")
        f = _body_font(int(11 * scale))
        f.setItalic(True)
        self._footer.setFont(f)
        self._footer.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._footer.setStyleSheet(
            f"color: rgba({COLOR_DIM.red()},{COLOR_DIM.green()},{COLOR_DIM.blue()},255);"
        )

        self._root.addWidget(self._header)
        self._root.addWidget(self._sub_header)
        self._root.addWidget(self._scroll, stretch=1)
        self._root.addWidget(self._footer)

        self.setFixedWidth(self._width)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)

        self._render_state()
        self._reposition()

    # ----------------------------------------------------------------- paint
    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Vertical gradient backdrop with subtle violet edge.
        path = QPainterPath()
        path.addRoundedRect(self.rect().toRectF(), 14, 14)
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0.0, COLOR_BG_TOP)
        grad.setColorAt(1.0, COLOR_BG_BOT)
        p.fillPath(path, QBrush(grad))
        pen = p.pen()
        pen.setColor(COLOR_BORDER)
        pen.setWidth(1)
        p.setPen(pen)
        p.drawPath(path)
        p.end()

    # ----------------------------------------------------------------- drag
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_anchor = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_anchor is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_anchor)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_anchor = None
            event.accept()

    # --------------------------------------------------------------- layout
    def _body_content_height(self) -> int:
        """Sum the natural heights of every row + spacing.

        We query each child's sizeHint directly because QScrollArea masks
        the inner body widget's own sizeHint (with setWidgetResizable=True
        it sizes the inner widget to fit the viewport, not the content).
        """
        spacing = self._body.spacing()
        count = self._body.count()
        total = 0
        for i in range(count):
            w = self._body.itemAt(i).widget()
            if w is None:
                continue
            total += max(w.sizeHint().height(), w.minimumSizeHint().height())
        if count > 1:
            total += spacing * (count - 1)
        return total

    def _desired_height(self) -> int:
        scale = self._scale
        chrome = (
            self._padding * 2
            + self._header.sizeHint().height()
            + self._sub_header.sizeHint().height()
            + self._footer.sizeHint().height()
            + int(6 * scale) * 3  # spacing between the four stacked elements
        )
        # isVisible() returns False until the parent window is shown — use
        # isHidden() (the explicit hide() state) so initial-render sizing works.
        if not self._scroll.isHidden():
            chrome += self._body_content_height()
        return chrome

    def _reposition(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        # Clear any height lock from the previous render before re-measuring.
        self.setMinimumHeight(0)
        self.setMaximumHeight(16777215)

        geo = screen.geometry()
        left_off, bot_off = self._preset.overlay_pos
        target = min(self._desired_height(), self._max_height)
        # Floor: keep header + sub-header + footer visible even if no body.
        target = max(target, int(110 * self._scale))
        self.setFixedHeight(target)
        x = geo.left() + left_off
        y = geo.bottom() - target - bot_off
        y = max(geo.top() + bot_off, y)
        self.move(x, y)

    def set_level(self, level: int) -> None:
        if level == self._current_level:
            return
        self._current_level = level
        self._render_state()
        self._reposition()

    # --------------------------------------------------------------- render
    def _clear_body(self) -> None:
        while self._body.count():
            item = self._body.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def _render_state(self) -> None:
        self._clear_body()
        # Reset height cap so layouts can grow naturally before we re-clamp.
        self.setMaximumHeight(16777215)
        scale = self._scale
        level = self._current_level

        if level is None:
            self._header.setText("Waiting for game…")
            self._sub_header.setText("Make sure Nullscape is visible")
            self._scroll.hide()
            self.adjustSize()
            return

        self._scroll.show()
        if is_shop_level(level):
            shop = SHOPS[level]
            self._header.setText(f"Shop  ·  Level {level}")
            self._sub_header.setText(f"Need:  {shop.total} gifts")
            for item in shop.items:
                if item.type == "choice":
                    self._body.addWidget(_ChoiceHeader(scale))
                    for opt in item.options:
                        self._body.addWidget(_ItemRow(opt, scale, indent=True))
                else:
                    self._body.addWidget(_ItemRow(item, scale))
        else:
            target = next_shop_target(level)
            next_lvl = next_shop_level(level)
            self._header.setText(f"Good luck!  ·  Level {level}")
            if target is not None and next_lvl is not None:
                self._sub_header.setText(f"Target:  {target} gifts by level {next_lvl}")
            else:
                self._sub_header.setText("No more shops")
            # No rows between shops — collapse the scroll area to nothing so
            # the overlay shrinks to just header + sub-header + footer.
            self._scroll.hide()
        self.adjustSize()
