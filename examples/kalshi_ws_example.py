from __future__ import annotations

import asyncio
import json
import logging
import os
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from kalshi_ws_settings import WsExampleSettings
import sys
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
SRC_DIR = os.path.join(BACKEND_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from datavents.providers.config import Config
from datavents.providers.kalshi.ws_client import (
    KalshiWsClient,
    SubscribeConfig,
)
from datavents.providers.kalshi.base_client import BaseKalshiClient
from datavents.providers.kalshi.rest_auth import KalshiAuth


def _expand_event_or_market_tickers(config: Config, items: Optional[List[str]]) -> Optional[List[str]]:
    if not items:
        return None
    # Try to resolve each item as an event_ticker first; if no markets found, treat as market_ticker
    client = BaseKalshiClient(KalshiAuth(config), config=config)
    result: List[str] = []
    for token in items:
        try:
            resp = client.get(client.markets_url, params={"event_ticker": token})
            markets = resp.get("markets") if isinstance(resp, dict) else None
            if isinstance(markets, list) and markets:
                for m in markets:
                    if isinstance(m, dict) and m.get("ticker"):
                        result.append(m["ticker"])
                continue
        except Exception:
            pass
        # Fallback: assume it's already a market_ticker
        result.append(token)
    return result or None


def _parse_data_block(msg: Dict[str, Any]) -> Dict[str, Any]:
    # Prefer 'data', fallback to 'msg', then whole
    data = msg.get("data")
    if isinstance(data, dict):
        return data
    data = msg.get("msg")
    if isinstance(data, dict):
        return data
    return msg


def _parse_args(defaults: WsExampleSettings) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Kalshi WebSocket example: subscribe to channels and print updates.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--env", choices=["paper", "live"], default=defaults.env, help="Target Kalshi environment")
    p.add_argument("--secs", type=float, default=defaults.secs, help="How long to run before exiting")
    p.add_argument(
        "--tickers",
        type=str,
        default=",".join(defaults.tickers) if defaults.tickers else "",
        help="Comma-separated event or market tickers. Event tickers will expand to their markets.",
    )
    p.add_argument(
        "--channels",
        type=str,
        default=",".join(defaults.channels) if defaults.channels else "ticker",
        help="Comma-separated channels, e.g. ticker,orderbook_delta,trade",
    )
    p.add_argument("--log-level", default=defaults.log_level, help="Logging level: DEBUG, INFO, WARNING, ...")
    p.add_argument(
        "--log-format",
        choices=["console", "json"],
        default=defaults.log_format,
        help="Console-friendly or JSON lines logging",
    )
    p.add_argument("--internal-level", default=defaults.internal_level, help="Level for internal libs (websockets, client)")
    p.add_argument("--output", choices=["readable", "json"], default=defaults.output, help="How to print events from the stream")
    p.add_argument("--events", type=str, default=",".join(defaults.events) if defaults.events else "", help="Subset of events to print: ticker,orderbook,trade (comma-separated)")
    p.add_argument("--no-acks", action="store_true", help="Do not print subscription ACK lines")
    p.add_argument("-v", "--verbose", action="store_true", help="Shortcut for --log-level DEBUG")
    return p.parse_args()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"))


def _setup_logging(level_name: str, fmt: str, internal_level: str) -> None:
    lvl = getattr(logging, level_name.upper(), logging.INFO)
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler()
    if fmt == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root.addHandler(handler)
    root.setLevel(lvl)

    # Tame noisy libraries unless explicitly elevated
    lib_level = getattr(logging, internal_level.upper(), logging.WARNING)
    for name in ("websockets", "websockets.client", "datavents.providers"):
        logging.getLogger(name).setLevel(lib_level)


def _env_to_config(env: str) -> Config:
    return Config.PAPER if env.lower() == "paper" else Config.LIVE


async def main() -> None:
    """Run a simple Kalshi WS demo with optional event-to-markets expansion.

    This refactor removes reliance on env vars for non-secret inputs.
    Configure via defaults in `backend/examples/kalshi_ws_settings.py` and/or CLI flags.
    Secrets (API keys) still come from environment variables for safety.
    """
    defaults = WsExampleSettings()
    args = _parse_args(defaults)

    # Logging setup
    effective_level = "DEBUG" if args.verbose else args.log_level
    _setup_logging(effective_level, args.log_format, args.internal_level)

    # Select config from --env
    config = _env_to_config(args.env)

    client = KalshiWsClient(config=config)

    # Parse tickers and channels from CLI/defaults; allow event->markets expansion
    market_tickers: Optional[List[str]] = None
    raw_tickers = [t.strip() for t in args.tickers.split(",") if t.strip()] if isinstance(args.tickers, str) else []
    if raw_tickers:
        market_tickers = _expand_event_or_market_tickers(config, raw_tickers)

    channels: List[str] = [c.strip() for c in args.channels.split(",") if c.strip()]

    # Event printing filters
    requested_events = {e.strip().lower() for e in (args.events.split(",") if isinstance(args.events, str) and args.events else []) if e.strip()}
    show_all_events = not requested_events

    async def on_message(msg: Dict[str, Any]) -> None:
        t = (msg.get("type") or msg.get("event") or "").lower()
        data = _parse_data_block(msg)
        if t in {"ticker", "ticker_update"} and (show_all_events or "ticker" in requested_events):
            mt = data.get("market_ticker") or data.get("ticker") or data.get("market")
            yb = data.get("yes_bid") or data.get("best_bid") or data.get("high_bid")
            ya = data.get("yes_ask") or data.get("best_ask") or data.get("low_ask")
            if args.output == "json":
                print(json.dumps({"type": "ticker", "market": mt, "yes_bid": yb, "yes_ask": ya}))
            else:
                print(f"ticker {mt} yb={yb} ya={ya}")
        elif t in {"orderbook_delta", "orderbook_snapshot", "orderbook_update"} and (show_all_events or "orderbook" in requested_events):
            mt = data.get("market_ticker") or data.get("market")
            if args.output == "json":
                print(json.dumps({"type": "orderbook", "market": mt}))
            else:
                print(f"orderbook {mt}")
        elif t in {"trade", "public_trade", "public_trades"} and (show_all_events or "trade" in requested_events):
            mt = data.get("market_ticker") or data.get("market")
            qty = data.get("count") or data.get("quantity") or data.get("size")
            px = data.get("yes_price") or data.get("price")
            if isinstance(px, (int, float)) and px <= 1:
                px = int(round(px * 100))
            side = data.get("taker_side") or data.get("side")
            suffix = f" [{side}]" if side else ""
            if args.output == "json":
                print(json.dumps({"type": "trade", "market": mt, "qty": qty, "price": px, "side": side}))
            else:
                print(f"trade {mt} {qty}@{px}{suffix}")
        elif t == "error":
            print(f"ERROR: {json.dumps(msg)}")
        else:
            # Pretty-print subscription acks when possible
            if t == "subscribed" and not args.no_acks:
                msgd = msg.get("msg") if isinstance(msg.get("msg"), dict) else {}
                ch = msgd.get("channel") or msg.get("channel")
                sid = msgd.get("sid") or msg.get("sid")
                if ch and sid is not None:
                    if args.output == "json":
                        print(json.dumps({"type": "subscribed", "channel": ch, "sid": sid}))
                    else:
                        print(f"subscribed {ch} sid={sid}")
                    return
            print(json.dumps(msg))

    stop_event = asyncio.Event()

    async def _auto_stop() -> None:
        await asyncio.sleep(float(args.secs))
        stop_event.set()

    # Subscribe per env; if market_tickers resolved from event, include them.
    default_sub = SubscribeConfig(channels=channels, market_tickers=market_tickers)

    asyncio.create_task(_auto_stop())
    await client.start(on_message, default_subscribe=default_sub, stop_event=stop_event)


if __name__ == "__main__":
    asyncio.run(main())
