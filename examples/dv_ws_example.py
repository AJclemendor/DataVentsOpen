from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
SRC_DIR = os.path.join(BACKEND_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
#
from datavents import DvWsClient, DvVendors, DvSubscription, NormalizedEvent
from datavents.providers.config import Config as KalshiConfig


@dataclass
class ExampleDefaults:
    vendors: str = "kalshi"  # kalshi|polymarket|both
    secs: float = 30.0
    output: str = "readable"  # readable|json
    kalshi_env: str = "live"  # paper|live
    kalshi_channels: List[str] = field(default_factory=lambda: ["ticker", "orderbook_delta", "trade"]) 
    tickers: List[str] = field(default_factory=list)
    kalshi_tickers: List[str] = field(default_factory=list)
    kalshi_events: List[str] = field(default_factory=list)
    assets: List[str] = field(
        default_factory=lambda: [
            "33945469250963963541781051637999677727672635213493648594066577298999471399137",
            "0xebddfcf7b4401dade8b4031770a1ab942b01854f3bed453d5df9425cd9f211a9",
        ]
    )


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"))


def _setup_logging(level_name: str, fmt: str) -> None:
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


def _parse_args(defaults: ExampleDefaults) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="DV WebSocket example: connect to Kalshi and/or Polymarket and print normalized events.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--vendors", choices=["kalshi", "polymarket", "both"], default=defaults.vendors)
    p.add_argument("--secs", type=float, default=defaults.secs)
    p.add_argument("--output", choices=["readable", "json"], default=defaults.output)
    p.add_argument("--log-level", default="INFO")
    p.add_argument("--log-format", choices=["console", "json"], default="console")
    p.add_argument("--internal-level", default="WARNING", help="Log level for internal libs (websockets, client)")
    p.add_argument("--events", type=str, default="", help="Subset of events to print: ticker,orderbook,trade; empty = all")
    p.add_argument("--include-raw", action="store_true", help="Also print raw/untyped messages (e.g., subscription ACKs)")

    # Shared convenience
    p.add_argument("--tickers", type=str, default="", help="Generic list passed to selected vendors (Kalshi tickers / Polymarket assets_ids)")

    # Kalshi-specific
    p.add_argument("--kalshi-env", choices=["paper", "live"], default=defaults.kalshi_env)
    p.add_argument("--kalshi-channels", type=str, default=",".join(defaults.kalshi_channels))
    p.add_argument("--kalshi-tickers", type=str, default="")
    p.add_argument("--kalshi-events", type=str, default="", help="Event tickers to expand to market tickers (best-effort)")

    # Polymarket-specific
    p.add_argument(
        "--assets",
        type=str,
        default=",".join(defaults.assets) if defaults.assets else "",
        help="Polymarket assets_ids (overrides --tickers for Polymarket)",
    )
    return p.parse_args()


def _split_csv(val: str) -> List[str]:
    return [x.strip() for x in (val or "").split(",") if x.strip()]


def _env_to_cfg(env: str) -> KalshiConfig:
    return KalshiConfig.PAPER if env.lower() == "paper" else KalshiConfig.LIVE


async def main() -> None:
    defaults = ExampleDefaults()
    args = _parse_args(defaults)
    _setup_logging(args.log_level, args.log_format)
    # Quiet noisy internals unless asked otherwise
    lib_level = getattr(logging, getattr(args, "internal_level", "WARNING").upper(), logging.WARNING)
    for name in ("websockets", "websockets.client", "datavents.providers"):
        logging.getLogger(name).setLevel(lib_level)

    vendors = {
        "kalshi": [DvVendors.KALSHI],
        "polymarket": [DvVendors.POLYMARKET],
        "both": [DvVendors.KALSHI, DvVendors.POLYMARKET],
    }[args.vendors]

    sub = DvSubscription(
        vendors=vendors,
        tickers_or_ids=_split_csv(args.tickers) or None,
        kalshi_env=_env_to_cfg(args.kalshi_env),
        kalshi_channels=_split_csv(args.kalshi_channels) or ["ticker"],
        kalshi_market_tickers=_split_csv(args.kalshi_tickers) or None,
        kalshi_event_tickers=_split_csv(args.kalshi_events) or None,
        polymarket_assets_ids=_split_csv(args.assets) or None,
    )

    stop_event = asyncio.Event()

    requested = {e.strip().lower() for e in _split_csv(getattr(args, "events", ""))}
    show_all = not requested

    def _should_show(evt: NormalizedEvent) -> bool:
        if evt.event == "raw" and not args.include_raw:
            return False
        return show_all or evt.event in requested

    def _format_readable(evt: NormalizedEvent) -> str:
        # Kalshi pretty prints similar to the dedicated example
        if evt.vendor == DvVendors.KALSHI:
            t = evt.event
            data = evt.data.get("data") or evt.data.get("msg") or evt.data
            mt = data.get("market_ticker") or data.get("ticker") or data.get("market") or evt.market
            if t == "ticker":
                yb = data.get("yes_bid") or data.get("best_bid") or data.get("high_bid")
                ya = data.get("yes_ask") or data.get("best_ask") or data.get("low_ask")
                return f"kalshi:ticker {mt} yb={yb} ya={ya}"
            if t == "orderbook":
                return f"kalshi:orderbook {mt}"
            if t == "trade":
                qty = data.get("count") or data.get("quantity") or data.get("size")
                px = data.get("yes_price") or data.get("price")
                try:
                    if isinstance(px, (int, float)) and px <= 1:
                        px = int(round(px * 100))
                except Exception:
                    pass
                side = data.get("taker_side") or data.get("side")
                suffix = f" [{side}]" if side else ""
                return f"kalshi:trade {mt} {qty}@{px}{suffix}"
        # Polymarket conservative readable print
        if evt.vendor == DvVendors.POLYMARKET:
            t = evt.event
            data = evt.data
            aid = (
                data.get("asset_id") or data.get("assetId") or data.get("id") or evt.market
            )
            if t == "ticker":
                price = data.get("price") or data.get("lastPrice") or data.get("mid")
                bb = data.get("bestBid") or data.get("bid")
                ba = data.get("bestAsk") or data.get("ask")
                return f"poly:ticker {aid} mid={price} bb={bb} ba={ba}"
            if t == "orderbook":
                return f"poly:orderbook {aid}"
            if t == "trade":
                qty = data.get("size") or data.get("qty")
                px = data.get("price")
                return f"poly:trade {aid} {qty}@{px}"
        # Raw or unknown
        return f"{evt.vendor}:{evt.event} market={evt.market} ts={evt.received_ts:.3f}"

    async def on_event(evt: NormalizedEvent) -> None:
        if not _should_show(evt):
            return
        if args.output == "json":
            print(
                json.dumps(
                    {
                        "vendor": getattr(evt.vendor, "value", str(evt.vendor)),
                        "event": evt.event,
                        "market": evt.market,
                        "received": datetime.fromtimestamp(evt.received_ts, tz=timezone.utc).isoformat(),
                        "data": evt.data,
                    },
                    separators=(",", ":"),
                )
            )
        else:
            print(_format_readable(evt))

    async def _auto_stop() -> None:
        await asyncio.sleep(float(args.secs))
        stop_event.set()

    dv = DvWsClient()
    asyncio.create_task(_auto_stop())
    await dv.run(sub, on_event, stop_event=stop_event)


if __name__ == "__main__":
    asyncio.run(main())
