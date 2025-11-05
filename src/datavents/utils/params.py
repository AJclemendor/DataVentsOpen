from __future__ import annotations

from typing import Any, Iterable, List, Mapping, Optional, Sequence

from datavents.client import DataVentsProviders


def provider_from_param(value: Any, *, default: DataVentsProviders = DataVentsProviders.ALL) -> DataVentsProviders:
    if value is None:
        return default
    s = str(value).strip().lower()
    if s == "kalshi":
        return DataVentsProviders.KALSHI
    if s == "polymarket":
        return DataVentsProviders.POLYMARKET
    return default


def dedupe_preserve(items: Iterable[Any]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for it in items:
        s = str(it).strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def coerce_string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (str, bytes, bytearray, int, float)):
        if isinstance(value, (bytes, bytearray)):
            try:
                text = value.decode("utf-8")
            except Exception:
                text = value.decode("utf-8", errors="ignore")
        else:
            text = str(value)
        text = text.strip()
        return [text] if text else []
    if isinstance(value, Mapping):
        return []
    if isinstance(value, (list, tuple, set)):
        out: List[str] = []
        for item in value:
            out.extend(coerce_string_list(item))
        return dedupe_preserve(out)
    return []


def collect_strings(source: Optional[Mapping[str, Any]], keys: Sequence[str]) -> List[str]:
    if not isinstance(source, Mapping):
        return []
    collected: List[str] = []
    for key in keys:
        if key in source:
            collected.extend(coerce_string_list(source.get(key)))
    return dedupe_preserve(collected)


def first_int(keys: Sequence[str], *sources: Optional[Mapping[str, Any]]) -> Optional[int]:
    for key in keys:
        for source in sources:
            if not isinstance(source, Mapping):
                continue
            if key not in source:
                continue
            candidate = source.get(key)
            if candidate is None or isinstance(candidate, bool):
                continue
            try:
                text = str(candidate).strip()
                if not text:
                    continue
                return int(float(text))
            except Exception:
                continue
    return None


def first_str(keys: Sequence[str], *sources: Optional[Mapping[str, Any]]) -> Optional[str]:
    for key in keys:
        for source in sources:
            if not isinstance(source, Mapping):
                continue
            if key not in source:
                continue
            value = source.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
    return None

