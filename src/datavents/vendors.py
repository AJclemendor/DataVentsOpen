from __future__ import annotations

from enum import Enum
from datavents.schemas import Provider


class DvVendors(str, Enum):
    """Unified vendor enum used across SDK layers (WS, utils).

    Mirrors `datavents.schemas.Provider` values to avoid duplicate concepts.
    """

    KALSHI = "kalshi"
    POLYMARKET = "polymarket"

    def to_provider(self) -> Provider:
        return Provider(self.value)

    @staticmethod
    def from_provider(provider: Provider | str) -> "DvVendors":
        p = Provider(provider) if not isinstance(provider, Provider) else provider
        return DvVendors(p.value)

