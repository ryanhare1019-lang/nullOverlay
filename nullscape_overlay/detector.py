"""Detects the current Nullscape level by template-matching the on-screen digit.

Pure pixel-based — no AI, no OCR. We render synthetic digit templates from
SEVERAL fonts (Roblox uses Gotham which often isn't available, so any single
font we pick will differ in subtle ways from the on-screen glyph). For each
digit we keep all the variants and pick the best score across all of them at
detection time, which is far more robust than betting on one font.

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
# Multi-font templates lift the per-digit best score, so we can hold the
# threshold at a level where 3 doesn't get confused with 8.
MATCH_THRESHOLD = 0.42
# Hole count (topological invariant) per digit — used as a hard tiebreaker
# because cross-correlation alone can't reliably distinguish 3 from 8 or
# 0 from 8 at the small resolution Roblox renders the level digit.
DIGIT_HOLE_COUNT = {
    "0": 1, "1": 0, "2": 0, "3": 0, "4": 1,
    "5": 0, "6": 1, "7": 0, "8": 2, "9": 1,
}
# Plausible level range — anything outside this is treated as a misread.
MIN_LEVEL = 0
MAX_LEVEL = 30
# Roblox UI text is dim anti-aliased gray (~80-120 brightness) on a varied game
# background. We use Otsu's threshold on top of a static fallback so we don't have
# to hand-tune brightness across scenes; this static value is the floor.
DIGIT_BRIGHTNESS_MIN = 60

# Fonts to try when rendering synthetic digit templates. ALL discoverable fonts
# are used (not just the first) so digits with shape variance between fonts
# (e.g. "5" — angular in Arial, rounded in Segoe UI / Gotham) have a matching
# variant in the template set.
_FONT_CANDIDATES = (
    # Windows
    "arial.ttf", "arialbd.ttf",
    "segoeui.ttf", "seguisb.ttf",
    "tahoma.ttf", "tahomabd.ttf",
    "calibri.ttf", "calibrib.ttf",
    "verdana.ttf",
    # macOS
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    # Linux
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
)


def _load_all_fonts(size: int) -> list[ImageFont.FreeTypeFont | ImageFont.ImageFont]:
    """Load every available font candidate at the given size.

    Returns at least one font (the PIL bitmap default) so callers always have
    something to work with on font-less systems.
    """
    fonts: list[ImageFont.FreeTypeFont | ImageFont.ImageFont] = []
    for path in _FONT_CANDIDATES:
        try:
            fonts.append(ImageFont.truetype(path, size))
        except (OSError, IOError):
            continue
    if not fonts:
        fonts.append(ImageFont.load_default())
    return fonts


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Single-font helper kept for tests / one-off rendering."""
    return _load_all_fonts(size)[0]


def _render_digit(digit: str, font, digit_height_px: int) -> np.ndarray | None:
    """Render a single digit with one font, return a tight binary mask, or
    None if the font couldn't draw it."""
    try:
        font_size = getattr(font, "size", digit_height_px * 2) or digit_height_px * 2
    except Exception:
        font_size = digit_height_px * 2
    canvas = Image.new("L", (font_size * 2, font_size * 2), color=0)
    draw = ImageDraw.Draw(canvas)
    draw.text((font_size // 2, font_size // 4), digit, fill=255, font=font)
    arr = np.array(canvas)
    ys, xs = np.where(arr > 0)
    if len(xs) == 0:
        return None
    cropped = arr[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    scale = digit_height_px / cropped.shape[0]
    new_w = max(1, int(cropped.shape[1] * scale))
    resized = cv2.resize(cropped, (new_w, digit_height_px), interpolation=cv2.INTER_AREA)
    _, binary = cv2.threshold(resized, 80, 255, cv2.THRESH_BINARY)
    return binary


def build_digit_templates(digit_height_px: int) -> dict[str, list[np.ndarray]]:
    """Render multiple template variants per digit (one per available font).

    Returns a dict {"0": [variant_a, variant_b, ...], ..., "9": [...]} of
    single-channel binary masks (255 for digit pixels, 0 for background).
    Callers correlate against EVERY variant and pick the best score per digit.
    """
    font_size = int(digit_height_px * 1.7)
    fonts = _load_all_fonts(font_size)

    templates: dict[str, list[np.ndarray]] = {d: [] for d in "0123456789"}
    for font in fonts:
        for d in "0123456789":
            tpl = _render_digit(d, font, digit_height_px)
            if tpl is not None:
                templates[d].append(tpl)
    # Drop any digit that ended up with zero variants (shouldn't happen given
    # PIL's default font fallback, but defend against it anyway).
    return {d: variants for d, variants in templates.items() if variants}


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


def _match_digit(
    crop_gray: np.ndarray,
    templates: dict[str, list[np.ndarray]],
) -> tuple[str, float, float]:
    """Correlate against EVERY font variant of EVERY digit.

    Returns (best_digit, best_score, runner_up_score) so the caller can also
    reject ambiguous matches where two digits score nearly the same — that's
    how 3 ends up being read as an 8.
    """
    _, crop_bin = cv2.threshold(crop_gray, DIGIT_BRIGHTNESS_MIN, 255, cv2.THRESH_BINARY)

    target_h = next(iter(templates.values()))[0].shape[0]
    scale = target_h / max(1, crop_bin.shape[0])
    new_w = max(1, int(crop_bin.shape[1] * scale))
    crop_resized = cv2.resize(crop_bin, (new_w, target_h), interpolation=cv2.INTER_AREA)

    digit_scores: dict[str, float] = {}
    for digit, variants in templates.items():
        digit_best = -1.0
        for tpl in variants:
            # cv2.matchTemplate requires source >= template in both dims.
            if crop_resized.shape[1] < tpl.shape[1]:
                target = cv2.resize(tpl, (crop_resized.shape[1], target_h))
                src = crop_resized
            else:
                target = crop_resized
                src = tpl
            if target.shape[1] < src.shape[1] or target.shape[0] < src.shape[0]:
                continue
            score = float(cv2.matchTemplate(target, src, cv2.TM_CCOEFF_NORMED).max())
            if score > digit_best:
                digit_best = score
        digit_scores[digit] = digit_best

    ranked = sorted(digit_scores.items(), key=lambda kv: kv[1], reverse=True)
    best_digit, best_score = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else -1.0
    return best_digit, best_score, runner_up


def _count_holes(binary_mask: np.ndarray) -> int:
    """Count enclosed background regions inside the digit (topological holes).

    Anti-aliased dim text can leave thin gaps in stroke connectivity that
    look like extra "holes"; we dilate first to fill them.
    """
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    dilated = cv2.dilate(binary_mask, kernel, iterations=1)
    contours, hierarchy = cv2.findContours(dilated, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        return 0
    return sum(1 for h in hierarchy[0] if h[3] != -1)


def detect_level(region_bgr: np.ndarray, templates: dict[str, list[np.ndarray]]) -> int | None:
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

        # Topology filter: only consider digits that share the crop's hole
        # count. This is the workhorse that prevents 3/8 and 0/8 confusion
        # at small render sizes where cross-correlation isn't decisive.
        _, crop_bin = cv2.threshold(crop, DIGIT_BRIGHTNESS_MIN, 255, cv2.THRESH_BINARY)
        observed_holes = _count_holes(crop_bin)
        candidates = {
            d: variants
            for d, variants in templates.items()
            if DIGIT_HOLE_COUNT[d] == observed_holes
        }
        if not candidates:
            # Unusual rendering (e.g. broken anti-aliasing) — fall back to all.
            candidates = templates

        digit, score, _runner_up = _match_digit(crop, candidates)
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
