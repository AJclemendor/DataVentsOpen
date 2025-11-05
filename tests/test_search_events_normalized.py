from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from datavents import (
    DataVentsNoAuthClient,
    DataVentsProviders,
    DataVentsOrderSortParams,
    DataVentsStatusParams,
)
from datavents import normalize_search_response
from datavents import Provider, OrderSort, StatusFilter, SearchResponseNormalized


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


def test_kalshi_search_events_normalized_live(client: DataVentsNoAuthClient):
    res = client.search_events(
        provider=DataVentsProviders.KALSHI,
        query="election",
        limit=5,
        page=0,
        order_sort_params=DataVentsOrderSortParams.ORDER_BY_TRENDING,
        status_params=DataVentsStatusParams.OPEN_MARKETS,
    )
    raw = res[0]["data"]
    norm = normalize_search_response(
        Provider.kalshi,
        raw,
        q="election",
        page=1,
        limit=5,
        order=OrderSort.trending,
        status=StatusFilter.open,
    )
    assert isinstance(norm, SearchResponseNormalized)
    assert norm.results and norm.meta.provider == "kalshi"
    _save("kalshi-search-events-normalized", norm)


def test_polymarket_search_events_normalized_live(client: DataVentsNoAuthClient):
    res = client.search_events(
        provider=DataVentsProviders.POLYMARKET,
        query="election",
        limit=5,
        page=0,
        order_sort_params=DataVentsOrderSortParams.ORDER_BY_TRENDING,
        status_params=DataVentsStatusParams.OPEN_MARKETS,
    )
    raw = res[0]["data"]
    norm = normalize_search_response(
        Provider.polymarket,
        raw,
        q="election",
        page=1,
        limit=5,
        order=OrderSort.trending,
        status=StatusFilter.open,
    )
    assert isinstance(norm, SearchResponseNormalized)
    assert norm.results and norm.meta.provider == "polymarket"
    _save("polymarket-search-events-normalized", norm)

