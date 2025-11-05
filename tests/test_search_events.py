"""Tests for DataVentsNoAuthClient.search_events method.

These tests make REAL API calls to verify actual integration with Kalshi and Polymarket.
NO MOCKS - All tests hit live APIs!

Run with: pytest src/datavents/tests/test_search_events.py -v -s
"""

import pytest
import json
from pathlib import Path
from ._helpers import write_json_artifact
from datavents import (
    DataVentsNoAuthClient,
    DataVentsProviders,
    DataVentsOrderSortParams,
    DataVentsStatusParams,
)


class TestSearchEvents:
    """Test suite that makes real API calls to Kalshi and Polymarket."""

    @pytest.fixture
    def client(self):
        """Create a real DataVentsNoAuthClient instance."""
        return DataVentsNoAuthClient()

    def test_kalshi_search_events_real_api(self, client):
        """Test KALSHI search_events with real API call."""
        print("\n=== Testing KALSHI API ===")

        result = client.search_events(
            provider=DataVentsProviders.KALSHI,
            query="election",
            limit=5,
            page=0,
            order_sort_params=DataVentsOrderSortParams.ORDER_BY_TRENDING,
            status_params=DataVentsStatusParams.OPEN_MARKETS,
        )

        print(f"Result type: {type(result)}")
        print(f"Result length: {len(result)}")
        print(f"Result: {result}")
        try:
            write_json_artifact("live-kalshi-search-events", result, subdir="live")
        except Exception:
            pass

        # Basic assertions
        assert result is not None
        assert isinstance(result, list)
        assert len(result) > 0

        # Check the response structure
        kalshi_response = result[0]
        print(f"\nKalshi response keys: {kalshi_response.keys() if isinstance(kalshi_response, dict) else 'Not a dict'}")
        print(f"Full Kalshi response: {kalshi_response}")

    def test_polymarket_search_events_real_api(self, client):
        """Test POLYMARKET search_events with real API call."""
        print("\n=== Testing POLYMARKET API ===")

        result = client.search_events(
            provider=DataVentsProviders.POLYMARKET,
            query="election",
            limit=5,
            page=0,
            order_sort_params=DataVentsOrderSortParams.ORDER_BY_TRENDING,
            status_params=DataVentsStatusParams.OPEN_MARKETS,
        )

        print(f"Result type: {type(result)}")
        print(f"Result length: {len(result)}")
        print(f"Result: {result}")
        try:
            write_json_artifact("live-polymarket-search-events", result, subdir="live")
        except Exception:
            pass

        # Basic assertions
        assert result is not None
        assert isinstance(result, list)
        assert len(result) > 0

        # Check the response structure
        polymarket_response = result[0]
        print(f"\nPolymarket response keys: {polymarket_response.keys() if isinstance(polymarket_response, dict) else 'Not a dict'}")
        print(f"Full Polymarket response: {polymarket_response}")

    def test_kalshi_different_sort_params_real_api(self, client):
        """Test KALSHI with different sort parameters."""
        print("\n=== Testing KALSHI with ORDER_BY_VOLUME ===")

        result = client.search_events(
            provider=DataVentsProviders.KALSHI,
            query="sports",
            limit=3,
            page=0,
            order_sort_params=DataVentsOrderSortParams.ORDER_BY_VOLUME,
            status_params=DataVentsStatusParams.OPEN_MARKETS,
        )

        print(f"Result: {result}")
        assert result is not None
        assert isinstance(result, list)

    def test_kalshi_closed_markets_real_api(self, client):
        """Test KALSHI with closed markets status."""
        print("\n=== Testing KALSHI with CLOSED_MARKETS ===")

        result = client.search_events(
            provider=DataVentsProviders.KALSHI,
            query="election",
            limit=3,
            page=0,
            order_sort_params=DataVentsOrderSortParams.ORDER_BY_NEWEST,
            status_params=DataVentsStatusParams.CLOSED_MARKETS,
        )

        print(f"Result: {result}")
        assert result is not None
        assert isinstance(result, list)

    def test_polymarket_different_query_real_api(self, client):
        """Test POLYMARKET with different query."""
        print("\n=== Testing POLYMARKET with 'trump' query ===")

        result = client.search_events(
            provider=DataVentsProviders.POLYMARKET,
            query="trump",
            limit=5,
            page=0,
            order_sort_params=DataVentsOrderSortParams.ORDER_BY_VOLUME,
            status_params=DataVentsStatusParams.OPEN_MARKETS,
        )

        print(f"Result: {result}")
        assert result is not None
        assert isinstance(result, list)

    def test_kalshi_all_markets_status_real_api(self, client):
        """Test KALSHI with all markets status."""
        print("\n=== Testing KALSHI with ALL_MARKETS ===")

        result = client.search_events(
            provider=DataVentsProviders.KALSHI,
            query="bitcoin",
            limit=5,
            page=0,
            order_sort_params=DataVentsOrderSortParams.ORDER_BY_TRENDING,
            status_params=DataVentsStatusParams.ALL_MARKETS,
        )

        print(f"Result: {result}")
        assert result is not None
        assert isinstance(result, list)

    def test_compare_providers_same_query(self, client):
        """Compare responses from both providers for the same query."""
        print("\n=== Comparing KALSHI vs POLYMARKET for 'election' ===")

        kalshi_result = client.search_events(
            provider=DataVentsProviders.KALSHI,
            query="election",
            limit=3,
            page=0,
            order_sort_params=DataVentsOrderSortParams.ORDER_BY_TRENDING,
            status_params=DataVentsStatusParams.OPEN_MARKETS,
        )

        polymarket_result = client.search_events(
            provider=DataVentsProviders.POLYMARKET,
            query="election",
            limit=3,
            page=0,
            order_sort_params=DataVentsOrderSortParams.ORDER_BY_TRENDING,
            status_params=DataVentsStatusParams.OPEN_MARKETS,
        )

        print(f"\nKALSHI result: {kalshi_result}")
        print(f"\nPOLYMARKET result: {polymarket_result}")
        try:
            write_json_artifact("live-compare-search-events", {"kalshi": kalshi_result, "polymarket": polymarket_result}, subdir="live")
        except Exception:
            pass

        assert kalshi_result is not None
        assert polymarket_result is not None
        assert isinstance(kalshi_result, list)
        assert isinstance(polymarket_result, list)

    def test_all_providers_parallel(self, client):
        """Test calling ALL providers in parallel and save formatted output."""
        print("\n=== Testing ALL providers in parallel ===")

        result = client.search_events(
            provider=DataVentsProviders.ALL,
            query="trump",
            limit=3,
            page=0,
            order_sort_params=DataVentsOrderSortParams.ORDER_BY_TRENDING,
            status_params=DataVentsStatusParams.OPEN_MARKETS,
        )

        print(f"\nResult type: {type(result)}")
        print(f"Result length: {len(result)}")

        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 2  # Should have results from both providers

        # Check that we have both providers
        providers = {r["provider"] for r in result}
        print(f"\nProviders: {providers}")
        assert providers == {"kalshi", "polymarket"}

        # Check that both have data
        for r in result:
            print(f"\n{r['provider'].upper()} data keys: {r['data'].keys() if isinstance(r['data'], dict) else 'Not a dict'}")
            assert "data" in r
            assert r["data"] is not None

        # Save formatted output to file
        # Write to backend/.test_output (and legacy .test-output for back-compat)
        underscore = Path(__file__).parent.parent.parent.parent / ".test_output"
        underscore.mkdir(exist_ok=True)
        hyphen = Path(__file__).parent.parent.parent.parent / ".test-output"
        hyphen.mkdir(exist_ok=True)
        output_file = underscore / "parallel_search_output.json"

        # Create a concise formatted version
        formatted_output = {
            "test": "test_all_providers_parallel",
            "query": "trump",
            "limit": 3,
            "providers_called": len(result),
            "results": []
        }

        for r in result:
            provider_name = r["provider"]
            data = r["data"]

            # Create summary based on provider
            if provider_name == "kalshi":
                summary = {
                    "provider": "kalshi",
                    "total_results": data.get("total_results_count", 0),
                    "events_returned": len(data.get("current_page", [])),
                    "event_titles": [
                        event.get("title", "No title")
                        for event in data.get("current_page", [])[:3]
                    ]
                }
            else:  # polymarket
                events = data.get("events", [])
                summary = {
                    "provider": "polymarket",
                    "events_returned": len(events),
                    "event_titles": [
                        event.get("title", "No title")
                        for event in events[:3]
                    ]
                }

            formatted_output["results"].append(summary)

        # Write to file with nice formatting
        with open(output_file, "w") as f:
            json.dump(formatted_output, f, indent=2)
        try:
            write_json_artifact("live-parallel-search-summary", formatted_output, subdir="live")
        except Exception:
            pass

        print(f"\n✅ Formatted output saved to: {output_file}")
        # Also duplicate into the hyphen directory for convenience
        try:
            with open(hyphen / "parallel_search_output.json", "w") as f2:
                json.dump(formatted_output, f2, indent=2)
        except Exception:
            pass
        print(f"Summary: Found {formatted_output['providers_called']} providers with results")
