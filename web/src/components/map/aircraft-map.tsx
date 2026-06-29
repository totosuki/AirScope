"use client";

import L from "leaflet";
import { MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet";
import { useEffect } from "react";

import { altitudeBandColor, getAltitudeBand } from "@/lib/aircraft";
import type { Aircraft } from "@/lib/api/types";
import { formatNumber, formatRelativeTime } from "@/lib/format";

type AircraftMapProps = {
  aircraft: Aircraft[];
  selectedIcao: string | null;
  onSelect: (icao24: string) => void;
};

const DEFAULT_CENTER: [number, number] = [35.6812, 139.7671];

function aircraftIcon(aircraft: Aircraft, selected: boolean) {
  const color = altitudeBandColor[getAltitudeBand(aircraft.altitude_ft)];
  const rotation = aircraft.track_deg ?? 0;
  return L.divIcon({
    className: "aircraft-marker-shell",
    html: `<span class="aircraft-marker${selected ? " is-selected" : ""}" style="--aircraft-color:${color};--aircraft-track:${rotation}deg" aria-hidden="true">✈</span>`,
    iconSize: [36, 36],
    iconAnchor: [18, 18],
  });
}

function FitAircraft({ aircraft }: { aircraft: Aircraft[] }) {
  const map = useMap();
  useEffect(() => {
    if (aircraft.length === 0) return;
    if (aircraft.length === 1) {
      map.setView([aircraft[0].lat, aircraft[0].lon], 10);
      return;
    }
    map.fitBounds(
      aircraft.map(({ lat, lon }) => [lat, lon] as [number, number]),
      { padding: [48, 48], maxZoom: 11 },
    );
  }, [aircraft, map]);
  return null;
}

export default function AircraftMap({ aircraft, selectedIcao, onSelect }: AircraftMapProps) {
  const center: [number, number] = aircraft[0]
    ? [aircraft[0].lat, aircraft[0].lon]
    : DEFAULT_CENTER;

  return (
    <MapContainer center={center} zoom={8} scrollWheelZoom className="h-full min-h-[420px] w-full">
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <FitAircraft aircraft={aircraft} />
      {aircraft.map((item) => (
        <Marker
          key={item.icao24}
          position={[item.lat, item.lon]}
          icon={aircraftIcon(item, item.icao24 === selectedIcao)}
          eventHandlers={{ click: () => onSelect(item.icao24) }}
          title={`${item.callsign ?? item.icao24}を選択`}
        >
          <Popup>
            <strong>{item.callsign ?? "コールサイン不明"}</strong>
            <br />ICAO: {item.icao24}
            <br />高度: {formatNumber(item.altitude_ft, " ft")}
            <br />速度: {formatNumber(item.ground_speed_kt, " kt")}
            <br />最終観測: {formatRelativeTime(item.freshness_at)}
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}
