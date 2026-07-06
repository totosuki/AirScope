from __future__ import annotations

import argparse
import json
import pathlib
import sys
import unittest
from unittest import mock


EDGE_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EDGE_DIR))

import send_adsb

SAMPLE_PATH = pathlib.Path(__file__).resolve().parent / "sample_aircraft.json"
SAMPLE_DOCUMENT = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))


class MapAircraftTests(unittest.TestCase):
    def test_maps_position_aircraft_fields(self) -> None:
        entry = SAMPLE_DOCUMENT["aircraft"][0]

        telemetry = send_adsb.map_aircraft(
            entry,
            SAMPLE_DOCUMENT["now"],
            receiver_id="receiver-test",
            received_at="2026-07-06T00:00:00.000Z",
        )

        assert telemetry is not None
        self.assertEqual(telemetry.icao24, "86D9A1")
        self.assertEqual(telemetry.callsign, "ANA245")
        self.assertEqual(telemetry.lat, 35.5523)
        self.assertEqual(telemetry.altitude_ft, 12800)
        self.assertEqual(telemetry.ground_speed_kt, 286)
        self.assertEqual(telemetry.track_deg, 72)
        self.assertEqual(telemetry.vertical_rate_fpm, 640)
        self.assertEqual(telemetry.squawk, "3301")
        self.assertEqual(telemetry.receiver_id, "receiver-test")
        # seen_at = document now (1751760000.0) - seen (0.4)
        self.assertEqual(telemetry.seen_at, "2026-07-05T23:59:59.600Z")
        self.assertIsNone(telemetry.distance_km)

    def test_ground_altitude_maps_to_zero(self) -> None:
        entry = SAMPLE_DOCUMENT["aircraft"][1]

        telemetry = send_adsb.map_aircraft(
            entry, SAMPLE_DOCUMENT["now"], "rx", "2026-07-06T00:00:00.000Z"
        )

        assert telemetry is not None
        self.assertEqual(telemetry.altitude_ft, 0)
        self.assertIsNone(telemetry.lat)

    def test_non_icao_prefix_is_stripped(self) -> None:
        entry = SAMPLE_DOCUMENT["aircraft"][2]

        telemetry = send_adsb.map_aircraft(
            entry, SAMPLE_DOCUMENT["now"], "rx", "2026-07-06T00:00:00.000Z"
        )

        assert telemetry is not None
        self.assertEqual(telemetry.icao24, "AB1234")
        # Falls back to alt_geom / geom_rate when barometric values are absent.
        self.assertEqual(telemetry.altitude_ft, 4500)
        self.assertEqual(telemetry.vertical_rate_fpm, -320)

    def test_entry_without_hex_is_skipped(self) -> None:
        entry = SAMPLE_DOCUMENT["aircraft"][3]

        telemetry = send_adsb.map_aircraft(
            entry, SAMPLE_DOCUMENT["now"], "rx", "2026-07-06T00:00:00.000Z"
        )

        self.assertIsNone(telemetry)

    def test_distance_km_uses_receiver_location(self) -> None:
        entry = SAMPLE_DOCUMENT["aircraft"][0]

        telemetry = send_adsb.map_aircraft(
            entry,
            SAMPLE_DOCUMENT["now"],
            "rx",
            "2026-07-06T00:00:00.000Z",
            receiver_lat=35.5,
            receiver_lon=139.78,
        )

        assert telemetry is not None
        assert telemetry.distance_km is not None
        self.assertAlmostEqual(telemetry.distance_km, 5.8, delta=0.5)


class BuildFleetTests(unittest.TestCase):
    def test_build_fleet_skips_hexless_entry(self) -> None:
        fleet = send_adsb.build_fleet(
            SAMPLE_DOCUMENT,
            received_at="2026-07-06T00:00:00.000Z",
            receiver_id="rx",
            receiver_lat=None,
            receiver_lon=None,
            require_position=False,
        )

        # Three of four sample entries carry a hex address.
        self.assertEqual(len(fleet), 3)

    def test_require_position_filters_positionless_aircraft(self) -> None:
        fleet = send_adsb.build_fleet(
            SAMPLE_DOCUMENT,
            received_at="2026-07-06T00:00:00.000Z",
            receiver_id="rx",
            receiver_lat=None,
            receiver_lon=None,
            require_position=True,
        )

        icaos = {t.icao24 for t in fleet}
        self.assertEqual(icaos, {"86D9A1", "AB1234"})


class PayloadTests(unittest.TestCase):
    def test_build_payload_uses_dump1090_schema_and_source(self) -> None:
        telemetry = send_adsb.map_aircraft(
            SAMPLE_DOCUMENT["aircraft"][0],
            SAMPLE_DOCUMENT["now"],
            "rx",
            "2026-07-06T00:00:00.000Z",
        )
        assert telemetry is not None

        payload = send_adsb.build_payload(telemetry, "session-test")

        self.assertEqual(payload["schema_version"], "airscope.telemetry.dump1090.v1")
        self.assertEqual(payload["source"], "airscope-dump1090")
        self.assertEqual(payload["session_id"], "session-test")
        self.assertEqual(payload["telemetry"]["icao24"], "86D9A1")


class SenderSelectionTests(unittest.TestCase):
    def test_build_sender_defaults_to_azure_iot_hub(self) -> None:
        args = argparse.Namespace(
            transport="azure-iot-hub",
            iothub_connection_string="HostName=example.azure-devices.net;DeviceId=d;SharedAccessKey=k",
        )

        sender = send_adsb.build_sender(args)

        self.assertIsInstance(sender, send_adsb.AzureIoTHubSender)

    def test_emit_fleet_sends_each_aircraft(self) -> None:
        fleet = send_adsb.build_fleet(
            SAMPLE_DOCUMENT,
            received_at="2026-07-06T00:00:00.000Z",
            receiver_id="rx",
            receiver_lat=None,
            receiver_lon=None,
            require_position=False,
        )
        sender = mock.Mock()
        sender.send.return_value = "ok"

        sent = send_adsb.emit_fleet(fleet, "session-test", sender)

        self.assertEqual(sent, 3)
        self.assertEqual(sender.send.call_count, 3)


class ReadDocumentTests(unittest.TestCase):
    def test_reads_local_file(self) -> None:
        document = send_adsb.read_aircraft_document(None, str(SAMPLE_PATH), 5.0)

        self.assertIn("aircraft", document)
        self.assertEqual(len(document["aircraft"]), 4)


if __name__ == "__main__":
    unittest.main()
