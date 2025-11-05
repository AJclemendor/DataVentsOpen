from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Union
import re as _re

from .schemas import (
    Market,
    Outcome,
    Fees,
    StatusNormalized,
    Provider,
    Event,
    SearchResponseNormalized,
    SearchMeta,
    SearchScopeKalshi,
    OrderSort,
    StatusFilter,
    MarketHistoryResponseNormalized,
)
import datetime as _dt


def _to_ms(ts: Optional[int | float | str]) -> Optional[int]:
    if ts is None:
        return None
    # ISO datetime string
    if isinstance(ts, str):
        s = ts.strip()
        if not s:
            return None
        # Try integer in string first
        if s.isdigit():
            try:
                v = int(s)
                if v < 10_000_000_000:
                    v *= 1000
                return v
            except Exception:
                pass
        # Try ISO date
        try:
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            dt = _dt.datetime.fromisoformat(s)
            return int(dt.timestamp() * 1000)
        except Exception:
            pass
        # Fallback: attempt float
        try:
            v = int(float(s))
            if v < 10_000_000_000:
                v *= 1000
            return v
        except Exception:
            return None
    # Numeric path
    try:
        v = int(float(ts))
    except Exception:
        return None
    # If seconds, convert to ms
    if v < 10_000_000_000:
        v *= 1000
    return v


def _safe_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _slugify(text: Optional[str]) -> Optional[str]:
    """Best-effort slugify for Kalshi event titles.

    Lowercase, replace non-alphanumerics with single dashes, trim edges.
    Returns None if input is falsy after normalization.
    """
    if not text:
        return None
    s = str(text).strip().lower()
    s = _re.sub(r"[^a-z0-9]+", "-", s)
    s = _re.sub(r"-+", "-", s).strip("-")
    return s or None


def _status_from_kalshi(raw: Dict[str, Any]) -> tuple[StatusNormalized, Optional[str]]:
    s = str(raw.get("status") or raw.get("market_status") or raw.get("state") or "").lower()
    # Kalshi may return market states like "initialized" for not-yet-opened but
    # listed markets. Treat it as part of the open bucket to match the
    # OPEN_MARKETS filter semantics (opened + unopened).
    if s in {"opened", "unopened", "open", "active", "initialized"}:
        return StatusNormalized.open, s or None
    if s in {"closed", "inactive"}:
        return StatusNormalized.closed, s or None
    if s in {"settled", "resolved"}:
        return StatusNormalized.settled, s or None
    if s in {"draft", "scheduled", "upcoming"}:
        return StatusNormalized.upcoming, s or None
    return StatusNormalized.unknown, (s or None)


def _status_from_polymarket(raw: Dict[str, Any]) -> tuple[StatusNormalized, Optional[str]]:
    # Prefer explicit status when present
    s_raw = raw.get("status") or raw.get("state")
    if isinstance(s_raw, str):
        s = s_raw.lower()
        if s in {"active", "open"}:
            return StatusNormalized.open, s_raw
        if s in {"closed"}:
            return StatusNormalized.closed, s_raw
        if s in {"resolved", "settled"}:
            return StatusNormalized.settled, s_raw
    # Fallbacks
    if bool(raw.get("isResolved") or raw.get("resolved")):
        return StatusNormalized.settled, "resolved"
    if isinstance(raw.get("closed"), bool):
        return (StatusNormalized.closed if raw["closed"] else StatusNormalized.open, "closed" if raw["closed"] else "active")
    return StatusNormalized.unknown, (str(s_raw) if s_raw else None)


def _mk_outcomes_binary(
    yes_price: Optional[float],
    yes_bid: Optional[float],
    yes_ask: Optional[float],
) -> List[Outcome]:
    out: List[Outcome] = []
    if yes_price is None and yes_bid is None and yes_ask is None:
        return out
    out.append(
        Outcome(
            name="Yes",
            side="yes",
            price=yes_price,
            best_bid=yes_bid,
            best_ask=yes_ask,
        )
    )
    no_price = (1.0 - yes_price) if isinstance(yes_price, float) else None
    # For bids/asks, mirror if present
    no_bid = (1.0 - yes_ask) if isinstance(yes_ask, float) else None
    no_ask = (1.0 - yes_bid) if isinstance(yes_bid, float) else None
    out.append(
        Outcome(
            name="No",
            side="no",
            price=no_price,
            best_bid=no_bid,
            best_ask=no_ask,
        )
    )
    return out


