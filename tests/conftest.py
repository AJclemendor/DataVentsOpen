from __future__ import annotations

from pathlib import Path
import sys


def pytest_configure(config):
    # Find nearest repo root that has a `src/datavents` package
    here = Path(__file__).resolve()
    root = None
    for p in [here.parent] + list(here.parents):
        if (p / "src" / "datavents").exists():
            root = p
            break
    if root is None:
        # Fallback to historical relative
        root = Path(__file__).parent.parent.parent.parent
    # Ensure `src` is on sys.path for package imports
    src_dir = root / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    # Create test output dirs (gitignored)
    for d in (
        root / ".test_output",
        root / ".test-output",
        root / ".test_output" / "normalized",
    ):
        try:
            d.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
