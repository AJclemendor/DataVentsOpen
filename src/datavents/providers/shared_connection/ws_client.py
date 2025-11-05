import asyncio
import json
import logging
import random
import ssl
from typing import Any, Awaitable, Callable, Mapping, Optional

import certifi
import websockets


class BaseWsClient:
    """Minimal async WebSocket wrapper with reconnect and pluggable auth headers.

    - Reconnects with exponential backoff + jitter on disconnects/errors.
    - Uses a headers provider so callers can regenerate timestamped auth per reconnect.
    - Leaves message parsing and higher-level logic to callers.
    """
    def __init__(
        self,
        url: str,
        headers_provider: Callable[[], Mapping[str, str]],
        *,
        ping_interval: Optional[float] = 30.0,
        ping_timeout: Optional[float] = 20.0,
        backoff_base_seconds: float = 0.5,
        backoff_factor: float = 2.0,
        backoff_cap_seconds: float = 30.0,
    ) -> None:
        self.url = url
        self._headers_provider = headers_provider
        self._ping_interval = ping_interval
        self._ping_timeout = ping_timeout
        self._backoff_base = backoff_base_seconds
        self._backoff_factor = backoff_factor
        self._backoff_cap = backoff_cap_seconds
        self._ws: Optional[Any] = None
        self._logger = logging.getLogger(__name__)

    async def __aenter__(self) -> "BaseWsClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    @property
    def is_connected(self) -> bool:
        return self._ws is not None and getattr(self._ws, "closed", True) is False

    async def connect(self) -> Any:
        headers = dict(self._headers_provider())
        try:
            ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        except Exception:
            ssl_ctx = None
        self._logger.info("ws.connect start url=%s", self.url)
        self._ws = await websockets.connect(
            self.url,
            additional_headers=headers,
            ping_interval=self._ping_interval,
            ping_timeout=self._ping_timeout,
            ssl=ssl_ctx,
        )
        self._logger.info("ws.connected url=%s", self.url)
        return self._ws

    async def close(self) -> None:
        if self._ws is not None:
            try:
                await self._ws.close()
            finally:
                self._ws = None

    async def send_text(self, text: str) -> None:
        if self._ws is None:
            raise RuntimeError("WebSocket is not connected")
        await self._ws.send(text)

    async def send_json(self, obj: Mapping[str, Any]) -> None:
        await self.send_text(json.dumps(obj))

    async def run(
        self,
        on_message: Callable[[str], Awaitable[None]],
        *,
        on_connected: Optional[Callable[[], Awaitable[None]]] = None,
        on_disconnected: Optional[Callable[[Optional[BaseException]], Awaitable[None]]] = None,
        stop_event: Optional[asyncio.Event] = None,
    ) -> None:
        attempt = 0
        while True:
            if stop_event is not None and stop_event.is_set():
                break

            try:
                await self.connect()
                attempt = 0  # reset backoff on successful connect
                if on_connected is not None:
                    await on_connected()

                assert self._ws is not None
                async for message in self._ws:
                    await on_message(message)

            except Exception as e:
                self._logger.warning("ws.disconnected err=%s", getattr(e, "__class__", type(e)).__name__)
                if on_disconnected is not None:
                    try:
                        await on_disconnected(e)
                    except Exception:
                        pass
                attempt += 1
                delay = min(self._backoff_cap, self._backoff_base * (self._backoff_factor ** (attempt - 1)))
                jitter = random.random() * 0.25 * delay
                self._logger.info("ws.reconnect_backoff attempt=%d sleep=%.3fs", attempt, delay + jitter)
                await asyncio.sleep(delay + jitter)
                continue
            finally:
                # Ensure connection object cleared on exit of loop
                if self._ws is not None and getattr(self._ws, "closed", False):
                    self._ws = None

            # Clean disconnect without exception, decide whether to stop or reconnect
            if stop_event is not None and stop_event.is_set():
                break
            # Treat as transient disconnect; call on_disconnected and backoff
            if on_disconnected is not None:
                try:
                    await on_disconnected(None)
                except Exception:
                    pass
            attempt += 1
            delay = min(self._backoff_cap, self._backoff_base * (self._backoff_factor ** (attempt - 1)))
            jitter = random.random() * 0.25 * delay
            self._logger.info("ws.reconnect_backoff attempt=%d sleep=%.3fs", attempt, delay + jitter)
            await asyncio.sleep(delay + jitter)


