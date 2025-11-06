# DataVents Open SDK

Unified Python SDK for Kalshi and Polymarket.

What’s inside
- Unified, no‑auth REST façade over Kalshi and Polymarket public endpoints.
- Normalization helpers and Pydantic models for events, markets, search, and history.
- A multiplexed WebSocket client that streams from Kalshi and Polymarket concurrently.

Supported Python: 3.9+

## Installation

From PyPI (preferred):

```bash
pip install datavents
```

From a local wheel (e.g., CI artifact):

```bash
pip install /path/to/datavents-0.1.0-py3-none-any.whl
```

Editable install for contributors:

```bash
pip install -e .[dev]
```

---

## Quickstart

List events (both providers) and print a few titles:

```python
from datavents import DataVentsNoAuthClient, DataVentsProviders, DataVentsOrderSortParams, DataVentsStatusParams

client = DataVentsNoAuthClient()
events = client.list_events(
    provider=DataVentsProviders.ALL,
    limit=5,
    page=0,
    status_params=DataVentsStatusParams.OPEN_MARKETS,
    order_sort_params=DataVentsOrderSortParams.ORDER_BY_TRENDING,
)
for payload in events:
    print(payload["provider"], "→ keys:", list(payload["data"].keys()))
```

Normalize provider search into one schema:

```python
from datavents import normalize_search_response, Provider, OrderSort, StatusFilter

raw = events[0]["data"]  # e.g., Kalshi payload
normalized = normalize_search_response(
    Provider.kalshi,
    raw,
    q="election",
    page=1,
    limit=5,
    order=OrderSort.trending,
    status=StatusFilter.open,
)
print("Normalized results:", len(normalized.results))
```

Explore more complete runnable samples under `examples/`.

---

## Unified Client

The `DataVentsNoAuthClient` exposes a small set of high‑leverage methods. All network calls hit live provider public APIs (no credentials needed for REST). Each method returns a list of provider‑tagged dictionaries like:

```python
[{"provider": "kalshi", "data": {...}}, {"provider": "polymarket", "data": {...}}]
```

### search_events
```python
search_events(
    provider: DataVentsProviders,
    query: str,
    limit: int,
    page: int,
    order_sort_params: DataVentsOrderSortParams,
    status_params: DataVentsStatusParams,
    **params
) -> list[dict]
```
- Provider‑specific mapped sorts and statuses (see Enums below).
- When `provider=ALL`, Kalshi and Polymarket are called in parallel.
- Returns raw provider search payloads (use normalization helpers to unify shape).

Common extra params
- `kalshi_params: dict` – forwarded to Kalshi search. If `scope="series"` with a status other than ALL, client falls back to Kalshi events search (series endpoint doesn’t support status).
- `polymarket_params: dict` – forwarded to Polymarket public‑search call.

### list_events
```python
list_events(
    provider: DataVentsProviders,
    limit: int = 50,
    page: int = 0,
    status_params: DataVentsStatusParams = DataVentsStatusParams.ALL_MARKETS,
    query: str = "",
    order_sort_params: DataVentsOrderSortParams = DataVentsOrderSortParams.ORDER_BY_TRENDING,
) -> list[dict]
```
- Thin wrapper around provider search tuned for event discovery.
- Use with `normalize_search_response` for unified typing.

### list_markets
```python
list_markets(
    provider: DataVentsProviders,
    limit: int = 50,
    page: int = 0,
    status_params: DataVentsStatusParams = DataVentsStatusParams.OPEN_MARKETS,
    query: str = "",
    order_sort_params: DataVentsOrderSortParams = DataVentsOrderSortParams.ORDER_BY_TRENDING,
) -> list[dict]
```
- Kalshi path currently uses events search (markets are nested under events).
- Polymarket path uses public‑search with `type="markets"` and exposes a top‑level `markets` list (flattened if needed).

### get_event / get_market
```python
get_event(provider, kalshi_event_ticker=None, polymarket_id=None, polymarket_slug=None, *, with_nested_markets=False, include_chat=False, include_template=False) -> list[dict]
get_market(provider, kalshi_ticker=None, polymarket_id=None, polymarket_slug=None, *, include_tag=False) -> list[dict]
```
- Supply the proper identifier for each provider (Kalshi uses tickers; Polymarket supports id or slug).
- With `provider=ALL`, only providers with identifiers provided are called.

### Orderbook (Kalshi, lazy auth)
While the client is "no‑auth" by default, it can lazily spin up a signed Kalshi REST client for auth‑only routes:

```python
from datavents import DataVentsNoAuthClient, DataVentsProviders
from datavents.providers.config import Config as ProviderConfig

dv = DataVentsNoAuthClient()

# Direct helper (returns raw provider JSON)
ob = dv.get_kalshi_market_orderbook("ABC-24-XYZ-T50", depth=50, env=ProviderConfig.LIVE)

# Unified facade (list with provider tag)
res = dv.get_market_orderbook(DataVentsProviders.KALSHI, kalshi_ticker="ABC-24-XYZ-T50", depth=50)
```

Set environment variables for Kalshi auth:
- LIVE: `KALSHI_API_KEY`, `KALSHI_PRIVATE_KEY` (PEM path)
- PAPER: `KALSHI_API_KEY_PAPER`, `KALSHI_PRIVATE_KEY_PAPER`

### Provider‑specific helpers
- `get_event_metadata(event_ticker: str)` – Kalshi event metadata.
- `get_event_tags(event_id: int)`, `get_market_tags(market_id: int)` – Polymarket tags.

---

## Normalization Layer

Convert raw provider payloads into consistent Pydantic models located in `datavents.schemas`.

