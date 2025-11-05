Kalshi WS Example (CLI)

Run the example without exporting env vars for non-secrets.

Secrets: provide API keys in env for the chosen `--env` (unchanged behavior).

Quick start

- Human output, minimal internal logs (INFO):
  `uv run backend/examples/kalshi_ws_example.py --env live --secs 30 --tickers KXNFLGAME-25NOV02KCBUF --channels orderbook_delta,ticker,trade`

- JSON output, quiet internals, only trades:
  `uv run backend/examples/kalshi_ws_example.py --env live --secs 30 --output json --events trade --internal-level WARNING --tickers KXNFLGAME-25NOV02KCBUF`

Notable flags

- `--env`: `paper|live`
- `--secs`: run duration
- `--tickers`: event or market tickers (event tickers expand to markets)
- `--channels`: `ticker,orderbook_delta,trade`
- `--log-level`: root log level (default from settings)
- `--internal-level`: log level for `websockets` and `src.client.connect_dest_client` (default WARNING)
- `--output`: `human|json` for event prints
- `--events`: subset to print: comma-separated from `ticker,orderbook,trade`; empty prints all
- `--no-acks`: hide subscription ACK prints

Defaults live in `backend/examples/kalshi_ws_settings.py`.

