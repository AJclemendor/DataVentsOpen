from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class WsExampleSettings:
    """Defaults for the Kalshi WS example.

    These replace the prior environment-variable-based configuration for:
    - environment (paper|live)
    - duration seconds
    - logging level and format
    - test tickers and channels

    Secrets like API keys remain sourced from env variables.
    """

    env: str = "live"  # "paper" or "live"
    secs: float = 200.0
    log_level: str = "INFO"  # INFO, DEBUG, WARNING, etc.
    log_format: str = "console"  # "console" or "json"
    internal_level: str = "WARNING"  # level for library/internal loggers
    tickers: List[str] = field(
        default_factory=lambda: [
            # Example NFL market (can be replaced as needed)
            "KXNFLGAME-25NOV02KCBUF",
        ]
    )
    channels: List[str] = field(
        default_factory=lambda: [
            "orderbook_delta",
            "ticker",
            "trade",
        ]
    )

    # Output behavior
    output: str = "readable"  # "readable" or "json"
    events: List[str] = field(default_factory=list)  # empty => all; else subset of {ticker,orderbook,trade}
    show_acks: bool = True
