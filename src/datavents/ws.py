from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Mapping, Optional, Sequence

# Vendor clients
from datavents.providers.config import Config as KalshiConfig
from datavents.providers.kalshi.ws_client import (
    KalshiWsClient,
    SubscribeConfig as KalshiSubscribe,
)
from datavents.providers.kalshi.base_client import BaseKalshiClient
from datavents.providers.kalshi.rest_auth import KalshiAuth
from datavents.providers.polymarket.ws_client import PolymarketWsClient
from datavents.vendors import DvVendors
from datavents.utils.resolve import resolve_polymarket_assets_ids
from datavents.providers.polymarket.polymarket_rest_noauth import PolymarketRestNoAuth


@dataclass
class DvSubscription:
    """Normalized DV subscription.

    - vendors: choose one or both vendors
    - kalshi: select environment and subscription details
    - polymarket: list of assets_ids
    - If you only set `tickers_or_ids`, the same list is passed to the selected vendors
      (treated as Kalshi market tickers and/or Polymarket assets_ids).
    - If `kalshi_event_tickers` is provided, the client will try to expand events -> market tickers
      via Kalshi REST. If auth is missing, it falls back to using the values as-is.
    """

    vendors: Sequence[DvVendors] = (DvVendors.KALSHI,)

    # Cross-vendor pass-through convenience
    tickers_or_ids: Optional[Sequence[str]] = None

    # Kalshi options
    kalshi_env: KalshiConfig = KalshiConfig.LIVE
    kalshi_channels: Sequence[str] = ("ticker", "orderbook_delta", "trade")
    kalshi_market_tickers: Optional[Sequence[str]] = None
    kalshi_event_tickers: Optional[Sequence[str]] = None  # attempt expansion to market tickers

    # Polymarket options
    polymarket_assets_ids: Optional[Sequence[str]] = None


@dataclass
class NormalizedEvent:
    vendor: DvVendors
    event: str  # e.g. "ticker" | "orderbook" | "trade" | "raw"
    market: Optional[str]
    data: Mapping[str, Any]
    received_ts: float


