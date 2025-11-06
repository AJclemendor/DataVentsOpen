from overrides import override
import requests
from .base_client import BasePolymarketClient
from ..config import Config
from .rest_auth import PolymarketAuth
from typing import Dict, Any, overload

import os
import sys

try:
    from ..shared_connection.rate_limit import RateLimitConfig
except Exception:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from shared_connection.rate_limit import RateLimitConfig


from enum import Enum
class PolymarketEventStatus(Enum):
    OPEN_MARKETS = "active"
    CLOSED_MARKETS = "closed"
    ALL_MARKETS = "all"

class InternalPolymarketRoutesSortBy(Enum):
    NO_SORT = ""
    ORDER_BY_CLOSING_SOON = "end_date"
    ORDER_BY_TRENDING = "volume_24hr"
    ORDER_BY_LIQUIDITY = "liquidity"
    ORDER_BY_VOLUME = "volume"
    ORDER_BY_NEWEST = "start_date"
    ORDER_BY_VOLATILE = "volume_24hr"  # Using volume_24hr as proxy for volatility
    ORDER_BY_EVEN_ODDS = ""  # No direct equivalent
    ORDER_BY_QUERYMATCH = ""  # No direct equivalent
    COMPETETIVE_EVENT = "competitive"

class PolymarketRestNoAuth(BasePolymarketClient):
    def __init__(self):
        auth = PolymarketAuth(config=Config.NOAUTH)
        super().__init__(
            polymarketAuth=auth,
            config=Config.NOAUTH,
            rate_limit_config=RateLimitConfig(),
        )

    def get_tags(
        self,
        limit: int,
        offset: int,
        order: str,  # csv list of fields to order by
        ascending: bool,
        include_template: bool,
        is_carousel: bool,
    ):
        assert limit >= 0
        assert offset >= 0
        return self.get(
            "/tags",
            params={
                "limit": limit,
                "offset": offset,
                "order": order,
                "ascending": ascending,
                "include_template": include_template,
                "is_carousel": is_carousel,
            },
        )

    def get_tag_by_id(self, id: int, include_template: bool):
        return self.get(
            f"/tags/{id}",
            params={
                "include_template": include_template,
            },
        )

    def get_tag_by_slug(self, slug: str, include_template: bool):
        return self.get(
            f"/tags/slug/{slug}",
            params={
                "include_template": include_template,
            },
        )

    def get_related_tags_relationships_by_tag_id(
        self, tag_id: int, omit_empty: bool, status: str
    ):
        assert status in ["active", "closed", "all"]
        return self.get(
            f"/tags/{tag_id}/related-tags",
            params={
                "omit_empty": omit_empty,
                "status": status,
            },
        )

    def get_related_tags_relationships_by_tag_slug(
        self, slug: str, omit_empty: bool, status: str
    ):
        assert status in ["active", "closed", "all"]
        return self.get(
            f"/tags/slug/{slug}/related-tags",
            params={
                "omit_empty": omit_empty,
                "status": status,
            },
        )

    def get_tags_related_to_a_tag_id(self, tag_id: int, omit_empty: bool, status: str):
        assert status in ["active", "closed", "all"]
        return self.get(
            f"/tags/{tag_id}/related-tags/tags",
            params={
                "omit_empty": omit_empty,
                "status": status,
            },
        )

    def get_tags_related_to_a_tag_slug(self, slug: str, omit_empty: bool, status: str):
        assert status in ["active", "closed", "all"]
        return self.get(
            f"/tags/slug/{slug}/related-tags/tags",
            params={
                "omit_empty": omit_empty,
                "status": status,
            },
        )

    def get_events(
        self,
        limit: int,
        offset: int,
        order: str,  # csv list of fields to order by
        ascending: bool,
        id: list[int],
        slug: list[str],
        tag_id: int,
        # Instincyt makes me thing these r swapped well c
        exclude_tag_id: list[int],
        related_tags: bool,
        featured: bool,
        cyom: bool,
        include_chat: bool,
        include_template: bool,
        recurrence: str,
        closed: bool,
        start_date_min: str,  # string<date-time>
        start_date_max: str,  # string<date-time>
        end_date_min: str,  # string<date-time>
        end_date_max: str,  # string<date-time>
    ):
        assert limit >= 0
        assert offset >= 0

        return self.get(
            "/events",
            params={
                "limit": limit,
                "offset": offset,
                "order": order,
                "ascending": ascending,
                "id": id,
                "slug": slug,
                "tag_id": tag_id,
                "exclude_tag_id": exclude_tag_id,
                "related_tags": related_tags,
                "featured": featured,
                "cyom": cyom,
                "include_chat": include_chat,
                "include_template": include_template,
                "recurrence": recurrence,
                "closed": closed,
                "start_date_min": start_date_min,
                "start_date_max": start_date_max,
                "end_date_min": end_date_min,
                "end_date_max": end_date_max,
            },
        )

    def get_events_by_id(self, id: int, include_chat: bool, include_template: bool):
        return self.get(
            f"/events/{id}",
            params={
                "include_chat": include_chat,
                "include_template": include_template,
            },
        )

    def get_event_by_slug(self, slug: str, include_chat: bool, include_template: bool):
        return self.get(
            f"/events/slug/{slug}",
            params={
                "include_chat": include_chat,
                "include_template": include_template,
            },
        )

    def get_event_tags(self, id: int):
        return self.get(f"/events/{id}/tags")

    def get_markets(
        self,
        limit: int,
        offset: int,
        order: str,  # csv list of fields to order by
        ascending: bool,
        id: list[int],
        slug: list[str],
        clob_token_ids: list[str],
        condition_ids: list[str],
        market_maker_addresses: list[str],
        liquidity_num_min: int,
        liquidity_num_max: int,
        volume_num_min: int,
        volume_num_max: int,
        start_date_min: str,  # string<date-time>
        start_date_max: str,  # string<date-time>
        end_date_min: str,  # string<date-time>
        end_date_max: str,  # string<date-time>
        tag_id: int,
        related_tags: bool,
        cyom: bool,
        uma_resolution_status: str,
        game_id: str,
        sports_market_types: list[str],
        rewards_min_size: int,
        question_ids: list[str],
        include_tags: bool,
        closed: bool,
    ):
        assert limit >= 0
        assert offset >= 0
        return self.get(
            "/markets",
            params={
                "limit": limit,
                "offset": offset,
                "order": order,
                "ascending": ascending,
                "id": id,
                "slug": slug,
                "clob_token_ids": clob_token_ids,
                "condition_ids": condition_ids,
                "market_maker_addresses": market_maker_addresses,
                "liquidity_num_min": liquidity_num_min,
                "liquidity_num_max": liquidity_num_max,
                "volume_num_min": volume_num_min,
                "volume_num_max": volume_num_max,
                "start_date_min": start_date_min,
                "start_date_max": start_date_max,
                "end_date_min": end_date_min,
                "end_date_max": end_date_max,
                "tag_id": tag_id,
                "related_tags": related_tags,
                "rewards_min_size": rewards_min_size,
                "question_ids": question_ids,
                "include_tags": include_tags,
                "closed": closed,
                "cyom": cyom,
                "uma_resolution_status": uma_resolution_status,
                "game_id": game_id,
                "sports_market_types": sports_market_types,
                "include_tags": include_tags,
                "closed": closed,
            },
        )

    def get_market_by_id(self, id: int, include_tag: bool):
        return self.get(
            f"/markets/{id}",
            params={
                "include_tag": include_tag,
            },
        )

    def get_market_by_slug(self, slug: str, include_tag: bool):
        return self.get(
            f"/markets/slug/{slug}",
            params={
                "include_tag": include_tag,
            },
        )

    # ---- CLOB order book endpoints (public, no auth) ------------------------
    # These live on the clob.polymarket.com host, not the gamma API.
    # We call them directly with proper rate limiting and timeout.

    def _clob_get(self, path: str, params: Dict[str, Any] | None = None) -> Any:
        import requests as _rq
        self.rate_limit_config.rate_limit()
        url = f"https://clob.polymarket.com{path}"
        r = _rq.get(url, params=params or {}, timeout=self._timeout_seconds)
        self.raise_if_bad_response(r)
        return r.json()

    def _clob_post(self, path: str, body: Any) -> Any:
        import requests as _rq
        self.rate_limit_config.rate_limit()
        url = f"https://clob.polymarket.com{path}"
        r = _rq.post(url, json=body, timeout=self._timeout_seconds)
        self.raise_if_bad_response(r)
        return r.json()

    def get_orderbook(self, token_id: str, *, side: str | None = None) -> Any:
        """Fetch a single order book snapshot for a token from CLOB.

        GET https://clob.polymarket.com/book?token_id=... [&side=BUY|SELL]

        Args
        - token_id: CLOB token id (string)
        - side: optional filter ("BUY" or "SELL") supported by some operations
        """
        params: Dict[str, Any] = {"token_id": str(token_id)}
        if side:
            s = str(side).upper()
            if s in {"BUY", "SELL"}:
                params["side"] = s
        return self._clob_get("/book", params=params)

    def get_orderbooks(self, requests_list: list[dict[str, Any]]) -> Any:
        """Fetch multiple order book summaries by POSTing a list of requests.

        POST https://clob.polymarket.com/books

        Body example (list of objects):
          [{"token_id": "...", "side": "SELL"}, {"token_id": "..."}]
        """
        if not isinstance(requests_list, list) or not requests_list:
            raise ValueError("requests_list must be a non-empty list of dicts")
        payload: list[dict[str, Any]] = []
        for it in requests_list:
            if not isinstance(it, dict):
                continue
            token_id = str(it.get("token_id") or "").strip()
            if not token_id:
                continue
            entry: dict[str, Any] = {"token_id": token_id}
            side = it.get("side")
            if isinstance(side, str) and side.strip():
                s = side.strip().upper()
                if s in {"BUY", "SELL"}:
                    entry["side"] = s
            payload.append(entry)
        if not payload:
            raise ValueError("No valid items provided; each item requires token_id")
        return self._clob_post("/books", body=payload)

    def get_market_tags_by_id(self, id: int):
        return self.get(f"/markets/{id}/tags")

    def list_series(
        self,
        limit: int,
        offset: int,
        order: str,  # csv list of fields to order by
        ascending: bool,
        slug: list[str],
        categories_ids: list[int],
        category_labels: list[str],
        closed: bool,
        include_chat: bool,
        recurrence: str,
    ):
        assert limit >= 0
        assert offset >= 0
        return self.get(
            "/series",
            params={
                "limit": limit,
                "offset": offset,
                "order": order,
                "ascending": ascending,
                "slug": slug,
                "categories_ids": categories_ids,
                "category_labels": category_labels,
                "closed": closed,
                "include_chat": include_chat,
                "recurrence": recurrence,
            },
        )

    def get_series_by_id(self, id: int, include_chat: bool):
        return self.get(
            f"/series/{id}",
            params={
                "include_chat": include_chat,
            },
        )

    def list_comments(
        self,
        limit: int,
        offset: int,
        order: str,  # csv list of fields to order by
        ascending: bool,
        parent_entity_check: str,
        parent_entity_id: int,
        get_positions: bool,
        holders_only: bool,
    ):

        assert limit >= 0
        assert offset >= 0
        assert parent_entity_check in ["Event", "Series", "Market"]
        return self.get(
            "/comments",
            params={
                "limit": limit,
                "offset": offset,
                "order": order,
                "ascending": ascending,
                "parent_entity_check": parent_entity_check,
                "parent_entity_id": parent_entity_id,
                "get_positions": get_positions,
                "holders_only": holders_only,
            },
        )

    def get_comment_by_id(self, id: int, get_positions: bool):
        return self.get(
            f"/comments/{id}",
            params={
                "get_positions": get_positions,
            },
        )

    def get_comment_by_user_address(
        self, user_address: str, limit: int, offset: int, order: str, ascending: bool
    ):
        return self.get(
            f"/comments/user_address/{user_address}",
            params={
                "limit": limit,
                "offset": offset,
                "order": order,
                "ascending": ascending,
            },
        )

    def search_markets_events_profiles(
        self,
        q: str,
        cache: bool,
        event_status: str,
        limit_per_type: int,
        page: int,
        events_tags: list[str],
        keep_closed_markets: bool,
        sort: str,
        ascending: bool,
        search_tags: bool,
        search_profiles: bool,
        recurrence: str,
        exclude_tag_ids: list[int],
        optimized: bool,
    ):
        assert limit_per_type >= 0
        assert page >= 0
        assert event_status in ["active", "closed", "all"]
        return self.get(
            "/public-search",
            params={
                "q": q,
                "cache": cache,
                "event_status": event_status,
                "limit_per_type": limit_per_type,
                "page": page,
                "events_tags": events_tags,
                "keep_closed_markets": keep_closed_markets,
                "sort": sort,
                "ascending": ascending,
                "search_tags": search_tags,
                "search_profiles": search_profiles,
                "recurrence": recurrence,
                "exclude_tag_ids": exclude_tag_ids,
                "optimized": optimized,
            },
        )

    def search_events(
        self,
        q: str,
        optimized: bool,
        limit_per_type: int,
        type: str,  # events
        search_tags: bool,
        search_profiles: bool,
        cache: bool,
        presets: list[str],  # EventsTitle, Events
        page: int,
        events_status: PolymarketEventStatus,
        sort: InternalPolymarketRoutesSortBy,
        ascending: bool,
    ):
        """
        public-search
        if no presets dont pass any
        if no events_status pass all
        """
        assert page >= 0
        assert isinstance(events_status, PolymarketEventStatus)
        assert sort in [
            InternalPolymarketRoutesSortBy.ORDER_BY_TRENDING,
            InternalPolymarketRoutesSortBy.ORDER_BY_VOLUME,
            InternalPolymarketRoutesSortBy.ORDER_BY_LIQUIDITY,
            InternalPolymarketRoutesSortBy.ORDER_BY_CLOSING_SOON,
            InternalPolymarketRoutesSortBy.ORDER_BY_NEWEST,
            InternalPolymarketRoutesSortBy.ORDER_BY_VOLATILE,
            InternalPolymarketRoutesSortBy.ORDER_BY_EVEN_ODDS,
            InternalPolymarketRoutesSortBy.ORDER_BY_QUERYMATCH,
            InternalPolymarketRoutesSortBy.COMPETETIVE_EVENT,
            InternalPolymarketRoutesSortBy.NO_SORT,
        ]
        # Build base payload
        payload = {
            "q": q,
            "page": page,
            "limit_per_type": limit_per_type,
            "type": type,
        }

        # Add optional parameters
        if events_status:
            payload["events_status"] = events_status.value
        if sort and sort.value:  # Only add if sort has a value
            payload["sort"] = sort.value

        # Handle presets as list (requests will convert to multiple params)
        if presets:
            payload["presets"] = presets

        return self.get(
            "/public-search",
            params=payload,
        )