def normalize_market_kalshi(raw: Dict[str, Any]) -> Market:
    # Accept several wrapper shapes
    m = raw
    if isinstance(raw, dict):
        if isinstance(raw.get("market"), dict):
            m = raw.get("market")
        elif isinstance(raw.get("markets"), list) and raw["markets"]:
            # choose exact ticker match if possible
            arr = raw["markets"]
            m = arr[0]
    m = m or {}

    ticker = m.get("ticker") or m.get("ticker_name")
    market_id = str(m.get("id") or ticker or m.get("market_id") or "").strip()
    # Titles vary; prefer explicit fields
    question = (
        m.get("title")
        or m.get("question")
        or m.get("name")
        or m.get("market_title")
    )
    status_n, status_raw = _status_from_kalshi(m)

    yes_bid_raw = _safe_float(m.get("yes_bid") or m.get("best_bid") or m.get("high_bid"))
    yes_ask_raw = _safe_float(m.get("yes_ask") or m.get("best_ask") or m.get("low_ask"))
    last_price_raw = _safe_float(m.get("last_price") or m.get("price"))
    # Normalize to [0,1]
    yes_bid = _normalize_probability(yes_bid_raw) if yes_bid_raw is not None else None
    yes_ask = _normalize_probability(yes_ask_raw) if yes_ask_raw is not None else None
    last_price = _normalize_probability(last_price_raw) if last_price_raw is not None else None

    # Compute mid if not provided
    mid_price = None
    if yes_bid is not None and yes_ask is not None:
        mid_price = (yes_bid + yes_ask) / 2.0

    liquidity = _safe_float(m.get("liquidity") or m.get("liquidity_usd"))
    vol24 = _safe_float(m.get("volume_24h") or m.get("volume24h") or m.get("volume_24hr"))
    oi = _safe_float(m.get("open_interest") or m.get("open_interest_usd") or m.get("oi"))

    # Timestamps
    start_ts = _to_ms(m.get("start_ts") or m.get("open_ts") or m.get("start_time"))
    end_ts = _to_ms(m.get("close_ts") or m.get("end_ts") or m.get("end_time"))

    outcomes: List[Outcome] = []
    # If explicit outcomes exist, try to use them
    if isinstance(m.get("outcomes"), list) and m["outcomes"]:
        for o in m["outcomes"]:
            if not isinstance(o, dict):
                continue
            pr = _normalize_probability(_safe_float(o.get("price")))
            bb = _normalize_probability(_safe_float(o.get("best_bid") or o.get("bid")))
            ba = _normalize_probability(_safe_float(o.get("best_ask") or o.get("ask")))
            outcomes.append(
                Outcome(
                    outcome_id=str(o.get("id") or o.get("outcome_id") or ""),
                    name=o.get("name") or o.get("label"),
                    side=(str(o.get("side")).lower() if o.get("side") else None),
                    price=pr,
                    best_bid=bb,
                    best_ask=ba,
                    vendor_fields={},
                )
            )
    else:
        outcomes = _mk_outcomes_binary(last_price, yes_bid, yes_ask)

    fees: Optional[Fees] = None
    maker = _safe_float(m.get("maker_fee_bps"))
    taker = _safe_float(m.get("taker_fee_bps"))
    settlement = _safe_float(m.get("settlement_fee_bps") or m.get("settlement_bps"))
    if maker is not None or taker is not None or settlement is not None:
        fees = Fees(maker_bps=maker, taker_bps=taker, settlement_bps=settlement)

    # Build a public URL if not provided by API
    url = m.get("url") or None
    if url is None and ticker:
        url = f"https://kalshi.com/trade/{ticker}"

    return Market(
        provider=Provider.kalshi,
        market_id=str(market_id),
        ticker=str(ticker) if ticker else None,
        question=question,
        status=status_n,
        status_raw=status_raw,
        event_id=(m.get("event_ticker") or None),
        series_id=(m.get("series_ticker") or None),
        category=m.get("category"),
        tags=[str(t) for t in (m.get("tags") or []) if isinstance(t, (str, int))],
        url=url,
        start_ts=start_ts,
        end_ts=end_ts,
        best_bid=yes_bid,
        best_ask=yes_ask,
        last_price=last_price,
        mid_price=mid_price,
        liquidity_usd=liquidity,
        volume_24h_usd=vol24,
        open_interest_usd=oi,
        outcomes=outcomes,
        fees=fees,
        vendor_market_id=str(m.get("id")) if m.get("id") is not None else None,
        vendor_fields={},
        vendor_raw=raw if isinstance(raw, dict) else {},
    )


