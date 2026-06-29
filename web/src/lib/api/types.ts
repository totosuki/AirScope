export type AircraftStatus = "current" | "stale";

export type Aircraft = {
  icao24: string;
  callsign: string | null;
  lat: number;
  lon: number;
  altitude_ft: number | null;
  ground_speed_kt: number | null;
  track_deg: number | null;
  vertical_rate_fpm: number | null;
  squawk: string | null;
  seen_at: string | null;
  received_at: string | null;
  freshness_at: string;
  receiver_id: string | null;
  distance_km: number | null;
  status: AircraftStatus;
};

export type Telemetry = {
  id: string;
  schema_version: string | null;
  source: string | null;
  session_id: string;
  sent_at: string | null;
  telemetry: Omit<Aircraft, "freshness_at" | "status">;
  ingested_at: string;
};

export type CurrentAircraftResponse = {
  session_id: string;
  generated_at: string;
  aircraft: Aircraft[];
};

export type RecentTelemetryResponse = {
  session_id: string;
  generated_at: string;
  telemetry: Telemetry[];
};
