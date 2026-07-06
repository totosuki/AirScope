from __future__ import annotations

import argparse
import json
import pathlib
import sys
import unittest
from unittest import mock


EDGE_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EDGE_DIR))

import send_demo_adsb


class DemoPayloadTests(unittest.TestCase):
    def test_build_payload_contains_expected_schema_and_telemetry(self) -> None:
        telemetry = send_demo_adsb.build_telemetry(0, "receiver-test")
        payload = send_demo_adsb.build_payload(telemetry, "session-test")

        self.assertEqual(payload["schema_version"], send_demo_adsb.SCHEMA_VERSION)
        self.assertEqual(payload["source"], "airscope-demo")
        self.assertEqual(payload["session_id"], "session-test")
        self.assertEqual(payload["telemetry"]["receiver_id"], "receiver-test")
        self.assertEqual(payload["telemetry"]["icao24"], "86D9A1")

    def test_encode_payload_outputs_compact_json_bytes(self) -> None:
        encoded = send_demo_adsb.encode_payload({"message": "ok"})

        self.assertIsInstance(encoded, bytes)
        self.assertEqual(json.loads(encoded.decode("utf-8")), {"message": "ok"})


class SenderTests(unittest.TestCase):
    def test_http_sender_posts_payload(self) -> None:
        telemetry = send_demo_adsb.build_telemetry(0, "receiver-test")
        payload = send_demo_adsb.build_payload(telemetry, "session-test")

        with mock.patch("airscope_telemetry.post_json", return_value=202) as post_json:
            sender = send_demo_adsb.HttpDemoSender("http://127.0.0.1:8080/telemetry", 3.0)
            result = sender.send(payload, telemetry)

        post_json.assert_called_once_with("http://127.0.0.1:8080/telemetry", payload, 3.0)
        self.assertIn("status=202", result)

    def test_build_sender_uses_azure_iot_hub_connection_string(self) -> None:
        args = argparse.Namespace(
            transport="azure-iot-hub",
            iothub_connection_string="HostName=example.azure-devices.net;DeviceId=device;SharedAccessKey=key",
        )

        sender = send_demo_adsb.build_sender(args)

        self.assertIsInstance(sender, send_demo_adsb.AzureIoTHubDemoSender)
        self.assertEqual(sender.connection_string, args.iothub_connection_string)

    def test_azure_sender_builds_message_with_custom_properties(self) -> None:
        telemetry = send_demo_adsb.build_telemetry(0, "receiver-test")
        payload = send_demo_adsb.build_payload(telemetry, "session-test")
        client = mock.Mock()
        message = mock.Mock()
        message.custom_properties = {}
        sender = send_demo_adsb.AzureIoTHubDemoSender("connection-string")
        sender._client = client
        sender._message_type = mock.Mock(return_value=message)

        result = sender.send(payload, telemetry)

        sender._message_type.assert_called_once()
        client.send_message.assert_called_once_with(message)
        self.assertEqual(message.content_type, "application/json")
        self.assertEqual(message.content_encoding, "utf-8")
        self.assertEqual(message.custom_properties["schema_version"], send_demo_adsb.SCHEMA_VERSION)
        self.assertEqual(message.custom_properties["session_id"], "session-test")
        self.assertEqual(message.custom_properties["receiver_id"], "receiver-test")
        self.assertIn("azure-iot-hub", result)


if __name__ == "__main__":
    unittest.main()
