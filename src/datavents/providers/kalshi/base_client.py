from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from typing import Dict, Any
import base64
import requests
import datetime
import time
import os
import logging

from datetime import datetime, timedelta

from .rest_auth import KalshiAuth
import os
import sys
try:
    from ..config import Config
    from ..shared_connection.rate_limit import RateLimitConfig
except Exception:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import Config
    from shared_connection.rate_limit import RateLimitConfig

logger = logging.getLogger(__name__)


class BaseKalshiClient:

    def __init__(
        self,
        kalshiAuth: KalshiAuth,
        config: Config = Config.PAPER,
        rate_limit_config: RateLimitConfig = RateLimitConfig(),
    ):
        self.kalshiAuth: KalshiAuth = kalshiAuth
        self.config: Config = config

        if self.config == Config.PAPER:
            self.BASE_API_URL = "https://demo-api.kalshi.co"
            self.WS_BASE_URL = "wss://demo-api.kalshi.co"
        elif self.config == Config.LIVE:
            self.BASE_API_URL = "https://api.elections.kalshi.com"
            self.WS_BASE_URL = "wss://api.elections.kalshi.com"
        elif self.config == Config.NOAUTH:
            logger.debug("Creating a kalshi client with no auth config")
            self.BASE_API_URL = "https://api.elections.kalshi.com"
            self.WS_BASE_URL = "wss://api.elections.kalshi.com"
        else:
            raise ValueError(f"Invalid config: {self.config}")


        self.api_path = "/trade-api/v2"
        self.exchange_url = "/exchange"
        self.markets_url = "/markets"
        self.portfolio_url = "/portfolio"

        self.rate_limit_config = rate_limit_config
        # Default HTTP timeout in seconds (override with HTTP_TIMEOUT_SECONDS)
        try:
            self._timeout_seconds = float(os.getenv("HTTP_TIMEOUT_SECONDS", "15"))
        except Exception:
            self._timeout_seconds = 15.0

    def _format_timestamp(self) -> str:
        current_time = datetime.now()
        timestamp = current_time.timestamp()
        current_time_milliseconds = int(timestamp * 1000)
        timestampt_str = str(current_time_milliseconds)
        return timestampt_str

    def _strip_path_from_query(self, path: str) -> str:
        return path.split("?")[0]

    def _form_msg_string(self, method: str, path: str) -> tuple[str, str]:

        # Weird little bundle
        timestampt_str = self._format_timestamp()
        path_without_query = self._strip_path_from_query(path)
        msg_string = timestampt_str + method + path_without_query
        signature = self.kalshiAuth.sign_pss_text(msg_string)
        return timestampt_str, signature


    def request_headers(self, method: str, path: str) -> Dict[str, Any]:
        timestampt_str, signature = self._form_msg_string(method=method, path=path)

        headers = {
            "Content-Type": "application/json",
            "KALSHI-ACCESS-KEY": self.kalshiAuth.api_key,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestampt_str,
        }
        return headers

    def raise_if_bad_response(self, response: requests.Response) -> None:
        """Raises an HTTPError if the response status code indicates an error."""
        if response.status_code not in range(200, 299):
            response.raise_for_status()

    def post(self, path: str, body: dict) -> Any:
        """Performs an authenticated POST request to the Kalshi API."""
        self.rate_limit_config.rate_limit()
        path = self.api_path + path
        last_exc = None
        for attempt in range(2):
            try:
                response = requests.post(
                    self.BASE_API_URL + path,
                    json=body,
                    headers=self.request_headers("POST", path),
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
        """Performs an authenticated GET request to the Kalshi API."""
        self.rate_limit_config.rate_limit()
        path = self.api_path + path
        last_exc = None
        for attempt in range(2):
            try:
                response = requests.get(
                    self.BASE_API_URL + path,
                    headers=self.request_headers("GET", path),
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
        """Performs an authenticated DELETE request to the Kalshi API."""
        self.rate_limit_config.rate_limit()
        path = self.api_path + path
        last_exc = None
        for attempt in range(2):
            try:
                response = requests.delete(
                    self.BASE_API_URL + path,
                    headers=self.request_headers("DELETE", path),
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
