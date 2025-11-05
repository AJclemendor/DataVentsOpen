from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional, Dict

import pytest

from datavents import (
    DataVentsNoAuthClient,
    DataVentsProviders,
    DataVentsOrderSortParams,
    DataVentsStatusParams,
)
from datavents import normalize_market
from datavents import Provider, Market


def _save(name: str, data: Any) -> None:
    root = Path(__file__).parent.parent.parent.parent
    out = root / ".test_output" / "normalized" / f"{name}.json"
    with open(out, "w") as f:
        if hasattr(data, "model_dump"):
            json.dump(data.model_dump(), f, indent=2)
        else:
            json.dump(data, f, indent=2)


@pytest.fixture
def client() -> DataVentsNoAuthClient:
    return DataVentsNoAuthClient()


def _discover_kalshi_market_ticker(client: DataVentsNoAuthClient) -> Optional[str]:
    sr = client.search_events(
        provider=DataVentsProviders.KALSHI,
        query=" ",
        limit=5,
        page=0,
        order_sort_params=DataVentsOrderSortParams.ORDER_BY_TRENDING,
        status_params=DataVentsStatusParams.OPEN_MARKETS,
    )[0]["data"]
    page = sr.get("current_page") or []
    for ev in page:
        if isinstance(ev, dict):
            for m in ev.get("markets", []) or []:
                if isinstance(m, dict):
                    t = (m.get("ticker") or m.get("ticker_name") or "").strip()
                    if t:
                        return t
    return None


def _discover_polymarket_market(client: DataVentsNoAuthClient) -> tuple[Optional[int], Optional[str]]:
    res = client.list_markets(
        provider=DataVentsProviders.POLYMARKET,
        limit=10,
        page=1,
        status_params=DataVentsStatusParams.OPEN_MARKETS,
        query=" ",
        order_sort_params=DataVentsOrderSortParams.ORDER_BY_TRENDING,
    )[0]["data"]
    markets = res.get("markets") or res.get("Markets") or []
    for it in markets:
        if isinstance(it, dict):
            mid = it.get("id") or it.get("marketId")
            slug = it.get("slug") or it.get("marketSlug")
            try:
                mid_i = int(mid) if mid is not None else None
            except Exception:
                mid_i = None
            if mid_i is not None or (isinstance(slug, str) and slug):
                return mid_i, (slug if isinstance(slug, str) else None)
    return None, None


def test_list_markets_kalshi_normalized_live(client: DataVentsNoAuthClient):
    res = client.list_markets(
        provider=DataVentsProviders.KALSHI,
        limit=5,
        page=0,
        status_params=DataVentsStatusParams.OPEN_MARKETS,
        query=" ",
        order_sort_params=DataVentsOrderSortParams.ORDER_BY_TRENDING,
    )[0]["data"]
    markets_raw = []
    for ev in res.get("current_page") or []:
        if isinstance(ev, dict):
            markets_raw.extend([m for m in (ev.get("markets") or []) if isinstance(m, dict)])
    normalized = [normalize_market(Provider.kalshi, m) for m in markets_raw[:5]]
    assert normalized and isinstance(normalized[0], Market)
    _save("kalshi-list-markets-normalized", [m.model_dump() for m in normalized])


def test_list_markets_polymarket_normalized_live(client: DataVentsNoAuthClient):
    res = client.list_markets(
        provider=DataVentsProviders.POLYMARKET,
        limit=10,
        page=1,
        status_params=DataVentsStatusParams.OPEN_MARKETS,
        query=" ",
        order_sort_params=DataVentsOrderSortParams.ORDER_BY_TRENDING,
    )[0]["data"]
    markets_raw = res.get("markets") or res.get("Markets") or []
    normalized = [normalize_market(Provider.polymarket, m) for m in markets_raw[:5] if isinstance(m, dict)]
    assert normalized and isinstance(normalized[0], Market)
    _save("polymarket-list-markets-normalized", [m.model_dump() for m in normalized])


def test_get_market_kalshi_normalized_live(client: DataVentsNoAuthClient):
    ticker = _discover_kalshi_market_ticker(client)
    if not ticker:
        pytest.skip("no kalshi market ticker discoverable")
    raw = client.get_market(provider=DataVentsProviders.KALSHI, kalshi_ticker=ticker)[0]["data"]
    m = normalize_market(Provider.kalshi, raw)
    assert isinstance(m, Market) and m.market_id
    _save("kalshi-get-market-normalized", m)


def test_get_market_polymarket_normalized_live(client: DataVentsNoAuthClient):
    mid, slug = _discover_polymarket_market(client)
    if mid is None and not slug:
        pytest.skip("no polymarket market discoverable")
    if mid is not None:
        raw = client.get_market(provider=DataVentsProviders.POLYMARKET, polymarket_id=int(mid))[0]["data"]
    else:
        raw = client.get_market(provider=DataVentsProviders.POLYMARKET, polymarket_slug=str(slug))[0]["data"]
    m = normalize_market(Provider.polymarket, raw)
    assert isinstance(m, Market) and m.market_id
    _save("polymarket-get-market-normalized", m)

