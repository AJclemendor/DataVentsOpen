DV WS Client Example (CLI)

Run a unified websocket client that connects to Kalshi, Polymarket, or both,
with normalized subscription flags. Output can be human-readable or JSON.

Quick start

- Kalshi only (live), ticker/orderbook/trade for a specific market ticker:
  `uv run backend/examples/dv_ws_example.py --vendors kalshi --kalshi-env live --tickers KXNFLGAME-25NOV02KCBUF --secs 30`

- Polymarket only, subscribe to a set of asset ids:
  `uv run backend/examples/dv_ws_example.py --vendors polymarket --assets 0xabc...,0xdef... --secs 30`

- Both vendors concurrently (Kalshi + Polymarket):
  `uv run backend/examples/dv_ws_example.py --vendors both --tickers KXNFLGAME-25NOV02KCBUF --assets 0xabc... --secs 20`

Smoke test (assert messages from both)

- Provide Kalshi event or market tickers and Polymarket assets_ids, then run:
  `uv run backend/examples/dv_ws_test.py --kalshi-events KXNFLGAME-25NOV02KCBUF --assets 0xabc...,0xdef... --secs 20`
  Exits non-zero if it does not receive at least one message per selected vendor.

Flags

- `--vendors`: `kalshi|polymarket|both`
- `--secs`: run duration before clean shutdown
- `--output`: `human|json` event formatting
- `--events`: filter which events to print: comma-separated from `ticker,orderbook,trade`; empty = all
- `--include-raw`: also print raw/untyped messages (e.g., subscription ACKs); off by default
- `--tickers`: list used for both vendors unless more specific lists are set.
  For Kalshi, these are auto-expanded when possible: if a token is an event
  ticker, it expands to its market tickers via REST; if not, it is used as a
  market ticker as-is.
- `--kalshi-env`: `paper|live` (default live)
- `--kalshi-channels`: comma-separated from `ticker,orderbook_delta,trade`
- `--kalshi-tickers`: Kalshi market tickers (overrides `--tickers` for Kalshi)
- `--kalshi-events`: Kalshi event tickers to expand to markets (best-effort)
- `--assets`: Polymarket assets_ids (overrides `--tickers` for Polymarket)

Notes

- Kalshi requires valid API credentials in env for the selected env.
- Event expansion for `--kalshi-events` is best-effort; if creds are missing,
  values are used as-is.
