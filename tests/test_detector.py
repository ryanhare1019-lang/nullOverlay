"""Tests for the pure detection logic. No PyQt6 GUI is involved here.

These compose test images directly from the digit templates so the round trip
doesn't depend on font rasterization being identical to template-build time.
"""
from __future__ import annotations

import numpy as np
import pytest

from nullscape_overlay.detector import build_digit_templates, detect_level


DIGIT_HEIGHT = 20


@pytest.fixture(scope="module")
def templates():
    return build_digit_templates(digit_height_px=DIGIT_HEIGHT)


def _compose_level_image(value: int, templates: dict[str, list[np.ndarray]]) -> np.ndarray:
    """Place the first template variant of each digit side-by-side on a black
    canvas. Returns BGR."""
    text = str(value)
    digit_imgs = [templates[d][0] for d in text]
    pad = 4
    spacing = 2
    canvas_w = sum(d.shape[1] for d in digit_imgs) + spacing * (len(digit_imgs) - 1) + pad * 2
    canvas_h = DIGIT_HEIGHT + pad * 2
    canvas = np.zeros((canvas_h, canvas_w), dtype=np.uint8)
    x = pad
    for d in digit_imgs:
        canvas[pad:pad + DIGIT_HEIGHT, x:x + d.shape[1]] = d
        x += d.shape[1] + spacing
    return np.stack([canvas] * 3, axis=-1)


def test_templates_built_for_all_digits(templates):
    assert set(templates.keys()) == {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9"}
    for digit, variants in templates.items():
        assert len(variants) >= 1, f"digit {digit} has no variants"
        for arr in variants:
            assert arr.dtype == np.uint8
            assert arr.shape[0] == DIGIT_HEIGHT


@pytest.mark.parametrize("level", [0, 1, 2, 3, 5, 7, 8, 9, 10, 13, 15])
def test_round_trip_single_and_double_digits(templates, level):
    img = _compose_level_image(level, templates)
    assert detect_level(img, templates) == level


def test_returns_none_for_empty_region(templates):
    blank = np.zeros((28, 60, 3), dtype=np.uint8)
    assert detect_level(blank, templates) is None


def test_returns_none_for_garbled_input(templates):
    # Pure low-value noise doesn't trigger the digit-brightness threshold.
    rng = np.random.default_rng(seed=7)
    noise = rng.integers(0, 40, (28, 60, 3), dtype=np.uint8)
    assert detect_level(noise, templates) is None


def test_rejects_values_outside_plausible_range(templates):
    # 4 digits exceeds the max-blob filter (>3 blobs => None).
    img = _compose_level_image(9999, templates)
    assert detect_level(img, templates) is None
