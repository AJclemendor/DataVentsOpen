__version__ = "0.1.0"

from .client import (
    DataVentsNoAuthClient,
    DataVentsProviders,
    DataVentsOrderSortParams,
    DataVentsStatusParams,
)
from .vendors import DvVendors
from .ws import DvWsClient, DvSubscription, NormalizedEvent
from .normalize import (
    normalize_market,
    normalize_event,
    normalize_search_response,
    normalize_market_history,
)
from .utils.vendors import extract_vendors, _extract_vendors
from .utils.ws import build_ws_info, _send_ws_info, json_default, event_payload
from .utils.params import (
    provider_from_param,
    dedupe_preserve,
    coerce_string_list,
    collect_strings,
    first_int,
    first_str,
)
from .utils.resolve import find_polymarket_asset_ids
from .utils.resolve import resolve_polymarket_assets_ids, _resolve_polymarket_assets_ids
from .utils.enums import enum_from_param, _enum_from_param
from .schemas import *  # re-export models

__all__ = [
    "DataVentsNoAuthClient",
    "DataVentsProviders",
    "DataVentsOrderSortParams",
    "DataVentsStatusParams",
    "DvWsClient",
    "DvSubscription",
    "DvVendors",
    "NormalizedEvent",
    "extract_vendors",
    "_extract_vendors",
    "build_ws_info",
    "_send_ws_info",
    "resolve_polymarket_assets_ids",
    "_resolve_polymarket_assets_ids",
    "enum_from_param",
    "_enum_from_param",
    "provider_from_param",
    "dedupe_preserve",
    "coerce_string_list",
    "collect_strings",
    "first_int",
    "first_str",
    "json_default",
    "event_payload",
    "find_polymarket_asset_ids",
    "__version__",
]
