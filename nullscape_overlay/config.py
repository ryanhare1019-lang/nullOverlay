"""Resolution presets and runtime config.

The level digit lives in the top-right of the Roblox screen, beside the boss bar.
Region coordinates are (x, y, width, height) in screen pixels.

Users can override any preset by dropping a JSON file at
  %USERPROFILE%\\.nullscape-overlay\\config.json
with the same shape as a preset entry.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class ResolutionPreset:
    # (x, y, w, h) — pixel region that contains the level digit(s) only (no "Level: " label)
    level_region: tuple[int, int, int, int]
    # (left_offset, bottom_offset) — overlay bottom-left corner offset from screen bottom-left
    overlay_pos: tuple[int, int]
    # UI scale factor for fonts / row heights
    scale: float
    # Pixel height of a digit at this resolution (used to render synthetic templates)
    digit_height: int


# Base 1080p coords were measured from the user's screenshot (Discord_XGfXk6pWWF.png).
# Other resolutions are linearly scaled from 1080p; refine via user config if needed.
PRESETS: dict[tuple[int, int], ResolutionPreset] = {
    (1920, 1080): ResolutionPreset(
        # Just past "Level: " label, tight around the digit(s). Measured from sample.
        level_region=(1338, 12, 50, 22),
        overlay_pos=(16, 16),
        scale=1.0,
        digit_height=14,
    ),
    (2560, 1440): ResolutionPreset(
        level_region=(1784, 16, 67, 29),
        overlay_pos=(22, 22),
        scale=1.33,
        digit_height=19,
    ),
    (3840, 2160): ResolutionPreset(
        level_region=(2676, 24, 100, 44),
        overlay_pos=(32, 32),
        scale=2.0,
        digit_height=28,
    ),
}


def user_config_path() -> Path:
    return Path.home() / ".nullscape-overlay" / "config.json"


def load_preset(width: int, height: int) -> ResolutionPreset:
    """Pick the best preset for the given resolution, applying any user overrides."""
    key = (width, height)
    preset = PRESETS.get(key) or _closest_preset(width, height)

    override_path = user_config_path()
    if override_path.exists():
        try:
            data = json.loads(override_path.read_text())
            res_key = f"{width}x{height}"
            if res_key in data:
                entry = data[res_key]
                preset = ResolutionPreset(
                    level_region=tuple(entry.get("level_region", preset.level_region)),
                    overlay_pos=tuple(entry.get("overlay_pos", preset.overlay_pos)),
                    scale=float(entry.get("scale", preset.scale)),
                    digit_height=int(entry.get("digit_height", preset.digit_height)),
                )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            print(f"warning: ignoring malformed user config: {e}", file=sys.stderr)

    return preset


def _closest_preset(width: int, height: int) -> ResolutionPreset:
    """Pick the supported resolution with the closest aspect ratio + total pixels."""
    target_aspect = width / height
    target_pixels = width * height

    def distance(key: tuple[int, int]) -> float:
        w, h = key
        aspect_diff = abs((w / h) - target_aspect)
        pixel_diff = abs(w * h - target_pixels) / target_pixels
        return aspect_diff * 10 + pixel_diff

    best = min(PRESETS.keys(), key=distance)
    return PRESETS[best]


def asset_dir() -> Path:
    """Path to bundled assets. Handles both dev runs and PyInstaller --onefile."""
    # PyInstaller sets sys._MEIPASS to the temp extraction dir
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return base / "assets"


def icons_dir() -> Path:
    return asset_dir() / "icons"


def example_user_config() -> str:
    """Print this to help users write their own override file."""
    return json.dumps(
        {f"{w}x{h}": asdict(p) for (w, h), p in PRESETS.items()},
        indent=2,
    )
