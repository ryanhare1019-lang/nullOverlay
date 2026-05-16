"""PyInstaller entry point. Boots the nullscape_overlay package.

We need a top-level script (outside the package) because PyInstaller runs the
entry script as __main__ with no package context, which breaks any relative
imports inside that script. Going through this thin shim, the package's own
__main__.py is imported as nullscape_overlay.__main__ and its `from .x import`
lines resolve normally.
"""
from __future__ import annotations

import sys

from nullscape_overlay.__main__ import main


if __name__ == "__main__":
    sys.exit(main())