def normalize_market_polymarket(raw: Dict[str, Any]) -> Market:
    m = raw
    if isinstance(raw, dict):
        if isinstance(raw.get("market"), dict):
            m = raw.get("market")
    m = m or {}

    pid = m.get("id") or m.get("marketId") or m.get("market_id")
    slug = m.get("slug") or m.get("marketSlug")
    question = m.get("question") or m.get("title") or m.get("name")
    status_n, status_raw = _status_from_polymarket(m)

    best_bid_raw = _safe_float(m.get("bestBid") or m.get("bid"))
    best_ask_raw = _safe_float(m.get("bestAsk") or m.get("ask"))
    last_price_raw = _safe_float(m.get("lastPrice") or m.get("lastTradePrice") or m.get("price") or m.get("mid"))
    # Normalize to [0,1]
    best_bid = _normalize_probability(best_bid_raw) if best_bid_raw is not None else None
    best_ask = _normalize_probability(best_ask_raw) if best_ask_raw is not None else None
    last_price = _normalize_probability(last_price_raw) if last_price_raw is not None else None
    mid_price = None
    if best_bid is not None and best_ask is not None:
        mid_price = (best_bid + best_ask) / 2.0

    liquidity = _safe_float(m.get("liquidity") or m.get("liquidity_num") or m.get("liquidityUsd"))
    vol24 = _safe_float(m.get("volume24hr") or m.get("volume_24h") or m.get("volume_24hr") or m.get("volume"))
    oi = _safe_float(m.get("openInterest") or m.get("open_interest_usd") or m.get("tvl"))

    start_ts = _to_ms(m.get("startDate") or m.get("start_date") or m.get("created_time"))
    end_ts = _to_ms(m.get("endDate") or m.get("end_date"))

    outcomes: List[Outcome] = []
    if isinstance(m.get("outcomes"), list) and m["outcomes"]:
        for o in m["outcomes"]:
            if not isinstance(o, dict):
                continue
            nm = o.get("name") or o.get("outcome") or o.get("label")
            side = None
            if isinstance(nm, str):
                if nm.lower() in ("yes", "no"):
                    side = nm.lower()
            pr = _normalize_probability(_safe_float(o.get("price")))
            bb = _normalize_probability(_safe_float(o.get("bestBid") or o.get("bid")))
            ba = _normalize_probability(_safe_float(o.get("bestAsk") or o.get("ask")))
            outcomes.append(
                Outcome(
                    outcome_id=str(o.get("id") or o.get("outcome_id") or ""),
                    name=nm,
                    side=side,  # best-effort
                    price=pr,
                    best_bid=bb,
                    best_ask=ba,
                    vendor_fields={},
                )
            )
    else:
        # Assume binary if we have a price
        outcomes = _mk_outcomes_binary(last_price, best_bid, best_ask)

    fees: Optional[Fees] = None
    maker = _safe_float(m.get("makerFeeBps") or m.get("maker_fee_bps"))
    taker = _safe_float(m.get("takerFeeBps") or m.get("taker_fee_bps"))
    settlement = _safe_float(m.get("settlementFeeBps") or m.get("settlement_bps"))
    if maker is not None or taker is not None or settlement is not None:
        fees = Fees(maker_bps=maker, taker_bps=taker, settlement_bps=settlement)

    url = None
    if isinstance(slug, str) and slug:
        url = f"https://polymarket.com/market/{slug}"

    return Market(
        provider=Provider.polymarket,
        market_id=str(pid) if pid is not None else (str(slug) if slug else ""),
        slug=str(slug) if slug else None,
        ticker=None,
        question=question,
        status=status_n,
        status_raw=status_raw,
        event_id=(str(m.get("eventId")) if m.get("eventId") is not None else None),
        series_id=(str(m.get("seriesId")) if m.get("seriesId") is not None else None),
        category=m.get("category") or m.get("categoryLabel"),
        tags=[str(t) for t in (m.get("tags") or m.get("tagNames") or []) if isinstance(t, (str, int))],
        url=url,
        start_ts=start_ts,
        end_ts=end_ts,
        best_bid=best_bid,
        best_ask=best_ask,
        last_price=last_price,
        mid_price=mid_price,
        liquidity_usd=liquidity,
        volume_24h_usd=vol24,
        open_interest_usd=oi,
        outcomes=outcomes,
        fees=fees,
        vendor_market_id=str(pid) if pid is not None else None,
        vendor_fields={},
        vendor_raw=raw if isinstance(raw, dict) else {},
    )


