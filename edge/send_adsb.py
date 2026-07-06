#!/usr/bin/env python3
"""Read dump1090-fa aircraft.json and send ADS-B telemetry to Azure IoT Hub.

This is the real edge collector for AirScope. It reads the aircraft snapshot
produced by dump1090-fa from RTL-SDR reception, maps each aircraft to the
AirScope telemetry schema, and sends one message per aircraft to Azure IoT Hub
(or to an HTTP endpoint for local testing).

The dump1090-fa snapshot is read either from a local file
(default `/run/dump1090-fa/aircraft.json`) or from its HTTP JSON feed
(for example `http://localhost:8080/data/aircraft.json`).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

from airscope_telemetry import (
    AircraftTelemetry,
    AzureIoTHubSender,
    HttpSender,
    TelemetrySender,
    build_envelope,
    iso_from_epoch,
    normalize_endpoint,
    utc_now_iso,
)


SCHEMA_VERSION = "airscope.telemetry.dump1090.v1"
SOURCE = "airscope-dump1090"

DEFAULT_SOURCE_FILE = "/run/dump1090-fa/aircraft.json"
DUMP1090_URL_ENV = "AIRSCOPE_DUMP1090_URL"
DUMP1090_FILE_ENV = "AIRSCOPE_DUMP1090_FILE"
HTTP_ENDPOINT_ENV = "AIRSCOPE_HTTP_ENDPOINT"
IOTHUB_CONNECTION_STRING_ENV = "AIRSCOPE_IOTHUB_DEVICE_CONNECTION_STRING"
RECEIVER_ID_ENV = "AIRSCOPE_RECEIVER_ID"
RECEIVER_LAT_ENV = "AIRSCOPE_RECEIVER_LAT"
RECEIVER_LON_ENV = "AIRSCOPE_RECEIVER_LON"

DEFAULT_TRANSPORT = "azure-iot-hub"
EARTH_RADIUS_KM = 6371.0088


def read_aircraft_document(
    source_url: str | None,
    source_file: str,
    timeout: float,
) -> dict[str, Any]:
    """Load one dump1090-fa aircraft.json snapshot from HTTP or a local file."""

    if source_url:
        request = urllib.request.Request(
            source_url,
            method="GET",
            headers={"User-Agent": "AirScope-edge-sender/0.1"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    else:
        with open(source_file, "rb") as handle:
            raw = handle.read()

    document = json.loads(raw.decode("utf-8"))
    if not isinstance(document, dict):
        raise ValueError("dump1090 aircraft.json must be a JSON object")
    return document


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _altitude_ft(entry: dict[str, Any]) -> int | None:
    for key in ("alt_baro", "alt_geom"):
        value = entry.get(key)
        if value == "ground":
            return 0
        number = _as_number(value)
        if number is not None:
            return int(round(number))
    return None


def _vertical_rate_fpm(entry: dict[str, Any]) -> int | None:
    for key in ("baro_rate", "geom_rate"):
        number = _as_number(entry.get(key))
        if number is not None:
            return int(round(number))
    return None


def _round_int(value: Any) -> int | None:
    number = _as_number(value)
    return int(round(number)) if number is not None else None


def _callsign(entry: dict[str, Any]) -> str | None:
    flight = entry.get("flight")
    if not isinstance(flight, str):
        return None
    stripped = flight.strip()
    return stripped or None


def _squawk(entry: dict[str, Any]) -> str | None:
    squawk = entry.get("squawk")
    if squawk is None:
        return None
    return str(squawk)


def _seen_at(entry: dict[str, Any], doc_now: float | None, received_at: str) -> str:
    """When the aircraft was last heard, derived from dump1090 `now` - `seen`."""

    seen = _as_number(entry.get("seen"))
    if doc_now is not None and seen is not None:
        return iso_from_epoch(doc_now - seen)
    return received_at


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def map_aircraft(
    entry: dict[str, Any],
    doc_now: float | None,
    receiver_id: str,
    received_at: str,
    receiver_lat: float | None = None,
    receiver_lon: float | None = None,
) -> AircraftTelemetry | None:
    """Map one dump1090-fa aircraft entry to AirScope telemetry.

    Returns None when the entry has no usable ICAO 24-bit address.
    """

    hex_id = entry.get("hex")
    if not isinstance(hex_id, str):
        return None
    # dump1090 marks non-ICAO (TIS-B / anonymous) addresses with a leading "~".
    icao24 = hex_id.strip().lstrip("~").upper()
    if not icao24:
        return None

    lat = _as_number(entry.get("lat"))
    lon = _as_number(entry.get("lon"))

    distance_km: float | None = None
    if (
        lat is not None
        and lon is not None
        and receiver_lat is not None
        and receiver_lon is not None
    ):
        distance_km = round(haversine_km(receiver_lat, receiver_lon, lat, lon), 1)

    return AircraftTelemetry(
        icao24=icao24,
        callsign=_callsign(entry),
        lat=lat,
        lon=lon,
        altitude_ft=_altitude_ft(entry),
        ground_speed_kt=_round_int(entry.get("gs")),
        track_deg=_round_int(entry.get("track")),
        vertical_rate_fpm=_vertical_rate_fpm(entry),
        squawk=_squawk(entry),
        seen_at=_seen_at(entry, doc_now, received_at),
        received_at=received_at,
        receiver_id=receiver_id,
        distance_km=distance_km,
    )


def build_fleet(
    document: dict[str, Any],
    received_at: str,
    receiver_id: str,
    receiver_lat: float | None,
    receiver_lon: float | None,
    require_position: bool,
) -> list[AircraftTelemetry]:
    doc_now = _as_number(document.get("now"))
    aircraft = document.get("aircraft")
    if not isinstance(aircraft, list):
        return []

    fleet: list[AircraftTelemetry] = []
    for entry in aircraft:
        if not isinstance(entry, dict):
            continue
        telemetry = map_aircraft(
            entry,
            doc_now,
            receiver_id,
            received_at,
            receiver_lat=receiver_lat,
            receiver_lon=receiver_lon,
        )
        if telemetry is None:
            continue
        if require_position and (telemetry.lat is None or telemetry.lon is None):
            continue
        fleet.append(telemetry)
    return fleet


def build_payload(telemetry: AircraftTelemetry, session_id: str) -> dict[str, Any]:
    return build_envelope(telemetry, session_id, SCHEMA_VERSION, SOURCE)


def _env_float(name: str) -> float | None:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send dump1090-fa ADS-B telemetry to Azure IoT Hub or HTTP.",
    )
    parser.add_argument(
        "--transport",
        choices=("azure-iot-hub", "http"),
        default=DEFAULT_TRANSPORT,
        help="Destination transport. Default sends to Azure IoT Hub.",
    )
    parser.add_argument(
        "--source-url",
        default=os.getenv(DUMP1090_URL_ENV),
        help=(
            "dump1090-fa aircraft.json HTTP URL, e.g. "
            "http://localhost:8080/data/aircraft.json. "
            f"Can also be set with {DUMP1090_URL_ENV}."
        ),
    )
    parser.add_argument(
        "--source-file",
        default=os.getenv(DUMP1090_FILE_ENV, DEFAULT_SOURCE_FILE),
        help=(
            "dump1090-fa aircraft.json file path. Used when --source-url is not set. "
            f"Can also be set with {DUMP1090_FILE_ENV}. Default: {DEFAULT_SOURCE_FILE}."
        ),
    )
    parser.add_argument(
        "--endpoint",
        default=os.getenv(HTTP_ENDPOINT_ENV),
        help=f"HTTP destination URL or IP. Can also be set with {HTTP_ENDPOINT_ENV}.",
    )
    parser.add_argument(
        "--iothub-connection-string",
        default=os.getenv(IOTHUB_CONNECTION_STRING_ENV),
        help=(
            "Azure IoT Hub device connection string. Can also be set with "
            f"{IOTHUB_CONNECTION_STRING_ENV}."
        ),
    )
    parser.add_argument(
        "--receiver-id",
        default=os.getenv(RECEIVER_ID_ENV, "airscope-rpi"),
        help="Receiver identifier included in payloads. Do not use personal data.",
    )
    parser.add_argument(
        "--receiver-lat",
        type=float,
        default=_env_float(RECEIVER_LAT_ENV),
        help=(
            "Receiver latitude for distance_km estimation. "
            f"Can also be set with {RECEIVER_LAT_ENV}."
        ),
    )
    parser.add_argument(
        "--receiver-lon",
        type=float,
        default=_env_float(RECEIVER_LON_ENV),
        help=(
            "Receiver longitude for distance_km estimation. "
            f"Can also be set with {RECEIVER_LON_ENV}."
        ),
    )
    parser.add_argument(
        "--session-id",
        default=f"live-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}",
        help="Session identifier included in payloads.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Number of poll cycles to run. Ignored when --follow is used.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Seconds to wait between poll cycles.",
    )
    parser.add_argument(
        "--follow",
        action="store_true",
        help="Keep polling until interrupted (Ctrl-C). Overrides --count.",
    )
    parser.add_argument(
        "--require-position",
        action="store_true",
        help="Only send aircraft that report a latitude and longitude.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="HTTP request timeout in seconds (source read and HTTP transport).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print payloads without sending them.",
    )

    args = parser.parse_args(argv)
    if args.count < 1:
        parser.error("--count must be 1 or greater")
    if args.interval < 0:
        parser.error("--interval must be 0 or greater")
    if args.timeout <= 0:
        parser.error("--timeout must be greater than 0")
    if not args.dry_run and args.transport == "http" and not args.endpoint:
        parser.error(f"--endpoint or {HTTP_ENDPOINT_ENV} is required unless --dry-run is used")
    if (
        not args.dry_run
        and args.transport == "azure-iot-hub"
        and not args.iothub_connection_string
    ):
        parser.error(
            "--iothub-connection-string or "
            f"{IOTHUB_CONNECTION_STRING_ENV} is required unless --dry-run is used"
        )
    if (args.receiver_lat is None) != (args.receiver_lon is None):
        parser.error("--receiver-lat and --receiver-lon must be provided together")
    if args.endpoint:
        args.endpoint = normalize_endpoint(args.endpoint)
    return args


def build_sender(args: argparse.Namespace) -> TelemetrySender:
    if args.transport == "http":
        return HttpSender(args.endpoint, args.timeout)
    if args.transport == "azure-iot-hub":
        return AzureIoTHubSender(args.iothub_connection_string)
    raise ValueError(f"unsupported transport: {args.transport}")


def emit_fleet(
    fleet: list[AircraftTelemetry],
    session_id: str,
    sender: TelemetrySender | None,
) -> int:
    sent = 0
    for telemetry in fleet:
        payload = build_payload(telemetry, session_id)
        if sender is None:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            detail = sender.send(payload, telemetry)
            print(f"  {detail}")
        sent += 1
    return sent


def run(args: argparse.Namespace, sender: TelemetrySender | None) -> int:
    cycles = 0
    total_sent = 0
    exit_code = 0

    try:
        while True:
            cycles += 1
            received_at = utc_now_iso()
            try:
                document = read_aircraft_document(
                    args.source_url, args.source_file, args.timeout
                )
            except (OSError, ValueError, urllib.error.URLError) as exc:
                print(f"failed to read dump1090 source: {exc}", file=sys.stderr)
                if not args.follow:
                    return 1
                exit_code = 1
                document = None

            if document is not None:
                fleet = build_fleet(
                    document,
                    received_at,
                    args.receiver_id,
                    args.receiver_lat,
                    args.receiver_lon,
                    args.require_position,
                )
                sent = emit_fleet(fleet, args.session_id, sender)
                total_sent += sent
                print(f"cycle {cycles}: {len(fleet)} aircraft, {sent} message(s) sent")

            if not args.follow and cycles >= args.count:
                break
            if args.interval > 0:
                time.sleep(args.interval)
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)

    print(f"done: {total_sent} message(s) over {cycles} cycle(s)")
    return exit_code


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    sender = None if args.dry_run else build_sender(args)

    try:
        if isinstance(sender, AzureIoTHubSender):
            with sender:
                return run(args, sender)
        return run(args, sender)
    except (RuntimeError, urllib.error.URLError) as exc:
        print(f"failed to send telemetry: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
