from __future__ import annotations

from datavents import normalize_market
from datavents import Provider, StatusNormalized, Market


def test_normalize_market_kalshi_binary_minimal():
    raw = {
        "id": "MKT123",
        "ticker": "SER-ABC-123",
        "event_ticker": "EVT-ABC",
        "series_ticker": "SER",
        "title": "Will it rain tomorrow?",
        "status": "opened",
        "yes_bid": 0.45,
        "yes_ask": 0.50,
        "last_price": 0.48,
        "liquidity": 10000,
        "volume_24h": 2500,
        "open_interest": 6000,
        "close_ts": 1730505600,  # seconds
    }

    m = normalize_market(Provider.kalshi, {"market": raw})
    assert isinstance(m, Market)
    assert m.provider == Provider.kalshi
    assert m.market_id == "MKT123"
    assert m.ticker == "SER-ABC-123"
    assert m.question == "Will it rain tomorrow?"
    assert m.status == StatusNormalized.open
    assert m.status_raw == "opened"
    assert m.best_bid == 0.45 and m.best_ask == 0.50 and m.last_price == 0.48
    assert m.mid_price and abs(m.mid_price - 0.475) < 1e-9
    assert m.volume_24h_usd == 2500
    assert m.open_interest_usd == 6000
    assert m.end_ts and m.end_ts > 10_000_000_000  # ms
    # outcomes present and well-formed
    assert m.outcomes and len(m.outcomes) == 2
    ys = next(o for o in m.outcomes if (o.side == "yes"))
    ns = next(o for o in m.outcomes if (o.side == "no"))
    assert ys.price == 0.48
    assert ys.best_bid == 0.45 and ys.best_ask == 0.50
    assert ns.price and abs(ns.price - 0.52) < 1e-9


def test_normalize_market_polymarket_binary_minimal():
    raw = {
        "id": 987654,
        "slug": "will-bitcoin-close-above-100k-in-2026",
        "question": "Will Bitcoin close above $100k in 2026?",
        "status": "active",
        "bestBid": 0.47,
        "bestAsk": 0.49,
        "lastPrice": 0.48,
        "liquidity": 50000,
        "volume24hr": 10000,
        "openInterest": 25000,
        "startDate": 1767225600,
        "endDate": 1769904000,
        "outcomes": [
            {"name": "Yes", "price": 0.48, "bestBid": 0.47, "bestAsk": 0.49},
            {"name": "No", "price": 0.52, "bestBid": 0.51, "bestAsk": 0.53},
        ],
    }

    m = normalize_market(Provider.polymarket, raw)
    assert isinstance(m, Market)
    assert m.provider == Provider.polymarket
    assert m.market_id == "987654"
    assert m.slug == "will-bitcoin-close-above-100k-in-2026"
    assert m.url and m.url.endswith(m.slug)
    assert m.status == StatusNormalized.open
    assert m.best_bid == 0.47 and m.best_ask == 0.49 and m.last_price == 0.48
    assert m.mid_price and abs(m.mid_price - 0.48) < 1e-9
    assert m.liquidity_usd == 50000
    assert m.volume_24h_usd == 10000
    assert m.open_interest_usd == 25000
    assert m.start_ts and m.end_ts
    assert m.start_ts > 10_000_000_000 and m.end_ts > 10_000_000_000  # ms
    assert m.outcomes and len(m.outcomes) == 2
    assert {o.name for o in m.outcomes} == {"Yes", "No"}

