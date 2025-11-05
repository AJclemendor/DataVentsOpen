from __future__ import annotations

from pathlib import Path
import sys


def pytest_configure(config):
    root = Path(__file__).parent.parent.parent.parent
    # Ensure `backend/src` is on sys.path for package imports
    src_dir = root / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    for d in (root / ".test_output", root / ".test-output", root / ".test_output" / "normalized"):
        try:
            d.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
