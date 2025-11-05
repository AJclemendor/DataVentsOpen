from __future__ import annotations

from pathlib import Path
import sys


def pytest_configure(config):
    # Ensure `backend/src` is importable as `src.*`
    root = Path(__file__).resolve().parents[3]
    src_dir = root / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    # Create test output dirs for logs if needed
    for d in (root / ".test_output", root / ".test-output"):
        d.mkdir(parents=True, exist_ok=True)

