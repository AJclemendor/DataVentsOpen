from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
SRC_DIR = os.path.join(BACKEND_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from datavents.providers.polymarket.ws_client import PolymarketWsClient

# Default assets hardcoded per request (can be overridden via --assets or env)
DEFAULT_ASSETS = [
    "33945469250963963541781051637999677727672635213493648594066577298999471399137",
    "0xebddfcf7b4401dade8b4031770a1ab942b01854f3bed453d5df9425cd9f211a9",
]


@dataclass
class Defaults:
    secs: float = 30.0
    output: str = "human"  # human|json


def _split_csv(val: str) -> List[str]:
    return [x.strip() for x in (val or "").split(",") if x.strip()]


def _setup_logging(level_name: str, internal_level: str) -> None:
    lvl = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(level=lvl, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    lib_level = getattr(logging, internal_level.upper(), logging.WARNING)
    for name in ("websockets", "websockets.client", "datavents.providers"):
        logging.getLogger(name).setLevel(lib_level)


async def main() -> None:
    d = Defaults()
    p = argparse.ArgumentParser(description="Polymarket Market WS example")
    p.add_argument(
        "--assets",
        type=str,
        default=os.getenv("POLYMARKET_TEST_ASSETS", ",".join(DEFAULT_ASSETS)),
        help="Comma-separated assets_ids to subscribe",
    )
    p.add_argument("--secs", type=float, default=d.secs)
    p.add_argument("--output", choices=["human", "json"], default=d.output)
    p.add_argument("--log-level", default="INFO")
    p.add_argument("--internal-level", default="WARNING")
    args = p.parse_args()

    _setup_logging(args.log_level, args.internal_level)
    assets = _split_csv(args.assets)
    if not assets:
        raise SystemExit("Provide --assets (comma-separated Polymarket assets_ids) or set POLYMARKET_TEST_ASSETS env var")

    client = PolymarketWsClient()
    stop_event = asyncio.Event()

    async def on_msg(msg):
        if args.output == "json":
            print(json.dumps(msg, separators=(",", ":")))
            return
        t = (msg.get("type") or msg.get("event") or "").lower()
        aid = msg.get("asset_id") or msg.get("assetId") or msg.get("id")
        if t in {"ticker", "quote", "price"}:
            mid = msg.get("price") or msg.get("lastPrice") or msg.get("mid")
            bb = msg.get("bestBid") or msg.get("bid")
            ba = msg.get("bestAsk") or msg.get("ask")
            print(f"poly:ticker {aid} mid={mid} bb={bb} ba={ba}")
        elif "orderbook" in t or t in {"book", "ob"}:
            print(f"poly:orderbook {aid}")
        elif t in {"trade", "fill", "match"}:
            qty = msg.get("size") or msg.get("qty")
            px = msg.get("price")
            print(f"poly:trade {aid} {qty}@{px}")
        else:
            print(json.dumps(msg, separators=(",", ":")))

    async def _auto_stop():
        await asyncio.sleep(float(args.secs))
        stop_event.set()

    asyncio.create_task(_auto_stop())
    await client.run(on_msg, assets_ids=assets, stop_event=stop_event)


if __name__ == "__main__":
    asyncio.run(main())
