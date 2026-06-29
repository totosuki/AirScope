"""Azure Functions-independent HTTP response logic for AirScope read APIs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import logging
from typing import Any, Mapping

from airscope_current import (
    DEFAULT_CURRENT_THRESHOLD_SECONDS,
    DEFAULT_STALE_THRESHOLD_SECONDS,
    utc_now_iso,
)
from airscope_query import read_current_aircraft, read_recent_telemetry, validate_session_id


NO_STORE_HEADERS = {"Cache-Control": "no-store"}


@dataclass(frozen=True)
class ApiResult:
    status_code: int
    payload: dict[str, Any]
    headers: dict[str, str]


def read_env_int(environ: Mapping[str, str], name: str, default: int) -> int:
    """Read an integer setting while preserving a safe application default."""

    value = environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        logging.warning("Invalid integer app setting %s=%r. Using %s.", name, value, default)
        return default


def _success(payload: dict[str, Any]) -> ApiResult:
    return ApiResult(status_code=200, payload=payload, headers=NO_STORE_HEADERS.copy())


def _bad_request(message: str) -> ApiResult:
    return ApiResult(
        status_code=400,
        payload={"error": {"code": "invalid_request", "message": message}},
        headers=NO_STORE_HEADERS.copy(),
    )


def internal_error_result() -> ApiResult:
    """Return a client-safe response without leaking the underlying exception."""

    return ApiResult(
        status_code=500,
        payload={
            "error": {
                "code": "internal_error",
                "message": "The request could not be completed.",
            }
        },
        headers=NO_STORE_HEADERS.copy(),
    )


def current_aircraft_result(
    params: Mapping[str, str],
    container: Any,
    *,
    now: datetime | None = None,
    current_threshold_seconds: int = DEFAULT_CURRENT_THRESHOLD_SECONDS,
    stale_threshold_seconds: int = DEFAULT_STALE_THRESHOLD_SECONDS,
) -> ApiResult:
    """Build the current-aircraft API result from request query parameters."""

    effective_now = now or datetime.now(UTC)
    try:
        session_id = validate_session_id(params.get("session_id"))
        aircraft = read_current_aircraft(
            container,
            session_id,
            now=effective_now,
            current_threshold_seconds=current_threshold_seconds,
            stale_threshold_seconds=stale_threshold_seconds,
        )
    except ValueError as exc:
        return _bad_request(str(exc))

    return _success(
        {
            "session_id": session_id,
            "generated_at": _iso_utc(effective_now),
            "aircraft": aircraft,
        }
    )


def recent_telemetry_result(
    params: Mapping[str, str],
    container: Any,
    *,
    generated_at: str | None = None,
) -> ApiResult:
    """Build the recent-telemetry API result from request query parameters."""

    try:
        session_id = validate_session_id(params.get("session_id"))
        telemetry = read_recent_telemetry(
            container,
            session_id,
            limit=params.get("limit"),
        )
    except ValueError as exc:
        return _bad_request(str(exc))

    return _success(
        {
            "session_id": session_id,
            "generated_at": generated_at or utc_now_iso(),
            "telemetry": telemetry,
        }
    )


def _iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("now must include timezone information")
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
