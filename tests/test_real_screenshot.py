"""Detect level from the user's real Nullscape screenshot.

Skips automatically if the screenshot file isn't reachable (e.g., on CI).
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from nullscape_overlay.config import PRESETS
from nullscape_overlay.detector import build_digit_templates, detect_level

REAL_SCREENSHOT = Path(
    "/mnt/c/Users/ryana/OneDrive/Documents/ShareX/Screenshots/2026-05/Discord_XGfXk6pWWF.png"
)


@pytest.mark.skipif(not REAL_SCREENSHOT.exists(), reason="real screenshot not available")
def test_detects_level_0_from_real_screenshot():
    img = cv2.imread(str(REAL_SCREENSHOT))
    assert img is not None, "failed to read real screenshot"

    h, w = img.shape[:2]
    assert (w, h) == (1920, 1080), f"unexpected screenshot resolution {w}x{h}"

    preset = PRESETS[(1920, 1080)]
    x, y, rw, rh = preset.level_region
    region = img[y:y + rh, x:x + rw]
    assert region.size > 0, "level region is empty"

    templates = build_digit_templates(preset.digit_height)
    level = detect_level(region, templates)
    assert level == 0, f"expected level 0, got {level!r}"
