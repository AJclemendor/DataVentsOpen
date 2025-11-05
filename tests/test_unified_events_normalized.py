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
from datavents import normalize_event, normalize_search_response
from datavents import Provider, Event


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


def _first_kalshi_event_ticker(data: Dict[str, Any]) -> Optional[str]:
    cp = data.get("current_page")
    if isinstance(cp, list):
        for it in cp:
            if isinstance(it, dict):
                et = (it.get("event_ticker") or it.get("ticker") or "").strip()
                if et:
                    return et
    return None


def _first_polymarket_event_id_slug(data: Dict[str, Any]) -> tuple[Optional[int], Optional[str]]:
    events = data.get("events")
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


def test_list_events_kalshi_normalized_live(client: DataVentsNoAuthClient):
    raw_res = client.list_events(
        provider=DataVentsProviders.KALSHI,
        limit=5,
        page=0,
        status_params=DataVentsStatusParams.OPEN_MARKETS,
        query="election",
        order_sort_params=DataVentsOrderSortParams.ORDER_BY_TRENDING,
    )[0]["data"]
    norm = normalize_search_response(Provider.kalshi, raw_res, q="election", page=1, limit=5)
    assert norm.results and isinstance(norm.results[0], Event)
    _save("kalshi-list-events-normalized", norm)


def test_list_events_polymarket_normalized_live(client: DataVentsNoAuthClient):
    raw_res = client.list_events(
        provider=DataVentsProviders.POLYMARKET,
        limit=5,
        page=0,
        status_params=DataVentsStatusParams.OPEN_MARKETS,
        query="election",
        order_sort_params=DataVentsOrderSortParams.ORDER_BY_TRENDING,
    )[0]["data"]
    norm = normalize_search_response(Provider.polymarket, raw_res, q="election", page=1, limit=5)
    assert norm.results and isinstance(norm.results[0], Event)
    _save("polymarket-list-events-normalized", norm)


def test_get_event_kalshi_normalized_live(client: DataVentsNoAuthClient):
    sr = client.search_events(
        provider=DataVentsProviders.KALSHI,
        query="election",
        limit=3,
        page=0,
        order_sort_params=DataVentsOrderSortParams.ORDER_BY_TRENDING,
        status_params=DataVentsStatusParams.OPEN_MARKETS,
    )[0]["data"]
    et = _first_kalshi_event_ticker(sr)
    if not et:
        pytest.skip("no kalshi event ticker found")
    raw = client.get_event(provider=DataVentsProviders.KALSHI, kalshi_event_ticker=et, with_nested_markets=True)[0]["data"]
    ev = normalize_event(Provider.kalshi, raw)
    assert isinstance(ev, Event) and ev.event_id
    _save("kalshi-get-event-normalized", ev)


def test_get_event_polymarket_normalized_live(client: DataVentsNoAuthClient):
    sr = client.search_events(
        provider=DataVentsProviders.POLYMARKET,
        query="election",
        limit=5,
        page=0,
        order_sort_params=DataVentsOrderSortParams.ORDER_BY_TRENDING,
        status_params=DataVentsStatusParams.OPEN_MARKETS,
    )[0]["data"]
    pid, slug = _first_polymarket_event_id_slug(sr)
    if pid is None and not slug:
        pytest.skip("no polymarket event id/slug found")
    if pid is not None:
        raw = client.get_event(provider=DataVentsProviders.POLYMARKET, polymarket_id=int(pid))[0]["data"]
    else:
        raw = client.get_event(provider=DataVentsProviders.POLYMARKET, polymarket_slug=str(slug))[0]["data"]
    ev = normalize_event(Provider.polymarket, raw)
    assert isinstance(ev, Event) and ev.event_id
    _save("polymarket-get-event-normalized", ev)

