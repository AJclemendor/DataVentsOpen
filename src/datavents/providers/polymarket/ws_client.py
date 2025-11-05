from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable, Dict, List, Mapping, Optional, Sequence

from ..shared_connection.ws_client import BaseWsClient


MARKET_WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
APPLICATION_PING_SECONDS = 10.0


class PolymarketWsClient:
    """Lightweight client for Polymarket's public Market WebSocket channel.

    - Builds on ``BaseWsClient`` for connection management and backoff.
    - Resubscribes automatically after reconnect using the most recent ``assets_ids``.
    - Emits application-level ``"PING"`` messages roughly every 10 seconds while connected.
    - Forwards decoded JSON payloads to the provided callback without additional shaping.
    """

    def __init__(
        self,
        *,
        ping_interval: float = 30.0,
        ping_timeout: float = 20.0,
        application_ping_interval: float = APPLICATION_PING_SECONDS,
    ) -> None:
        self.ws_url = MARKET_WS_URL
        self._logger = logging.getLogger(__name__)
        self._application_ping_interval = max(0.0, application_ping_interval)
        self._last_assets_ids: Optional[List[str]] = None
        self._ping_task: Optional[asyncio.Task[None]] = None
        self._stop_event: Optional[asyncio.Event] = None

        def _headers_provider() -> Mapping[str, str]:
            return {}

        self._base = BaseWsClient(
            self.ws_url,
            headers_provider=_headers_provider,
            ping_interval=ping_interval,
            ping_timeout=ping_timeout,
        )

    @property
    def is_connected(self) -> bool:
        return self._base.is_connected

    async def connect(self) -> None:
        await self._base.connect()

    async def close(self) -> None:
        await self._stop_ping_task()
        await self._base.close()

    async def subscribe(self, assets_ids: Sequence[str]) -> None:
        ids = self._normalize_assets_ids(assets_ids)
        if not ids:
            raise ValueError("assets_ids must contain at least one non-empty identifier")
        self._last_assets_ids = ids
        await self._send_subscribe(ids)

    async def run(
        self,
        on_message: Callable[[Dict[str, Any]], Awaitable[None]],
        *,
        assets_ids: Optional[Sequence[str]] = None,
        stop_event: Optional[asyncio.Event] = None,
    ) -> None:
        if assets_ids is not None:
            ids = self._normalize_assets_ids(assets_ids)
            if not ids:
                raise ValueError("assets_ids must contain at least one non-empty identifier")
            self._last_assets_ids = ids
        elif not self._last_assets_ids:
            raise ValueError("Provide assets_ids to run() or call subscribe() before run().")

        self._stop_event = stop_event

        async def _on_connected() -> None:
            if self._last_assets_ids:
                await self._send_subscribe(self._last_assets_ids)
            self._start_ping_task()

        async def _on_message(raw: str) -> None:
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                self._logger.debug("ws.message_not_json payload=%s", raw)
                await on_message({"type": "raw", "data": raw})
                return

            if isinstance(payload, list):
                for item in payload:
                    if isinstance(item, dict):
                        await on_message(item)
                    else:
                        await on_message({"type": "raw", "data": item})
                return

            if isinstance(payload, dict):
                await on_message(payload)
                return

            await on_message({"type": "raw", "data": payload})

        async def _on_disconnected(_exc: Optional[BaseException]) -> None:
            await self._stop_ping_task()

        try:
            await self._base.run(
                _on_message,
                on_connected=_on_connected,
                on_disconnected=_on_disconnected,
                stop_event=stop_event,
            )
        finally:
            await self._stop_ping_task()

    def _start_ping_task(self) -> None:
        if self._ping_task is not None and not self._ping_task.done():
            return
        if self._application_ping_interval <= 0:
            return
        self._ping_task = asyncio.create_task(self._ping_loop())

    async def _stop_ping_task(self) -> None:
        if self._ping_task is None:
            return
        task = self._ping_task
        self._ping_task = None
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def _ping_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._application_ping_interval)
                if self._stop_event is not None and self._stop_event.is_set():
                    return
                if not self._base.is_connected:
                    return
                try:
                    await self._base.send_text("PING")
                    self._logger.debug("ws.ping_sent")
                except Exception as exc:
                    self._logger.debug("ws.ping_send_failed err=%s", getattr(exc, "__class__", type(exc)).__name__)
                    return
        except asyncio.CancelledError:
            raise

    async def _send_subscribe(self, assets_ids: Sequence[str]) -> None:
        payload = {"assets_ids": list(assets_ids), "type": "market"}
        self._logger.info("ws.subscribe assets_ids=%s", payload["assets_ids"])
        await self._base.send_json(payload)

    def _normalize_assets_ids(self, assets_ids: Sequence[str]) -> List[str]:
        seen = set()
        deduped: List[str] = []
        for asset_id in assets_ids:
            val = (asset_id or "").strip()
            if not val or val in seen:
                continue
            seen.add(val)
            deduped.append(val)
        return deduped


