from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional


def _root_dir() -> Path:
    return Path(__file__).parent.parent.parent.parent


def ensure_output_dirs() -> tuple[Path, Path]:
    root = _root_dir()
    underscore = root / ".test_output"
    hyphen = root / ".test-output"
    underscore.mkdir(exist_ok=True)
    hyphen.mkdir(exist_ok=True)
    return underscore, hyphen


def stamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def write_json_artifact(name: str, data: Any, *, subdir: Optional[str] = None) -> list[Path]:
    underscore, hyphen = ensure_output_dirs()
    base_name = f"{name}-{stamp()}.json"
    paths: list[Path] = []
    for base in (underscore, hyphen):
        d = base / subdir if subdir else base
        d.mkdir(parents=True, exist_ok=True)
        p = d / base_name
        try:
            with open(p, "w") as f:
                json.dump(data, f, indent=2)
            paths.append(p)
        except Exception:
            pass
    return paths

