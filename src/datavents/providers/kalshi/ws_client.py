from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Mapping, Optional

from ..config import Config
from ..shared_connection.ws_client import BaseWsClient
from .rest_auth import KalshiAuth


WS_PATH = "/trade-api/ws/v2"


@dataclass
class SubscribeConfig:
    channels: List[str]
    market_tickers: Optional[List[str]] = None


class KalshiWsClient:
    """Authenticated Kalshi WebSocket client built on BaseWsClient.

    - Builds signed headers per docs using RSA-PSS over: timestamp + "GET" + WS_PATH.
    - Provides minimal command helpers: subscribe, list, unsubscribe, update.
    - Captures subscription IDs to support unsubscribe/update and resubscribe on reconnect.
    """

    def __init__(
        self,
        *,
        config: Config = Config.PAPER,
        auth: Optional[KalshiAuth] = None,
        ping_interval: float = 30.0,
        ping_timeout: float = 20.0,
    ) -> None:
        self.config = config
        self.auth = auth or KalshiAuth(config)

        if self.config == Config.PAPER:
            ws_base = "wss://demo-api.kalshi.co"
        elif self.config == Config.LIVE:
            ws_base = "wss://api.elections.kalshi.com"
        elif self.config == Config.NOAUTH:
            # NOAUTH makes little sense for private WS, but allow instantiation; will error on connect
            ws_base = "wss://api.elections.kalshi.com"
        else:
            raise ValueError(f"Invalid config: {self.config}")

        self.ws_url = ws_base + WS_PATH
        self._msg_id: int = 1
        self._sid_by_channel: Dict[str, int] = {}
        self._last_subscription: Optional[SubscribeConfig] = None
        self._logger = logging.getLogger(__name__)

        def _headers_provider() -> Mapping[str, str]:
            return self._build_ws_headers()

        self._base = BaseWsClient(
            self.ws_url,
            headers_provider=_headers_provider,
            ping_interval=ping_interval,
            ping_timeout=ping_timeout,
        )

        self._stop_event: Optional[asyncio.Event] = None

    # ---- lifecycle ----
    async def connect(self) -> None:
        if self.config == Config.NOAUTH:
            raise RuntimeError("NOAUTH config is not supported for authenticated WebSocket")
        await self._base.connect()

    async def close(self) -> None:
        await self._base.close()

    # ---- auth headers ----
    def _build_ws_headers(self) -> Dict[str, str]:
        """Create headers for WebSocket opening handshake.

        Per Kalshi docs, sign the string: timestamp_ms + "GET" + WS_PATH.
        The timestamp must be milliseconds since epoch.
        """
        timestamp_ms = str(int(time.time() * 1000))
        msg_string = timestamp_ms + "GET" + WS_PATH
        signature = self.auth.sign_pss_text(msg_string)
        return {
            "Content-Type": "application/json",
            "KALSHI-ACCESS-KEY": self.auth.api_key,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp_ms,
            "User-Agent": "kalshi-ws-client/0.1",
        }

    # ---- commands ----
    def _next_id(self) -> int:
        self._msg_id += 1
        return self._msg_id

    def _normalize_channels(self, channels: List[str]) -> List[str]:
        """Map friendly aliases to canonical channel names.

        - "orderbook" -> "orderbook_delta"
        - "trades" -> "trade"
        """
        out: List[str] = []
        for ch in channels:
            c = (ch or "").lower()
            if c == "orderbook":
                c = "orderbook_delta"
            elif c == "trades":
                c = "trade"
            out.append(c)
        return out

    async def _send(self, payload: Mapping[str, Any]) -> None:
        self._logger.debug("ws.send %s", payload)
        await self._base.send_json(payload)

    async def subscribe(self, channels: List[str], market_tickers: Optional[List[str]] = None) -> None:
        params: Dict[str, Any] = {"channels": self._normalize_channels(list(channels))}
        mt_list: Optional[List[str]] = None
        if market_tickers:
            mt_list = list(market_tickers)
            if len(mt_list) == 1:
                # Per docs, prefer single 'market_ticker' when only one market
                params["market_ticker"] = mt_list[0]
            else:
                params["market_tickers"] = mt_list
        msg = {"id": self._next_id(), "cmd": "subscribe", "params": params}
        # Log either single or multi market keys to avoid confusing 'None'
        markets_repr = None
        if "market_ticker" in params:
            markets_repr = params["market_ticker"]
        elif "market_tickers" in params:
            markets_repr = params["market_tickers"]
        self._logger.info("ws.cmd subscribe channels=%s markets=%s", params["channels"], markets_repr)
        await self._send(msg)
        # Store last subscription for reconnect
        # Store last requested list if available, even if we used single 'market_ticker'
        self._last_subscription = SubscribeConfig(
            channels=params["channels"],
            market_tickers=mt_list if mt_list else params.get("market_tickers"),
        )

    async def list_subscriptions(self) -> None:
        self._logger.info("ws.cmd list_subscriptions")
        await self._send({"id": self._next_id(), "cmd": "list_subscriptions"})

    async def unsubscribe(self, channels: List[str]) -> None:
        # Unsubscribe requires sids
        sids = [sid for ch, sid in self._sid_by_channel.items() if ch in channels]
        if not sids:
            self._logger.info("ws.cmd unsubscribe no_sids_for_channels channels=%s", channels)
            return
        self._logger.info("ws.cmd unsubscribe sids=%s", sids)
        await self._send({"id": self._next_id(), "cmd": "unsubscribe", "params": {"sids": sids}})

    async def update_subscription(self, channel: str, action: str, market_tickers: List[str]) -> None:
        sid = self._sid_by_channel.get(channel)
        if sid is None:
            self._logger.info("ws.cmd update_subscription missing_sid channel=%s", channel)
            return
        self._logger.info("ws.cmd update_subscription sid=%s action=%s markets=%s", sid, action, market_tickers)
        await self._send(
            {
                "id": self._next_id(),
                "cmd": "update_subscription",
                "params": {"sid": sid, "market_tickers": list(market_tickers), "action": action},
            }
        )

    # ---- run loop ----
    async def start(
        self,
        on_message: Callable[[Dict[str, Any]], Awaitable[None]],
        *,
        default_subscribe: Optional[SubscribeConfig] = None,
        stop_event: Optional[asyncio.Event] = None,
    ) -> None:
        self._stop_event = stop_event

        async def _on_connected() -> None:
            # Resubscribe first to maintain continuity across reconnects
            if self._last_subscription is not None:
                await self.subscribe(
                    self._last_subscription.channels,
                    self._last_subscription.market_tickers,
                )
            elif default_subscribe is not None:
                await self.subscribe(default_subscribe.channels, default_subscribe.market_tickers)

        async def _on_message(raw: str) -> None:
            try:
                msg = json.loads(raw)
            except Exception:
                # Deliver raw text as a diagnostic envelope
                await on_message({"type": "raw", "data": raw})
                return

            t = (msg.get("type") or msg.get("event") or "").lower()
            if t == "subscribed" or msg.get("cmd") == "subscribed":
                # Capture sid mapping for channel; response formats vary
                sid = None
                channel = None
                if isinstance(msg.get("msg"), dict):
                    sid = msg["msg"].get("sid")
                    channel = msg["msg"].get("channel")
                if sid is None:
                    sid = msg.get("sid")
                if channel is None:
                    channel = msg.get("channel") or (msg.get("channels")[0] if isinstance(msg.get("channels"), list) and msg.get("channels") else None)
                if isinstance(channel, str) and isinstance(sid, int):
                    self._sid_by_channel[channel] = sid
                    self._logger.info("ws.subscribed channel=%s sid=%s", channel, sid)

            await on_message(msg)

        async def _on_disconnected(_exc: Optional[BaseException]) -> None:
            # Nothing to do; reconnection will occur with backoff in BaseWsClient
            return

        await self._base.run(
            _on_message,
            on_connected=_on_connected,
            on_disconnected=_on_disconnected,
            stop_event=stop_event,
        )
