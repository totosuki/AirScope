import type {
  Aircraft,
  CurrentAircraftResponse,
  RecentTelemetryResponse,
  Telemetry,
} from "./types";

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);
const isString = (value: unknown): value is string => typeof value === "string";
const isNullableString = (value: unknown): value is string | null =>
  value === null || isString(value);
const isNumber = (value: unknown): value is number =>
  typeof value === "number" && Number.isFinite(value);
const isNullableNumber = (value: unknown): value is number | null =>
  value === null || isNumber(value);

function isAircraft(value: unknown): value is Aircraft {
  if (!isRecord(value)) return false;
  return (
    isString(value.icao24) &&
    isNullableString(value.callsign) &&
    isNumber(value.lat) &&
    isNumber(value.lon) &&
    isNullableNumber(value.altitude_ft) &&
    isNullableNumber(value.ground_speed_kt) &&
    isNullableNumber(value.track_deg) &&
    isNullableNumber(value.vertical_rate_fpm) &&
    isNullableString(value.squawk) &&
    isNullableString(value.seen_at) &&
    isNullableString(value.received_at) &&
    isString(value.freshness_at) &&
    isNullableString(value.receiver_id) &&
    isNullableNumber(value.distance_km) &&
    (value.status === "current" || value.status === "stale")
  );
}

function isTelemetry(value: unknown): value is Telemetry {
  if (!isRecord(value) || !isRecord(value.telemetry)) return false;
  const aircraft = value.telemetry;
  return (
    isString(value.id) &&
    isNullableString(value.schema_version) &&
    isNullableString(value.source) &&
    isString(value.session_id) &&
    isNullableString(value.sent_at) &&
    isString(value.ingested_at) &&
    isString(aircraft.icao24) &&
    isNullableString(aircraft.callsign) &&
    isNumber(aircraft.lat) &&
    isNumber(aircraft.lon) &&
    isNullableNumber(aircraft.altitude_ft) &&
    isNullableNumber(aircraft.ground_speed_kt) &&
    isNullableNumber(aircraft.track_deg) &&
    isNullableNumber(aircraft.vertical_rate_fpm) &&
    isNullableString(aircraft.squawk) &&
    isNullableString(aircraft.seen_at) &&
    isNullableString(aircraft.received_at) &&
    isNullableString(aircraft.receiver_id) &&
    isNullableNumber(aircraft.distance_km)
  );
}

export function parseCurrentAircraftResponse(value: unknown): CurrentAircraftResponse {
  if (
    !isRecord(value) ||
    !isString(value.session_id) ||
    !isString(value.generated_at) ||
    !Array.isArray(value.aircraft) ||
    !value.aircraft.every(isAircraft)
  ) {
    throw new Error("航空機APIの応答形式が正しくありません。");
  }
  return value as CurrentAircraftResponse;
}

export function parseRecentTelemetryResponse(value: unknown): RecentTelemetryResponse {
  if (
    !isRecord(value) ||
    !isString(value.session_id) ||
    !isString(value.generated_at) ||
    !Array.isArray(value.telemetry) ||
    !value.telemetry.every(isTelemetry)
  ) {
    throw new Error("テレメトリAPIの応答形式が正しくありません。");
  }
  return value as RecentTelemetryResponse;
}
