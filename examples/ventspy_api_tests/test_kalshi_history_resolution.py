from __future__ import annotations

import json
from typing import Any, Dict

import pytest


@pytest.fixture
def flask_client():
    # Ensure `backend/src` is on sys.path in case conftest didn't run yet
    import sys
    from pathlib import Path
    here = Path(__file__).resolve()
    backend_root = here.parents[3]
    src_dir = backend_root / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    from api.flask_app import app

    app.testing = True
    with app.test_client() as c:
        yield c


def _fake_requests_get(url: str, params: Dict[str, Any] | None = None, timeout: int | float | None = None):
    class _Resp:
        def __init__(self, status_code: int, payload: Dict[str, Any]):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

        def raise_for_status(self):
            if not (200 <= self.status_code < 300):
                raise Exception(f"HTTP {self.status_code}")

    # Block v1 event/series resolution to force v2 fallback
    if "/v1/events/" in url or "/v1/search/series" in url:
        return _Resp(404, {})

    # Provide minimal forecast_history when identifiers are finally resolved
    if "/v1/series/" in url and "/markets/" in url and "/forecast_history" in url:
        p = params or {}
        st = int(p.get("start_ts", 0))
        et = int(p.get("end_ts", st))
        return _Resp(
            200,
            {
                "forecast_history": [
                    {"end_period_ts": st, "numerical_forecast": 50.0},
                    {"end_period_ts": et, "numerical_forecast": 60.0},
                ]
            },
        )

    return _Resp(404, {})


def _fake_get_market_v2(*args, **kwargs):
    # Mimic DataVentsNoAuthClient.get_market(provider=KALSHI, kalshi_ticker=...) shape
    ticker = kwargs.get("kalshi_ticker") or "KX-TEST-ABC"
    return [
        {
            "provider": "kalshi",
            "data": {
                "market": {
                    "id": "MK123",
                    "series_ticker": "KXTEST",
                    "ticker": ticker,
                }
            },
        }
    ]


def test_market_history_get_resolves_identifiers(monkeypatch, flask_client):
    # Patch DataVents client and requests to avoid network and force our flows
    import api.flask_app as fa

    monkeypatch.setattr(fa.DataVentsNoAuthClient, "get_market", _fake_get_market_v2)
    import requests as _rq
    monkeypatch.setattr(_rq, "get", _fake_requests_get)

    r = flask_client.get(
        "/api/market/history",
        query_string={
            "provider": "kalshi",
            "ticker": "KXTEST-01-ABC",
            "interval": "300",
        },
    )
    assert r.status_code == 200, r.data
    js = r.get_json(force=True)
    assert isinstance(js, dict)
    assert js.get("provider") == "kalshi"
    pts = js.get("points") or []
    assert isinstance(pts, list) and len(pts) >= 2


def test_market_history_post_resolves_identifiers(monkeypatch, flask_client):
    import api.flask_app as fa
    monkeypatch.setattr(fa.DataVentsNoAuthClient, "get_market", _fake_get_market_v2)
    import requests as _rq
    monkeypatch.setattr(_rq, "get", _fake_requests_get)

    body = {
        "provider": "kalshi",
        "market": {"ticker": "KXTEST-01-ABC"},
        "interval": 300,
    }

    r = flask_client.post("/api/history", data=json.dumps(body), content_type="application/json")
    assert r.status_code == 200, r.data
    js = r.get_json(force=True)
    assert isinstance(js, dict)
    assert js.get("provider") == "kalshi"
    pts = js.get("points") or []
    assert isinstance(pts, list) and len(pts) >= 2
