from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from datavents.vendors import DvVendors
from datavents.ws import DvSubscription
from datavents.providers.config import Config as KalshiConfig
from datavents.providers.kalshi.ws_client import WS_PATH as KALSHI_WS_PATH
from datavents.providers.polymarket.ws_client import (
    MARKET_WS_URL as POLY_WS_URL,
    APPLICATION_PING_SECONDS as POLY_APP_PING,
)
from datavents.ws import NormalizedEvent
from typing import Any
import json


def _kalshi_ws_base(env: KalshiConfig) -> str:
    if env == KalshiConfig.PAPER:
        return "wss://demo-api.kalshi.co"
    # Treat LIVE and NOAUTH the same for base URL purposes
    return "wss://api.elections.kalshi.com"


def build_ws_info(subscription: DvSubscription, *, include_urls: bool = True) -> Dict[str, Any]:
    """Summarize a WS subscription in a transport-agnostic structure.

    Returns a JSON-serializable dict suitable for logging, UI surfaces, or HTTP responses.
    This mirrors legacy helpers like `_send_ws_info` from the VentsPyConsolidate service.
    """
    vendors: List[str] = [v.value for v in subscription.vendors]
    info: Dict[str, Any] = {
        "vendors": vendors,
        "kalshi": None,
        "polymarket": None,
    }

    if DvVendors.KALSHI in subscription.vendors:
        kalshi_block: Dict[str, Any] = {
            "env": subscription.kalshi_env.value,
            "channels": list(subscription.kalshi_channels),
            "market_tickers": (list(subscription.kalshi_market_tickers) if subscription.kalshi_market_tickers else None),
            "event_tickers": (list(subscription.kalshi_event_tickers) if subscription.kalshi_event_tickers else None),
        }
        if include_urls:
            kalshi_block["ws_url"] = _kalshi_ws_base(subscription.kalshi_env) + KALSHI_WS_PATH
        info["kalshi"] = kalshi_block

    if DvVendors.POLYMARKET in subscription.vendors:
        poly_block: Dict[str, Any] = {
            "assets_ids": (list(subscription.polymarket_assets_ids) if subscription.polymarket_assets_ids else None),
            "application_ping_seconds": POLY_APP_PING,
        }
        if include_urls:
            poly_block["ws_url"] = POLY_WS_URL
        info["polymarket"] = poly_block

    return info


def _send_ws_info(subscription: DvSubscription, *, include_urls: bool = True) -> Dict[str, Any]:
    """Back-compat alias used by older apps; returns the same dict as build_ws_info."""
    return build_ws_info(subscription, include_urls=include_urls)


def json_default(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump()
        except Exception:
            pass
    if isinstance(value, (set, frozenset)):
        return list(value)
    if isinstance(value, (bytes, bytearray)):
        try:
            return value.decode("utf-8")
        except Exception:
            return value.decode("utf-8", errors="ignore")
    return str(value)


def event_payload(ev: NormalizedEvent) -> str:
    envelope = {
        "vendor": ev.vendor.value if isinstance(ev.vendor, DvVendors) else str(ev.vendor),
        "event": ev.event,
        "market": ev.market,
        "ts": ev.received_ts,
        "data": ev.data,
    }
    return json.dumps(envelope, default=json_default)
