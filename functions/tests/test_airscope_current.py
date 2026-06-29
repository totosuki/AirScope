from __future__ import annotations

from datetime import UTC, datetime, timedelta
import pathlib
import sys
import unittest


FUNCTIONS_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FUNCTIONS_DIR))

import airscope_current


def demo_payload(seen_at: str = "2026-06-15T00:00:00.000Z") -> dict:
    return {
        "schema_version": "airscope.telemetry.demo.v1",
        "source": "airscope-demo",
        "session_id": "demo-session",
        "sent_at": "2026-06-15T00:00:01.000Z",
        "telemetry": {
            "icao24": "86D9A1",
            "callsign": "ANA245",
            "lat": 35.5523,
            "lon": 139.7798,
            "altitude_ft": 12800,
            "ground_speed_kt": 286,
            "track_deg": 72,
            "vertical_rate_fpm": 640,
            "squawk": "3301",
            "seen_at": seen_at,
            "received_at": "2026-06-15T00:00:01.000Z",
            "receiver_id": "airscope-demo-rpi",
            "distance_km": 18.4,
        },
    }


class CurrentAircraftTests(unittest.TestCase):
    def test_build_current_item_uses_session_and_icao_fixed_id(self) -> None:
        payload = demo_payload()
        item = airscope_current.build_current_item(
            payload,
            updated_at="2026-06-15T00:00:02.000Z",
            now=datetime(2026, 6, 15, 0, 0, 10, tzinfo=UTC),
        )

        self.assertIsNotNone(item)
        assert item is not None
        self.assertEqual(item["id"], "demo-session:86D9A1")
        self.assertEqual(item["session_id"], "demo-session")
        self.assertEqual(item["icao24"], "86D9A1")
        self.assertEqual(item["freshness_at"], "2026-06-15T00:00:00.000Z")
        self.assertEqual(item["status"], "current")

    def test_build_current_item_skips_payload_without_position(self) -> None:
        payload = demo_payload()
        payload["telemetry"]["lat"] = None

        item = airscope_current.build_current_item(payload)

        self.assertIsNone(item)

    def test_aircraft_status_marks_stale_and_expired(self) -> None:
        freshness = "2026-06-15T00:00:00.000Z"

        self.assertEqual(
            airscope_current.aircraft_status(
                freshness,
                datetime(2026, 6, 15, 0, 0, 31, tzinfo=UTC),
                current_threshold_seconds=30,
                stale_threshold_seconds=120,
            ),
            "stale",
        )
        self.assertEqual(
            airscope_current.aircraft_status(
                freshness,
                datetime(2026, 6, 15, 0, 2, 1, tzinfo=UTC),
                current_threshold_seconds=30,
                stale_threshold_seconds=120,
            ),
            "expired",
        )

    def test_default_status_keeps_aircraft_current_for_one_day(self) -> None:
        freshness = "2026-06-15T00:00:00.000Z"

        self.assertEqual(
            airscope_current.aircraft_status(
                freshness,
                datetime(2026, 6, 16, 0, 0, tzinfo=UTC),
            ),
            "current",
        )
        self.assertEqual(
            airscope_current.aircraft_status(
                freshness,
                datetime(2026, 6, 16, 0, 0, 1, tzinfo=UTC),
            ),
            "expired",
        )

    def test_should_update_current_only_accepts_newer_freshness(self) -> None:
        existing = {"freshness_at": "2026-06-15T00:00:20.000Z"}
        older = {"freshness_at": "2026-06-15T00:00:10.000Z"}
        newer = {"freshness_at": "2026-06-15T00:00:30.000Z"}

        self.assertFalse(airscope_current.should_update_current(existing, older))
        self.assertTrue(airscope_current.should_update_current(existing, newer))
        self.assertTrue(airscope_current.should_update_current(None, older))

    def test_build_raw_item_has_unique_id_and_ingested_at(self) -> None:
        payload = demo_payload()
        item_a = airscope_current.build_raw_item(payload, ingested_at="2026-06-15T00:00:02.000Z")
        item_b = airscope_current.build_raw_item(payload, ingested_at="2026-06-15T00:00:02.000Z")

        self.assertNotEqual(item_a["id"], item_b["id"])
        self.assertEqual(item_a["ingested_at"], "2026-06-15T00:00:02.000Z")
        self.assertEqual(item_a["telemetry"]["icao24"], "86D9A1")


if __name__ == "__main__":
    unittest.main()
