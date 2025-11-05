from __future__ import annotations

import argparse
import asyncio
from datavents import DvWsClient, DvSubscription, DvVendors


async def run_ws(vendors: list[str], kalshi_tickers: list[str], poly_assets: list[str]) -> None:
    dv = DvWsClient()

    async def on_evt(evt):  # datavents.ws.NormalizedEvent
        print(evt.vendor, evt.event, evt.market)

    vend_enums = []
    if "kalshi" in vendors:
        vend_enums.append(DvVendors.KALSHI)
    if "polymarket" in vendors:
        vend_enums.append(DvVendors.POLYMARKET)
    if not vend_enums:
        raise SystemExit("Choose at least one vendor")

    sub = DvSubscription(
        vendors=tuple(vend_enums),
        kalshi_market_tickers=kalshi_tickers or None,
        polymarket_assets_ids=poly_assets or None,
    )
    await dv.run(sub, on_evt)


def main() -> None:
    ap = argparse.ArgumentParser(description="Stream Kalshi and/or Polymarket WS events")
    ap.add_argument("--vendors", default="polymarket", help="csv of vendors: kalshi,polymarket")
    ap.add_argument("--kalshi-tickers", default="", help="csv Kalshi market tickers (optional)")
    ap.add_argument("--poly-assets", default="", help="csv Polymarket assets_ids (required if using polymarket)")
    args = ap.parse_args()

    vendors = [v.strip() for v in args.vendors.split(",") if v.strip()]
    kalshi_tickers = [t.strip() for t in args.kalshi_tickers.split(",") if t.strip()]
    poly_assets = [p.strip() for p in args.poly_assets.split(",") if p.strip()]

    asyncio.run(run_ws(vendors, kalshi_tickers, poly_assets))


if __name__ == "__main__":
    main()

