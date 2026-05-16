# Nullscape Overlay

A tiny Windows overlay for the Roblox game **Nullscape** that tells you which upgrades to buy at every shop.

> Tuned for **Duo Standard**. Solo / Hardcore / other difficulties have different optimal builds — this tool's recommendations won't match.

## What it does

Watches the level number in the top-right of your Roblox window. When you reach a shop (levels **3, 5, 8, 10, 13, 15**), the overlay shows the recommended upgrade list with prices and color coding:

- 🟢 **Green** — buy this upgrade
- 🟡 **Yellow** — "MAYBE" buy if you can afford it
- 🔴 **Red** — curse you'll be hit with (informational only, e.g. `Lap 2` at level 8)

Between shops it shows `Good luck!` plus the target gift count for the next shop.

## Install

1. Go to the [Releases](../../releases) page.
2. Download `NullscapeOverlay.exe` from the latest release.
3. Double-click it. The overlay appears in the bottom-left of your primary monitor.
4. A `N` icon shows up in the system tray — right-click it to hide, show, or quit.

No Python, no installer. Just one `.exe`.

## How it works

- Captures a small region of the top-right of the screen every 500 ms via `mss`.
- Threshold + template-matches the gray level digit using PIL-rendered synthetic templates.
- Pure pixel correlation — no AI, no OCR, no network calls.

## Supported resolutions

| Resolution | Status |
|---|---|
| 1920×1080 | ✅ measured from sample screenshot |
| 2560×1440 | ⚠️ linearly scaled from 1080p — fine-tune if detection is flaky |
| 3840×2160 | ⚠️ linearly scaled from 1080p — fine-tune if detection is flaky |
| anything else | falls back to closest preset |

If detection is unreliable at your resolution, you can override the level region. Right-click the tray icon → **Show config path** to see where to drop a `config.json` with custom coordinates.

## Shop data

Hardcoded in [`nullscape_overlay/shops.py`](nullscape_overlay/shops.py). If the meta changes, edit that file and rebuild.

| Level | Total cost | Notes |
|---:|---:|---|
| 3 | 415 | Paycheck, Business License, *maybe* Adrenaline |
| 5 | 714 | Swiftness Rings, Medal, Adrenaline, Business License, Paycheck, *maybe* Defuse Kit |
| 8 | 1996 | Double Jump, Grace Wings, Swiftness Rings, Paycheck, Ice Skates, *maybe* Defuse Kit + Lap 2 curse |
| 10 | 2642 | Pocket Bell, Adv. Gravity Coil, Swiftness Rings, Tria Orbs, Paycheck, Fanny Pack, choose Helmet+Radar OR More Alters |
| 13 | 1764 | Ninja Belt, *maybe* Bigger Grapple Points, choose Radar+Helmet OR More Alters |
| 15 | 7870 | Shield, Sports Shoes |

## Build from source

```powershell
git clone <this-repo>
cd nullscape-overlay
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
python -m nullscape_overlay          # run from source
pyinstaller build.spec               # build dist/NullscapeOverlay.exe
```

## Releasing

Push a tag matching `v*`:

```
git tag v0.1.0
git push origin v0.1.0
```

The GitHub Actions workflow builds the Windows `.exe` on `windows-latest` and attaches it to a new GitHub Release.

## Credits

Upgrade icons sourced from the [official Nullscape wiki](https://nullscape.wiki/wiki/Upgrades) (CC BY-SA).
