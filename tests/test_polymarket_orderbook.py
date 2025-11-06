from __future__ import annotations

from datavents.providers.polymarket.polymarket_rest_noauth import PolymarketRestNoAuth
import json
import logging
from pathlib import Path
import pytest


# ---- Integration (real API, no auth only) -----------------------------------

TID1 = "66281600716773880802753015201294956591448454218578699327801428058257011939378"
TID2 = "59964717011473581387089048234239097005165234934041431203725679550377112731340"


def _write_output(filename: str, data: dict) -> Path:
    root = Path(__file__).parent.parent
    out_dir = root / ".test_output"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / filename
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)
    return out_path


@pytest.mark.integration
def test_polymarket_orderbook_real_api_writes_output():
    logger = logging.getLogger(__name__)
    client = PolymarketRestNoAuth()

    # Single book
    logger.info("Fetching Polymarket /book token_id=%s", TID1)
    single = client.get_orderbook(TID1)
    assert isinstance(single, (dict, list))
    p1 = _write_output("polymarket_orderbook_single.json", {"token_id": TID1, "data": single})
    logger.info("Wrote single book JSON → %s", p1)

    # Batch books
    logger.info("Fetching Polymarket /books token_ids=%s,%s", TID1, TID2)
    batch = client.get_orderbooks([
        {"token_id": TID1},
        {"token_id": TID2, "side": "SELL"},
    ])
    assert isinstance(batch, (list, dict))
    p2 = _write_output("polymarket_orderbooks_batch.json", {"tokens": [TID1, TID2], "data": batch})
    logger.info("Wrote batch books JSON → %s", p2)
