# Legacy API Tests (migrated from VentsPyConsolidate)

These tests exercised the Flask API in the VentsPyConsolidate repo (e.g., `/api/market/history`, `/api/history`).
They are kept here for reference and future porting to this package.

Notes
- They assume a Flask app module at `api.flask_app` and a repo layout like `backend/src`.
- They will not run in this repository without adapting imports and bootstrapping a minimal Flask app or using the HTTP service.
- Consider rewriting them against the public `datavents` client APIs exposed in this repo, or moving them under a separate service repo.

Original files moved:
- `conftest.py`
- `test_kalshi_history_resolution.py`
- `test_polymarket_history_range.py`

