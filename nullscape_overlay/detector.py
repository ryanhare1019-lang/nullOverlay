"""Detects the current Nullscape level by template-matching the on-screen digit.

Pure pixel-based — no AI, no OCR. We render synthetic digit templates with PIL
in a common sans-serif font, then correlate each captured digit-blob against
the template set.

Design:
  - `detect_level(region_bgr, templates)` is a pure function that takes a numpy
    image and returns int | None. This is the unit-testable bit.
  - `LevelDetector(QThread)` wraps the pure function with mss screen capture
    and a Qt signal so the overlay can subscribe.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from PyQt6.QtCore import QThread, pyqtSignal

try:
    import mss
except ImportError:  # mss isn't strictly needed for unit tests
    mss = None  # type: ignore[assignment]


# Minimum normalized cross-correlation score for a digit match to count.
MATCH_THRESHOLD = 0.45
# Plausible level range — anything outside this is treated as a misread.
MIN_LEVEL = 0
MAX_LEVEL = 30
# Roblox UI text is dim anti-aliased gray (~80-120 brightness) on a varied game
# background. We use Otsu's threshold on top of a static fallback so we don't have
# to hand-tune brightness across scenes; this static value is the floor.
DIGIT_BRIGHTNESS_MIN = 60

# Fonts to try when rendering synthetic digit templates, in priority order.
_FONT_CANDIDATES = (
    # Windows
    "arial.ttf",
    "segoeui.ttf",
    "tahoma.ttf",
    # macOS / Linux
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
)


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def build_digit_templates(digit_height_px: int) -> dict[str, np.ndarray]:
    """Render synthetic templates for digits 0-9 at the target height.

    Returns a dict {"0": np.ndarray, ..., "9": np.ndarray} of single-channel
    binary masks (255 for digit pixels, 0 for background).
    """
    # Render at 2x for crisper edges, then downsample.
    font_size = int(digit_height_px * 1.7)
    font = _load_font(font_size)

    templates: dict[str, np.ndarray] = {}
    for d in "0123456789":
        # Big canvas so any digit fits, we crop tight after.
        canvas = Image.new("L", (font_size * 2, font_size * 2), color=0)
        draw = ImageDraw.Draw(canvas)
        draw.text((font_size // 2, font_size // 4), d, fill=255, font=font)
        arr = np.array(canvas)
        ys, xs = np.where(arr > 0)
        if len(xs) == 0:
            continue
        cropped = arr[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        # Resize so all templates share the same height; widths can differ.
        scale = digit_height_px / cropped.shape[0]
        new_w = max(1, int(cropped.shape[1] * scale))
        resized = cv2.resize(cropped, (new_w, digit_height_px), interpolation=cv2.INTER_AREA)
        _, binary = cv2.threshold(resized, 80, 255, cv2.THRESH_BINARY)
        templates[d] = binary

    return templates


def _isolate_digit_blobs(region_bgr: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Find bounding boxes of likely digit blobs, sorted left-to-right.

    Roblox renders the level digit as dim anti-aliased gray text. We:
      1. Threshold permissively (static floor)
      2. Dilate to merge anti-aliased fragments into one digit blob
      3. Filter contour bboxes by typical digit aspect ratio
    """
    if region_bgr.ndim == 3:
        gray = cv2.cvtColor(region_bgr, cv2.COLOR_BGR2GRAY)
    else:
        gray = region_bgr

    _, mask = cv2.threshold(gray, DIGIT_BRIGHTNESS_MIN, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    mask = cv2.dilate(mask, kernel, iterations=1)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes: list[tuple[int, int, int, int]] = []
    region_h = mask.shape[0]
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        # A digit fills a chunk of the row height; tiny specks (commas/dots) and
        # super-tall artifacts (vertical UI bars) are noise.
        if h < region_h * 0.35 or h > region_h * 1.05:
            continue
        if w < 2 or w > region_h * 1.2:  # digits aren't wider than they are tall
            continue
        boxes.append((x, y, w, h))
    boxes.sort(key=lambda b: b[0])
    return boxes


def _match_digit(crop_gray: np.ndarray, templates: dict[str, np.ndarray]) -> tuple[str, float]:
    """Return (best_digit, score) for the given digit crop."""
    # Binarize to match the templates.
    _, crop_bin = cv2.threshold(crop_gray, DIGIT_BRIGHTNESS_MIN, 255, cv2.THRESH_BINARY)

    target_h = next(iter(templates.values())).shape[0]
    scale = target_h / max(1, crop_bin.shape[0])
    new_w = max(1, int(crop_bin.shape[1] * scale))
    crop_resized = cv2.resize(crop_bin, (new_w, target_h), interpolation=cv2.INTER_AREA)

    best_digit = "?"
    best_score = -1.0
    for digit, tpl in templates.items():
        # Resize the smaller image to match — matchTemplate needs target >= template.
        if crop_resized.shape[1] < tpl.shape[1]:
            target = cv2.resize(tpl, (crop_resized.shape[1], target_h))
            src = crop_resized
        else:
            target = crop_resized
            src = tpl
        if target.shape[1] < src.shape[1] or target.shape[0] < src.shape[0]:
            continue
        result = cv2.matchTemplate(target, src, cv2.TM_CCOEFF_NORMED)
        score = float(result.max())
        if score > best_score:
            best_score = score
            best_digit = digit
    return best_digit, best_score


def detect_level(region_bgr: np.ndarray, templates: dict[str, np.ndarray]) -> int | None:
    """Return the level integer in the captured region, or None if unreadable."""
    if region_bgr is None or region_bgr.size == 0:
        return None

    boxes = _isolate_digit_blobs(region_bgr)
    if not boxes:
        return None
    if len(boxes) > 3:  # level should be at most 2 digits; >3 means noise
        return None

    gray = cv2.cvtColor(region_bgr, cv2.COLOR_BGR2GRAY) if region_bgr.ndim == 3 else region_bgr
    digits: list[str] = []
    for x, y, w, h in boxes:
        crop = gray[y:y + h, x:x + w]
        digit, score = _match_digit(crop, templates)
        if score < MATCH_THRESHOLD:
            return None
        digits.append(digit)

    try:
        value = int("".join(digits))
    except ValueError:
        return None

    if value < MIN_LEVEL or value > MAX_LEVEL:
        return None
    return value


class LevelDetector(QThread):
    """Polls the level region every `interval_ms` and emits level_changed on change."""

    level_changed = pyqtSignal(int)

    def __init__(
        self,
        level_region: tuple[int, int, int, int],
        digit_height: int,
        interval_ms: int = 500,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._region = level_region
        self._templates = build_digit_templates(digit_height)
        self._interval = interval_ms / 1000.0
        self._stop = False
        self._last_emitted: int | None = None
        # Debounce: only emit after the same value is read N consecutive times.
        self._pending: int | None = None
        self._pending_count = 0

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        if mss is None:
            return
        x, y, w, h = self._region
        bbox = {"left": x, "top": y, "width": w, "height": h}
        with mss.mss() as sct:
            while not self._stop:
                try:
                    shot = sct.grab(bbox)
                    img = np.array(shot)[:, :, :3]  # drop alpha
                    level = detect_level(img, self._templates)
                except Exception:
                    level = None

                if level is not None:
                    if level == self._pending:
                        self._pending_count += 1
                    else:
                        self._pending = level
                        self._pending_count = 1
                    if self._pending_count >= 2 and level != self._last_emitted:
                        self._last_emitted = level
                        self.level_changed.emit(level)

                time.sleep(self._interval)
