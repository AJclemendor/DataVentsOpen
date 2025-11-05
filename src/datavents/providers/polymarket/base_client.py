


import os
import sys
import time
import logging
from typing import Any, Dict

import requests
try:
    from ..config import Config
    from .rest_auth import PolymarketAuth
    from ..shared_connection.rate_limit import RateLimitConfig
except Exception:
    # Fallback for ad-hoc execution
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import Config  # type: ignore
    from rest_auth import PolymarketAuth  # type: ignore
    from shared_connection.rate_limit import RateLimitConfig  # type: ignore

logger = logging.getLogger(__name__)


class BasePolymarketClient:
    def __init__(self, polymarketAuth: PolymarketAuth, config: Config = Config.PAPER, rate_limit_config: RateLimitConfig = RateLimitConfig()):


        self.config: Config = config

        if self.config == Config.PAPER:
            raise NotImplementedError("Polymarket does not currently support paper trading")
        elif self.config == Config.LIVE:
            logger.info("Creating a polymarket client with live config")
        elif self.config == Config.NOAUTH:
            logger.debug("Creating a polymarket client with no auth config (CLOB, lvl 0)")
        else:
            raise ValueError(f"Invalid config: {self.config}")

        self.BASE_API_URL = "https://gamma-api.polymarket.com"
        self.polymarketAuth: PolymarketAuth = polymarketAuth
        self.rate_limit_config: RateLimitConfig = rate_limit_config
        # Default HTTP timeout in seconds (override with HTTP_TIMEOUT_SECONDS)
        try:
            self._timeout_seconds = float(os.getenv("HTTP_TIMEOUT_SECONDS", "15"))
        except Exception:
            self._timeout_seconds = 15.0



    def post(self, path: str, body: dict) -> Any:
        """Performs an authenticated POST request to the Polymarket API."""
        self.rate_limit_config.rate_limit()
        last_exc = None
        for attempt in range(2):
            try:
                response = requests.post(
                    self.BASE_API_URL + path,
                    json=body,
                    timeout=self._timeout_seconds,
                )
                break
            except requests.exceptions.Timeout as e:
                last_exc = e
                if attempt == 0:
                    time.sleep(0.2)
                    continue
                raise
        self.raise_if_bad_response(response)
        return response.json()


    def get(self, path: str, params: Dict[str, Any] = {}) -> Any:
        """Performs an authenticated GET request to the Polymarket API."""
        self.rate_limit_config.rate_limit()
        last_exc = None
        for attempt in range(2):
            try:
                response = requests.get(
                    self.BASE_API_URL + path,
                    params=params,
                    timeout=self._timeout_seconds,
                )
                break
            except requests.exceptions.Timeout as e:
                last_exc = e
                if attempt == 0:
                    time.sleep(0.2)
                    continue
                raise
        self.raise_if_bad_response(response)
        return response.json()

    def delete(self, path: str, params: Dict[str, Any] = {}) -> Any:
        """Performs an authenticated DELETE request to the Polymarket API."""
        self.rate_limit_config.rate_limit()
        last_exc = None
        for attempt in range(2):
            try:
                response = requests.delete(
                    self.BASE_API_URL + path,
                    params=params,
                    timeout=self._timeout_seconds,
                )
                break
            except requests.exceptions.Timeout as e:
                last_exc = e
                if attempt == 0:
                    time.sleep(0.2)
                    continue
                raise
        self.raise_if_bad_response(response)
        return response.json()



    def raise_if_bad_response(self, response: requests.Response) -> None:
        """Raises an HTTPError if the response status code indicates an error."""
        if response.status_code not in range(200, 299):
            response.raise_for_status()


    # currently no utils
    