Key entry points
- `normalize_search_response(provider, raw, q, order, status, page, limit)` → `SearchResponseNormalized`
- `normalize_event(provider, raw)` → `Event`
- `normalize_market(provider, raw)` → `Market`
- `normalize_market_history(provider, identifiers=..., start, end, interval, raw|points)` → `MarketHistoryResponseNormalized`

Highlights
- Prices normalized to probability in [0,1] (accepts common provider units such as 0..1, percent, or bps‑like).
- Timestamps normalized to epoch milliseconds.
- `status` mapped to `StatusNormalized` (open/closed/settled/upcoming/unknown) while retaining `status_raw`.
- Provider snapshots preserved under `vendor_raw` with optional structured `vendor_fields`.

Example (market → binary outcomes):

```python
from datavents import normalize_market, Provider

raw_market = {"id": 123, "slug": "will-something-happen", "bestBid": 0.47, "bestAsk": 0.49}
m = normalize_market(Provider.polymarket, raw_market)
print(m.mid_price, [o.name for o in m.outcomes])
```

---

## WebSockets

Use `DvWsClient` to multiplex Kalshi and Polymarket streams with a single async loop.

```python
import asyncio
from datavents import DvWsClient, DvSubscription, DvVendors

async def main():
    dv = DvWsClient()

    async def on_event(evt):  # evt is datavents.ws.NormalizedEvent
        print(evt.vendor, evt.event, evt.market)

    sub = DvSubscription(
        vendors=(DvVendors.POLYMARKET,),
        polymarket_assets_ids=["asset-id-1", "asset-id-2"],
    )

    await dv.run(sub, on_event)

asyncio.run(main())
```

Kalshi WS requires valid API credentials in your environment. Polymarket market WS is public and needs only asset ids.

Environment variables (Kalshi; see provider docs)
- `KALSHI_API_KEY` (live) or `KALSHI_API_KEY_PAPER` (paper)
- `KALSHI_PRIVATE_KEY` (live) or `KALSHI_PRIVATE_KEY_PAPER` (paper) – path to PEM file used for RSA‑PSS signing

---

## Enums and Mappings

Order sorts (`DataVentsOrderSortParams`) map to provider‑specific semantics, e.g.:
- `ORDER_BY_TRENDING` → Kalshi `trending`, Polymarket `volume_24hr` (proxy).
- `ORDER_BY_CLOSING_SOON` → Kalshi `closing`, Polymarket `end_date`.

Status filters (`DataVentsStatusParams`):
- `OPEN_MARKETS` → Kalshi `opened,unopened`; Polymarket `active`.
- `CLOSED_MARKETS` → Kalshi `closed,settled`; Polymarket `closed`.
- `ALL_MARKETS` → no status filter.

Note: Kalshi series search does not accept a `status` filter; when you request `scope="series"` with a non‑ALL status, the client uses events search under the hood.

---

## Configuration, Timeouts, and Rate Limiting

- HTTP timeout (seconds): `HTTP_TIMEOUT_SECONDS` env (default 15s).
- Basic pacing between requests via `RateLimitConfig` (default ~100ms between calls).
- Logging: the SDK uses the standard library’s `logging` module; enable debug logs by configuring handlers in your app.

---

## Examples

See `examples/` for small, runnable scripts:
- `search_events.py` – search across providers.
- `list_markets.py` – get Polymarket markets and Kalshi event‑nested markets.
- `get_event.py` / `get_market.py` – fetch single resources by id/ticker/slug.
- `ws_multiplex.py` – stream from Polymarket and/or Kalshi in one loop.
- `normalize_examples.py` – convert raw payloads into normalized Pydantic models.

Run like:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
python examples/search_events.py --q "election" --limit 5
```

---

## Utilities

- `extract_vendors(value, *, strict=False)` → `[DvVendors, ...]`
  - Accepts flexible input such as `"kalshi"`, `"poly,kalshi"`, `"all"`, `Provider.kalshi`, or a list of mixed tokens.
  - Returns a stable, de‑duplicated order: `[DvVendors.KALSHI, DvVendors.POLYMARKET]` when both.
  - Back‑compat alias: `_extract_vendors(...)`.

```python
from datavents import extract_vendors, DvVendors

assert extract_vendors("all") == [DvVendors.KALSHI, DvVendors.POLYMARKET]
assert extract_vendors(["k", "pm"]) == [DvVendors.KALSHI, DvVendors.POLYMARKET]
```

- `build_ws_info(subscription)` → dict summarizing a `DvSubscription` (WS URLs, channels, identifiers).
  - Back‑compat alias: `_send_ws_info(subscription)` for legacy callers.

```python
from datavents import DvSubscription, DvVendors, build_ws_info

sub = DvSubscription(
    vendors=(DvVendors.KALSHI, DvVendors.POLYMARKET),
    kalshi_market_tickers=["SER-ABC-123"],
    polymarket_assets_ids=["asset-1"],
)
info = build_ws_info(sub)
print(info["kalshi"]["ws_url"], info["polymarket"]["ws_url"])  # ready for UIs/logging
```

---

## Limitations & Notes

- This SDK targets provider public endpoints. Some features (e.g., private Kalshi WS) require valid credentials.
- `list_markets` on Kalshi returns markets nested inside events; flatten as needed.
- Provider APIs evolve; enums map to best‑available sorts/filters and may be updated across releases.

---

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest
```

To publish artifacts:

```bash
make build   # dist/*.whl + dist/*.tar.gz
make check   # twine check dist
make publish # twine upload dist/*
```

---

## License

MIT
