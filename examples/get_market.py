from __future__ import annotations

import argparse
from pprint import pprint

from datavents import DataVentsNoAuthClient, DataVentsProviders


def main() -> None:
    ap = argparse.ArgumentParser(description="Get a single market by provider identifier")
    ap.add_argument("--provider", required=True, choices=["kalshi", "polymarket"]) 
    ap.add_argument("--kalshi-ticker")
    ap.add_argument("--poly-id", type=int)
    ap.add_argument("--poly-slug")
    args = ap.parse_args()

    client = DataVentsNoAuthClient()
    if args.provider == "kalshi":
        assert args.kalshi_ticker, "--kalshi-ticker is required"
        res = client.get_market(
            provider=DataVentsProviders.KALSHI,
            kalshi_ticker=args.kalshi_ticker,
        )
        pprint(res[0]["data"])  # raw Kalshi payload
    else:
        if not (args.poly_id or args.poly_slug):
            raise SystemExit("Provide --poly-id or --poly-slug")
        res = client.get_market(
            provider=DataVentsProviders.POLYMARKET,
            polymarket_id=args.poly_id,
            polymarket_slug=args.poly_slug,
        )
        pprint(res[0]["data"])  # raw Polymarket payload


if __name__ == "__main__":
    main()
