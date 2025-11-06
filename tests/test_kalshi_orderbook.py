"""Tests for Kalshi orderbook helpers and lazy auth wiring.

These tests avoid real network calls and API keys by stubbing the
underlying HTTP method (`get`) and the auth client class used by the
DataVents client.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import types
import builtins

from datavents.providers.kalshi.kalshi_rest_auth import KalshiRestAuth
from datavents import DataVentsNoAuthClient
from datavents.providers.config import Config as ProviderConfig
from datavents import DataVentsProviders
import json
import os
from pathlib import Path
import logging
import pytest


def _make_stubbed_auth_client() -> KalshiRestAuth:
    """Create a KalshiRestAuth-like instance without invoking real __init__.

    We bypass key loading and attach only the attributes used by
    `get_market_orderbook`.
    """
    inst = KalshiRestAuth.__new__(KalshiRestAuth)  # type: ignore
    # Path base used by the method under test
    inst.markets_url = "/markets"  # type: ignore[attr-defined]

    captured: Dict[str, Any] = {}

    def fake_get(self, path: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        captured["path"] = path
        captured["params"] = dict(params or {})
        return {"ok": True, "echo": {"path": path, "params": params or {}}}

    # Bind the fake get to the instance
    inst.get = types.MethodType(fake_get, inst)  # type: ignore[attr-defined]
    # Attach capture dict for assertions from tests
    inst._captured = captured  # type: ignore[attr-defined]
    return inst


def test_kalshi_rest_auth_orderbook_calls_inherited_get():
    client = _make_stubbed_auth_client()

    # depth within bounds
    out = client.get_market_orderbook("ABC-24-XYZ-T50", depth=25)
    assert out["ok"] is True
    assert client._captured["path"] == "/markets/ABC-24-XYZ-T50/orderbook"  # type: ignore[attr-defined]
    assert client._captured["params"].get("depth") == 25  # type: ignore[attr-defined]

    # depth clamps low to 0
    client.get_market_orderbook("TICK", depth=-10)
    assert client._captured["params"].get("depth") == 0  # type: ignore[attr-defined]

    # depth clamps high to 100
    client.get_market_orderbook("TICK", depth=999)
    assert client._captured["params"].get("depth") == 100  # type: ignore[attr-defined]

    # no depth provided → param omitted
    client.get_market_orderbook("TICK")
    assert "depth" not in client._captured["params"]  # type: ignore[attr-defined]


def test_dv_client_lazy_auth_orderbook(monkeypatch):
    """Verify DataVentsNoAuthClient lazily constructs an auth client and calls it."""

    # Prepare a fake auth client class to inject into datavents.client
    stub_instance = _make_stubbed_auth_client()

    class FakeAuth(KalshiRestAuth):  # type: ignore[misc]
        def __init__(self, *args, **kwargs):  # noqa: D401
            # Do not call super().__init__ (avoids env/keys)
            # Reuse the pre-made stub
            self.__dict__.update(stub_instance.__dict__)

    # Replace the class used by DataVentsNoAuthClient with our fake
    import datavents.client as dv_client_mod

    monkeypatch.setattr(dv_client_mod, "KalshiRestAuth", FakeAuth, raising=True)

    dv = DataVentsNoAuthClient()

    # Direct helper (LIVE by default)
    out = dv.get_kalshi_market_orderbook("XYZ-24-ABC-T12", depth=5)
    assert out["ok"] is True
    assert stub_instance._captured["path"].endswith("/XYZ-24-ABC-T12/orderbook")  # type: ignore[attr-defined]

    # Unified facade returns list with provider tag and raw data
    res = dv.get_market_orderbook(
        DataVentsProviders.KALSHI,
        kalshi_ticker="XYZ-24-ABC-T12",
        depth=10,
        kalshi_env=ProviderConfig.LIVE,
    )
    assert isinstance(res, list) and res and res[0]["provider"] == "kalshi"
    assert res[0]["data"].get("ok") is True


# -------- Integration (real API) -------------------------------------------

def _write_output(filename: str, data: dict) -> Path:
    root = Path(__file__).parent.parent
    out_dir = root / ".test_output"
    out_dir.mkdir(exist_ok=True)
    try:
        out_path = out_dir / filename
        with open(out_path, "w") as f:
            json.dump(data, f, indent=2)
        return out_path
    except Exception:
        return out_dir / filename


def _discover_kalshi_market_ticker(dv: DataVentsNoAuthClient) -> str | None:
    sr = dv.search_events(
        provider=DataVentsProviders.KALSHI,
        query=" ",
        limit=5,
        page=0,
        order_sort_params=dv.DataVentsOrderSortParams.ORDER_BY_TRENDING if hasattr(dv, "DataVentsOrderSortParams") else None,  # type: ignore
        status_params=dv.DataVentsStatusParams.OPEN_MARKETS if hasattr(dv, "DataVentsStatusParams") else None,  # type: ignore
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


@pytest.mark.integration
def test_kalshi_orderbook_real_api_writes_output(tmp_path):
    logger = logging.getLogger(__name__)
    # Choose env via override; default to LIVE per request
    env_override = (os.getenv("TEST_KALSHI_ENV", "LIVE") or "").strip().lower()
    env = ProviderConfig.LIVE if env_override in ("live", "prod", "production") else ProviderConfig.PAPER

    # Validate required credentials for chosen env
    if env == ProviderConfig.LIVE:
        keyfile = os.getenv("KALSHI_PRIVATE_KEY")
        apikey = os.getenv("KALSHI_API_KEY")
        if not (apikey and keyfile and os.path.exists(keyfile)):
            pytest.skip("LIVE creds not set or key file missing; set KALSHI_API_KEY and KALSHI_PRIVATE_KEY")
    else:
        keyfile = os.getenv("KALSHI_PRIVATE_KEY_PAPER")
        apikey = os.getenv("KALSHI_API_KEY_PAPER")
        if not (apikey and keyfile and os.path.exists(keyfile)):
            pytest.skip("PAPER creds not set or key file missing; set KALSHI_API_KEY_PAPER and KALSHI_PRIVATE_KEY_PAPER")
    dv = DataVentsNoAuthClient()
    ticker = TICKER_HARDCODED

    # Fetch a shallow orderbook to keep payload small
    depth = 5
    logger.info("Fetching Kalshi orderbook env=%s ticker=%s depth=%s", env.value, ticker, depth)
    ob = dv.get_kalshi_market_orderbook(str(ticker), depth=depth, env=env)
    assert isinstance(ob, dict)

    # Write to gitignored folder for manual inspection
    out_path = _write_output("kalshi_orderbook.json", {"env": env.value, "ticker": ticker, "depth": depth, "data": ob})
    logger.info("Wrote orderbook JSON → %s", out_path)
TICKER_HARDCODED = "KXMAYORNYCPARTY-25-D"
