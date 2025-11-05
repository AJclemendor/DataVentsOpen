from __future__ import annotations

from datavents import (
    provider_from_param,
    dedupe_preserve,
    coerce_string_list,
    collect_strings,
    first_int,
    first_str,
    DataVentsProviders,
)


def test_provider_from_param():
    assert provider_from_param("kalshi") == DataVentsProviders.KALSHI
    assert provider_from_param("polymarket") == DataVentsProviders.POLYMARKET
    assert provider_from_param("unknown") == DataVentsProviders.ALL


def test_coerce_and_collect_helpers():
    assert dedupe_preserve([" a ", "a", "b"]) == ["a", "b"]
    assert coerce_string_list([" a ", ["b", 3]]) == ["a", "b", "3"]
    src = {"x": [" A ", "B"], "y": "c"}
    assert collect_strings(src, ("x", "y")) == ["A", "B", "c"]
    assert first_int(("n",), {"n": "42"}) == 42
    assert first_str(("s",), {"s": " z "}) == "z"

