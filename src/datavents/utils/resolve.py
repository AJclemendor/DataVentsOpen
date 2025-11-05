from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

try:
    # Optional import to avoid circulars during docs build
    from datavents.providers.polymarket.polymarket_rest_noauth import PolymarketRestNoAuth
except Exception:  # pragma: no cover - type hints only
    PolymarketRestNoAuth = object  # type: ignore


AssetLike = Union[str, int]


def _is_candidate_asset_id(val: Any) -> bool:
    if not isinstance(val, str):
        return False
    s = val.strip()
    if len(s) < 3:
        return False
    # Keep it generous: alnum + - _  (covers uuids, base36, hex, etc.)
    for ch in s:
        if not (ch.isalnum() or ch in {"-", "_"}):
            return False
    return True


def _collect_asset_ids_from_obj(obj: Any, *, max_items: Optional[int] = None) -> List[str]:
    """Depth‑limited scan for asset ids in common Polymarket shapes.

    Looks for keys like: asset_id, assetId, assets_ids, assetsIds, clobTokenIds, clob_token_ids,
    outcomes[*].asset_id, markets[*].outcomes[*].asset_id, etc.
    """
    keys_single = {"asset_id", "assetId"}
    keys_multi = {"assets_ids", "assetsIds", "clobTokenIds", "clob_token_ids", "asset_ids"}

    out: List[str] = []

    def add_one(v: Any) -> None:
        if isinstance(v, str) and _is_candidate_asset_id(v):
            out.append(v)

    def add_many(v: Any) -> None:
        if isinstance(v, (list, tuple)):
            for it in v:
                add_one(it)

    def walk(x: Any, depth: int = 0) -> None:
        if max_items is not None and len(out) >= max_items:
            return
        if depth > 4:
            return
        if isinstance(x, Mapping):
            for k, v in x.items():
                ks = str(k)
                if ks in keys_single:
                    add_one(v)
                elif ks in keys_multi:
                    add_many(v)
                elif ks == "outcomes" and isinstance(v, (list, tuple)):
                    for o in v:
                        if isinstance(o, Mapping):
                            add_one(o.get("asset_id") or o.get("assetId") or o.get("id"))
                else:
                    walk(v, depth + 1)
        elif isinstance(x, (list, tuple)):
            for it in x:
                walk(it, depth + 1)

    walk(obj, 0)
    # de‑dupe preserving order
    seen = set()
    uniq = []
    for a in out:
        if a not in seen:
            uniq.append(a)
            seen.add(a)
    return uniq if max_items is None else uniq[: max(0, int(max_items))]


def find_polymarket_asset_ids(obj: Any, *, max_items: Optional[int] = None) -> List[str]:
    """Public helper to collect asset/clob ids from arbitrary nested objects."""
    return _collect_asset_ids_from_obj(obj, max_items=max_items)


def resolve_polymarket_assets_ids(
    source: Any,
    *,
    client: Optional[PolymarketRestNoAuth] = None,
    fetch: bool = True,
    max_items: Optional[int] = None,
) -> List[str]:
    """Resolve Polymarket WS `assets_ids` from flexible inputs.

    Accepts:
    - string (comma/space separated), list/tuple of strings
    - dicts resembling public-search or market detail payloads
    - markers like "id:123456" or "slug:will-xyz" when a client is provided

    If `client` is provided and `fetch=True`, will attempt to expand numeric ids or slugs
    by fetching `get_market_by_id/slug` and scanning for asset ids.
    """
    if source is None:
        return []

    ids: List[str] = []
    pending_ids: List[int] = []
    pending_slugs: List[str] = []

    def handle_token(tok: str) -> None:
        s = tok.strip()
        if not s:
            return
        # Tagged markers
        if s.startswith("id:"):
            try:
                pending_ids.append(int(s.split(":", 1)[1]))
            except Exception:
                pass
            return
        if s.startswith("slug:"):
            pending_slugs.append(s.split(":", 1)[1].strip())
            return
        # Heuristics
        if s.isdigit():
            try:
                pending_ids.append(int(s))
            except Exception:
                pass
            return
        # UUID/slug/asset id
        if _is_candidate_asset_id(s):
            # Could be asset id; if it's slug‑like we’ll also try to fetch later
            ids.append(s)
            if "-" in s and not s.replace("-", "").isalnum():
                # Skip: covered by _is_candidate_asset_id already
                pass
        else:
            # treat as slug if it looks like one
            if "-" in s:
                pending_slugs.append(s)

    def handle_any(x: Any) -> None:
        if isinstance(x, str):
            parts = _split_tokens(x)
            for p in parts:
                handle_token(p)
        elif isinstance(x, (list, tuple, set)):
            for it in x:
                handle_any(it)
        elif isinstance(x, Mapping):
            ids.extend(_collect_asset_ids_from_obj(x, max_items=max_items))
        else:
            # try to stringify
            s = str(x)
            handle_token(s)

    def _split_tokens(s: str) -> List[str]:
        if "," in s:
            items = sum([p.strip().split() for p in s.split(",")], [])
        else:
            items = s.split()
        return [i.strip() for i in items if i.strip()]

    handle_any(source)

    # Optionally fetch to expand ids/slugs
    if client is not None and fetch and (pending_ids or pending_slugs):
        for mid in pending_ids:
            try:
                data = client.get_market_by_id(id=int(mid), include_tag=False)
                ids.extend(_collect_asset_ids_from_obj(data, max_items=max_items))
            except Exception:
                continue
        for slug in pending_slugs:
            try:
                data = client.get_market_by_slug(slug=str(slug), include_tag=False)
                ids.extend(_collect_asset_ids_from_obj(data, max_items=max_items))
            except Exception:
                continue

    # Return de‑duplicated
    seen = set()
    out: List[str] = []
    for a in ids:
        if not _is_candidate_asset_id(a):
            continue
        if a in seen:
            continue
        out.append(a)
        seen.add(a)
        if max_items is not None and len(out) >= max_items:
            break
    return out


# Back‑compat alias for legacy callers
def _resolve_polymarket_assets_ids(*args: Any, **kwargs: Any) -> List[str]:
    """Back‑compat alias accepting multiple signatures.

    Supported forms:
    - _resolve_polymarket_assets_ids(source, *, client=None, fetch=True, max_items=None)
    - _resolve_polymarket_assets_ids(payload, market, client)
    """
    if len(args) >= 3 and isinstance(args[0], Mapping) and isinstance(args[1], Mapping):
        src_list: List[Any] = [args[0], args[1]]
        client = args[2]
        return resolve_polymarket_assets_ids(src_list, client=client, fetch=True)
    if len(args) >= 1:
        source = args[0]
        return resolve_polymarket_assets_ids(source, client=kwargs.get("client"), fetch=kwargs.get("fetch", True), max_items=kwargs.get("max_items"))
    return []
