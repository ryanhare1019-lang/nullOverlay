# PyInstaller 6+ spec for the Nullscape Overlay.
# Produces dist/NullscapeOverlay.exe (single file, no console window).
# Build with:  pyinstaller build.spec --noconfirm --clean
from pathlib import Path

root = Path(SPECPATH)
pkg = root / "nullscape_overlay"

# Bundle assets at <bundle_root>/assets/... so config.asset_dir() resolves to
# sys._MEIPASS/assets at runtime (matching the dev-mode <pkg>/assets layout
# via Path(__file__).parent). Digits are synthesized at runtime so we don't
# ship a digits subtree.
datas = [
    (str(pkg / "assets" / "icons"), "assets/icons"),
]

a = Analysis(
    [str(pkg / "__main__.py")],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "PyQt6.sip",
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "test",
        "unittest",
        "pydoc",
        "doctest",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="NullscapeOverlay",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
