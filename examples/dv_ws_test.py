from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
SRC_DIR = os.path.join(BACKEND_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from datavents import DvWsClient, DvVendors, DvSubscription
from datavents.providers.config import Config as KalshiConfig


def _split_csv(val: str) -> List[str]:
    return [x.strip() for x in (val or "").split(",") if x.strip()]


def _env_to_cfg(env: str) -> KalshiConfig:
    return KalshiConfig.PAPER if env.lower() == "paper" else KalshiConfig.LIVE


async def main() -> None:
    p = argparse.ArgumentParser(description="DV WS smoke test: connect to Kalshi and Polymarket and assert at least one message from each")
    p.add_argument("--secs", type=float, default=20.0, help="Run duration")
    p.add_argument("--kalshi-env", choices=["paper", "live"], default=os.getenv("DV_TEST_KALSHI_ENV", "live"))
    p.add_argument("--kalshi-events", type=str, default=os.getenv("DV_TEST_KALSHI_EVENTS", ""), help="Kalshi event tickers to expand")
    p.add_argument("--kalshi-tickers", type=str, default=os.getenv("DV_TEST_KALSHI_TICKERS", ""), help="Kalshi market tickers")
    p.add_argument("--assets", type=str, default=os.getenv("DV_TEST_POLY_ASSETS", ""), help="Polymarket assets_ids (comma-separated)")
    args = p.parse_args()

    kalshi_tokens = _split_csv(args.kalshi_tickers) or None
    kalshi_events = _split_csv(args.kalshi_events) or None
    assets = _split_csv(args.assets) or None

    vendors = []
    if kalshi_tokens or kalshi_events:
        vendors.append(DvVendors.KALSHI)
    if assets:
        vendors.append(DvVendors.POLYMARKET)
    if not vendors:
        raise SystemExit("Provide --kalshi-tickers or --kalshi-events and --assets to test both vendors")

    sub = DvSubscription(
        vendors=vendors,
        kalshi_env=_env_to_cfg(args.kalshi_env),
        kalshi_market_tickers=kalshi_tokens,
        kalshi_event_tickers=kalshi_events,
        polymarket_assets_ids=assets,
    )

    counts: Dict[str, int] = defaultdict(int)
    by_vendor: Dict[str, int] = defaultdict(int)
    stop_event = asyncio.Event()

    async def on_event(evt):
        key = f"{getattr(evt.vendor, 'value', str(evt.vendor))}:{evt.event}"
        counts[key] += 1
        by_vendor[getattr(evt.vendor, 'value', str(evt.vendor))] += 1

    async def _auto_stop():
        await asyncio.sleep(float(args.secs))
        stop_event.set()

    dv = DvWsClient()
    asyncio.create_task(_auto_stop())
    await dv.run(sub, on_event, stop_event=stop_event)

    summary = {
        "ended": datetime.now(tz=timezone.utc).isoformat(),
        "counts": counts,
        "by_vendor": by_vendor,
    }
    print(json.dumps(summary, default=lambda o: dict(o), separators=(",", ":")))

    # Simple assertion: at least one message per selected vendor
    failures: List[str] = []
    for v in vendors:
        name = getattr(v, "value", str(v))
        if by_vendor.get(name, 0) <= 0:
            failures.append(name)
    if failures:
        raise SystemExit(f"FAIL: no messages received for {failures}")


if __name__ == "__main__":
    asyncio.run(main())
