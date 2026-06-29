from __future__ import annotations

from datetime import UTC, datetime
import pathlib
import sys
import unittest
from typing import Any


FUNCTIONS_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FUNCTIONS_DIR))

import airscope_query


class FakeContainer:
    def __init__(self, items: list[dict[str, Any]]) -> None:
        self.items = items
        self.calls: list[dict[str, Any]] = []

    def query_items(
        self,
        query: str,
        parameters: list[dict[str, Any]],
        partition_key: str,
    ) -> list[dict[str, Any]]:
        self.calls.append(
            {
                "query": query,
                "parameters": parameters,
                "partition_key": partition_key,
            }
        )
        return self.items


def current_item(icao24: str, freshness_at: str) -> dict[str, Any]:
    return {
        "id": f"demo-session:{icao24}",
        "session_id": "demo-session",
        "icao24": icao24,
        "callsign": "ANA245",
        "lat": 35.5523,
        "lon": 139.7798,
        "altitude_ft": 12800,
        "ground_speed_kt": 286,
        "track_deg": 72,
        "vertical_rate_fpm": 640,
        "squawk": "3301",
        "seen_at": freshness_at,
        "received_at": freshness_at,
        "freshness_at": freshness_at,
        "receiver_id": "airscope-demo-rpi",
        "distance_km": 18.4,
        "status": "current",
        "updated_at": freshness_at,
        "_etag": "secret-internal-value",
    }


class ValidationTests(unittest.TestCase):
    def test_validate_session_id_accepts_expected_identifier(self) -> None:
        self.assertEqual(
            airscope_query.validate_session_id(" demo-session:20260629 "),
            "demo-session:20260629",
        )

    def test_validate_session_id_rejects_missing_and_unsupported_values(self) -> None:
        for value in (None, "", "spaces are not allowed", "../session", "x" * 129):
            with self.subTest(value=value), self.assertRaises(ValueError):
                airscope_query.validate_session_id(value)

    def test_validate_telemetry_limit_applies_default_and_bounds(self) -> None:
        self.assertEqual(airscope_query.validate_telemetry_limit(None), 50)
        self.assertEqual(airscope_query.validate_telemetry_limit("200"), 200)
        for value in (True, "not-a-number", 0, 201):
            with self.subTest(value=value), self.assertRaises(ValueError):
                airscope_query.validate_telemetry_limit(value)


class CurrentAircraftQueryTests(unittest.TestCase):
    def test_recomputes_status_excludes_expired_and_sorts_newest_first(self) -> None:
        container = FakeContainer(
            [
                current_item("EXPIRED", "2026-06-29T00:57:59.000Z"),
                current_item("STALE", "2026-06-29T00:59:29.000Z"),
                current_item("CURRENT", "2026-06-29T00:59:30.000Z"),
                current_item("NEWEST", "2026-06-29T00:59:59.000Z"),
            ]
        )

        result = airscope_query.read_current_aircraft(
            container,
            "demo-session",
            now=datetime(2026, 6, 29, 1, 0, tzinfo=UTC),
            current_threshold_seconds=30,
            stale_threshold_seconds=120,
        )

        self.assertEqual([item["icao24"] for item in result], ["NEWEST", "CURRENT", "STALE"])
        self.assertEqual([item["status"] for item in result], ["current", "current", "stale"])
        self.assertNotIn("_etag", result[0])
        self.assertNotIn("id", result[0])

    def test_default_query_keeps_aircraft_current_for_one_day(self) -> None:
        container = FakeContainer(
            [
                current_item("ONE-DAY", "2026-06-28T01:00:00.000Z"),
                current_item("TOO-OLD", "2026-06-28T00:59:59.000Z"),
            ]
        )

        result = airscope_query.read_current_aircraft(
            container,
            "demo-session",
            now=datetime(2026, 6, 29, 1, 0, tzinfo=UTC),
        )

        self.assertEqual([item["icao24"] for item in result], ["ONE-DAY"])
        self.assertEqual(result[0]["status"], "current")

    def test_skips_missing_or_malformed_freshness(self) -> None:
        missing = current_item("MISSING", "2026-06-29T00:59:59.000Z")
        missing.pop("freshness_at")
        malformed = current_item("INVALID", "not-a-time")
        container = FakeContainer([missing, malformed])

        result = airscope_query.read_current_aircraft(
            container,
            "demo-session",
            now=datetime(2026, 6, 29, 1, 0, tzinfo=UTC),
        )

        self.assertEqual(result, [])

    def test_uses_parameterized_query_and_partition_key(self) -> None:
        container = FakeContainer([])

        airscope_query.read_current_aircraft(
            container,
            "demo-session",
            now=datetime(2026, 6, 29, 1, 0, tzinfo=UTC),
        )

        call = container.calls[0]
        self.assertIn("@session_id", call["query"])
        self.assertEqual(
            call["parameters"],
            [{"name": "@session_id", "value": "demo-session"}],
        )
        self.assertEqual(call["partition_key"], "demo-session")


class RecentTelemetryQueryTests(unittest.TestCase):
    def test_uses_bounded_parameterized_query_and_shapes_results(self) -> None:
        container = FakeContainer(
            [
                {
                    "id": "item-1",
                    "schema_version": "airscope.telemetry.demo.v1",
                    "source": "airscope-demo",
                    "session_id": "demo-session",
                    "sent_at": "2026-06-29T01:00:00.000Z",
                    "telemetry": {"icao24": "86D9A1"},
                    "ingested_at": "2026-06-29T01:00:01.000Z",
                    "_etag": "secret-internal-value",
                }
            ]
        )

        result = airscope_query.read_recent_telemetry(
            container,
            "demo-session",
            limit="25",
        )

        self.assertEqual(result[0]["id"], "item-1")
        self.assertNotIn("_etag", result[0])
        call = container.calls[0]
        self.assertIn("TOP @limit", call["query"])
        self.assertIn("ORDER BY c.ingested_at DESC", call["query"])
        self.assertEqual(
            call["parameters"],
            [
                {"name": "@limit", "value": 25},
                {"name": "@session_id", "value": "demo-session"},
            ],
        )
        self.assertEqual(call["partition_key"], "demo-session")


if __name__ == "__main__":
    unittest.main()
