"""
users dont actually need to auth via api to use these endpoints
diff rate lims also
no paper needed
"""

import json
from overrides import override  # type: ignore
import requests
from .base_client import BaseKalshiClient
from ..config import Config
from .rest_auth import KalshiAuth
from typing import Dict, Any, overload
from enum import Enum

import os
import sys

try:
    # Prefer package-relative import
    from ..shared_connection.rate_limit import RateLimitConfig
except Exception:
    # Fallback to path tweak if package imports are not configured
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from shared_connection.rate_limit import RateLimitConfig



class InternalKalshiRoutesSortBy(Enum):
    NO_SORT = "querymatch"
    ORDER_BY_CLOSING_SOON = "closing"
    ORDER_BY_TRENDING = "trending"
    ORDER_BY_VOLATILE= "price-delta"
    ORDER_BY_NEWEST = "newest"
    ORDER_BY_VOLUME = "event-volume"
    ORDER_BY_LIQUIDITY = "liquidity"
    ORDER_BY_EVEN_ODDS = "price-balance"
    ORDER_BY_QUERYMATCH = "querymatch"


class MarketStatus(Enum):
    CLOSED_MARKETS = "closed,settled"
    OPEN_MARKETS = "opened,unopened"
    ALL_MARKETS = ""


class KalshiRestNoAuth(BaseKalshiClient):
    def __init__(self):
        auth = KalshiAuth(config=Config.NOAUTH)
        super().__init__(
            kalshiAuth=auth, config=Config.NOAUTH, rate_limit_config=RateLimitConfig()
        )

        self.exchange_url = "/exchange"
        self.series_url = "/series"
        self.markets_url = "/markets"
        self.search = "/search"
        self.live_data = "/live-data"
        self.multivariate_event_collections_url = "/multivariate_event_collections"

    @override
    def post(self, path: str, body: dict) -> Any:
        """Performs an authenticated POST request to the Kalshi API."""
        self.rate_limit_config.rate_limit()
        path = self.api_path + path
        response = requests.post(
            self.BASE_API_URL + path,
            json=body,
        )
        self.raise_if_bad_response(response)
        return response.json()

    def get(self, path: str, params: Dict[str, Any] = {}) -> Any:
        """Performs an authenticated GET request to the Kalshi API."""
        self.rate_limit_config.rate_limit()
        path = self.api_path + path
        response = requests.get(
            self.BASE_API_URL + path,
            params=params,
        )
        self.raise_if_bad_response(response)
        return response.json()

    def delete(self, path: str, params: Dict[str, Any] = {}) -> Any:
        """Performs an authenticated DELETE request to the Kalshi API."""
        self.rate_limit_config.rate_limit()
        path = self.api_path + path
        response = requests.delete(
            self.BASE_API_URL + path,
            params=params,
        )
        self.raise_if_bad_response(response)
        return response.json()

    def get_exchange_status(self) -> Dict[str, Any]:
        """Retrieves the exchange status."""
        return self.get(self.exchange_url + "/status")

    def get_exchange_announcements(self) -> Dict[str, Any]:
        """Retrieves the exchange announcements."""
        return self.get(self.exchange_url + "/announcements")

    def get_exchange_schedule(self) -> Dict[str, Any]:
        """Retrieves the exchange schedule."""
        return self.get(self.exchange_url + "/schedule")

    def get_user_data_timestamp(self) -> Dict[str, Any]:
        """Retrieves the user data timestamp."""
        return self.get(self.exchange_url + "/user_data_timestamp")

    def get_series_fee_changes(self) -> Dict[str, Any]:
        """Retrieves the series fee changes."""
        return self.get(self.series_url + "/fee_changes")

    def get_tags_for_series_categories(self) -> Dict[str, Any]:
        """Retrieves the tags for series categories."""
        return self.get(self.search + "/tags_by_categories")

    def get_filters_for_sports(self) -> Dict[str, Any]:
        """Retrieves the filters for sports."""
        return self.get(self.search + "/filters_by_sport")

    def get_market_candlesticks(
        self,
        series_ticker: str,
        ticker: str,
        start_ts: int,
        end_ts: int,
        period_interval: int,
    ):
        """Retrieves the candlesticks for a market."""
        return self.get(
            self.series_url + f"/{series_ticker}/markets/{ticker}/candlesticks",
            params={
                "start_ts": start_ts,
                "end_ts": end_ts,
                "period_interval": period_interval,
            },
        )

    def get_trades(
        self,
        ticker: str,
        cursor: str = None,
        limit: int = 100,
        min_ts: int = None,
        max_ts: int = None,
    ):
        """Retrieves the trades for a market."""
        # todo test
        return self.get(
            self.markets_url + f"/trades",
            params={
                "cursor": cursor,
                "limit": limit,
                "min_ts": min_ts,
                "max_ts": max_ts,
                "ticker": ticker,
            },
        )

    def get_series(self, series_ticker: str):
        """Retrieves the series for a market."""
        return self.get(
            self.series_url + f"/{series_ticker}",
        )

    def get_series_list(
        self, category: str, tags: str, include_product_metadata: bool = False
    ):
        """Retrieves the series list."""
        return self.get(
            self.series_url,
            params={
                "category": category,
                "tags": tags,
                "include_product_metadata": include_product_metadata,
            },
        )

    def get_markets(
        self,
        limit: int = 100,
        cursor: str = None,
        event_ticker: str = "",
        series_ticker: str = "",
        max_close_ts: int = None,
        min_close_ts: int = None,
        status: str = "",
        tickers: list[str] = [],  # csv list of tickers
    ):

        return self.get(
            self.markets_url,
            params={
                "limit": limit,
                "cursor": cursor,
                "event_ticker": event_ticker,
                "series_ticker": series_ticker,
                "max_close_ts": max_close_ts,
                "min_close_ts": min_close_ts,
                "status": status,
                "tickers": tickers,
            },
        )

    def get_market(self, ticker: str):
        """Retrieves the market for a ticker."""
        return self.get(
            self.markets_url,
            params={
                "ticker": ticker,
            },
        )

    def get_event_candlesticks(
        self,
        ticker: str,
        series_ticker: str,
        start_ts: int,
        end_ts: int,
        period_interval: int,
    ):  # Peirod Inrerv al is enum<integet>
        """Retrieves the candlesticks for an event."""
        return self.get(
            self.series_url + f"/{series_ticker}/events/{ticker}/candlesticks",
            params={
                "start_ts": start_ts,
                "end_ts": end_ts,
                "period_interval": period_interval,
            },
        )

    def get_events(
        self,
        limit: int = 100,
        cursor: str = None,
        with_nested_markets: bool = False,
        with_milestones: bool = False,
        status: str = "",  # enum<string>
        series_ticker: str = "",
        min_close_ts: int = None,
        max_close_ts: int = None,
    ):
        assert 1 <= limit <= 200, "Limit must be between 1 and 200"

        return self.get(
            self.series_url + f"/events",
            params={
                "limit": limit,
                "cursor": cursor,
                "with_nested_markets": with_nested_markets,
                "with_milestones": with_milestones,
                "status": status,
                "series_ticker": series_ticker,
                "min_close_ts": min_close_ts,
                "max_close_ts": max_close_ts,
            },
        )

    def get_event(self, event_ticker: str, with_nested_markets: bool = False):
        """Retrieve a single event by its ticker (v2 non-series path)."""
        return self.get(
            f"/events/{event_ticker}",
            params={
                "with_nested_markets": with_nested_markets,
            },
        )

    def get_event_metadata(self, event_ticker: str):
        """Retrieve metadata for an event by its ticker (v2 non-series path)."""
        return self.get(
            f"/events/{event_ticker}/metadata",
        )

    def get_live_data(self, type: str, milestone_id: str):
        return self.get(
            self.live_data + f"/{type}/milestone/{milestone_id}",
        )

    def get_multiple_live_data(self, milestone_ids: list[str]):
        return self.get(
            self.live_data + f"/batch",
            params={
                "milestone_ids": milestone_ids,
            },
        )

    def get_structured_targets(
        self, type: str, competetion: str, page_size: int, cursor: str = None
    ):
        assert 1 <= page_size <= 2000, "Page size must be between 1 and 2000"
        return self.get(
            self.live_data + f"/structured-targets",
            params={
                "type": type,
                "competetion": competetion,
                "page_size": page_size,
                "cursor": cursor,
            },
        )

    def get_structured_target(self, structured_target_id: str):
        return self.get(
            self.live_data + f"/structured-targets/{structured_target_id}",
        )

    def get_milestone(self, milestone_id: str):
        return self.get(
            self.live_data + f"/milestones/{milestone_id}",
        )

    def get_milestones(
        self,
        minimum_start_date: str,
        category: str,
        competetion: str,
        source_id: str,
        type: str,
        related_event_ticker: str = "",
        limit: int = 100,
        cursor: str = None,
    ):
        # "min date is a string<date-time>"
        assert 1 <= limit <= 500, "Limit must be between 1 and 200"
        return self.get(
            self.live_data + f"/milestones",
            params={
                "minimum_start_date": minimum_start_date,
                "category": category,
                "competetion": competetion,
                "source_id": source_id,
                "type": type,
                "related_event_ticker": related_event_ticker,
                "limit": limit,
                "cursor": cursor,
            },
        )

    def get_multivariate_event_collection(self, collection_ticker: str):
        return self.get(
            self.multivariate_event_collections_url + f"/{collection_ticker}",
        )

    def get_multivariate_event_colllections(
        self,
        status: str,
        associated_event_ticker: str,
        series_ticker: str,
        limit: int = 100,
        cursor: str = None,
    ):
        assert 1 <= limit <= 200, "Limit must be between 1 and 200"
        return self.get(
            self.multivariate_event_collections_url,
            params={
                "status": status,
                "associated_event_ticker": associated_event_ticker,
                "series_ticker": series_ticker,
            },
        )

    def get_multivariate_event_collection_events_history(
        self, collection_ticker: str, lookback_seconds: int
    ):
        assert int in [10, 60, 300, 3600]
        return self.get(
            self.multivariate_event_collections_url
            + f"/{collection_ticker}/events/history",
            params={
                "lookback_seconds": lookback_seconds,
            },
        )

    # Internal kalshi apis
    def search_events(
        self,
        query: str,
        order_by: InternalKalshiRoutesSortBy,
        status: MarketStatus,
        page_size: int,
        fuzzy_threshold: int = 4,
        with_milestones: bool = False,
        excluded_categories: list[str] = None,
        frequency: str = "",
    ):
        if excluded_categories is None:
            excluded_categories = []
        params = {
            "query": query,
            "order_by": order_by.value,
            "page_size": page_size,
            "fuzzy_threshold": fuzzy_threshold,
            "with_milestones": with_milestones,
            "excluded_categories": excluded_categories,
        }
        if frequency:
            params["frequency"] = frequency
        if status != MarketStatus.ALL_MARKETS:
            params["status"] = status.value

        # Search endpoint uses v1 API, not v2
        self.rate_limit_config.rate_limit()
        path = "/v1/search/events"
        response = requests.get(
            self.BASE_API_URL + path,
            params=params,
        )
        self.raise_if_bad_response(response)
        return response.json()

    def search_series(
        self,
        query: str,
        order_by: InternalKalshiRoutesSortBy,
        page_size: int,
        fuzzy_threshold: int = 4,
        with_milestones: bool = True,
        excluded_categories: list[str] = None,
        frequency: str = "",
    ):
        """Query Kalshi series search (v1).

        Note: the series endpoint does not accept the same `status` param as events.
        """
        if excluded_categories is None:
            excluded_categories = []
        params = {
            "query": query,
            "order_by": order_by.value,
            "page_size": page_size,
            "fuzzy_threshold": fuzzy_threshold,
            "with_milestones": with_milestones,
            "excluded_categories": excluded_categories,
        }
        if frequency:
            params["frequency"] = frequency

        self.rate_limit_config.rate_limit()
        path = "/v1/search/series"
        response = requests.get(
            self.BASE_API_URL + path,
            params=params,
        )
        self.raise_if_bad_response(response)
        return response.json()



if __name__ == "__main__":
    kalshiRestNoAuth = KalshiRestNoAuth()
    # print(kalshiRestNoAuth.get_exchange_status())
    # print(kalshiRestNoAuth.get_exchange_announcements())
    # print(kalshiRestNoAuth.get_series_fee_changes())
    # print(kalshiRestNoAuth.get_exchange_schedule())
    # print(kalshiRestNoAuth.get_user_data_timestamp())
    # print(kalshiRestNoAuth.get_tags_for_series_categories())
    # print(kalshiRestNoAuth.get_filters_for_sports())
