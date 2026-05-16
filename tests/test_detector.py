"""Tests for the pure detection logic. No PyQt6 GUI is involved here."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from nullscape_overlay.detector import (
    build_digit_templates,
    detect_level,
    _load_font,
)


@pytest.fixture(scope="module")
def templates():
    return build_digit_templates(digit_height_px=20)


def _render_level_image(value: int, height: int = 28, bg_value: int = 0) -> np.ndarray:
    """Render a synthetic 'level digit' image we can feed back to the detector.

    We use the same font helper the detector uses, so this is essentially asking
    the detector to recognize its own output — a useful sanity check that the
    template-matching loop is wired correctly end-to-end.
    """
    font = _load_font(int(height * 0.95))
    text = str(value)
    canvas = Image.new("L", (height * 3, height), color=bg_value)
    draw = ImageDraw.Draw(canvas)
    draw.text((4, -2), text, fill=255, font=font)
    bgr = np.stack([np.array(canvas)] * 3, axis=-1)
    return bgr


def test_templates_built_for_all_digits(templates):
    assert set(templates.keys()) == {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9"}
    for arr in templates.values():
        assert arr.dtype == np.uint8
        assert arr.shape[0] == 20  # configured digit_height_px


@pytest.mark.parametrize("level", [1, 2, 3, 5, 7, 8, 9, 10, 13, 15])
def test_detects_single_and_double_digits(templates, level):
    img = _render_level_image(level)
    assert detect_level(img, templates) == level


def test_returns_none_for_empty_region(templates):
    blank = np.zeros((28, 60, 3), dtype=np.uint8)
    assert detect_level(blank, templates) is None


def test_returns_none_for_garbled_input(templates):
    # Noise that doesn't look like digits at all.
    rng = np.random.default_rng(seed=7)
    noise = rng.integers(0, 60, (28, 60, 3), dtype=np.uint8)
    assert detect_level(noise, templates) is None


def test_rejects_values_outside_plausible_range(templates):
    # Render a 3-digit number — should be rejected as implausible.
    img = _render_level_image(999)
    assert detect_level(img, templates) is None
