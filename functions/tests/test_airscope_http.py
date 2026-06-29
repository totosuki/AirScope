from __future__ import annotations

from datetime import UTC, datetime
import pathlib
import sys
import unittest
from typing import Any


FUNCTIONS_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FUNCTIONS_DIR))

import airscope_http


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


class SettingsTests(unittest.TestCase):
    def test_read_env_int_handles_present_missing_and_invalid_values(self) -> None:
        self.assertEqual(airscope_http.read_env_int({"SECONDS": "86400"}, "SECONDS", 30), 86400)
        self.assertEqual(airscope_http.read_env_int({}, "SECONDS", 30), 30)
        self.assertEqual(airscope_http.read_env_int({"SECONDS": "invalid"}, "SECONDS", 30), 30)


def current_item(freshness_at: str) -> dict[str, Any]:
    return {
        "session_id": "demo-session",
        "icao24": "86D9A1",
        "callsign": "ANA245",
        "lat": 35.5523,
        "lon": 139.7798,
        "freshness_at": freshness_at,
    }


class CurrentAircraftHttpTests(unittest.TestCase):
    def test_returns_current_aircraft_envelope(self) -> None:
        container = FakeContainer([current_item("2026-06-29T00:59:59.000Z")])

        result = airscope_http.current_aircraft_result(
            {"session_id": "demo-session"},
            container,
            now=datetime(2026, 6, 29, 1, 0, tzinfo=UTC),
        )

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.headers["Cache-Control"], "no-store")
        self.assertEqual(result.payload["session_id"], "demo-session")
        self.assertEqual(result.payload["generated_at"], "2026-06-29T01:00:00.000Z")
        self.assertEqual(result.payload["aircraft"][0]["icao24"], "86D9A1")

    def test_returns_empty_array_as_success(self) -> None:
        result = airscope_http.current_aircraft_result(
            {"session_id": "demo-session"},
            FakeContainer([]),
            now=datetime(2026, 6, 29, 1, 0, tzinfo=UTC),
        )

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.payload["aircraft"], [])

    def test_returns_400_for_missing_or_invalid_session(self) -> None:
        for params in ({}, {"session_id": "../invalid"}):
            with self.subTest(params=params):
                result = airscope_http.current_aircraft_result(
                    params,
                    FakeContainer([]),
                    now=datetime(2026, 6, 29, 1, 0, tzinfo=UTC),
                )

                self.assertEqual(result.status_code, 400)
                self.assertEqual(result.payload["error"]["code"], "invalid_request")

    def test_passes_one_day_thresholds_to_query_logic(self) -> None:
        container = FakeContainer([current_item("2026-06-28T01:00:00.000Z")])

        result = airscope_http.current_aircraft_result(
            {"session_id": "demo-session"},
            container,
            now=datetime(2026, 6, 29, 1, 0, tzinfo=UTC),
        )

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.payload["aircraft"][0]["status"], "current")


class RecentTelemetryHttpTests(unittest.TestCase):
    def test_returns_recent_telemetry_envelope(self) -> None:
        container = FakeContainer(
            [
                {
                    "id": "item-1",
                    "session_id": "demo-session",
                    "telemetry": {"icao24": "86D9A1"},
                    "ingested_at": "2026-06-29T01:00:00.000Z",
                }
            ]
        )

        result = airscope_http.recent_telemetry_result(
            {"session_id": "demo-session", "limit": "25"},
            container,
            generated_at="2026-06-29T01:00:01.000Z",
        )

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.headers["Cache-Control"], "no-store")
        self.assertEqual(result.payload["generated_at"], "2026-06-29T01:00:01.000Z")
        self.assertEqual(result.payload["telemetry"][0]["id"], "item-1")

    def test_returns_400_for_invalid_limits(self) -> None:
        for limit in ("0", "201", "not-a-number"):
            with self.subTest(limit=limit):
                result = airscope_http.recent_telemetry_result(
                    {"session_id": "demo-session", "limit": limit},
                    FakeContainer([]),
                )

                self.assertEqual(result.status_code, 400)
                self.assertEqual(result.payload["error"]["code"], "invalid_request")


class ErrorResponseTests(unittest.TestCase):
    def test_internal_error_does_not_expose_exception_details(self) -> None:
        result = airscope_http.internal_error_result()

        self.assertEqual(result.status_code, 500)
        self.assertEqual(result.headers["Cache-Control"], "no-store")
        self.assertNotIn("Cosmos", str(result.payload))
        self.assertNotIn("key", str(result.payload).lower())


if __name__ == "__main__":
    unittest.main()