def normalize_market(provider: Provider | str, raw: Dict[str, Any]) -> Market:
    pv: Provider
    if isinstance(provider, str):
        pv = Provider(provider)
    else:
        pv = provider
    if pv == Provider.kalshi:
        return normalize_market_kalshi(raw)
    if pv == Provider.polymarket:
        return normalize_market_polymarket(raw)
    # Default: try to infer by keys
    if "clob_token_id" in str(raw) or raw.get("slug"):
        return normalize_market_polymarket(raw)
    return normalize_market_kalshi(raw)


# -------------------- Event normalization --------------------


def _status_from_any(raw: Dict[str, Any], provider: Provider) -> tuple[StatusNormalized, Optional[str]]:
    return (_status_from_kalshi(raw) if provider == Provider.kalshi else _status_from_polymarket(raw))


def normalize_event_kalshi(raw: Dict[str, Any]) -> Event:
    ev = raw or {}
    # Accept wrappers like {"event": {...}}
    if isinstance(ev.get("event"), dict):
        ev = ev["event"]
    event_id = str(ev.get("event_ticker") or ev.get("ticker") or ev.get("id") or "").strip()
    title = ev.get("event_title") or ev.get("title") or ev.get("name")
    status_n, status_raw = _status_from_kalshi(ev)
    series_ticker = ev.get("series_ticker") or None
    created_ts = _to_ms(ev.get("created_ts") or ev.get("created_time"))
    start_ts = _to_ms(ev.get("start_ts") or ev.get("open_ts"))
    end_ts = _to_ms(ev.get("end_ts") or ev.get("close_ts"))

    markets: Optional[List[Market]] = None
    mlist = ev.get("markets")
    if isinstance(mlist, list) and mlist:
        markets = [normalize_market_kalshi(m) for m in mlist if isinstance(m, dict)]
        # Derive event status from child markets when event status is unknown
        if status_n == StatusNormalized.unknown:
            try:
                child_statuses = {getattr(m, "status", StatusNormalized.unknown) for m in markets}
                if StatusNormalized.open in child_statuses:
                    status_n, status_raw = StatusNormalized.open, "open"
                elif StatusNormalized.settled in child_statuses:
                    status_n, status_raw = StatusNormalized.settled, "settled"
                elif StatusNormalized.closed in child_statuses:
                    status_n, status_raw = StatusNormalized.closed, "closed"
            except Exception:
                pass

    # Attempt to construct a public event URL that matches the Kalshi site
    # shape: /markets/{series_slug}/{event_slug}/{market_group}
    event_url = ev.get("url") or None
    try:
        if event_url is None:
            series_slug = (str(series_ticker).lower() if series_ticker else None)
            # Prefer mini_title when present (shorter, matches site slugs more closely)
            title_for_slug = ev.get("mini_title") or title
            event_slug = _slugify(title_for_slug)
            market_group = None
            if markets and len(markets) > 0:
                t = getattr(markets[0], "ticker", None)
                if isinstance(t, str) and t:
                    parts = t.split("-")
                    if len(parts) >= 2:
                        market_group = f"{parts[0].lower()}-{parts[1].lower()}"
                    else:
                        market_group = t.lower()
            if series_slug and event_slug and market_group:
                event_url = f"https://kalshi.com/markets/{series_slug}/{event_slug}/{market_group}"
    except Exception:
        # Non-fatal: leave url as None if we cannot construct it
        pass

    return Event(
        provider=Provider.kalshi,
        event_id=event_id or (title or ""),
        slug=None,
        event_ticker=event_id or None,
        title=title,
        status=status_n,
        status_raw=status_raw,
        series_id=str(series_ticker) if series_ticker else None,
        category=ev.get("category"),
        tags=[str(t) for t in (ev.get("tags") or []) if isinstance(t, (str, int))],
        url=event_url,
        created_ts=created_ts,
        start_ts=start_ts,
        end_ts=end_ts,
        markets_count=(len(markets) if markets is not None else None),
        markets=markets,
        vendor_fields={},
        vendor_raw=raw if isinstance(raw, dict) else {},
    )


