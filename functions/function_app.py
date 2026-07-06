"""Azure Functions entry points for AirScope ingestion and read APIs."""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

import azure.functions as func
from azure.cosmos import CosmosClient, exceptions

from airscope_current import (
    DEFAULT_CURRENT_THRESHOLD_SECONDS,
    DEFAULT_STALE_THRESHOLD_SECONDS,
    build_current_item,
    build_raw_item,
    should_update_current,
    utc_now_iso,
)
from airscope_http import (
    ApiResult,
    current_aircraft_result,
    internal_error_result,
    read_env_int,
    recent_telemetry_result,
)


app = func.FunctionApp()


def _json_response(result: ApiResult) -> func.HttpResponse:
    return func.HttpResponse(
        body=json.dumps(result.payload, ensure_ascii=False),
        status_code=result.status_code,
        headers=result.headers,
        mimetype="application/json",
        charset="utf-8",
    )


def _http_error_response(function_name: str) -> func.HttpResponse:
    logging.exception("Unhandled error in %s", function_name)
    return _json_response(internal_error_result())


@lru_cache(maxsize=1)
def _containers() -> tuple[Any, Any]:
    client = CosmosClient(
        os.environ["AIRSCOPE_COSMOS_ENDPOINT"],
        credential=os.environ["AIRSCOPE_COSMOS_KEY"],
    )
    database = client.get_database_client(os.environ.get("AIRSCOPE_COSMOS_DATABASE", "airscope"))
    telemetry_container = database.get_container_client(
        os.environ.get("AIRSCOPE_COSMOS_TELEMETRY_CONTAINER", "telemetry")
    )
    current_container = database.get_container_client(
        os.environ.get("AIRSCOPE_COSMOS_CURRENT_CONTAINER", "current_aircraft")
    )
    return telemetry_container, current_container


@app.function_name(name="ProcessAirScopeTelemetry")
@app.event_hub_message_trigger(
    arg_name="event",
    event_hub_name="%AIRSCOPE_IOTHUB_EVENTHUB_NAME%",
    connection="AIRSCOPE_IOTHUB_EVENTHUB_CONNECTION",
    consumer_group="%AIRSCOPE_IOTHUB_CONSUMER_GROUP%",
)
def process_airscope_telemetry(event: func.EventHubEvent) -> None:
    telemetry_container, current_container = _containers()
    payload = json.loads(event.get_body().decode("utf-8"))
    ingested_at = utc_now_iso()

    raw_item = build_raw_item(payload, ingested_at=ingested_at)
    telemetry_container.upsert_item(raw_item)

    current_item = build_current_item(
        payload,
        updated_at=ingested_at,
        now=datetime.now(UTC),
        current_threshold_seconds=read_env_int(
            os.environ, "AIRSCOPE_CURRENT_THRESHOLD_SECONDS", DEFAULT_CURRENT_THRESHOLD_SECONDS
        ),
        stale_threshold_seconds=read_env_int(
            os.environ, "AIRSCOPE_STALE_THRESHOLD_SECONDS", DEFAULT_STALE_THRESHOLD_SECONDS
        ),
    )
    if current_item is None:
        logging.info("Skip current_aircraft update: payload is missing aircraft identity or position")
        return

    try:
        existing = current_container.read_item(
            item=current_item["id"],
            partition_key=current_item["session_id"],
        )
    except exceptions.CosmosResourceNotFoundError:
        existing = None

    if not should_update_current(existing, current_item):
        logging.info("Skip current_aircraft update: existing snapshot is newer or equal")
        return

    current_container.upsert_item(current_item)


@app.function_name(name="GetCurrentAircraft")
@app.route(
    route="aircraft/current",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def get_current_aircraft(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _, current_container = _containers()
        result = current_aircraft_result(
            req.params,
            current_container,
            current_threshold_seconds=read_env_int(
                os.environ,
                "AIRSCOPE_CURRENT_THRESHOLD_SECONDS",
                DEFAULT_CURRENT_THRESHOLD_SECONDS,
            ),
            stale_threshold_seconds=read_env_int(
                os.environ,
                "AIRSCOPE_STALE_THRESHOLD_SECONDS",
                DEFAULT_STALE_THRESHOLD_SECONDS,
            ),
        )
        return _json_response(result)
    except Exception:  # The client receives a generic response; details stay in logs.
        return _http_error_response("GetCurrentAircraft")


@app.function_name(name="GetRecentTelemetry")
@app.route(
    route="telemetry/recent",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def get_recent_telemetry(req: func.HttpRequest) -> func.HttpResponse:
    try:
        telemetry_container, _ = _containers()
        result = recent_telemetry_result(req.params, telemetry_container)
        return _json_response(result)
    except Exception:  # The client receives a generic response; details stay in logs.
        return _http_error_response("GetRecentTelemetry")
