# PyInstaller spec for the Nullscape Overlay.
# Produces dist/NullscapeOverlay.exe (single file, no console window).
# Build with:  pyinstaller build.spec
from pathlib import Path

block_cipher = None
root = Path(SPECPATH)
pkg = root / "nullscape_overlay"

datas = [
    (str(pkg / "assets" / "icons"), "assets/icons"),
    (str(pkg / "assets" / "digits"), "assets/digits"),
]

a = Analysis(
    [str(pkg / "__main__.py")],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "test",
        "unittest",
        "pydoc",
        "doctest",
        "xmlrpc",
        "PyQt6.QtNetwork",
        "PyQt6.QtQml",
        "PyQt6.QtQuick",
        "PyQt6.QtMultimedia",
        "PyQt6.QtWebEngineCore",
        "PyQt6.QtWebEngineWidgets",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
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
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
