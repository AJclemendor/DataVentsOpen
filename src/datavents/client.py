"""Unified, no‑auth DataVents client.

This module provides a thin façade over provider no‑auth clients for Kalshi and
Polymarket. It intentionally keeps parameter and response shapes close to the
underlying clients while offering a handful of conveniences:

- Unified search across providers with consistent output items
- Optional fuzzy filtering (`q`) over provider list responses
- Elections API integrations to surface Kalshi discovery/search use cases
- WS helpers that return a small handle for lifecycle control

Auth note (lazy)
----------------
- While the default is no‑auth, this module can lazily initialize signed
  provider clients for endpoints that require authentication. For example,
  ``get_kalshi_market_orderbook(...)`` spins up a signed Kalshi REST client
  (LIVE or PAPER) on first use, pulling credentials from the environment.
  This keeps common flows dependency‑free while still enabling auth‑only
  routes when explicitly requested.

The class is designed for server‑side use within any backend or script. All network
calls are delegated to provider client modules in `src/client/...`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Literal, Optional, List, Tuple
import re
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed

# Third-party imports
import requests
import logging

# Provider clients
from datavents.providers.kalshi.kalshi_rest_noauth import KalshiRestNoAuth
from datavents.providers.kalshi.kalshi_rest_auth import KalshiRestAuth
from datavents.providers.polymarket.polymarket_rest_noauth import (
    PolymarketRestNoAuth,
)
from datavents.providers.kalshi.rest_auth import KalshiAuth
from datavents.providers.polymarket.rest_auth import PolymarketAuth
from datavents.providers.config import Config as ProviderConfig
from datavents.providers.kalshi.kalshi_rest_noauth import (
    InternalKalshiRoutesSortBy,
)
from datavents.providers.polymarket.polymarket_rest_noauth import (
    InternalPolymarketRoutesSortBy,
)
from datavents.providers.kalshi.kalshi_rest_noauth import MarketStatus
from datavents.providers.polymarket.polymarket_rest_noauth import (
    PolymarketEventStatus,
)
from enum import Enum

logger = logging.getLogger(__name__)

class DataVentsProviders(Enum):
    KALSHI = "kalshi"
    POLYMARKET = "polymarket"
    ALL = "all"


class DataVentsOrderSortParams(Enum):
    NO_SORT = {
        "POLYMARKET": InternalPolymarketRoutesSortBy.NO_SORT,
        "KALSHI": InternalKalshiRoutesSortBy.NO_SORT,
    }
    ORDER_BY_CLOSING_SOON = {
        "POLYMARKET": InternalPolymarketRoutesSortBy.ORDER_BY_CLOSING_SOON,
        "KALSHI": InternalKalshiRoutesSortBy.ORDER_BY_CLOSING_SOON,
    }
    ORDER_BY_TRENDING = {
        "POLYMARKET": InternalPolymarketRoutesSortBy.ORDER_BY_TRENDING,
        "KALSHI": InternalKalshiRoutesSortBy.ORDER_BY_TRENDING,
    }
    ORDER_BY_LIQUIDITY = {
        "POLYMARKET": InternalPolymarketRoutesSortBy.ORDER_BY_LIQUIDITY,
        "KALSHI": InternalKalshiRoutesSortBy.ORDER_BY_LIQUIDITY,
    }
    ORDER_BY_VOLUME = {
        "POLYMARKET": InternalPolymarketRoutesSortBy.ORDER_BY_VOLUME,
        "KALSHI": InternalKalshiRoutesSortBy.ORDER_BY_VOLUME,
    }
    ORDER_BY_NEWEST = {
        "POLYMARKET": InternalPolymarketRoutesSortBy.ORDER_BY_NEWEST,
        "KALSHI": InternalKalshiRoutesSortBy.ORDER_BY_NEWEST,
    }
    ORDER_BY_VOLATILE = {
        "POLYMARKET": InternalPolymarketRoutesSortBy.ORDER_BY_VOLATILE,
        "KALSHI": InternalKalshiRoutesSortBy.ORDER_BY_VOLATILE,
    }
    ORDER_BY_EVEN_ODDS = {
        "POLYMARKET": InternalPolymarketRoutesSortBy.ORDER_BY_EVEN_ODDS,
        "KALSHI": InternalKalshiRoutesSortBy.ORDER_BY_EVEN_ODDS,
    }
    ORDER_BY_QUERYMATCH = {
        "POLYMARKET": InternalPolymarketRoutesSortBy.ORDER_BY_QUERYMATCH,
        "KALSHI": InternalKalshiRoutesSortBy.ORDER_BY_QUERYMATCH,
    }


class DataVentsStatusParams(Enum):
    OPEN_MARKETS = {
        "POLYMARKET": PolymarketEventStatus.OPEN_MARKETS,
        "KALSHI": MarketStatus.OPEN_MARKETS,
    }
    CLOSED_MARKETS = {
        "POLYMARKET": PolymarketEventStatus.CLOSED_MARKETS,
        "KALSHI": MarketStatus.CLOSED_MARKETS,
    }
    ALL_MARKETS = {
        "POLYMARKET": PolymarketEventStatus.ALL_MARKETS,
        "KALSHI": MarketStatus.ALL_MARKETS,
    }


 


class DataVentsNoAuthClient:
    """Unified, no‑auth client that proxies to provider no‑auth REST/WS clients.

    Focuses on the intersection of routes supported by both providers:
    - Markets: list/get
    - Events: list/get
    - Series: list/get
    - Streaming: market/ticker updates

    Notes
    - Parameters are provider‑specific pass‑through. This keeps MVP scope light
      and mirrors the underlying clients exactly.
    - For polymarket `get_market`/`get_event` you must specify `id` or `slug`.
    - For kalshi `get_market`/`get_event` you must specify `ticker`/`event_ticker`.
    - Lazy auth: certain helpers (e.g., ``get_kalshi_market_orderbook`` and the
      unified ``get_market_orderbook`` facade for Kalshi) create an authenticated
      client on first call if the required env vars are present
      (``KALSHI_API_KEY[_PAPER]``, ``KALSHI_PRIVATE_KEY[_PAPER]``).
    """

    def __init__(self) -> None:
        # REST clients
        self._kalshi_rest = KalshiRestNoAuth()
        self._poly_rest = PolymarketRestNoAuth()
        # Lazy auth REST clients (initialized on first use)
        self._kalshi_rest_auth_live: Optional[KalshiRestAuth] = None
        self._kalshi_rest_auth_paper: Optional[KalshiRestAuth] = None

        # WS auth tokens/objects (no‑auth configs)
        self._kalshi_auth = KalshiAuth(config=ProviderConfig.NOAUTH)
        self._poly_auth = PolymarketAuth(config=ProviderConfig.NOAUTH)

        # Public Elections API base (no auth) for search endpoints
        self._kalshi_elections_base = "https://api.elections.kalshi.com/v1"

    @staticmethod
    def common_routes() -> Dict[str, str]:
        """Return a map of route names available in both providers (no‑auth).

        Keys are method names on this client. Values briefly describe usage.
        """
        return {
            "search_events": "List events with provider-specific filters",
        }

    def search_events(
        self,
        provider: DataVentsProviders,
        query: str,
        limit: int,
        page: int,
        order_sort_params: DataVentsOrderSortParams,
        status_params: DataVentsStatusParams,
        **params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Search events using provider discovery endpoints (parallel for ALL).

        Parameters
        - provider: choose `KALSHI`, `POLYMARKET`, or `ALL` to fan out in parallel.
        - query: free‑text search string (coerced to a space for Polymarket if empty).
        - limit: per‑provider page size (Kalshi `page_size`, Polymarket `limit_per_type`).
        - page: results page (Polymarket starts at 1; Kalshi uses cursors internally).
        - order_sort_params: high‑level sort mapped to provider‑specific values.
        - status_params: high‑level status filter mapped to provider‑specific values.
        - params: optional `kalshi_params` and/or `polymarket_params` dicts forwarded to providers.

        Returns
        - list of dict: `[{"provider": "kalshi|polymarket", "data": <raw provider payload>}, ...]`

        Notes
        - Kalshi series search does not accept `status`; when `scope="series"` and a non‑ALL
          status is requested, this method uses Kalshi events search instead.
        - Use `normalize_search_response(...)` to convert raw payloads into unified models.
        """

        polymarket_params = params.get("polymarket_params", {})
        kalshi_params = params.get("kalshi_params", {})
        # add a param for milestones
        kalshi_params["with_milestones"] = params.get("with_milestones", True)

        assert (
            order_sort_params in DataVentsOrderSortParams
        ), f"Invalid order sort params: {order_sort_params}"
        assert (
            status_params in DataVentsStatusParams
        ), f"Invalid status params: {status_params}"
        # process both calls in parallel
        # shared params r ones we can match
        # if polymarket has no params use querymatch for kalshio and none for other
        search_params_kalshi = order_sort_params.value["KALSHI"]
        search_params_polymarket = order_sort_params.value["POLYMARKET"]
        status_params_kalshi = status_params.value["KALSHI"]
        status_params_polymarket = status_params.value["POLYMARKET"]

        def call_kalshi():
            """Call Kalshi API.

            If `scope=series` is requested but a status filter other than ALL is
            applied, fall back to events search because the series endpoint does
            not support `status` and cannot reliably filter by open/closed.
            """
            scope_req = str(kalshi_params.get("scope", "series")).lower() if isinstance(kalshi_params, dict) else "series"
            force_events = status_params_kalshi != MarketStatus.ALL_MARKETS and scope_req == "series"
            scope_eff = "events" if force_events else scope_req

            if scope_eff == "series":
                data = self._kalshi_rest.search_series(
                    query=query,
                    order_by=search_params_kalshi,
                    page_size=limit,
                    excluded_categories=kalshi_params.get("excluded_categories", []) if isinstance(kalshi_params, dict) else [],
                )
            else:
                data = self._kalshi_rest.search_events(
                    query=query,
                    status=status_params_kalshi,
                    order_by=search_params_kalshi,
                    page_size=limit,
                    excluded_categories=kalshi_params.get("excluded_categories", []) if isinstance(kalshi_params, dict) else [],
                    **({k: v for k, v in kalshi_params.items() if k not in ("scope", "excluded_categories")} if isinstance(kalshi_params, dict) else {}),
                )
            return {"provider": "kalshi", "data": data}

        def call_polymarket():
            """Call Polymarket API"""
            qval = query if str(query or "").strip() else " "  # avoid empty q → 422
            return {
                "provider": "polymarket",
                "data": self._poly_rest.search_events(
                    q=qval,
                    optimized=True,
                    limit_per_type=limit,
                    type="events",
                    search_tags=False,
                    search_profiles=False,
                    cache=True,
                    presets=["EventsTitle", "Events"],
                    page=page if page > 0 else 1,  # Polymarket pages start at 1
                    events_status=status_params_polymarket,
                    sort=search_params_polymarket,
                    ascending=False,
                    **polymarket_params,
                )
            }

        if provider == DataVentsProviders.KALSHI:
            result = call_kalshi()
            return [result]
        elif provider == DataVentsProviders.POLYMARKET:
            result = call_polymarket()
            return [result]
        elif provider == DataVentsProviders.ALL:
            # Run both providers in parallel
            results = []
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = {
                    executor.submit(call_kalshi): "kalshi",
                    executor.submit(call_polymarket): "polymarket"
                }
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        # Log the error but continue with other providers
                        import logging
                        logging.getLogger(__name__).warning(
                            "Error calling %s: %s", futures[future], e
                        )

            return results
        else:
            raise ValueError(f"Invalid provider: {provider}")

    def list_events(
        self,
        provider: DataVentsProviders,
        limit: int = 50,
        page: int = 0,
        status_params: DataVentsStatusParams = DataVentsStatusParams.ALL_MARKETS,
        series_ticker: str = "",
        with_nested_markets: bool = False,
        with_milestones: bool = False,
        query: str = "",
        order_sort_params: DataVentsOrderSortParams = DataVentsOrderSortParams.ORDER_BY_TRENDING,
    ) -> List[Dict[str, Any]]:
        """List events from one or both providers using search endpoints.

        Returns
        - list of dict blocks with `provider` and raw `data` fields.

        Tip
        - Feed the `data` field to `normalize_search_response(...)` when a unified schema is desired.
        """

        assert status_params in DataVentsStatusParams, f"Invalid status params: {status_params}"
        assert order_sort_params in DataVentsOrderSortParams, f"Invalid order sort params: {order_sort_params}"

        status_k = status_params.value["KALSHI"]
        status_p = status_params.value["POLYMARKET"]

        def call_kalshi_list():
            return {
                "provider": "kalshi",
                "data": self._kalshi_rest.search_events(
                    query=query,
                    status=status_k,
                    order_by=order_sort_params.value["KALSHI"],
                    page_size=max(1, min(200, int(limit))),
                ),
            }

        def call_poly_list():
            return {
                "provider": "polymarket",
                "data": self._poly_rest.search_events(
                    q=(query if str(query or "").strip() else " "),
                    optimized=True,
                    limit_per_type=max(1, int(limit)),
                    type="events",
                    search_tags=False,
                    search_profiles=False,
                    cache=True,
                    presets=["EventsTitle", "Events"],
                    page=page if page > 0 else 1,
                    events_status=status_p,
                    sort=order_sort_params.value["POLYMARKET"],
                    ascending=False,
                ),
            }

        if provider == DataVentsProviders.KALSHI:
            return [call_kalshi_list()]
        elif provider == DataVentsProviders.POLYMARKET:
            return [call_poly_list()]
        elif provider == DataVentsProviders.ALL:
            results: List[Dict[str, Any]] = []
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = {
                    executor.submit(call_kalshi_list): "kalshi",
                    executor.submit(call_poly_list): "polymarket",
                }
                for future in as_completed(futures):
                    try:
                        results.append(future.result())
                    except Exception as e:
                        import logging
                        logging.getLogger(__name__).warning(
                            "Error listing events for %s: %s", futures[future], e
                        )
            return results
        else:
            raise ValueError(f"Invalid provider: {provider}")

    def get_event(
        self,
        provider: DataVentsProviders,
        kalshi_event_ticker: Optional[str] = None,
        polymarket_id: Optional[int] = None,
        polymarket_slug: Optional[str] = None,
        *,
        with_nested_markets: bool = False,
        include_chat: bool = False,
        include_template: bool = False,
    ) -> List[Dict[str, Any]]:
        """Get an event by provider‑specific identifier(s).

        Identifiers
        - Kalshi: `kalshi_event_ticker`
        - Polymarket: numeric `polymarket_id` or string `polymarket_slug`

        Returns
        - list with one block for the called provider(s): `[{"provider": ..., "data": <raw>}]`
        """

        def call_kalshi_get():
            if not kalshi_event_ticker:
                raise ValueError("kalshi_event_ticker is required for provider=KALSHI")
            return {
                "provider": "kalshi",
                "data": self._kalshi_rest.get_event(
                    event_ticker=kalshi_event_ticker,
                    with_nested_markets=with_nested_markets,
                ),
            }

        def call_poly_get():
            if polymarket_id is None and not polymarket_slug:
                raise ValueError("polymarket_id or polymarket_slug is required for provider=POLYMARKET")
            if polymarket_id is not None:
                data = self._poly_rest.get_events_by_id(
                    id=int(polymarket_id),
                    include_chat=include_chat,
                    include_template=include_template,
                )
            else:
                data = self._poly_rest.get_event_by_slug(
                    slug=str(polymarket_slug),
                    include_chat=include_chat,
                    include_template=include_template,
                )
            return {"provider": "polymarket", "data": data}

        if provider == DataVentsProviders.KALSHI:
            return [call_kalshi_get()]
        elif provider == DataVentsProviders.POLYMARKET:
            return [call_poly_get()]
        elif provider == DataVentsProviders.ALL:
            results: List[Dict[str, Any]] = []
            # Try each provider only if its identifier is provided
            if kalshi_event_ticker:
                try:
                    results.append(call_kalshi_get())
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning("Error getting Kalshi event: %s", e)
            if polymarket_id is not None or polymarket_slug:
                try:
                    results.append(call_poly_get())
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning("Error getting Polymarket event: %s", e)
            if not results:
                raise ValueError("Provide at least one identifier for Kalshi or Polymarket")
            return results
        else:
            raise ValueError(f"Invalid provider: {provider}")

    def get_event_metadata(
        self,
        event_ticker: str,
    ) -> Dict[str, Any]:
        """Fetch Kalshi event metadata (no unified equivalent on Polymarket)."""
        return self._kalshi_rest.get_event_metadata(event_ticker=event_ticker)

    def get_event_tags(self, event_id: int) -> Dict[str, Any]:
        """Fetch Polymarket event tags (no unified equivalent on Kalshi)."""
        return self._poly_rest.get_event_tags(id=int(event_id))

    # -------------------------------
    # Markets (unified, no‑auth)
    # -------------------------------

    def list_markets(
        self,
        provider: DataVentsProviders,
        limit: int = 50,
        page: int = 0,
        status_params: DataVentsStatusParams = DataVentsStatusParams.OPEN_MARKETS,
        query: str = "",
        order_sort_params: DataVentsOrderSortParams = DataVentsOrderSortParams.ORDER_BY_TRENDING,
        event_ticker: str = "",
        series_ticker: str = "",
    ) -> List[Dict[str, Any]]:
        """List markets across providers.

        Behavior
        - Kalshi: currently leverages events search (markets are nested under events).
        - Polymarket: uses public‑search with `type="markets"`, normalized to a top‑level `markets` list.
        """

        assert status_params in DataVentsStatusParams
        assert order_sort_params in DataVentsOrderSortParams

        status_k = status_params.value["KALSHI"]
        status_p = status_params.value["POLYMARKET"]

        def call_kalshi_list():
            # Kalshi /markets requires filters; instead, use search/events and let callers
            # derive markets from nested items if needed.
            qval = query if str(query or "").strip() else " "
            return {
                "provider": "kalshi",
                "data": self._kalshi_rest.search_events(
                    query=qval,
                    order_by=order_sort_params.value["KALSHI"],
                    status=status_k,
                    page_size=max(1, min(200, int(limit))),
                ),
            }

        def call_poly_list():
            # Use public-search type=markets (works like events search)
            qval = query if str(query or "").strip() else " "
            # Normalize response to always expose a top-level "markets" list.
            # Polymarket public-search may return markets nested under each event.
            resp = self._poly_rest.search_events(
                q=qval,
                optimized=True,
                limit_per_type=max(1, int(limit)),
                type="markets",
                search_tags=False,
                search_profiles=False,
                cache=True,
                presets=[],
                page=page if page > 0 else 1,
                events_status=status_p,
                sort=order_sort_params.value["POLYMARKET"],
                ascending=False,
            )

            # If the API already provides a markets list, keep it.
            if isinstance(resp, dict) and ("markets" in resp or "Markets" in resp):
                data = resp
            else:
                # Flatten nested markets from events → markets[] with minimal fields.
                markets: List[Dict[str, Any]] = []
                if isinstance(resp, dict):
                    events = resp.get("events") or resp.get("Events") or []
                    if isinstance(events, list):
                        for ev in events:
                            if not isinstance(ev, dict):
                                continue
                            for m in ev.get("markets") or []:
                                if isinstance(m, dict):
                                    # Preserve common fields used by tests/discovery
                                    slim = {
                                        k: v
                                        for k, v in m.items()
                                        if k in ("id", "marketId", "market_id", "slug", "marketSlug", "question")
                                    }
                                    # If event provided an id/slug, attach for context
                                    if "event_id" not in slim and isinstance(ev.get("id"), (str, int)):
                                        slim["event_id"] = ev["id"]
                                    if "event_slug" not in slim and isinstance(ev.get("slug"), str):
                                        slim["event_slug"] = ev["slug"]
                                    markets.append(slim or m)
                data = {**(resp or {}), "markets": markets}

            return {
                "provider": "polymarket",
                "data": data,
            }

        if provider == DataVentsProviders.KALSHI:
            return [call_kalshi_list()]
        elif provider == DataVentsProviders.POLYMARKET:
            return [call_poly_list()]
        elif provider == DataVentsProviders.ALL:
            results: List[Dict[str, Any]] = []
            with ThreadPoolExecutor(max_workers=2) as ex:
                futs = {ex.submit(call_kalshi_list): "kalshi", ex.submit(call_poly_list): "polymarket"}
                for fut in as_completed(futs):
                    try:
                        results.append(fut.result())
                    except Exception as e:
                        import logging
                        logging.getLogger(__name__).warning(
                            "Error listing markets for %s: %s", futs[fut], e
                        )
            return results
        else:
            raise ValueError(f"Invalid provider: {provider}")

    def get_market(
        self,
        provider: DataVentsProviders,
        kalshi_ticker: Optional[str] = None,
        polymarket_id: Optional[int] = None,
        polymarket_slug: Optional[str] = None,
        *,
        include_tag: bool = False,
    ) -> List[Dict[str, Any]]:
        """Get a market by provider-specific identifier.

        Identifiers
        - Kalshi: `kalshi_ticker`
        - Polymarket: numeric `polymarket_id` or string `polymarket_slug`
        """

        def call_kalshi_get():
            if not kalshi_ticker:
                raise ValueError("kalshi_ticker is required for provider=KALSHI")
            return {"provider": "kalshi", "data": self._kalshi_rest.get_market(kalshi_ticker)}

        def call_poly_get():
            if polymarket_id is None and not polymarket_slug:
                raise ValueError("polymarket_id or polymarket_slug is required for provider=POLYMARKET")
            if polymarket_id is not None:
                data = self._poly_rest.get_market_by_id(id=int(polymarket_id), include_tag=include_tag)
            else:
                data = self._poly_rest.get_market_by_slug(slug=str(polymarket_slug), include_tag=include_tag)
            return {"provider": "polymarket", "data": data}

        if provider == DataVentsProviders.KALSHI:
            return [call_kalshi_get()]
        elif provider == DataVentsProviders.POLYMARKET:
            return [call_poly_get()]
        elif provider == DataVentsProviders.ALL:
            results: List[Dict[str, Any]] = []
            if kalshi_ticker:
                try:
                    results.append(call_kalshi_get())
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning("Error getting Kalshi market: %s", e)
            if polymarket_id is not None or polymarket_slug:
                try:
                    results.append(call_poly_get())
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning("Error getting Polymarket market: %s", e)
            if not results:
                raise ValueError("Provide kalshi_ticker and/or polymarket_id|polymarket_slug")
            return results
        else:
            raise ValueError(f"Invalid provider: {provider}")

    def get_market_tags(self, market_id: int) -> Any:
        """Fetch Polymarket market tags by numeric ID (helper)."""
        return self._poly_rest.get_market_tags_by_id(id=int(market_id))

    # ==== Auth-required helpers ============================================
    def get_kalshi_market_orderbook(
        self,
        ticker: str,
        *,
        depth: Optional[int] = None,
        env: ProviderConfig = ProviderConfig.LIVE,
    ) -> Dict[str, Any]:
        """Fetch Kalshi market orderbook using signed REST.

        Args
        - ticker: market ticker (e.g., "ABC-24-XYZ-T50")
        - depth: optional 0..100 (0=all levels)
        - env: ProviderConfig.LIVE or ProviderConfig.PAPER
        """
        if env == ProviderConfig.PAPER:
            if self._kalshi_rest_auth_paper is None:
                self._kalshi_rest_auth_paper = KalshiRestAuth(config=ProviderConfig.PAPER)
            client = self._kalshi_rest_auth_paper
        else:
            if self._kalshi_rest_auth_live is None:
                self._kalshi_rest_auth_live = KalshiRestAuth(config=ProviderConfig.LIVE)
            client = self._kalshi_rest_auth_live
        try:
            logger.debug("dv.client.get_kalshi_market_orderbook env=%s ticker=%s depth=%s", env.value, ticker, depth)
        except Exception:
            pass
        return client.get_market_orderbook(ticker, depth)

    def get_market_orderbook(
        self,
        provider: DataVentsProviders,
        *,
        kalshi_ticker: Optional[str] = None,
        depth: Optional[int] = None,
        kalshi_env: ProviderConfig = ProviderConfig.LIVE,
    ) -> List[Dict[str, Any]]:
        """Unified orderbook facade.

        Supported providers:
        - KALSHI (signed REST)

        Returns a list with provider-tagged payloads, matching other DV client methods.
        """
        if provider == DataVentsProviders.KALSHI:
            if not kalshi_ticker:
                raise ValueError("kalshi_ticker is required for provider=KALSHI")
            data = self.get_kalshi_market_orderbook(kalshi_ticker, depth=depth, env=kalshi_env)
            return [{"provider": "kalshi", "data": data}]
        elif provider == DataVentsProviders.POLYMARKET:
            raise NotImplementedError("Polymarket does not expose REST orderbook")
        elif provider == DataVentsProviders.ALL:
            if not kalshi_ticker:
                return []
            data = self.get_kalshi_market_orderbook(kalshi_ticker, depth=depth, env=kalshi_env)
            return [{"provider": "kalshi", "data": data}]
        else:
            raise ValueError(f"Invalid provider: {provider}")
