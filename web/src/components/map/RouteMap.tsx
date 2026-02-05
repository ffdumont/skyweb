/**
 * RouteMap - Simple 2D map with route display using Leaflet.
 */

import { useEffect, useRef } from "react";
import { MapContainer, TileLayer, Polyline, CircleMarker, Tooltip, useMap } from "react-leaflet";
import type { LatLngBoundsExpression, LatLngTuple } from "leaflet";
import "leaflet/dist/leaflet.css";
import type { WaypointData } from "../../data/mockDossier";

interface Props {
  waypoints: WaypointData[];
}

// Component to fit bounds when waypoints change
function FitBounds({ waypoints }: { waypoints: WaypointData[] }) {
  const map = useMap();
  const fittedRef = useRef(false);

  useEffect(() => {
    if (waypoints.length < 2 || fittedRef.current) return;

    const bounds: LatLngBoundsExpression = waypoints.map((w) => [w.lat, w.lon] as LatLngTuple);
    map.fitBounds(bounds, { padding: [50, 50] });
    fittedRef.current = true;
  }, [map, waypoints]);

  return null;
}

export default function RouteMap({ waypoints }: Props) {
  if (waypoints.length === 0) {
    return (
      <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", background: "#f5f5f5" }}>
        <span style={{ color: "#888" }}>Aucun waypoint</span>
      </div>
    );
  }

  // Route line coordinates
  const routeLine: LatLngTuple[] = waypoints.map((w) => [w.lat, w.lon]);

  // Default center on France
  const defaultCenter: LatLngTuple = [46.6, 2.3];

  return (
    <MapContainer
      center={defaultCenter}
      zoom={6}
      style={{ width: "100%", height: "100%" }}
      scrollWheelZoom={true}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {/* Route polyline */}
      <Polyline
        positions={routeLine}
        color="#1e90ff"
        weight={3}
        dashArray="10, 6"
      />

      {/* Waypoint markers */}
      {waypoints.map((wp, i) => {
        const isIntermediate = wp.is_intermediate ?? false;
        const isEndpoint = i === 0 || i === waypoints.length - 1;

        return (
          <CircleMarker
            key={i}
            center={[wp.lat, wp.lon]}
            radius={isIntermediate ? 4 : isEndpoint ? 8 : 6}
            fillColor={isIntermediate ? "#ff9800" : "#1e90ff"}
            color="#fff"
            weight={2}
            fillOpacity={1}
          >
            {!isIntermediate && (
              <Tooltip permanent direction="top" offset={[0, -10]}>
                <span style={{ fontWeight: 600 }}>{wp.name}</span>
                {wp.altitude_ft && <span style={{ marginLeft: 4, color: "#666" }}>{wp.altitude_ft} ft</span>}
              </Tooltip>
            )}
          </CircleMarker>
        );
      })}

      <FitBounds waypoints={waypoints} />
    </MapContainer>
  );
}
