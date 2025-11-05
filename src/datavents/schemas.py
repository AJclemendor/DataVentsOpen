from __future__ import annotations

"""
Unified request/response schemas for Kalshi + Polymarket.

Goals
- Provide normalized models for REST-style endpoints your application may expose:
  - health, search, event, market, market/history
- Provide normalized models for WS envelopes (ticker/orderbook/trade) used by the
  DV WS client.
- Preserve provider-specific information so we never lose data. Every normalized
  entity includes a `vendor_raw: dict[str, Any]` snapshot of the original item
  and optional `vendor_fields: dict[str, Any]` for structured, useful extras.

All prices and probabilities are normalized to floats in [0,1]. Timestamps are
epoch milliseconds (int) unless otherwise stated.
"""

from typing import Any, Dict, List, Literal, Optional, Sequence, Union
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


# ----------------------------- Common Enums -----------------------------


class Provider(str, Enum):
    kalshi = "kalshi"
    polymarket = "polymarket"


class Entity(str, Enum):
    series = "series"
    event = "event"
    market = "market"


class StatusNormalized(str, Enum):
    """Cross-provider status summary.

    Keep `unknown` to avoid lossy mapping when upstream adds new states.
    """

    open = "open"  # Kalshi opened/unopened → open; Poly active → open
    closed = "closed"
    settled = "settled"
    upcoming = "upcoming"  # drafts/scheduled, if applicable
    unknown = "unknown"


class SearchScopeKalshi(str, Enum):
    series = "series"
    events = "events"


class OrderSort(str, Enum):
    no_sort = "NO_SORT"
    closing_soon = "ORDER_BY_CLOSING_SOON"
    trending = "ORDER_BY_TRENDING"
    liquidity = "ORDER_BY_LIQUIDITY"
    volume = "ORDER_BY_VOLUME"
    newest = "ORDER_BY_NEWEST"
    volatile = "ORDER_BY_VOLATILE"
    even_odds = "ORDER_BY_EVEN_ODDS"
    querymatch = "ORDER_BY_QUERYMATCH"


class StatusFilter(str, Enum):
    open = "OPEN_MARKETS"
    closed = "CLOSED_MARKETS"
    all = "ALL_MARKETS"


class WsEventType(str, Enum):
    ticker = "ticker"
    orderbook = "orderbook"
    trade = "trade"
    raw = "raw"


# --------------------------- Request Models -----------------------------


class SearchQuery(BaseModel):
    provider: Literal["kalshi", "polymarket", "all"] = Field(
        default="all", description="Which provider(s) to search"
    )
    q: str = Field(default="", description="Free-text query")
    limit: int = Field(default=10, ge=1, le=50)
    page: int = Field(default=1, ge=1)
    order: OrderSort = Field(default=OrderSort.trending)
    status: StatusFilter = Field(default=StatusFilter.open)
    exclude_sports: bool = Field(default=False)
    kalshi_scope: SearchScopeKalshi = Field(default=SearchScopeKalshi.series)
    normalized: bool = Field(
        default=True,
        description="Return normalized results when true; raw provider shape otherwise.",
    )


class EventQuery(BaseModel):
    provider: Provider
    # Kalshi
    event_ticker: Optional[str] = Field(default=None, description="Kalshi event ticker")
    with_nested_markets: bool = Field(default=True)
    # Polymarket
    id: Optional[int] = Field(default=None, description="Polymarket numeric event id")
    slug: Optional[str] = Field(default=None, description="Polymarket event slug")
    include_chat: bool = Field(default=False)
    include_template: bool = Field(default=False)
    normalized: bool = Field(default=True)


class MarketQuery(BaseModel):
    provider: Provider
    # Kalshi
    ticker: Optional[str] = Field(default=None, description="Kalshi market ticker")
    # Polymarket
    id: Optional[int] = Field(default=None, description="Polymarket market id")
    slug: Optional[str] = Field(default=None, description="Polymarket market slug")
    normalized: bool = Field(default=True)


