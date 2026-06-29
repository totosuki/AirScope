"""Read and shape AirScope aircraft data from Cosmos DB containers."""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any, Protocol

from airscope_current import (
    DEFAULT_CURRENT_THRESHOLD_SECONDS,
    DEFAULT_STALE_THRESHOLD_SECONDS,
    aircraft_status,
)


DEFAULT_TELEMETRY_LIMIT = 50
MAX_TELEMETRY_LIMIT = 200
SESSION_ID_MAX_LENGTH = 128

_SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")

_CURRENT_AIRCRAFT_FIELDS = (
    "icao24",
    "callsign",
    "lat",
    "lon",
    "altitude_ft",
    "ground_speed_kt",
    "track_deg",
    "vertical_rate_fpm",
    "squawk",
    "seen_at",
    "received_at",
    "freshness_at",
    "receiver_id",
    "distance_km",
)

_TELEMETRY_FIELDS = (
    "id",
    "schema_version",
    "source",
    "session_id",
    "sent_at",
    "telemetry",
    "ingested_at",
)


class QueryableContainer(Protocol):
    """Subset of the Cosmos ContainerProxy interface used by this module."""

    def query_items(
        self,
        query: str,
        parameters: list[dict[str, Any]],
        partition_key: str,
    ) -> Iterable[dict[str, Any]]: ...


def validate_session_id(value: str | None) -> str:
    """Return a valid session ID or raise ValueError for an API-safe bad request."""

    if value is None:
        raise ValueError("session_id is required")

    session_id = value.strip()
    if not session_id:
        raise ValueError("session_id is required")
    if len(session_id) > SESSION_ID_MAX_LENGTH:
        raise ValueError(f"session_id must be at most {SESSION_ID_MAX_LENGTH} characters")
    if _SESSION_ID_PATTERN.fullmatch(session_id) is None:
        raise ValueError("session_id contains unsupported characters")
    return session_id


def validate_telemetry_limit(value: int | str | None) -> int:
    """Return a bounded telemetry page size."""

    if value is None or value == "":
        return DEFAULT_TELEMETRY_LIMIT
    if isinstance(value, bool):
        raise ValueError("limit must be an integer")

    try:
        limit = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("limit must be an integer") from exc

    if limit < 1 or limit > MAX_TELEMETRY_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_TELEMETRY_LIMIT}")
    return limit


def read_current_aircraft(
    container: QueryableContainer,
    session_id: str | None,
    *,
    now: datetime | None = None,
    current_threshold_seconds: int = DEFAULT_CURRENT_THRESHOLD_SECONDS,
    stale_threshold_seconds: int = DEFAULT_STALE_THRESHOLD_SECONDS,
) -> list[dict[str, Any]]:
    """Read displayable aircraft for one session and recompute their freshness."""

    validated_session_id = validate_session_id(session_id)
    effective_now = now or datetime.now(UTC)
    if effective_now.tzinfo is None:
        raise ValueError("now must include timezone information")

    items = container.query_items(
        query="SELECT * FROM c WHERE c.session_id = @session_id",
        parameters=[{"name": "@session_id", "value": validated_session_id}],
        partition_key=validated_session_id,
    )

    aircraft: list[dict[str, Any]] = []
    for item in items:
        freshness = item.get("freshness_at")
        if not isinstance(freshness, str) or not freshness:
            continue
        try:
            status = aircraft_status(
                freshness,
                effective_now,
                current_threshold_seconds=current_threshold_seconds,
                stale_threshold_seconds=stale_threshold_seconds,
            )
        except (TypeError, ValueError):
            continue
        if status == "expired":
            continue

        shaped = {field: item.get(field) for field in _CURRENT_AIRCRAFT_FIELDS}
        shaped["status"] = status
        aircraft.append(shaped)

    aircraft.sort(key=lambda item: item["freshness_at"], reverse=True)
    return aircraft


def read_recent_telemetry(
    container: QueryableContainer,
    session_id: str | None,
    *,
    limit: int | str | None = None,
) -> list[dict[str, Any]]:
    """Read a bounded newest-first telemetry page for one session."""

    validated_session_id = validate_session_id(session_id)
    validated_limit = validate_telemetry_limit(limit)
    items = container.query_items(
        query=(
            "SELECT TOP @limit * FROM c "
            "WHERE c.session_id = @session_id ORDER BY c.ingested_at DESC"
        ),
        parameters=[
            {"name": "@limit", "value": validated_limit},
            {"name": "@session_id", "value": validated_session_id},
        ],
        partition_key=validated_session_id,
    )
    return [{field: item.get(field) for field in _TELEMETRY_FIELDS} for item in items]
