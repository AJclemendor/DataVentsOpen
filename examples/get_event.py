from __future__ import annotations

import argparse
from pprint import pprint

from datavents import DataVentsNoAuthClient, DataVentsProviders


def main() -> None:
    ap = argparse.ArgumentParser(description="Get a single event by provider identifier")
    ap.add_argument("--provider", required=True, choices=["kalshi", "polymarket"]) 
    ap.add_argument("--kalshi-event-ticker")
    ap.add_argument("--poly-id", type=int)
    ap.add_argument("--poly-slug")
    ap.add_argument("--with-nested-markets", action="store_true")
    args = ap.parse_args()

    client = DataVentsNoAuthClient()
    if args.provider == "kalshi":
        assert args.kalshi_event_ticker, "--kalshi-event-ticker is required"
        res = client.get_event(
            provider=DataVentsProviders.KALSHI,
            kalshi_event_ticker=args.kalshi_event_ticker,
            with_nested_markets=args.with_nested_markets,
        )
    else:
        if not (args.poly_id or args.poly_slug):
            raise SystemExit("Provide --poly-id or --poly-slug")
        res = client.get_event(
            provider=DataVentsProviders.POLYMARKET,
            polymarket_id=args.poly_id,
            polymarket_slug=args.poly_slug,
            with_nested_markets=args.with_nested_markets,
        )
    pprint(res[0]["data"])  # raw provider payload


if __name__ == "__main__":
    main()

