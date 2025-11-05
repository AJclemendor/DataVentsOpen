from __future__ import annotations

from pprint import pprint

from datavents import (
    DataVentsNoAuthClient,
    DataVentsProviders,
    DataVentsOrderSortParams,
    DataVentsStatusParams,
    normalize_search_response,
    normalize_market,
    Provider,
    OrderSort,
    StatusFilter,
)


def main() -> None:
    client = DataVentsNoAuthClient()

    # Kalshi search → normalize
    k = client.search_events(
        provider=DataVentsProviders.KALSHI,
        query="election",
        limit=5,
        page=0,
        order_sort_params=DataVentsOrderSortParams.ORDER_BY_TRENDING,
        status_params=DataVentsStatusParams.OPEN_MARKETS,
    )[0]["data"]
    kn = normalize_search_response(Provider.kalshi, k, q="election", page=1, limit=5, order=OrderSort.trending, status=StatusFilter.open)
    print("Kalshi normalized search items:", len(kn.results))

    # Polymarket markets → normalize first few
    p = client.list_markets(
        provider=DataVentsProviders.POLYMARKET,
        limit=10,
        page=1,
        status_params=DataVentsStatusParams.OPEN_MARKETS,
        query=" ",
        order_sort_params=DataVentsOrderSortParams.ORDER_BY_TRENDING,
    )[0]["data"]
    markets = [m for m in (p.get("markets") or []) if isinstance(m, dict)]
    if markets:
        nm = [normalize_market(Provider.polymarket, markets[i]) for i in range(min(3, len(markets)))]
        print("Polymarket normalized markets (sample):")
        for m in nm:
            print("-", m.market_id, m.status, m.best_bid, m.best_ask)


if __name__ == "__main__":
    main()

