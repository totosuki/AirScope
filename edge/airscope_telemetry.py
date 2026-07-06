#!/usr/bin/env python3
"""Shared AirScope edge telemetry envelope and transport.

This module holds the pieces that both the demo sender (`send_demo_adsb.py`)
and the real dump1090-fa sender (`send_adsb.py`) reuse: the telemetry
dataclass, the payload envelope, and the HTTP / Azure IoT Hub senders.

Keeping a single transport layer means the payload sent from real ADS-B data
is byte-for-byte compatible with the demo payload that the Azure Functions
ingestion already consumes.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class AircraftTelemetry:
    """One aircraft observation, matching the Cosmos DB telemetry schema."""

    icao24: str
    callsign: str | None
    lat: float | None
    lon: float | None
    altitude_ft: int | None
    ground_speed_kt: int | None
    track_deg: int | None
    vertical_rate_fpm: int | None
    squawk: str | None
    seen_at: str
    received_at: str
    receiver_id: str
    distance_km: float | None


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def iso_from_epoch(epoch_seconds: float) -> str:
    return (
        datetime.fromtimestamp(epoch_seconds, tz=UTC)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def normalize_endpoint(endpoint: str) -> str:
    parsed = urllib.parse.urlparse(endpoint)
    if parsed.scheme:
        return endpoint
    return f"http://{endpoint}"


def build_envelope(
    telemetry: AircraftTelemetry,
    session_id: str,
    schema_version: str,
    source: str,
    sent_at: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": schema_version,
        "source": source,
        "session_id": session_id,
        "sent_at": sent_at or utc_now_iso(),
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
            "User-Agent": "AirScope-edge-sender/0.1",
        },
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        response.read()
        return response.status


class TelemetrySender:
    """Base transport. Subclasses deliver one payload per aircraft."""

    def send(self, payload: dict[str, Any], telemetry: AircraftTelemetry) -> str:
        raise NotImplementedError


class HttpSender(TelemetrySender):
    def __init__(self, endpoint: str, timeout: float) -> None:
        self.endpoint = endpoint
        self.timeout = timeout

    def send(self, payload: dict[str, Any], telemetry: AircraftTelemetry) -> str:
        status = post_json(self.endpoint, payload, self.timeout)
        return f"{telemetry.icao24} {telemetry.callsign} -> {self.endpoint} status={status}"


class AzureIoTHubSender(TelemetrySender):
    def __init__(self, connection_string: str) -> None:
        self.connection_string = connection_string
        self._client: Any | None = None
        self._message_type: Any | None = None

    def __enter__(self) -> "AzureIoTHubSender":
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
