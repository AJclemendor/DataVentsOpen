from __future__ import annotations

from datavents import DvSubscription, DvVendors, build_ws_info, _send_ws_info
from datavents.providers.config import Config as KalshiConfig


def test_build_ws_info_minimal_kalshi():
    sub = DvSubscription(vendors=(DvVendors.KALSHI,), kalshi_env=KalshiConfig.LIVE, kalshi_market_tickers=["ABC-XYZ-123"]) 
    info = build_ws_info(sub)
    assert info["kalshi"]["env"] == "live"
    assert "ws_url" in info["kalshi"]
    assert "polymarket" in info and info["polymarket"] is None


def test_build_ws_info_poly_only():
    sub = DvSubscription(vendors=(DvVendors.POLYMARKET,), polymarket_assets_ids=["asset-1", "asset-2"]) 
    info = build_ws_info(sub)
    assert info["polymarket"]["assets_ids"] == ["asset-1", "asset-2"]
    assert info["polymarket"]["application_ping_seconds"] > 0
    assert "ws_url" in info["polymarket"]


def test_send_ws_info_alias():
    sub = DvSubscription(vendors=(DvVendors.KALSHI, DvVendors.POLYMARKET))
    info = _send_ws_info(sub)
    assert set(info["vendors"]) == {"kalshi", "polymarket"}

