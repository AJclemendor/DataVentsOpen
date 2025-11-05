from __future__ import annotations

import pytest

from datavents import extract_vendors
from datavents.vendors import DvVendors
from datavents.schemas import Provider


def test_extract_vendors_none_default():
    v = extract_vendors(None)
    assert v == [DvVendors.KALSHI, DvVendors.POLYMARKET]


def test_extract_vendors_string_aliases():
    assert extract_vendors("kalshi") == [DvVendors.KALSHI]
    assert extract_vendors("poly") == [DvVendors.POLYMARKET]
    assert extract_vendors("polymarket") == [DvVendors.POLYMARKET]
    assert extract_vendors("k,pm") == [DvVendors.KALSHI, DvVendors.POLYMARKET]
    assert extract_vendors("all") == [DvVendors.KALSHI, DvVendors.POLYMARKET]
    assert extract_vendors("*") == [DvVendors.KALSHI, DvVendors.POLYMARKET]


def test_extract_vendors_mixed_iterables():
    mixed = ["kalshi", Provider.polymarket]
    v = extract_vendors(mixed)
    assert v == [DvVendors.KALSHI, DvVendors.POLYMARKET]


def test_extract_vendors_strict_failure():
    with pytest.raises(ValueError):
        extract_vendors("unknown", strict=True)

