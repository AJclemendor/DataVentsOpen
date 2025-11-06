from __future__ import annotations

from datavents.normalize import normalize_orderbook
from datavents.schemas import Provider


def test_normalize_orderbook_polymarket_sample():
    raw = {
        "token_id": "TID",
        "data": {
            "market": "0xabc",
            "asset_id": "TID",
            "timestamp": "1762393948209",
            "bids": [{"price": "0.010", "size": "100"}, {"price": "0.002", "size": "50"}],
            "asks": [{"price": "0.990", "size": "25"}],
            "min_order_size": "5",
            "tick_size": "0.001",
            "neg_risk": True,
        },
    }
    ob = normalize_orderbook(Provider.polymarket, raw, token_id="TID")
    d = ob.model_dump()
    assert d["provider"] == "polymarket"
    assert d["token_id"] == "TID"
    assert isinstance(d["bids"], list) and len(d["bids"]) == 2
    # Bids sorted desc
    assert d["bids"][0]["price"] == 0.01
    assert d["bids"][1]["price"] == 0.002
    assert d["asks"][0]["price"] == 0.99


def test_normalize_orderbook_kalshi_sample_yes_only():
    raw = {
        "ticker": "ABC-24-XYZ-T50",
        "data": {
            "orderbook": {
                "yes_dollars": [["0.9500", 15325], ["0.9600", 10]],
                "no_dollars": None,
            }
        },
    }
    ob = normalize_orderbook(Provider.kalshi, raw, ticker="ABC-24-XYZ-T50")
    d = ob.model_dump()
    assert d["provider"] == "kalshi"
    assert d["ticker"] == "ABC-24-XYZ-T50"
    assert isinstance(d["bids"], list) and len(d["bids"]) == 2
    assert [lvl["price"] for lvl in d["bids"]] == [0.96, 0.95]
    assert isinstance(d["asks"], list) and len(d["asks"]) == 0
