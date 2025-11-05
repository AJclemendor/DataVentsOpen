from __future__ import annotations

import json
from typing import Any, Dict

import pytest


@pytest.fixture
def flask_client():
    # Ensure `backend/src` is on sys.path
    import sys
    from pathlib import Path

    here = Path(__file__).resolve()
    src_dir = here.parents[3] / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    from api.flask_app import app

    app.testing = True
    with app.test_client() as c:
        yield c


def _fake_prices_history(url: str, params: Dict[str, Any] | None = None, timeout: int | float | None = None):
    """Fake Polymarket prices-history that respects startTs/endTs.

    Returns a small list of points including both ends, so the server's
    chunk-merging and de-dup logic can be exercised (duplicate at chunk
    boundary will be removed by the route).
    """

    class _Resp:
        def __init__(self, status_code: int, payload: Dict[str, Any]):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

        def raise_for_status(self):
            if not (200 <= self.status_code < 300):
                raise Exception(f"HTTP {self.status_code}")

    if "clob.polymarket.com/prices-history" in url:
        p = params or {}
        st = int(p.get("startTs", 0))
        et = int(p.get("endTs", st))
        # 3 points per call: start, +60s, end
        return _Resp(
            200,
            {
                "history": [
                    {"t": st, "p": 0.10},
                    {"t": st + 60, "p": 0.20},
                    {"t": et, "p": 0.30},
                ]
            },
        )

    # Default: anything else 404 to make unintended calls obvious
    return _Resp(404, {})


def test_polymarket_history_post_30d_returns_full_range(monkeypatch, flask_client):
    # Patch requests.get to our fake prices-history
    import requests as _rq

    monkeypatch.setattr(_rq, "get", _fake_prices_history)

    # 30d window → route should chunk into two 15d requests and merge
    start = 1_700_000_000  # epoch seconds (arbitrary)
    end = start + 30 * 24 * 3600

    body = {
        "provider": "polymarket",
        # Provide clob ids inline so no market fetch occurs
        "market": {
            "provider": "polymarket",
            "slug": "example-slug",
            "clobTokenIds": [
                "72685162394098505217895638060393901041260225434938300730127268362092284806692"
            ],
        },
        "start": start,
        "end": end,
        "interval": 86400,
    }

    r = flask_client.post("/api/history", data=json.dumps(body), content_type="application/json")
    assert r.status_code == 200, r.data
    js = r.get_json(force=True)
    assert js.get("provider") == "polymarket"

    pts = js.get("points") or []
    assert isinstance(pts, list) and len(pts) >= 4  # two chunks merged, boundary deduped

    # Ensure ascending timestamps
    ts = [int(p["t"]) for p in pts]
    assert ts == sorted(ts)

    # Best (earliest/latest) response timestamps match requested range (ms in payload)
    assert ts[0] == start * 1000
    assert ts[-1] == end * 1000

    # Poly interval tag indicates chunked strategy
    assert js.get("poly_interval") == "chunked<=15d"

