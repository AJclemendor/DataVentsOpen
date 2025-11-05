from __future__ import annotations

import argparse
from pprint import pprint

from datavents import (
    DataVentsNoAuthClient,
    DataVentsProviders,
    DataVentsOrderSortParams,
    DataVentsStatusParams,
)


def main() -> None:
    ap = argparse.ArgumentParser(description="List markets across providers")
    ap.add_argument("--q", default=" ", help="query string; space returns broader results")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--page", type=int, default=1)
    ap.add_argument("--provider", default="all", choices=["kalshi", "polymarket", "all"]) 
    args = ap.parse_args()

    provider = {
        "kalshi": DataVentsProviders.KALSHI,
        "polymarket": DataVentsProviders.POLYMARKET,
        "all": DataVentsProviders.ALL,
    }[args.provider]

    client = DataVentsNoAuthClient()
    res = client.list_markets(
        provider=provider,
        limit=args.limit,
        page=args.page,
        status_params=DataVentsStatusParams.OPEN_MARKETS,
        query=args.q,
        order_sort_params=DataVentsOrderSortParams.ORDER_BY_TRENDING,
    )
    for block in res:
        print("\n===", block["provider"].upper(), "===")
        data = block.get("data") or {}
        markets = data.get("markets") or []
        print("markets:", len(markets))
        for mk in markets[:3]:
            if isinstance(mk, dict):
                print("-", mk.get("id") or mk.get("marketId") or mk.get("slug") or mk.get("marketSlug"))
        if not markets:
            # Kalshi path returns events with nested markets
            print("(Kalshi path uses events search; markets are nested under events)")
            evs = data.get("current_page") or []
            if evs:
                nested = []
                for ev in evs:
                    nested.extend([m for m in (ev.get("markets") or []) if isinstance(m, dict)])
                print("nested markets:", len(nested))
                for mk in nested[:3]:
                    print("-", mk.get("ticker") or mk.get("ticker_name"))


if __name__ == "__main__":
    main()