class MarketHistoryQuery(BaseModel):
    provider: Provider
    # Common time window; epoch seconds or ms accepted by route, normalized to seconds here.
    start: Optional[int] = None
    end: Optional[int] = None
    interval: int = Field(default=300, ge=10, le=24 * 3600)
    # Kalshi identifiers
    ticker: Optional[str] = None
    series_ticker: Optional[str] = None
    market_id: Optional[str] = None
    # Polymarket identifiers
    id: Optional[int] = None
    slug: Optional[str] = None
    normalized: bool = Field(default=True)


# --------------------------- Normalized Models --------------------------


class PriceLevel(BaseModel):
    price: float = Field(description="Price/probability in [0,1]")
    size: Optional[float] = Field(default=None, description="Quantity/size at price level")


class Outcome(BaseModel):
    outcome_id: Optional[str] = None
    name: Optional[str] = Field(default=None, description="Outcome label, e.g., Yes/No")
    side: Optional[Literal["yes", "no"]] = None
    price: Optional[float] = Field(default=None, description="Current outcome price [0,1]")
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    last_price: Optional[float] = None
    vendor_fields: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured provider-specific extras for this outcome",
    )


class Fees(BaseModel):
    maker_bps: Optional[float] = None
    taker_bps: Optional[float] = None
    settlement_bps: Optional[float] = None
    vendor_fields: Dict[str, Any] = Field(default_factory=dict)


