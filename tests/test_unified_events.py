"""Real-API tests for DataVentsNoAuthClient unified event methods.

These tests hit live Kalshi and Polymarket public APIs (no mocks),
mirroring the style of test_search_events.py.

Run with: pytest src/datavents/tests/test_unified_events.py -v -s
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


def _first_kalshi_event_ticker(from_data: Dict[str, Any]) -> Optional[str]:
    """Return a usable Kalshi event identifier from search payload.

    Preference:
    1) event_ticker (if present)
    2) ticker (fallback — appears to be the event identifier in search results)
    """
    cp = from_data.get("current_page")
    if isinstance(cp, list):
        for it in cp:
            if isinstance(it, dict):
                et = (it.get("event_ticker") or "").strip()
                if et:
                    return et
        for it in cp:
            if isinstance(it, dict):
                tk = (it.get("ticker") or "").strip()
                if tk:
                    return tk
    # Top-level fallbacks
    v = from_data.get("event_ticker")
    if isinstance(v, str) and v:
        return v
    v2 = from_data.get("ticker")
    if isinstance(v2, str) and v2:
        return v2
    return None


def _first_polymarket_event_id_slug(from_data: Dict[str, Any]) -> tuple[Optional[int], Optional[str]]:
    # Polymarket search returns { events: [ { id, slug, ... }, ... ] }
    # Events list returns { events: [ ... ] } as well.
    events = from_data.get("events")
    if isinstance(events, list):
        for it in events:
            if isinstance(it, dict):
                pid = it.get("id")
                slug = it.get("slug")
                try:
                    pid_i = int(pid) if pid is not None else None
                except Exception:
                    pid_i = None
                if pid_i is not None or (isinstance(slug, str) and slug):
                    return pid_i, (slug if isinstance(slug, str) else None)
    return None, None


class TestUnifiedEvents:
    @pytest.fixture
    def client(self) -> DataVentsNoAuthClient:
        return DataVentsNoAuthClient()

    # Debug helpers: write snapshots under backend/.test_output (and legacy .test-output)
    def _debug_dir(self) -> Path:
        p = Path(__file__).parent.parent.parent.parent / ".test_output"
        p.mkdir(exist_ok=True)
        return p

    def _debug_dir_hyphen(self) -> Path:
        p = Path(__file__).parent.parent.parent.parent / ".test-output"
        p.mkdir(exist_ok=True)
        return p

    def _write_debug(self, filename: str, data: Any) -> None:
        for base in (self._debug_dir(), self._debug_dir_hyphen()):
            try:
                with open(base / filename, "w") as f:
                    json.dump(data, f, indent=2)
            except Exception:
                pass

    def test_list_events_kalshi_real_api(self, client: DataVentsNoAuthClient):
        print("\n=== Unified list_events: KALSHI ===")
        res = client.list_events(
            provider=DataVentsProviders.KALSHI,
            limit=5,
            page=0,
            status_params=DataVentsStatusParams.OPEN_MARKETS,
            series_ticker="",
        )
        assert isinstance(res, list) and len(res) == 1
        assert res[0]["provider"] == "kalshi"
        data = res[0]["data"]
        assert isinstance(data, dict)
        print("Kalshi list keys:", list(data.keys()))
        self._write_debug(
            "kalshi_list_events_open.json",
            {
                "case": "list_events_kalshi_real_api",
                "keys": list(data.keys()),
                "total_results_count": data.get("total_results_count"),
                "first_items": (data.get("current_page") or [])[:3],
            },
        )

    def test_list_events_polymarket_real_api(self, client: DataVentsNoAuthClient):
        print("\n=== Unified list_events: POLYMARKET ===")
        res = client.list_events(
            provider=DataVentsProviders.POLYMARKET,
            limit=5,
            page=0,
            status_params=DataVentsStatusParams.OPEN_MARKETS,
        )
        assert isinstance(res, list) and len(res) == 1
        assert res[0]["provider"] == "polymarket"
        data = res[0]["data"]
        assert isinstance(data, dict)
        print("Polymarket list keys:", list(data.keys()))
        self._write_debug(
            "polymarket_list_events_open.json",
            {
                "case": "list_events_polymarket_real_api",
                "keys": list(data.keys()),
                "events_len": len(data.get("events", []) if isinstance(data, dict) else []),
                "first_events": (data.get("events") or [])[:3] if isinstance(data, dict) else [],
            },
        )
    
    def test_list_events_all_parallel(self, client: DataVentsNoAuthClient):
        print("\n=== Unified list_events: ALL (parallel) ===")
        res = client.list_events(
            provider=DataVentsProviders.ALL,
            limit=3,
            page=0,
            status_params=DataVentsStatusParams.OPEN_MARKETS,
        )
        assert isinstance(res, list)
        providers = {r.get("provider") for r in res}
        assert providers == {"kalshi", "polymarket"}

        # Save concise output
        formatted_output = {
            "test": "test_list_events_all_parallel",
            "providers": list(providers),
        }
        self._write_debug("unified_events_list_output.json", formatted_output)
        print("✅ Saved:", self._debug_dir() / "unified_events_list_output.json")

    def test_list_events_polymarket_all_status(self, client: DataVentsNoAuthClient):
        """Polymarket ALL_MARKETS should be supported by merging open+closed under the hood."""
        print("\n=== Unified list_events: POLYMARKET (ALL status) ===")
        res = client.list_events(
            provider=DataVentsProviders.POLYMARKET,
            limit=5,
            page=0,
            status_params=DataVentsStatusParams.ALL_MARKETS,
        )
        assert isinstance(res, list) and len(res) == 1
        assert res[0]["provider"] == "polymarket"
        data = res[0]["data"]
        assert isinstance(data, dict)
        # If the API exposes 'events', ensure it's a list
        evs = data.get("events")
        if evs is not None:
            assert isinstance(evs, list)
        self._write_debug("polymarket_list_events_all_status.json", data)

    def test_list_events_kalshi_all_status(self, client: DataVentsNoAuthClient):
        print("\n=== Unified list_events: KALSHI (ALL status) ===")
        res = client.list_events(
            provider=DataVentsProviders.KALSHI,
            limit=5,
            page=0,
            status_params=DataVentsStatusParams.ALL_MARKETS,
        )
        assert isinstance(res, list) and len(res) == 1
        assert res[0]["provider"] == "kalshi"
        assert isinstance(res[0]["data"], dict)
        self._write_debug("kalshi_list_events_all_status.json", res[0]["data"])

    def test_get_event_all_without_identifiers_raises(self, client: DataVentsNoAuthClient):
        print("\n=== Unified get_event: ALL without identifiers should error ===")
        with pytest.raises(ValueError):
            client.get_event(provider=DataVentsProviders.ALL)

    def test_get_event_kalshi_real_api(self, client: DataVentsNoAuthClient):
        print("\n=== Unified get_event: KALSHI ===")
        # Discover a ticker first
        ls = client.list_events(
            provider=DataVentsProviders.KALSHI,
            limit=5,
            status_params=DataVentsStatusParams.OPEN_MARKETS,
        )
        data_k = ls[0]["data"] if ls else {}
        ticker = _first_kalshi_event_ticker(data_k)
        if not ticker:
            # Dump discovery payload for debugging then assert
            self._write_debug(
                "kalshi_get_event_discovery.json",
                {
                    "case": "get_event_kalshi_real_api",
                    "keys": list(data_k.keys()),
                    "current_page_sample": (data_k.get("current_page") or [])[:5],
                },
            )
        assert ticker, f"Could not find a Kalshi event ticker in: {list(data_k.keys())}"
        print("Using Kalshi event_ticker:", ticker)
        self._write_debug(
            "kalshi_get_event_input.json",
            {"chosen_event_ticker": ticker},
        )

        res = client.get_event(
            provider=DataVentsProviders.KALSHI,
            kalshi_event_ticker=ticker,
            with_nested_markets=False,
        )
        assert isinstance(res, list) and len(res) == 1
        assert res[0]["provider"] == "kalshi"
        assert isinstance(res[0]["data"], dict)

    def test_get_event_polymarket_by_id_real_api(self, client: DataVentsNoAuthClient):
        print("\n=== Unified get_event: POLYMARKET by id ===")
        # Discover an event id via search
        sr = client.search_events(
            provider=DataVentsProviders.POLYMARKET,
            query="election",
            limit=5,
            page=0,
            order_sort_params=DataVentsOrderSortParams.ORDER_BY_TRENDING,
            status_params=DataVentsStatusParams.OPEN_MARKETS,
        )
        data_p = sr[0]["data"] if sr else {}
        pid, slug = _first_polymarket_event_id_slug(data_p)
        assert pid is not None or slug, "Could not locate a Polymarket event id or slug from search"
        if pid is None:
            pytest.skip("No numeric event id available; covered by slug test")
        res = client.get_event(
            provider=DataVentsProviders.POLYMARKET,
            polymarket_id=pid,
        )
        assert isinstance(res, list) and len(res) == 1
        assert res[0]["provider"] == "polymarket"
        assert isinstance(res[0]["data"], dict)

    def test_get_event_polymarket_by_slug_real_api(self, client: DataVentsNoAuthClient):
        print("\n=== Unified get_event: POLYMARKET by slug ===")
        # Discover an event slug via search
        sr = client.search_events(
            provider=DataVentsProviders.POLYMARKET,
            query="trump",
            limit=5,
            page=0,
            order_sort_params=DataVentsOrderSortParams.ORDER_BY_TRENDING,
            status_params=DataVentsStatusParams.OPEN_MARKETS,
        )
        data_p = sr[0]["data"] if sr else {}
        pid, slug = _first_polymarket_event_id_slug(data_p)
        if not slug:
            pytest.skip("No event slug available from search")
        res = client.get_event(
            provider=DataVentsProviders.POLYMARKET,
            polymarket_slug=slug,
        )
        assert isinstance(res, list) and len(res) == 1
        assert res[0]["provider"] == "polymarket"
        assert isinstance(res[0]["data"], dict)

    def test_get_event_all_combined_real_api(self, client: DataVentsNoAuthClient):
        print("\n=== Unified get_event: ALL ===")
        # Discover one Kalshi ticker and one Polymarket slug
        ls_k = client.list_events(
            provider=DataVentsProviders.KALSHI,
            limit=3,
            status_params=DataVentsStatusParams.OPEN_MARKETS,
        )
        ticker = _first_kalshi_event_ticker(ls_k[0]["data"]) if ls_k else None

        sr_p = client.search_events(
            provider=DataVentsProviders.POLYMARKET,
            query="election",
            limit=3,
            page=0,
            order_sort_params=DataVentsOrderSortParams.ORDER_BY_TRENDING,
            status_params=DataVentsStatusParams.OPEN_MARKETS,
        )
        _, slug = _first_polymarket_event_id_slug(sr_p[0]["data"]) if sr_p else (None, None)

        if not ticker and not slug:
            pytest.skip("Could not discover identifiers for both providers")
        res = client.get_event(
            provider=DataVentsProviders.ALL,
            kalshi_event_ticker=ticker,
            polymarket_slug=slug,
        )
        assert isinstance(res, list)
        provs = {r.get("provider") for r in res}
        assert provs <= {"kalshi", "polymarket"} and len(res) >= 1
        self._write_debug("get_event_all_combined.json", {"provs": list(provs), "results_len": len(res)})

    def test_kalshi_event_metadata_real_api(self, client: DataVentsNoAuthClient):
        print("\n=== Kalshi event metadata ===")
        ls = client.list_events(
            provider=DataVentsProviders.KALSHI,
            limit=5,
            status_params=DataVentsStatusParams.OPEN_MARKETS,
        )
        ticker = _first_kalshi_event_ticker(ls[0]["data"]) if ls else None
        if not ticker:
            # Capture the listing response to debug why ticker wasn't available
            self._write_debug(
                "kalshi_event_metadata_discovery.json",
                ls[0]["data"] if ls else {},
            )
            pytest.skip("No Kalshi event ticker available for metadata test")
        meta = client.get_event_metadata(event_ticker=ticker)
        assert isinstance(meta, dict)

    def test_polymarket_event_tags_real_api(self, client: DataVentsNoAuthClient):
        print("\n=== Polymarket event tags ===")
        sr = client.search_events(
            provider=DataVentsProviders.POLYMARKET,
            query="election",
            limit=5,
            page=0,
            order_sort_params=DataVentsOrderSortParams.ORDER_BY_TRENDING,
            status_params=DataVentsStatusParams.OPEN_MARKETS,
        )
        data_p = sr[0]["data"] if sr else {}
        pid, _ = _first_polymarket_event_id_slug(data_p)
        if pid is None:
            pytest.skip("No numeric Polymarket event id available for tags test")
        tags = client.get_event_tags(event_id=pid)
        # Polymarket returns a list of tags for an event
        assert isinstance(tags, (list, dict))
