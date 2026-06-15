#!/usr/bin/env python3
"""Send demo ADS-B-like telemetry to HTTP or Azure IoT Hub.

This script does not require dump1090-fa or RTL-SDR hardware. It creates
plausible demo aircraft telemetry and sends it for early pipeline tests.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any


SCHEMA_VERSION = "airscope.telemetry.demo.v1"
DEFAULT_ENDPOINT_ENV = "AIRSCOPE_HTTP_ENDPOINT"
DEFAULT_IOTHUB_CONNECTION_STRING_ENV = "AIRSCOPE_IOTHUB_DEVICE_CONNECTION_STRING"
DEFAULT_TRANSPORT = "http"


@dataclass(frozen=True)
class AircraftTelemetry:
    icao24: str
    callsign: str
    lat: float
    lon: float
    altitude_ft: int
    ground_speed_kt: int
    track_deg: int
    vertical_rate_fpm: int
    squawk: str
    seen_at: str
    received_at: str
    receiver_id: str
    distance_km: float


DEMO_AIRCRAFT = [
    {
        "icao24": "86D9A1",
        "callsign": "ANA245",
        "lat": 35.5523,
        "lon": 139.7798,
        "altitude_ft": 12800,
        "ground_speed_kt": 286,
        "track_deg": 72,
        "vertical_rate_fpm": 640,
        "squawk": "3301",
        "distance_km": 18.4,
    },
    {
        "icao24": "84B7C2",
        "callsign": "JAL516",
        "lat": 35.7061,
        "lon": 139.8642,
        "altitude_ft": 23100,
        "ground_speed_kt": 421,
        "track_deg": 212,
        "vertical_rate_fpm": -320,
        "squawk": "2204",
        "distance_km": 33.8,
    },
    {
        "icao24": "8990F3",
        "callsign": "SIA632",
        "lat": 35.4217,
        "lon": 140.0514,
        "altitude_ft": 34750,
        "ground_speed_kt": 474,
        "track_deg": 315,
        "vertical_rate_fpm": 0,
        "squawk": "5542",
        "distance_km": 54.1,
    },
]


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def normalize_endpoint(endpoint: str) -> str:
    parsed = urllib.parse.urlparse(endpoint)
    if parsed.scheme:
        return endpoint
    return f"http://{endpoint}"


def build_telemetry(index: int, receiver_id: str) -> AircraftTelemetry:
    base = DEMO_AIRCRAFT[index % len(DEMO_AIRCRAFT)]
    lap = index // len(DEMO_AIRCRAFT)
    timestamp = utc_now_iso()

    # Move each demo aircraft slightly so receivers can verify changing payloads.
    lat_offset = 0.012 * lap
    lon_offset = 0.018 * lap
    speed_offset = (index % 4) * 3

    return AircraftTelemetry(
        icao24=base["icao24"],
        callsign=base["callsign"],
        lat=round(float(base["lat"]) + lat_offset, 6),
        lon=round(float(base["lon"]) + lon_offset, 6),
        altitude_ft=int(base["altitude_ft"]) + (lap * 250),
        ground_speed_kt=int(base["ground_speed_kt"]) + speed_offset,
        track_deg=(int(base["track_deg"]) + lap * 2) % 360,
        vertical_rate_fpm=int(base["vertical_rate_fpm"]),
        squawk=str(base["squawk"]),
        seen_at=timestamp,
        received_at=timestamp,
        receiver_id=receiver_id,
        distance_km=round(float(base["distance_km"]) + lap * 1.7, 1),
    )


def build_payload(telemetry: AircraftTelemetry, session_id: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "source": "airscope-demo",
        "session_id": session_id,
        "sent_at": utc_now_iso(),
        "telemetry": asdict(telemetry),
    }


def encode_payload(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def post_json(endpoint: str, payload: dict[str, Any], timeout: float) -> int:
    body = encode_payload(payload)
    request = urllib.request.Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "AirScope-demo-sender/0.1",
        },
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        response.read()
        return response.status


class DemoSender:
    def send(self, payload: dict[str, Any], telemetry: AircraftTelemetry) -> str:
        raise NotImplementedError


class HttpDemoSender(DemoSender):
    def __init__(self, endpoint: str, timeout: float) -> None:
        self.endpoint = endpoint
        self.timeout = timeout

    def send(self, payload: dict[str, Any], telemetry: AircraftTelemetry) -> str:
        status = post_json(self.endpoint, payload, self.timeout)
        return f"{telemetry.icao24} {telemetry.callsign} -> {self.endpoint} status={status}"


class AzureIoTHubDemoSender(DemoSender):
    def __init__(self, connection_string: str) -> None:
        self.connection_string = connection_string
        self._client: Any | None = None
        self._message_type: Any | None = None

    def __enter__(self) -> "AzureIoTHubDemoSender":
        try:
            from azure.iot.device import IoTHubDeviceClient, Message
        except ImportError as exc:
            raise RuntimeError(
                "Azure IoT Hub transport requires the 'azure-iot-device' package. "
                "Install edge dependencies before using --transport azure-iot-hub."
            ) from exc

        self._message_type = Message
        self._client = IoTHubDeviceClient.create_from_connection_string(self.connection_string)
        self._client.connect()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self._client is not None:
            self._client.disconnect()

    def send(self, payload: dict[str, Any], telemetry: AircraftTelemetry) -> str:
        if self._client is None or self._message_type is None:
            raise RuntimeError("Azure IoT Hub sender is not connected")

        message = self._message_type(encode_payload(payload))
        message.content_type = "application/json"
        message.content_encoding = "utf-8"
        message.custom_properties["schema_version"] = str(payload["schema_version"])
        message.custom_properties["source"] = str(payload["source"])
        message.custom_properties["session_id"] = str(payload["session_id"])
        message.custom_properties["receiver_id"] = telemetry.receiver_id
        self._client.send_message(message)
        return f"{telemetry.icao24} {telemetry.callsign} -> azure-iot-hub"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send demo ADS-B-like telemetry to HTTP or Azure IoT Hub.",
    )
    parser.add_argument(
        "--transport",
        choices=("http", "azure-iot-hub"),
        default=DEFAULT_TRANSPORT,
        help="Destination transport. Use http for local endpoints or azure-iot-hub for IoT Hub.",
    )
    parser.add_argument(
        "--endpoint",
        default=os.getenv(DEFAULT_ENDPOINT_ENV),
        help=f"HTTP destination URL or IP. Can also be set with {DEFAULT_ENDPOINT_ENV}.",
    )
    parser.add_argument(
        "--iothub-connection-string",
        default=os.getenv(DEFAULT_IOTHUB_CONNECTION_STRING_ENV),
        help=(
            "Azure IoT Hub device connection string. Can also be set with "
            f"{DEFAULT_IOTHUB_CONNECTION_STRING_ENV}."
        ),
    )
    parser.add_argument(
        "--count",
        type=int,
        default=5,
        help="Number of demo telemetry messages to send.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Seconds to wait between messages.",
    )
    parser.add_argument(
        "--receiver-id",
        default="airscope-demo-rpi",
        help="Receiver identifier included in payloads.",
    )
    parser.add_argument(
        "--session-id",
        default=f"demo-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}",
        help="Session identifier included in payloads.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="HTTP request timeout in seconds.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print payloads without sending HTTP requests.",
    )

    args = parser.parse_args()
    if args.count < 1:
        parser.error("--count must be 1 or greater")
    if args.interval < 0:
        parser.error("--interval must be 0 or greater")
    if args.timeout <= 0:
        parser.error("--timeout must be greater than 0")
    if not args.dry_run and args.transport == "http" and not args.endpoint:
        parser.error(f"--endpoint or {DEFAULT_ENDPOINT_ENV} is required unless --dry-run is used")
    if (
        not args.dry_run
        and args.transport == "azure-iot-hub"
        and not args.iothub_connection_string
    ):
        parser.error(
            "--iothub-connection-string or "
            f"{DEFAULT_IOTHUB_CONNECTION_STRING_ENV} is required unless --dry-run is used"
        )
    if args.endpoint:
        args.endpoint = normalize_endpoint(args.endpoint)
    return args


def build_sender(args: argparse.Namespace) -> DemoSender:
    if args.transport == "http":
        return HttpDemoSender(args.endpoint, args.timeout)
    if args.transport == "azure-iot-hub":
        return AzureIoTHubDemoSender(args.iothub_connection_string)
    raise ValueError(f"unsupported transport: {args.transport}")


def main() -> int:
    args = parse_args()
    sender = None if args.dry_run else build_sender(args)

    try:
        if isinstance(sender, AzureIoTHubDemoSender):
            with sender:
                return send_payloads(args, sender)
        return send_payloads(args, sender)
    except (RuntimeError, urllib.error.URLError) as exc:
        print(f"failed to send demo telemetry: {exc}", file=sys.stderr)
        return 1


def send_payloads(args: argparse.Namespace, sender: DemoSender | None) -> int:
    for index in range(args.count):
        telemetry = build_telemetry(index, args.receiver_id)
        payload = build_payload(telemetry, args.session_id)

        if sender is None:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            detail = sender.send(payload, telemetry)
            print(f"sent {index + 1}/{args.count} {detail}")

        if index < args.count - 1 and args.interval > 0:
            time.sleep(args.interval)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