def normalize_event_polymarket(raw: Dict[str, Any]) -> Event:
    ev = raw or {}
    # Accept wrappers like {"event": {...}}
    if isinstance(ev.get("event"), dict):
        ev = ev["event"]
    pid = ev.get("id")
    slug = ev.get("slug") or ev.get("eventSlug")
    title = ev.get("title") or ev.get("name")
    status_n, status_raw = _status_from_polymarket(ev)
    created_ts = _to_ms(ev.get("created_time") or ev.get("createdTs"))
    start_ts = _to_ms(ev.get("start_date") or ev.get("startDate"))
    end_ts = _to_ms(ev.get("end_date") or ev.get("endDate"))

    markets: Optional[List[Market]] = None
    mlist = ev.get("markets")
    if isinstance(mlist, list) and mlist:
        markets = [normalize_market_polymarket(m) for m in mlist if isinstance(m, dict)]

    return Event(
        provider=Provider.polymarket,
        event_id=(str(pid) if pid is not None else (str(slug) if slug else title or "")),
        slug=str(slug) if slug else None,
        event_ticker=None,
        title=title,
        status=status_n,
        status_raw=status_raw,
        series_id=(str(ev.get("seriesId")) if ev.get("seriesId") is not None else None),
        category=ev.get("category") or ev.get("categoryLabel"),
        tags=[str(t) for t in (ev.get("tags") or ev.get("tagNames") or []) if isinstance(t, (str, int))],
        url=ev.get("url") or (f"https://polymarket.com/event/{slug}" if slug else None),
        created_ts=created_ts,
        start_ts=start_ts,
        end_ts=end_ts,
        markets_count=(len(markets) if markets is not None else None),
        markets=markets,
        vendor_fields={},
        vendor_raw=raw if isinstance(raw, dict) else {},
    )


def normalize_event(provider: Provider | str, raw: Dict[str, Any]) -> Event:
    pv = Provider(provider) if isinstance(provider, str) else provider
    return normalize_event_kalshi(raw) if pv == Provider.kalshi else normalize_event_polymarket(raw)


# -------------------- Search normalization --------------------


def _coerce_order(v: Union[str, OrderSort]) -> OrderSort:
    if isinstance(v, OrderSort):
        return v
    s = str(v or "").strip().upper()
    if s and not s.startswith("ORDER_BY_"):
        s = "ORDER_BY_" + s
    try:
        return OrderSort[s]
    except Exception:
        return OrderSort.trending


def _coerce_status(v: Union[str, StatusFilter]) -> StatusFilter:
    if isinstance(v, StatusFilter):
        return v
    s = str(v or "").strip().upper()
    if s and not s.endswith("_MARKETS") and s != "ALL":
        s = s + "_MARKETS"
    if s == "ALL":
        s = "ALL_MARKETS"
    try:
        return StatusFilter[s]
    except Exception:
        return StatusFilter.open


