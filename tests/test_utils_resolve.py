from __future__ import annotations

from datavents.utils.resolve import resolve_polymarket_assets_ids


def test_resolve_assets_from_simple_list():
    assets = ["aaa111", "bbb222", "bbb222"]
    out = resolve_polymarket_assets_ids(assets)
    assert out == ["aaa111", "bbb222"]


def test_resolve_assets_from_dict_shapes():
    payload = {
        "market": {
            "clobTokenIds": ["tok1", "tok2"],
            "outcomes": [
                {"asset_id": "tok1"},
                {"assetId": "tok2"},
                {"asset_id": "tok3"},
            ],
        }
    }
    out = resolve_polymarket_assets_ids(payload)
    assert out == ["tok1", "tok2", "tok3"]


def test_resolve_assets_from_mixed_tokens():
    out = resolve_polymarket_assets_ids("tokA, id:123, slug:some-market")
    # Without client/fetch this should include only direct asset-like tokens
    assert out == ["tokA"]

