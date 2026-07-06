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
from datetime import UTC, datetime
from typing import Any

from airscope_telemetry import (
    AircraftTelemetry,
    AzureIoTHubSender,
    HttpSender,
    TelemetrySender,
    build_envelope,
    encode_payload,
    normalize_endpoint,
    post_json,
    utc_now_iso,
)


SCHEMA_VERSION = "airscope.telemetry.demo.v1"
SOURCE = "airscope-demo"
DEFAULT_ENDPOINT_ENV = "AIRSCOPE_HTTP_ENDPOINT"
DEFAULT_IOTHUB_CONNECTION_STRING_ENV = "AIRSCOPE_IOTHUB_DEVICE_CONNECTION_STRING"
DEFAULT_TRANSPORT = "http"

# Backwards-compatible aliases: the demo transport is now the shared transport.
DemoSender = TelemetrySender
HttpDemoSender = HttpSender
AzureIoTHubDemoSender = AzureIoTHubSender


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
    return build_envelope(telemetry, session_id, SCHEMA_VERSION, SOURCE)


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