def normalize_search_response(
    provider: Provider | str,
    raw: Dict[str, Any],
    *,
    q: str = "",
    order: Union[str, OrderSort] = OrderSort.trending,
    status: Union[str, StatusFilter] = StatusFilter.open,
    page: int = 1,
    limit: int = 10,
    exclude_sports: bool = False,
    kalshi_scope: Optional[SearchScopeKalshi] = None,
) -> SearchResponseNormalized:
    pv = Provider(provider) if isinstance(provider, str) else provider
    order_e = _coerce_order(order)
    status_e = _coerce_status(status)

    results: List[Union[Event, Market]] = []
    if pv == Provider.kalshi:
        items = (raw or {}).get("current_page") or []
        for ev in items:
            if not isinstance(ev, dict):
                continue
            results.append(normalize_event_kalshi(ev))
        meta = SearchMeta(
            provider=pv.value,
            order=order_e,
            status=status_e,
            page=page,
            limit=limit,
            exclude_sports=exclude_sports,
            excluded_categories=["Sports"] if exclude_sports else [],
            kalshi_scope=kalshi_scope or SearchScopeKalshi.series,
        )
    else:
        events = (raw or {}).get("events") or []
        for ev in events:
            if not isinstance(ev, dict):
                continue
            results.append(normalize_event_polymarket(ev))
        meta = SearchMeta(
            provider=pv.value,
            order=order_e,
            status=status_e,
            page=page,
            limit=limit,
            exclude_sports=exclude_sports,
            excluded_categories=["Sports"] if exclude_sports else [],
            kalshi_scope=None,
        )

    return SearchResponseNormalized(results=results, meta=meta)


# -------------------- History normalization --------------------

def _normalize_probability(v: Any) -> Optional[float]:
    """Normalize various provider price units to probability in [0, 1].

    Accepts common encodings:
    - already-normalized probabilities (0..1)
    - percents (0..100 → divide by 100)
    - basis points / cents-like (0..10000 → divide by 10000)
    Values outside expected ranges are clamped to [0,1].
    """
    try:
        n = float(v)
    except Exception:
        return None
    if 0.0 <= n <= 1.0:
        return n
    if 1.0 < n <= 100.0:
        return n / 100.0
    if 100.0 < n <= 10000.0:
        return n / 10000.0
    # Fallback clamp for unexpected units
    if n < 0.0:
        return 0.0
    if n > 1.0:
        # Heuristic: treat large values as percents if reasonably small
        return min(1.0, n / 100.0)
    return n

def _points_from_kalshi_forecast_history(raw: Dict[str, Any]) -> List[Dict[str, float]]:
    """Convert Kalshi v1 forecast_history payload to normalized points list.

    Expects {"forecast_history": [{"end_period_ts": int, "numerical_forecast": float}, ...]}.
    Returns list of {"t": epoch_ms, "p": probability in [0,1]}.
    """
    points: List[Dict[str, float]] = []
    items = (raw or {}).get("forecast_history") or []
    for it in items:
        if not isinstance(it, dict):
            continue
        ts = it.get("end_period_ts") or it.get("ts") or it.get("timestamp")
        val = it.get("numerical_forecast") or it.get("raw_numerical_forecast")
        if ts is None or val is None:
            continue
        try:
            ts_i = int(ts)
            v_f = float(val) / 100.0
        except Exception:
            continue
        if ts_i < 10_000_000_000:
            ts_i *= 1000
        points.append({"t": ts_i, "p": v_f})
    return points


def _points_from_polymarket_prices_history(raw: Dict[str, Any]) -> List[Dict[str, float]]:
    """Convert Polymarket clob prices-history payload to normalized points list.

    Accepts common variants such as {"prices": [[ts, price], ...]} or nested under "data".
    Returns list of {"t": epoch_ms, "p": probability}.
    """
    points: List[Dict[str, float]] = []
    obj = raw or {}
    if isinstance(obj.get("data"), dict) and not obj.get("prices"):
        obj = obj["data"]
    rows = obj.get("prices") or obj.get("Points") or []
    for row in rows:
        if isinstance(row, (list, tuple)) and len(row) >= 2:
            ts, p = row[0], row[1]
        elif isinstance(row, dict):
            ts = row.get("t") or row.get("ts") or row.get("timestamp")
            p = row.get("p") or row.get("price")
        else:
            continue
        try:
            ts_i = int(float(ts))
            pv = float(p)
        except Exception:
            continue
        if ts_i < 10_000_000_000:
            ts_i *= 1000
        points.append({"t": ts_i, "p": pv})
    return points


