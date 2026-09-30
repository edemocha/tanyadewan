"""Vercel entrypoint: the same FastAPI app as local, in public mode, on the CPU models.

Everything it needs next to this file is assembled by build.py (src/, config*.yaml, data/, models/).
"""

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "src"))
os.environ.setdefault("PUBLIC_MODE", "1")
os.environ.setdefault("TANYADEWAN_OVERRIDE", str(HERE / "config.prod.yaml"))  # opened relative to the cwd otherwise

from tanyadewan.api.main import app  # noqa: E402  (path and env must be set first)

__all__ = ["app"]
