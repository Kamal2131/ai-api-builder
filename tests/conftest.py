"""Shared pytest setup — put src/ on the import path so tests can import the app packages."""

import sys
from pathlib import Path

src_path = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(src_path))