def normalize_market_history_kalshi(
    *,
    ticker: str,
    series_ticker: str,
    market_id: str,
    start: int,
    end: int,
    interval: int,
    raw: Optional[Dict[str, Any]] = None,
    points: Optional[Sequence[Dict[str, float]]] = None,
) -> MarketHistoryResponseNormalized:
    """Normalize Kalshi market history to MarketHistoryResponseNormalized.

    If `points` is provided, it wins. Otherwise parse `raw` forecast_history.
    """
    pts = list(points or _points_from_kalshi_forecast_history(raw or {}))
    # Normalize all p values to [0,1]
    norm_pts: List[Dict[str, float]] = []
    for p in pts:
        try:
            t = int(p.get("t"))
            pv = _normalize_probability(p.get("p"))
            if pv is None:
                continue
            norm_pts.append({"t": t, "p": float(pv)})
        except Exception:
            continue
    norm_pts.sort(key=lambda d: d.get("t", 0))
    return MarketHistoryResponseNormalized(
        provider=Provider.kalshi,
        ticker=ticker,
        series_ticker=series_ticker,
        market_id=market_id,
        start=start,
        end=end,
        interval=interval,
        points=norm_pts,
    )


def normalize_market_history_polymarket(
    *,
    market_id: Optional[str],
    slug: Optional[str],
    clob_token_id: Optional[str],
    start: int,
    end: int,
    interval: int,
    poly_interval: Optional[str] = None,
    raw: Optional[Dict[str, Any]] = None,
    points: Optional[Sequence[Dict[str, float]]] = None,
) -> MarketHistoryResponseNormalized:
    """Normalize Polymarket market history to MarketHistoryResponseNormalized.

    If `points` is provided, it wins. Otherwise parse `raw` prices-history.
    """
    pts = list(points or _points_from_polymarket_prices_history(raw or {}))
    # Normalize all p values to [0,1]
    norm_pts: List[Dict[str, float]] = []
    for p in pts:
        try:
            t = int(p.get("t"))
            pv = _normalize_probability(p.get("p"))
            if pv is None:
                continue
            norm_pts.append({"t": t, "p": float(pv)})
        except Exception:
            continue
    norm_pts.sort(key=lambda d: d.get("t", 0))
    return MarketHistoryResponseNormalized(
        provider=Provider.polymarket,
        id=(int(market_id) if market_id is not None and str(market_id).isdigit() else None),
        slug=slug,
        clob_token_id=str(clob_token_id) if clob_token_id else None,
        start=start,
        end=end,
        interval=interval,
        poly_interval=poly_interval,
        points=norm_pts,
    )


def normalize_market_history(
    provider: Provider | str,
    *,
    identifiers: Dict[str, Any],
    start: int,
    end: int,
    interval: int,
    raw: Optional[Dict[str, Any]] = None,
    points: Optional[Sequence[Dict[str, float]]] = None,
    poly_interval: Optional[str] = None,
) -> MarketHistoryResponseNormalized:
    """Unified entry point delegating to provider-specific helpers.

    identifiers keys:
      - kalshi: {"ticker": str, "series_ticker": str, "market_id": str}
      - polymarket: {"market_id"?: str|int, "slug"?: str, "clob_token_id"?: str}
    """
    pv = Provider(provider) if isinstance(provider, str) else provider
    if pv == Provider.kalshi:
        return normalize_market_history_kalshi(
            ticker=str(identifiers.get("ticker") or ""),
            series_ticker=str(identifiers.get("series_ticker") or ""),
            market_id=str(identifiers.get("market_id") or ""),
            start=start,
            end=end,
            interval=interval,
            raw=raw,
            points=points,
        )
    return normalize_market_history_polymarket(
        market_id=(str(identifiers.get("market_id")) if identifiers.get("market_id") is not None else None),
        slug=(str(identifiers.get("slug")) if identifiers.get("slug") else None),
        clob_token_id=(str(identifiers.get("clob_token_id")) if identifiers.get("clob_token_id") else None),
        start=start,
        end=end,
        interval=interval,
        poly_interval=poly_interval,
        raw=raw,
        points=points,
    )
