from __future__ import annotations

from typing import Any, Iterable, List, Sequence

from datavents.schemas import Provider
from datavents.vendors import DvVendors


_ALIASES = {
    "kalshi": DvVendors.KALSHI,
    "k": DvVendors.KALSHI,
    "poly": DvVendors.POLYMARKET,
    "pm": DvVendors.POLYMARKET,
    "polymarket": DvVendors.POLYMARKET,
    "p": DvVendors.POLYMARKET,
}


def _normalize_token(token: Any) -> List[DvVendors]:
    if token is None:
        return []
    # Accept Provider / DvVendors enums directly
    if isinstance(token, DvVendors):
        return [token]
    if isinstance(token, Provider):
        return [DvVendors.from_provider(token)]

    # Strings: split on commas/spaces
    if isinstance(token, str):
        s = token.strip().lower()
        if not s:
            return []
        if s in {"all", "both", "*"}:
            return [DvVendors.KALSHI, DvVendors.POLYMARKET]
        # split and map each piece
        parts = [p for p in _split_tokens(s) if p]
        out: List[DvVendors] = []
        for p in parts:
            v = _ALIASES.get(p)
            if v is not None:
                out.append(v)
        return out

    # Iterables (lists/tuples) of mixed content
    if isinstance(token, (list, tuple, set)):
        out: List[DvVendors] = []
        for t in token:
            out.extend(_normalize_token(t))
        return out

    return []


def _split_tokens(s: str) -> List[str]:
    # Split by comma or whitespace, collapse empties
    if "," in s:
        items = sum([p.strip().split() for p in s.split(",")], [])
    else:
        items = s.split()
    return [i.strip() for i in items if i.strip()]


def extract_vendors(value: Any = None, *, default: Sequence[DvVendors] = (DvVendors.KALSHI, DvVendors.POLYMARKET), strict: bool = False) -> List[DvVendors]:
    """Extract a de‑duplicated vendor list from flexible inputs.

    Accepts:
    - None → returns default
    - string: "kalshi", "polymarket", "poly,kalshi", "all", "*"
    - list/tuple/set: mixed tokens (strings, Provider, DvVendors)
    - Provider / DvVendors enums

    Returns a stable order list (Kalshi then Polymarket if both).

    If `strict=True`, raises ValueError when no valid vendors can be parsed.
    """
    tokens = _normalize_token(value)
    if not tokens:
        if strict and value is not None:
            raise ValueError("No valid vendors parsed from input")
        tokens = list(default)

    # de‑dupe and order: KALSHI, POLYMARKET
    seen = set()
    ordered = []
    for v in (DvVendors.KALSHI, DvVendors.POLYMARKET):
        if v in tokens and v not in seen:
            ordered.append(v)
            seen.add(v)

    if strict and not ordered:
        raise ValueError("No valid vendors parsed from input")
    return ordered


def to_provider_list(vendors: Sequence[DvVendors]) -> List[Provider]:
    """Map DvVendors → schemas.Provider list with preserved order."""
    out: List[Provider] = []
    for v in vendors:
        out.append(v.to_provider())
    return out


# Back-compat alias for legacy callers
def _extract_vendors(value: Any = None, *, default: Sequence[DvVendors] = (DvVendors.KALSHI, DvVendors.POLYMARKET), strict: bool = False) -> List[DvVendors]:
    return extract_vendors(value, default=default, strict=strict)
