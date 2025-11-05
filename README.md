# DataVents Open SDK

Unified Python SDK for Kalshi and Polymarket. It bundles:

- A no-auth REST client that proxies provider APIs with a single interface.
- Normalization helpers + Pydantic models for events, markets, and history.
- A multiplexed WebSocket client that streams Kalshi + Polymarket in one loop.

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
pip install -e .
```

## Quickstart

```python
from datavents import (
    DataVentsNoAuthClient,
    DataVentsProviders,
    DvWsClient,
    DvSubscription,
    DvVendors,
    normalize_market,
)

client = DataVentsNoAuthClient()
markets = client.list_events(
    provider=DataVentsProviders.ALL,
    limit=5,
    page=0,
)
```

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
