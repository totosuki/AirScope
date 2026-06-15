"""Azure Functions entry point for AirScope telemetry ingestion."""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

import azure.functions as func
from azure.cosmos import CosmosClient, exceptions

from airscope_current import build_current_item, build_raw_item, should_update_current, utc_now_iso


app = func.FunctionApp()


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        logging.warning("Invalid integer app setting %s=%r. Using %s.", name, value, default)
        return default


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
        current_threshold_seconds=_env_int("AIRSCOPE_CURRENT_THRESHOLD_SECONDS", 30),
        stale_threshold_seconds=_env_int("AIRSCOPE_STALE_THRESHOLD_SECONDS", 120),
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
