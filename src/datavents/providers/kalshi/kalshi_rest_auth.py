"""Authenticated Kalshi REST client.

Inherits all convenience endpoints from the no‑auth client, but overrides
HTTP methods to send Kalshi's required signed headers. Use this when you need
authenticated access patterns or want to be explicit about signing even for
public endpoints.

Environment
- LIVE:  KALSHI_API_KEY, KALSHI_PRIVATE_KEY (path to PEM file)
- PAPER: KALSHI_API_KEY_PAPER, KALSHI_PRIVATE_KEY_PAPER

Example
    from datavents.providers.kalshi.kalshi_rest_auth import KalshiRestAuth
    from datavents.providers.config import Config

    client = KalshiRestAuth(config=Config.PAPER)
    ob = client.get_market_orderbook("ABC-24-XYZ-T50", depth=50)
    print(ob.get("orderbook"))
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .kalshi_rest_noauth import KalshiRestNoAuth
from .base_client import BaseKalshiClient
from .rest_auth import KalshiAuth
from ..config import Config
from ..shared_connection.rate_limit import RateLimitConfig
import logging

logger = logging.getLogger(__name__)


class KalshiRestAuth(KalshiRestNoAuth):
    """Signed REST client for Kalshi, compatible with KalshiRestNoAuth API.

    - Inherits all route helpers from `KalshiRestNoAuth` (e.g., get_markets, get_trades,
      get_market_orderbook, ...)
    - Overrides HTTP verbs to use the signed implementations from `BaseKalshiClient`.
    - Choose `config=Config.PAPER` for the demo environment or `Config.LIVE` for production.
    """

    def __init__(
        self,
        *,
        config: Config = Config.PAPER,
        auth: Optional[KalshiAuth] = None,
        rate_limit_config: RateLimitConfig = RateLimitConfig(),
    ) -> None:
        # Do NOT call KalshiRestNoAuth.__init__ (that would wire NOAUTH);
        # initialize the BaseKalshiClient directly with a real KalshiAuth.
        auth = auth or KalshiAuth(config)
        BaseKalshiClient.__init__(self, kalshiAuth=auth, config=config, rate_limit_config=rate_limit_config)

    # Override verbs to the signed versions from BaseKalshiClient
    def get(self, path: str, params: Dict[str, Any] = {}) -> Any:  # type: ignore[override]
        return BaseKalshiClient.get(self, path, params)

    def post(self, path: str, body: Dict[str, Any]) -> Any:  # type: ignore[override]
        return BaseKalshiClient.post(self, path, body)

    def delete(self, path: str, params: Dict[str, Any] = {}) -> Any:  # type: ignore[override]
        return BaseKalshiClient.delete(self, path, params)

    # Note: get_market_orderbook(...) is inherited from KalshiRestNoAuth and will
    # use this class's signed `get(...)` because of the override above.

    def get_market_orderbook(self, ticker: str, depth: Optional[int] = None):
        """Get Market Orderbook (signed).

        API: https://docs.kalshi.com/api-reference/market/get-market-orderbook

        Args
        - ticker: market ticker (e.g., "ABC-24-XYZ-T50")
        - depth: optional 0..100; 0 or omitted returns all available levels

        Returns raw provider JSON.
        """
        params: Dict[str, Any] = {}
        if depth is not None:
            try:
                d = int(depth)
                if d < 0:
                    d = 0
                if d > 100:
                    d = 100
                params["depth"] = d
            except Exception:
                pass

        # Trace at debug level to avoid noisy logs by default
        try:
            logger.debug("kalshi.rest.get_market_orderbook ticker=%s depth=%s", ticker, params.get("depth"))
        except Exception:
            pass
        return self.get(self.markets_url + f"/{ticker}/orderbook", params=params)