class DvWsClient:
    """Intermediate DV WS client that multiplexes Kalshi and Polymarket.

    - Opens 1 or 2 websocket connections depending on `DvSubscription.vendors`.
    - Normalizes subscription inputs with a single `DvSubscription` structure.
    - Emits `NormalizedEvent` envelopes with vendor, coarse event type, and market identifier when available.
    - Kalshi requires valid API credentials in the environment for the chosen env.
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)

    async def run(
        self,
        subscription: DvSubscription,
        on_event: Callable[[NormalizedEvent], Awaitable[None]],
        *,
        stop_event: Optional[asyncio.Event] = None,
    ) -> None:
        # Resolve normalized lists for each vendor
        kalshi_tickers = self._resolve_kalshi_tickers(subscription)
        poly_ids = self._resolve_poly_ids(subscription)

        tasks: List[asyncio.Task[None]] = []
        stop_event = stop_event or asyncio.Event()

        if DvVendors.KALSHI in subscription.vendors:
            tasks.append(
                asyncio.create_task(
                    self._run_kalshi(
                        env=subscription.kalshi_env,
                        channels=list(subscription.kalshi_channels),
                        market_tickers=kalshi_tickers or [],
                        on_event=on_event,
                        stop_event=stop_event,
                    )
                )
            )

        if DvVendors.POLYMARKET in subscription.vendors:
            if not poly_ids:
                raise ValueError("Polymarket selected but no assets_ids provided (set DvSubscription.polymarket_assets_ids or tickers_or_ids)")
            tasks.append(
                asyncio.create_task(
                    self._run_polymarket(
                        assets_ids=poly_ids or [],
                        on_event=on_event,
                        stop_event=stop_event,
                    )
                )
            )

        if not tasks:
            raise ValueError("No vendors selected in subscription.vendors")

        try:
            await asyncio.gather(*tasks)
        finally:
            for t in tasks:
                if not t.done():
                    t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    # ---- vendor runners --------------------------------------------------
    async def _run_kalshi(
        self,
        *,
        env: KalshiConfig,
        channels: List[str],
        market_tickers: List[str],
        on_event: Callable[[NormalizedEvent], Awaitable[None]],
        stop_event: asyncio.Event,
    ) -> None:
        client = KalshiWsClient(config=env)

        def _mk_sub() -> KalshiSubscribe:
            return KalshiSubscribe(channels=channels, market_tickers=market_tickers or None)

        async def _on_msg(msg: Dict[str, Any]) -> None:
            await on_event(self._normalize_kalshi_msg(msg))

        await client.start(_on_msg, default_subscribe=_mk_sub(), stop_event=stop_event)

    async def _run_polymarket(
        self,
        *,
        assets_ids: List[str],
        on_event: Callable[[NormalizedEvent], Awaitable[None]],
        stop_event: asyncio.Event,
    ) -> None:
        client = PolymarketWsClient()

        async def _on_msg(msg: Dict[str, Any]) -> None:
            await on_event(self._normalize_polymarket_msg(msg))

        await client.run(_on_msg, assets_ids=assets_ids, stop_event=stop_event)

    # ---- normalization helpers ------------------------------------------
    def _resolve_kalshi_tickers(self, sub: DvSubscription) -> Optional[List[str]]:
        # Priority: explicit Kalshi list; else fall back to cross-vendor list
        tokens: List[str] = []
        if sub.kalshi_market_tickers:
            tokens.extend(self._dedupe_trim(sub.kalshi_market_tickers))
        elif sub.tickers_or_ids:
            tokens.extend(self._dedupe_trim(sub.tickers_or_ids))

        # If explicit event list provided, try to expand first
        if sub.kalshi_event_tickers:
            expanded = self._expand_kalshi_events(sub.kalshi_event_tickers, env=sub.kalshi_env)
            if expanded:
                self._logger.info("dv.kalshi.expand explicit events->markets %s -> %s", list(sub.kalshi_event_tickers), expanded)
                return expanded
        # Otherwise, best-effort: try expanding whatever we have; if it yields results, prefer them
        if tokens:
            expanded = self._expand_kalshi_events(tokens, env=sub.kalshi_env)
            if expanded:
                # Only log if actually changed shape
                if expanded != tokens:
                    self._logger.info("dv.kalshi.expand tokens->markets %s -> %s", tokens, expanded)
                return expanded
        return tokens or None

    def _resolve_poly_ids(self, sub: DvSubscription) -> Optional[List[str]]:
        # Prefer explicit assets_ids
        if sub.polymarket_assets_ids:
            return self._dedupe_trim(sub.polymarket_assets_ids)
        # Best-effort: try to resolve tickers_or_ids into assets_ids via REST
        if sub.tickers_or_ids:
            try:
                client = PolymarketRestNoAuth()
                resolved = resolve_polymarket_assets_ids(list(sub.tickers_or_ids), client=client, fetch=True)
                if resolved:
                    return self._dedupe_trim(resolved)
            except Exception:
                pass
            # Fallback: pass through as-is
            return self._dedupe_trim(sub.tickers_or_ids)
        return None

    def _dedupe_trim(self, vals: Iterable[str]) -> List[str]:
        seen = set()
        out: List[str] = []
        for v in vals:
            s = (v or "").strip()
            if not s or s in seen:
                continue
            seen.add(s)
            out.append(s)
        return out

    def _expand_kalshi_events(self, event_tickers: Sequence[str], *, env: KalshiConfig) -> Optional[List[str]]:
        # Best-effort expansion; requires Kalshi REST auth. If not available, return None.
        try:
            auth = KalshiAuth(env)
            rest = BaseKalshiClient(auth, config=env)
        except Exception:
            self._logger.debug("kalshi_event_expand_auth_unavailable; using input as-is")
            return None

        results: List[str] = []
        for token in self._dedupe_trim(event_tickers):
            try:
                resp = rest.get(rest.markets_url, params={"event_ticker": token})
                markets = resp.get("markets") if isinstance(resp, dict) else None
                if isinstance(markets, list) and markets:
                    for m in markets:
                        if isinstance(m, dict) and m.get("ticker"):
                            results.append(m["ticker"]) 
                    continue
            except Exception:
                pass
            # Fallback: if no markets returned, keep token
            results.append(token)
        return results or None

    # ---- event shaping ---------------------------------------------------
    def _normalize_kalshi_msg(self, msg: Mapping[str, Any]) -> NormalizedEvent:
        t = (msg.get("type") or msg.get("event") or "").lower()
        data = self._kalshi_data_block(msg)
        market = data.get("market_ticker") or data.get("ticker") or data.get("market")

        # Direct mapping from declared type
        if t in {"ticker", "ticker_update"}:
            evt = "ticker"
        elif t in {"orderbook_delta", "orderbook_snapshot", "orderbook_update"}:
            evt = "orderbook"
        elif t in {"trade", "public_trade", "public_trades"}:
            evt = "trade"
        else:
            # Heuristic fallback based on payload keys
            evt = self._infer_kalshi_event_from_data(data)
        return NormalizedEvent(vendor=DvVendors.KALSHI, event=evt, market=market, data=msg, received_ts=time.time())

    def _kalshi_data_block(self, msg: Mapping[str, Any]) -> Mapping[str, Any]:
        data = msg.get("data")
        if isinstance(data, dict):
            return data
        data = msg.get("msg")
        if isinstance(data, dict):
            return data
        return msg

    def _normalize_polymarket_msg(self, msg: Mapping[str, Any]) -> NormalizedEvent:
        # Polymarket payloads can wrap details in a nested 'data' block.
        data = msg.get("data") if isinstance(msg.get("data"), dict) else msg

        # Market/asset identifier
        market = (
            data.get("asset_id")
            or data.get("assetId")
            or data.get("id")
            or data.get("market")
            or msg.get("asset_id")
            or msg.get("assetId")
            or msg.get("id")
            or msg.get("market")
            or None
        )

        # Event type detection: check both top-level and nested 'data'
        subtype = (
            (msg.get("type") or msg.get("event") or "")
            or (data.get("type") or data.get("event") or "")
        ).lower()

        evt: str
        if subtype in {"ticker", "quote", "price"}:
            evt = "ticker"
        elif "orderbook" in subtype or subtype in {"book", "ob", "l2"}:
            evt = "orderbook"
        elif subtype in {"trade", "fill", "match"}:
            evt = "trade"
        else:
            # Heuristics on nested fields
            if any(k in data for k in ("deltas", "bids", "asks", "levels", "orderbook")):
                evt = "orderbook"
            elif (
                any(k in data for k in ("size", "qty", "quantity"))
                and any(k in data for k in ("price",))
            ):
                evt = "trade"
            elif any(k in data for k in ("bestBid", "bestAsk", "bid", "ask", "mid", "lastPrice")):
                evt = "ticker"
            else:
                evt = "raw"

        return NormalizedEvent(
            vendor=DvVendors.POLYMARKET,
            event=evt,
            market=market,
            data=msg,
            received_ts=time.time(),
        )

    def _infer_kalshi_event_from_data(self, data: Mapping[str, Any]) -> str:
        # Orderbook-like signals
        if any(k in data for k in ("deltas", "bids", "asks", "orderbook", "book")):
            return "orderbook"
        # Trade-like signals
        if any(k in data for k in ("yes_price", "price")) and any(k in data for k in ("quantity", "count", "size")):
            return "trade"
        # Ticker-like signals
        if any(k in data for k in ("yes_bid", "yes_ask", "best_bid", "best_ask", "high_bid", "low_ask", "last_price")):
            return "ticker"
        return "raw"