class Market(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    provider: Provider
    entity: Literal["market"] = "market"
    market_id: str = Field(description="Provider-stable identifier (stringified)")
    slug: Optional[str] = None
    ticker: Optional[str] = None
    question: Optional[str] = None
    status: StatusNormalized = StatusNormalized.unknown
    status_raw: Optional[str] = None
    event_id: Optional[str] = None
    series_id: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    url: Optional[str] = None
    start_ts: Optional[int] = Field(default=None, description="Epoch ms")
    end_ts: Optional[int] = Field(default=None, description="Epoch ms (close/end)")

    # Market-level price summary (binary convenience)
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    last_price: Optional[float] = None
    mid_price: Optional[float] = None

    # Liquidity & volume (USD)
    liquidity_usd: Optional[float] = None
    volume_24h_usd: Optional[float] = None
    open_interest_usd: Optional[float] = None

    # Outcomes (binary or multi-outcome)
    outcomes: List[Outcome] = Field(default_factory=list)

    # Fees and extras
    fees: Optional[Fees] = None

    # Provider-specific preservation
    vendor_market_id: Optional[str] = Field(
        default=None, description="Provider-native id if different from market_id"
    )
    vendor_fields: Dict[str, Any] = Field(default_factory=dict)
    vendor_raw: Dict[str, Any] = Field(default_factory=dict)


class Event(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    provider: Provider
    entity: Literal["event"] = "event"
    event_id: str = Field(description="Provider-stable identifier (stringified)")
    slug: Optional[str] = None
    event_ticker: Optional[str] = None  # Kalshi
    title: Optional[str] = None
    status: StatusNormalized = StatusNormalized.unknown
    status_raw: Optional[str] = None
    series_id: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    url: Optional[str] = None
    created_ts: Optional[int] = None
    start_ts: Optional[int] = None
    end_ts: Optional[int] = None
    markets_count: Optional[int] = None
    markets: Optional[List[Market]] = Field(
        default=None, description="Optional embedded markets when requested"
    )

    vendor_fields: Dict[str, Any] = Field(default_factory=dict)
    vendor_raw: Dict[str, Any] = Field(default_factory=dict)


class Series(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    provider: Provider
    entity: Literal["series"] = "series"
    series_id: str = Field(description="Provider-stable identifier (stringified)")
    slug: Optional[str] = None
    series_ticker: Optional[str] = None  # Kalshi
    name: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    url: Optional[str] = None
    events_count: Optional[int] = None
    events: Optional[List[Event]] = None

    vendor_fields: Dict[str, Any] = Field(default_factory=dict)
    vendor_raw: Dict[str, Any] = Field(default_factory=dict)


# --------------------------- Search Responses ---------------------------


class SearchMeta(BaseModel):
    provider: Literal["kalshi", "polymarket", "all"]
    order: OrderSort
    status: StatusFilter
    page: int
    limit: int
    exclude_sports: bool
    excluded_categories: List[str] = Field(default_factory=list)
    kalshi_scope: Optional[SearchScopeKalshi] = None
    version: str = Field(default="v1", description="Normalized schema version")


SearchItem = Union[Series, Event, Market]


class SearchResponseNormalized(BaseModel):
    results: List[SearchItem]
    meta: SearchMeta


class ProviderRawItem(BaseModel):
    provider: Provider
    data: Dict[str, Any]


class SearchResponseRaw(BaseModel):
    results: List[ProviderRawItem]
    meta: SearchMeta


# --------------------------- Get Responses -----------------------------


class EventResponseNormalized(BaseModel):
    provider: Provider
    data: Event
    version: str = "v1"


class MarketResponseNormalized(BaseModel):
    provider: Provider
    data: Market
    version: str = "v1"


class SingleRawResponse(BaseModel):
    provider: Provider
    data: Dict[str, Any]


# --------------------------- History Responses --------------------------


class PricePoint(BaseModel):
    t: int = Field(description="Epoch ms")
    p: float = Field(description="Price/probability in [0,1]")
    vendor_fields: Dict[str, Any] = Field(default_factory=dict)


class MarketHistoryResponseNormalized(BaseModel):
    provider: Provider
    # Kalshi: ticker, series_ticker, market_id; Polymarket: id/slug + clob id
    ticker: Optional[str] = None
    series_ticker: Optional[str] = None
    market_id: Optional[str] = None
    id: Optional[int] = None
    slug: Optional[str] = None
    clob_token_id: Optional[str] = None

    start: int
    end: int
    interval: int
    poly_interval: Optional[str] = None  # when provider=polymarket

    points: List[PricePoint]
    version: str = "v1"


# --------------------------- WS Models ----------------------------------


class WsTicker(BaseModel):
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    last_price: Optional[float] = None
    mid_price: Optional[float] = None
    volume_24h_usd: Optional[float] = None
    vendor_fields: Dict[str, Any] = Field(default_factory=dict)


class WsOrderbook(BaseModel):
    bids: List[PriceLevel] = Field(default_factory=list)
    asks: List[PriceLevel] = Field(default_factory=list)
    vendor_fields: Dict[str, Any] = Field(default_factory=dict)


class WsTrade(BaseModel):
    side: Optional[Literal["buy", "sell"]] = None
    price: float
    size: Optional[float] = None
    ts: Optional[int] = None  # epoch ms
    vendor_fields: Dict[str, Any] = Field(default_factory=dict)


WsData = Union[WsTicker, WsOrderbook, WsTrade, Dict[str, Any]]


class WsEnvelope(BaseModel):
    provider: Provider
    event_type: WsEventType
    market_id: Optional[str] = None  # ticker (Kalshi) or clob/asset id (Poly)
    ts: int = Field(description="Received timestamp (epoch ms)")
    data: WsData
    vendor_raw: Dict[str, Any] = Field(default_factory=dict)


# --------------------------- Utility Types ------------------------------


class HealthResponse(BaseModel):
    ok: bool
    ts: int


class SearchOptionsItem(BaseModel):
    name: str
    value: Optional[str] = None
    label: str


class SearchOptionsResponse(BaseModel):
    providers: List[SearchOptionsItem]
    order: List[SearchOptionsItem]
    status: List[SearchOptionsItem]
