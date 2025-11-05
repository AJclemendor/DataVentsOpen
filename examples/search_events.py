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
    ap = argparse.ArgumentParser(description="Search events across providers")
    ap.add_argument("--q", default="election", help="query string")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--page", type=int, default=0)
    ap.add_argument("--provider", default="all", choices=["kalshi", "polymarket", "all"]) 
    args = ap.parse_args()

    provider = {
        "kalshi": DataVentsProviders.KALSHI,
        "polymarket": DataVentsProviders.POLYMARKET,
        "all": DataVentsProviders.ALL,
    }[args.provider]

    client = DataVentsNoAuthClient()
    res = client.search_events(
        provider=provider,
        query=args.q,
        limit=args.limit,
        page=args.page,
        order_sort_params=DataVentsOrderSortParams.ORDER_BY_TRENDING,
        status_params=DataVentsStatusParams.OPEN_MARKETS,
    )
    for block in res:
        print("\n===", block["provider"].upper(), "===")
        keys = list(block["data"].keys()) if isinstance(block.get("data"), dict) else []
        print("keys:", keys)
        # Print a short snippet
        pprint({k: block["data"].get(k) for k in keys[:2]})


if __name__ == "__main__":
    main()

