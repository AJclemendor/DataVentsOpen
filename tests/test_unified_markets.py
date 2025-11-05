"""Real-API tests for DataVentsNoAuthClient unified market methods.

This mirrors the events tests and hits live provider endpoints (no mocks).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from datavents import (
    DataVentsNoAuthClient,
    DataVentsProviders,
    DataVentsOrderSortParams,
    DataVentsStatusParams,
)


def _write_debug(filename: str, data: Any) -> None:
    root = Path(__file__).parent.parent.parent.parent
    for name in (".test_output", ".test-output"):
        d = root / name
        d.mkdir(exist_ok=True)
        try:
            with open(d / filename, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass


def _discover_kalshi_market_ticker(client: DataVentsNoAuthClient) -> Optional[str]:
    # Reuse event search to flatten a market ticker (ticker_name)
    sr = client.search_events(
        provider=DataVentsProviders.KALSHI,
        query=" ",
        limit=5,
        page=0,
        order_sort_params=DataVentsOrderSortParams.ORDER_BY_TRENDING,
        status_params=DataVentsStatusParams.OPEN_MARKETS,
    )
    data = sr[0]["data"] if sr else {}
    page = data.get("current_page") or []
    for ev in page:
        if isinstance(ev, dict):
            for m in ev.get("markets", []) or []:
                if isinstance(m, dict):
                    t = (m.get("ticker_name") or "").strip()
                    if t:
                        return t
    return None


def _discover_polymarket_market(client: DataVentsNoAuthClient) -> tuple[Optional[int], Optional[str]]:
    # Try a few pages and sort orders to reliably find a market with id or slug
    sorts = [
        DataVentsOrderSortParams.ORDER_BY_TRENDING,
        DataVentsOrderSortParams.ORDER_BY_VOLUME,
        DataVentsOrderSortParams.ORDER_BY_LIQUIDITY,
        DataVentsOrderSortParams.ORDER_BY_NEWEST,
    ]
    queries = [" ", "bitcoin", "trump", "election", "usd"]
    for order in sorts:
        for q in queries:
            for page in (1, 2, 3, 4, 5):
                try:
                    res = client.list_markets(
                        provider=DataVentsProviders.POLYMARKET,
                        limit=20,
                        page=page,
                        status_params=DataVentsStatusParams.OPEN_MARKETS,
                        query=q,
                        order_sort_params=order,
                    )
                    data = res[0]["data"] if res else {}
                except Exception as e:
                    _write_debug("polymarket_market_discovery_error.json", {
                        "order": order.name,
                        "q": q,
                        "page": page,
                        "error": str(e),
                    })
                    continue
                # data can have markets under different keys depending on search version
                markets = data.get("markets") or data.get("Markets") or []
                if isinstance(markets, list):
                    for it in markets:
                        if isinstance(it, dict):
                            mid = it.get("id") or it.get("marketId") or it.get("market_id")
                            slug = it.get("slug") or it.get("marketSlug")
                            try:
                                mid_i = int(mid) if mid is not None else None
                            except Exception:
                                mid_i = None
                            if mid_i is not None or (isinstance(slug, str) and slug):
                                _write_debug("polymarket_market_discovery.json", {
                                    "order": order.name,
                                    "q": q,
                                    "page": page,
                                    "id": mid_i,
                                    "slug": slug,
                                })
                                return mid_i, (slug if isinstance(slug, str) else None)
    return None, None


class TestUnifiedMarkets:
    @pytest.fixture
    def client(self) -> DataVentsNoAuthClient:
        return DataVentsNoAuthClient()

    def test_list_markets_kalshi_real_api(self, client: DataVentsNoAuthClient):
        print("\n=== Unified list_markets: KALSHI ===")
        res = client.list_markets(
            provider=DataVentsProviders.KALSHI,
            limit=5,
            page=0,
            status_params=DataVentsStatusParams.OPEN_MARKETS,
        )
        assert isinstance(res, list) and len(res) == 1
        assert res[0]["provider"] == "kalshi"
        data = res[0]["data"]
        assert isinstance(data, dict)
        _write_debug("kalshi_list_markets_open.json", {"keys": list(data.keys())})

    def test_list_markets_polymarket_real_api(self, client: DataVentsNoAuthClient):
        print("\n=== Unified list_markets: POLYMARKET ===")
        res = client.list_markets(
            provider=DataVentsProviders.POLYMARKET,
            limit=5,
            page=0,
            status_params=DataVentsStatusParams.OPEN_MARKETS,
            query=" ",
        )
        assert isinstance(res, list) and len(res) == 1
        assert res[0]["provider"] == "polymarket"
        data = res[0]["data"]
        assert isinstance(data, dict)
        mk = data.get("markets")
        if mk is not None:
            assert isinstance(mk, list)
        _write_debug("polymarket_list_markets_open.json", {"has_markets": mk is not None})

    def test_list_markets_all_parallel(self, client: DataVentsNoAuthClient):
        print("\n=== Unified list_markets: ALL ===")
        res = client.list_markets(
            provider=DataVentsProviders.ALL,
            limit=3,
            page=0,
            status_params=DataVentsStatusParams.OPEN_MARKETS,
            query=" ",
        )
        providers = {r.get("provider") for r in res}
        assert providers == {"kalshi", "polymarket"}
        _write_debug("unified_markets_list_output.json", {"providers": list(providers)})

    def test_get_market_kalshi_real_api(self, client: DataVentsNoAuthClient):
        print("\n=== Unified get_market: KALSHI ===")
        mt = _discover_kalshi_market_ticker(client)
        if not mt:
            pytest.skip("No Kalshi market ticker discovered from events")
        res = client.get_market(
            provider=DataVentsProviders.KALSHI,
            kalshi_ticker=mt,
        )
        assert isinstance(res, list) and len(res) == 1
        assert res[0]["provider"] == "kalshi"
        assert isinstance(res[0]["data"], dict)

    def test_get_market_polymarket_by_id_real_api(self, client: DataVentsNoAuthClient):
        print("\n=== Unified get_market: POLYMARKET by id ===")
        mid, slug = _discover_polymarket_market(client)
        if mid is None and not slug:
            pytest.skip("No Polymarket market discovered")
        if mid is None:
            # If only slug available, first fetch by slug to get id
            assert slug, "No slug either — discovery should have found one"
            data = client.get_market(
                provider=DataVentsProviders.POLYMARKET,
                polymarket_slug=slug,
            )[0]["data"]
            mid = int(data.get("id")) if isinstance(data, dict) else None
            assert mid is not None, "Could not resolve market id from slug"
        res = client.get_market(provider=DataVentsProviders.POLYMARKET, polymarket_id=mid)
        assert isinstance(res, list) and len(res) == 1
        assert res[0]["provider"] == "polymarket"
        assert isinstance(res[0]["data"], dict)

    def test_get_market_polymarket_by_slug_real_api(self, client: DataVentsNoAuthClient):
        print("\n=== Unified get_market: POLYMARKET by slug ===")
        mid, slug = _discover_polymarket_market(client)
        if not slug:
            # If only id available, fetch by id to obtain slug
            assert mid is not None, "No id either — discovery should have found one"
            data = client.get_market(
                provider=DataVentsProviders.POLYMARKET,
                polymarket_id=mid,
            )[0]["data"]
            slug = data.get("slug") if isinstance(data, dict) else None
            assert isinstance(slug, str) and slug, "Could not resolve market slug from id"
        res = client.get_market(provider=DataVentsProviders.POLYMARKET, polymarket_slug=slug)
        assert isinstance(res, list) and len(res) == 1
        assert res[0]["provider"] == "polymarket"
        assert isinstance(res[0]["data"], dict)

    def test_polymarket_market_tags_real_api(self, client: DataVentsNoAuthClient):
        print("\n=== Polymarket market tags ===")
        mid, slug = _discover_polymarket_market(client)
        if mid is None and slug:
            # Resolve id via slug first
            data = client.get_market(
                provider=DataVentsProviders.POLYMARKET,
                polymarket_slug=slug,
            )[0]["data"]
            mid = int(data.get("id")) if isinstance(data, dict) else None
        assert mid is not None, "No numeric Polymarket market id available for tags test"
        tags = client.get_market_tags(market_id=int(mid))
        assert isinstance(tags, (list, dict))
