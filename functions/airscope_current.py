"""Build AirScope raw telemetry and current aircraft Cosmos DB items."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


DEFAULT_CURRENT_THRESHOLD_SECONDS = 30
DEFAULT_STALE_THRESHOLD_SECONDS = 120


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def freshness_at(payload: dict[str, Any]) -> str | None:
    telemetry = payload.get("telemetry") or {}
    return telemetry.get("seen_at") or telemetry.get("received_at") or payload.get("sent_at")


def aircraft_status(
    freshness: str,
    now: datetime,
    current_threshold_seconds: int = DEFAULT_CURRENT_THRESHOLD_SECONDS,
    stale_threshold_seconds: int = DEFAULT_STALE_THRESHOLD_SECONDS,
) -> str:
    age_seconds = (now - parse_utc(freshness)).total_seconds()
    if age_seconds <= current_threshold_seconds:
        return "current"
    if age_seconds <= stale_threshold_seconds:
        return "stale"
    return "expired"


def build_raw_item(payload: dict[str, Any], ingested_at: str | None = None) -> dict[str, Any]:
    telemetry = payload.get("telemetry") or {}
    timestamp = telemetry.get("received_at") or payload.get("sent_at") or ingested_at or utc_now_iso()
    session_id = payload.get("session_id") or "unknown-session"
    icao24 = telemetry.get("icao24") or "unknown-icao24"

    return {
        **payload,
        "id": f"{session_id}:{icao24}:{timestamp}:{uuid4().hex}",
        "ingested_at": ingested_at or utc_now_iso(),
    }


def build_current_item(
    payload: dict[str, Any],
    updated_at: str | None = None,
    now: datetime | None = None,
    current_threshold_seconds: int = DEFAULT_CURRENT_THRESHOLD_SECONDS,
    stale_threshold_seconds: int = DEFAULT_STALE_THRESHOLD_SECONDS,
) -> dict[str, Any] | None:
    telemetry = payload.get("telemetry") or {}
    session_id = payload.get("session_id")
    icao24 = telemetry.get("icao24")
    freshness = freshness_at(payload)

    if not session_id or not icao24 or not freshness:
        return None
    if telemetry.get("lat") is None or telemetry.get("lon") is None:
        return None

    effective_now = now or datetime.now(UTC)
    return {
        "id": f"{session_id}:{icao24}",
        "session_id": session_id,
        "icao24": icao24,
        "callsign": telemetry.get("callsign"),
        "lat": telemetry.get("lat"),
        "lon": telemetry.get("lon"),
        "altitude_ft": telemetry.get("altitude_ft"),
        "ground_speed_kt": telemetry.get("ground_speed_kt"),
        "track_deg": telemetry.get("track_deg"),
        "vertical_rate_fpm": telemetry.get("vertical_rate_fpm"),
        "squawk": telemetry.get("squawk"),
        "seen_at": telemetry.get("seen_at"),
        "received_at": telemetry.get("received_at"),
        "freshness_at": freshness,
        "receiver_id": telemetry.get("receiver_id"),
        "distance_km": telemetry.get("distance_km"),
        "status": aircraft_status(
            freshness,
            effective_now,
            current_threshold_seconds=current_threshold_seconds,
            stale_threshold_seconds=stale_threshold_seconds,
        ),
        "updated_at": updated_at or utc_now_iso(),
    }


def should_update_current(existing: dict[str, Any] | None, candidate: dict[str, Any]) -> bool:
    if existing is None:
        return True

    existing_freshness = existing.get("freshness_at")
    candidate_freshness = candidate.get("freshness_at")
    if not existing_freshness or not candidate_freshness:
        return True

    return parse_utc(candidate_freshness) > parse_utc(existing_freshness)
