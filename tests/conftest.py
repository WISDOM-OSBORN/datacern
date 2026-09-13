"""Shared pytest fixtures: ensure ``src/`` layout is importable."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

os.environ.setdefault("MPLBACKEND", "Agg")
