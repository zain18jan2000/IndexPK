"""Filesystem paths used across the app.

In development, ASSETS_DIR points at the repo's assets/ folder.
When frozen by PyInstaller, it points into the bundle (_MEIPASS).
Per-user writable data/logs go through platformdirs so the same
code works on Windows, macOS and Linux without hardcoded paths.
"""
from pathlib import Path
import sys

from platformdirs import user_data_dir, user_log_dir

APP_NAME = "IndexPK"

# --- bundled resources (read-only) -----------------------------------------
if getattr(sys, "frozen", False):           # PyInstaller bundle
    ASSETS_DIR = Path(sys._MEIPASS) / "assets"
else:                                        # running from source
    ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"

# --- per-user writable locations -------------------------------------------
DATA_DIR = Path(user_data_dir(APP_NAME))
LOG_DIR = Path(user_log_dir(APP_NAME))

DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)