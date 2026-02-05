/**
 * NavigationTab - VFR navigation log with segment-based layout.
 *
 * Displays: Rm, Drift, Rc, Distance, Altitude, ETE, ETA, Frequencies
 * Integrates with:
 * - routeData (segments, waypoints)
 * - airspaceAnalysis (frequencies from SIV/APP/TWR services)
 * - weatherSimulation (wind data for drift calculation)
 */

import { useState, useMemo, useEffect } from "react";
import { useDossierStore } from "../../stores/dossierStore";
import type { SegmentData } from "../../data/mockDossier";
import type { LegAirspaces, SimulationResponse } from "../../api/types";
import { formatHdg } from "../../utils/units";

interface NavigationParams {
  departureTimeUtc: string; // HH:MM format
  tasKt: number;
  fuelFlowLph: number;
  reserveMin: number;
}

// Service types we want to show in the nav log (prioritized order)
const RELEVANT_SERVICE_TYPES = ["SIV", "APP", "TWR", "ATIS", "AFIS", "A/A"];

export default function NavigationTab() {
  const routeData = useDossierStore((s) => s.routeData);
  const airspaceAnalysis = useDossierStore((s) => s.airspaceAnalysis);
  const currentRouteId = useDossierStore((s) => s.currentRouteId);
  const loadAirspaceAnalysis = useDossierStore((s) => s.loadAirspaceAnalysis);

  // Weather simulation from shared store
  const weatherSimulations = useDossierStore((s) => s.weatherSimulations);
  const currentWeatherSimulationId = useDossierStore((s) => s.currentWeatherSimulationId);
  const currentWeatherModelId = useDossierStore((s) => s.currentWeatherModelId);

  // Auto-load airspace analysis if not already loaded
  useEffect(() => {
    if (currentRouteId && !airspaceAnalysis) {
      loadAirspaceAnalysis(currentRouteId);
    }
  }, [currentRouteId, airspaceAnalysis, loadAirspaceAnalysis]);

  // Derive selected simulation from store
  const selectedSimulation = useMemo(() => {
    if (!currentWeatherSimulationId) return null;
    return weatherSimulations.find((s) => s.simulation_id === currentWeatherSimulationId) ?? null;
  }, [weatherSimulations, currentWeatherSimulationId]);

  // Navigation parameters (local state for now)
  const [params, setParams] = useState<NavigationParams>({
    departureTimeUtc: "12:00",
    tasKt: 100,
    fuelFlowLph: 25,
    reserveMin: 45,
  });

  // Computed navigation log entries
  const navLog = useMemo(() => {
    if (!routeData?.segments) return [];

    const entries: NavLogEntry[] = [];
    let cumulativeDistNm = 0;
    let cumulativeTimeMin = 0;
    const departureMinutes = parseTimeToMinutes(params.departureTimeUtc);

    for (let i = 0; i < routeData.segments.length; i++) {
      const seg = routeData.segments[i];
      const legAirspaces = findLegAirspaces(airspaceAnalysis?.legs, seg, i);
      const frequencies = extractFrequencies(legAirspaces);

      // Get wind data for drift calculation if simulation available
      const windData = getWindDataForSegment(selectedSimulation, currentWeatherModelId, i);
      const { driftDeg, rcDeg, gsKt } = calculateDrift(seg.rm_deg, params.tasKt, windData);

      // Time calculations using ground speed
      const groundSpeed = gsKt || params.tasKt;
      const eteMin = (seg.distance_nm / groundSpeed) * 60;
      cumulativeTimeMin += eteMin;
      cumulativeDistNm += seg.distance_nm;

      const etaMinutes = departureMinutes + cumulativeTimeMin;
      const fuelUsedL = (cumulativeTimeMin / 60) * params.fuelFlowLph;

      entries.push({
        segment: `${seg.from}→${seg.to}`,
        from: seg.from,
        to: seg.to,
        rmDeg: seg.rm_deg,
        driftDeg,
        rcDeg,
        distanceNm: seg.distance_nm,
        altitudeFt: seg.altitude_ft,
        eteMin,
        etaUtc: formatMinutesToTime(etaMinutes),
        cumulativeDistNm,
        cumulativeTimeMin,
        fuelUsedL,
        frequencies,
        hasWindData: windData !== null,
      });
    }

    return entries;
  }, [routeData, airspaceAnalysis, params, selectedSimulation, currentWeatherModelId]);

  // Totals
  const totals = useMemo(() => {
    if (navLog.length === 0) return null;
    const last = navLog[navLog.length - 1];
    const reserveFuelL = (params.reserveMin / 60) * params.fuelFlowLph;
    return {
      distanceNm: last.cumulativeDistNm,
      flightTimeMin: last.cumulativeTimeMin,
      fuelFlightL: last.fuelUsedL,
      fuelReserveL: reserveFuelL,
      fuelTotalL: last.fuelUsedL + reserveFuelL,
    };
  }, [navLog, params]);

  if (!routeData?.segments || routeData.segments.length === 0) {
    return (
      <div style={{ padding: 24, color: "#888" }}>
        Chargez d'abord une route pour voir le log de navigation.
      </div>
    );
  }

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      {/* Parameters bar */}
      <div style={paramsBarStyle}>
        <div style={paramGroupStyle}>
          <label style={labelStyle}>Départ UTC</label>
          <input
            type="time"
            value={params.departureTimeUtc}
            onChange={(e) => setParams((p) => ({ ...p, departureTimeUtc: e.target.value }))}
            style={inputStyle}
          />
        </div>
        <div style={paramGroupStyle}>
          <label style={labelStyle}>TAS</label>
          <input
            type="number"
            value={params.tasKt}
            onChange={(e) => setParams((p) => ({ ...p, tasKt: Number(e.target.value) }))}
            style={{ ...inputStyle, width: 70 }}
          />
          <span style={unitStyle}>kt</span>
        </div>
        <div style={paramGroupStyle}>
          <label style={labelStyle}>Conso</label>
          <input
            type="number"
            value={params.fuelFlowLph}
            onChange={(e) => setParams((p) => ({ ...p, fuelFlowLph: Number(e.target.value) }))}
            style={{ ...inputStyle, width: 60 }}
          />
          <span style={unitStyle}>L/h</span>
        </div>
        <div style={paramGroupStyle}>
          <label style={labelStyle}>Réserve</label>
          <input
            type="number"
            value={params.reserveMin}
            onChange={(e) => setParams((p) => ({ ...p, reserveMin: Number(e.target.value) }))}
            style={{ ...inputStyle, width: 60 }}
          />
          <span style={unitStyle}>min</span>
        </div>
      </div>

      {/* Navigation log table */}
      <div style={{ flex: 1, overflow: "auto", padding: 16 }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ background: "#f8f9fa", borderBottom: "2px solid #dee2e6" }}>
              <th style={thStyle}>Segment</th>
              <th style={{ ...thStyle, textAlign: "center" }}>Rm</th>
              <th style={{ ...thStyle, textAlign: "center" }}>Dérive</th>
              <th style={{ ...thStyle, textAlign: "center" }}>Rc</th>
              <th style={{ ...thStyle, textAlign: "right" }}>Dist</th>
              <th style={{ ...thStyle, textAlign: "center" }}>Alt</th>
              <th style={{ ...thStyle, textAlign: "right" }}>ETE</th>
              <th style={{ ...thStyle, textAlign: "center" }}>ETA</th>
              <th style={thStyle}>Fréquences</th>
            </tr>
          </thead>
          <tbody>
            {navLog.map((entry, i) => (
              <tr key={i} style={{ borderBottom: "1px solid #eee" }}>
                <td style={tdStyle}>
                  <span style={{ fontWeight: 500 }}>{entry.from}</span>
                  <span style={{ color: "#888" }}> → </span>
                  <span style={{ fontWeight: 500 }}>{entry.to}</span>
                </td>
                <td style={{ ...tdStyle, textAlign: "center", fontFamily: "monospace" }}>
                  {formatHdg(entry.rmDeg)}
                </td>
                <td style={{ ...tdStyle, textAlign: "center", fontFamily: "monospace", color: entry.hasWindData ? "#333" : "#ccc" }}>
                  {entry.driftDeg !== null
                    ? `${entry.driftDeg >= 0 ? "+" : ""}${entry.driftDeg}°`
                    : "—"}
                </td>
                <td style={{ ...tdStyle, textAlign: "center", fontFamily: "monospace", fontWeight: 600 }}>
                  {entry.rcDeg !== null ? formatHdg(entry.rcDeg) : formatHdg(entry.rmDeg)}
                </td>
                <td style={{ ...tdStyle, textAlign: "right", fontFamily: "monospace" }}>
                  {entry.distanceNm.toFixed(1)} nm
                </td>
                <td style={{ ...tdStyle, textAlign: "center", fontFamily: "monospace" }}>
                  {formatAltitude(entry.altitudeFt)}
                </td>
                <td style={{ ...tdStyle, textAlign: "right", fontFamily: "monospace" }}>
                  {formatEte(entry.eteMin)}
                </td>
                <td style={{ ...tdStyle, textAlign: "center", fontFamily: "monospace", fontWeight: 500 }}>
                  {entry.etaUtc}
                </td>
                <td style={{ ...tdStyle, fontSize: 12 }}>
                  {entry.frequencies.length > 0 ? (
                    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                      {entry.frequencies.slice(0, 2).map((freq, j) => (
                        <div key={j}>
                          <span style={{ color: "#555" }}>{freq.callsign}</span>
                          <span style={{ color: "#0066cc", marginLeft: 6 }}>{freq.frequency}</span>
                        </div>
                      ))}
                      {entry.frequencies.length > 2 && (
                        <span style={{ color: "#888", fontSize: 11 }}>
                          +{entry.frequencies.length - 2} autres
                        </span>
                      )}
                    </div>
                  ) : (
                    <span style={{ color: "#ccc" }}>—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Totals footer */}
      {totals && (
        <div style={totalsBarStyle}>
          <div style={totalItemStyle}>
            <span style={totalLabelStyle}>Distance</span>
            <span style={totalValueStyle}>{totals.distanceNm.toFixed(0)} NM</span>
          </div>
          <div style={totalItemStyle}>
            <span style={totalLabelStyle}>Temps vol</span>
            <span style={totalValueStyle}>{formatDuration(totals.flightTimeMin)}</span>
          </div>
          <div style={totalItemStyle}>
            <span style={totalLabelStyle}>Carburant vol</span>
            <span style={totalValueStyle}>{totals.fuelFlightL.toFixed(0)} L</span>
          </div>
          <div style={totalItemStyle}>
            <span style={totalLabelStyle}>+ Réserve {params.reserveMin}min</span>
            <span style={totalValueStyle}>{totals.fuelReserveL.toFixed(0)} L</span>
          </div>
          <div style={{ ...totalItemStyle, background: "#e3f2fd", padding: "8px 16px", borderRadius: 6 }}>
            <span style={{ ...totalLabelStyle, fontWeight: 600 }}>Total carburant</span>
            <span style={{ ...totalValueStyle, fontSize: 16 }}>{totals.fuelTotalL.toFixed(0)} L</span>
          </div>
        </div>
      )}
    </div>
  );
}

// ============ Types ============

interface NavLogEntry {
  segment: string;
  from: string;
  to: string;
  rmDeg: number;
  driftDeg: number | null;
  rcDeg: number | null;
  distanceNm: number;
  altitudeFt: number;
  eteMin: number;
  etaUtc: string;
  cumulativeDistNm: number;
  cumulativeTimeMin: number;
  fuelUsedL: number;
  frequencies: { callsign: string; frequency: string }[];
  hasWindData: boolean;
}

interface WindData {
  speedKt: number;
  directionDeg: number;
}

// ============ Helper Functions ============

function parseTimeToMinutes(time: string): number {
  const [h, m] = time.split(":").map(Number);
  return (h || 0) * 60 + (m || 0);
}

function formatMinutesToTime(totalMinutes: number): string {
  const mins = totalMinutes % (24 * 60); // Wrap around midnight
  const h = Math.floor(mins / 60);
  const m = Math.round(mins % 60);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

function formatEte(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = Math.round(minutes % 60);
  if (h === 0) return `${m}'`;
  return `${h}h${String(m).padStart(2, "0")}`;
}

function formatDuration(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = Math.round(minutes % 60);
  return `${h}h${String(m).padStart(2, "0")}`;
}

function formatAltitude(ft: number): string {
  if (ft >= 3000) {
    return `FL${Math.round(ft / 100).toString().padStart(3, "0")}`;
  }
  return `${ft}ft`;
}

function findLegAirspaces(
  legs: LegAirspaces[] | undefined,
  segment: SegmentData,
  segmentIndex: number
): LegAirspaces | null {
  if (!legs || legs.length === 0) return null;

  // Try exact name match first
  const byName = legs.find(
    (leg) => leg.from_waypoint === segment.from && leg.to_waypoint === segment.to
  );
  if (byName) return byName;

  // Fallback: match by sequence index (segment i = from_seq i to to_seq i+1)
  const bySeq = legs.find(
    (leg) => leg.from_seq === segmentIndex && leg.to_seq === segmentIndex + 1
  );
  if (bySeq) return bySeq;

  // Last resort: use segment at same index if available
  if (segmentIndex < legs.length) {
    return legs[segmentIndex];
  }

  return null;
}

function extractFrequencies(legAirspaces: LegAirspaces | null): { callsign: string; frequency: string }[] {
  if (!legAirspaces) return [];

  const frequencies: { callsign: string; frequency: string; priority: number }[] = [];
  const seen = new Set<string>();

  // Collect from both route_airspaces and corridor_airspaces
  const allAirspaces = [
    ...(legAirspaces.route_airspaces || []),
    ...(legAirspaces.corridor_airspaces || []),
  ];

  for (const airspace of allAirspaces) {
    for (const service of airspace.services) {
      const priority = RELEVANT_SERVICE_TYPES.indexOf(service.service_type);
      if (priority === -1) continue; // Skip irrelevant services

      for (const freq of service.frequencies) {
        const key = `${service.callsign}-${freq.frequency_mhz}`;
        if (seen.has(key)) continue;
        seen.add(key);
        frequencies.push({
          callsign: service.callsign,
          frequency: freq.frequency_mhz,
          priority,
        });
      }
    }
  }

  // Sort by priority (SIV first, then APP, then TWR, etc.)
  frequencies.sort((a, b) => a.priority - b.priority);

  return frequencies.map(({ callsign, frequency }) => ({ callsign, frequency }));
}

function getWindDataForSegment(
  simulation: SimulationResponse | null,
  modelId: string,
  segmentIndex: number
): WindData | null {
  if (!simulation) return null;

  const modelResult = simulation.model_results.find((mr) => mr.model === modelId);
  if (!modelResult) return null;

  // Use the "to" waypoint's wind data for the segment
  const pointIndex = segmentIndex + 1; // Segment 0 = from wp0 to wp1, so use wp1's wind
  const point = modelResult.points[pointIndex];
  if (!point) return null;

  const speedLevels = Object.values(point.forecast.wind_speed_levels) as number[];
  const dirLevels = Object.values(point.forecast.wind_direction_levels) as number[];

  if (speedLevels.length === 0) return null;

  return {
    speedKt: speedLevels[0],
    directionDeg: dirLevels[0] ?? 0,
  };
}

function calculateDrift(
  trackDeg: number,
  tasKt: number,
  wind: WindData | null
): { driftDeg: number | null; rcDeg: number | null; gsKt: number | null } {
  if (!wind || wind.speedKt === 0) {
    return { driftDeg: null, rcDeg: null, gsKt: null };
  }

  // Wind correction angle calculation
  // WCA = arcsin((wind_speed / TAS) * sin(wind_direction - track))
  const windAngle = ((wind.directionDeg - trackDeg + 540) % 360) - 180; // -180 to +180
  const windAngleRad = (windAngle * Math.PI) / 180;

  // Cross-wind component
  const crossWind = wind.speedKt * Math.sin(windAngleRad);

  // Drift angle (wind correction angle)
  // Using small angle approximation: WCA ≈ (60 / TAS) * crosswind
  const driftDeg = Math.round((60 / tasKt) * crossWind);

  // Corrected heading = track - drift (we correct INTO the wind)
  const rcDeg = ((trackDeg - driftDeg) % 360 + 360) % 360;

  // Ground speed calculation
  const headWind = wind.speedKt * Math.cos(windAngleRad);
  const gsKt = Math.round(tasKt - headWind); // Simplified

  return { driftDeg, rcDeg: Math.round(rcDeg), gsKt };
}

// ============ Styles ============

const paramsBarStyle: React.CSSProperties = {
  display: "flex",
  gap: 24,
  alignItems: "center",
  padding: "12px 16px",
  background: "#f8f9fa",
  borderBottom: "1px solid #e0e0e0",
  flexWrap: "wrap",
};

const paramGroupStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
};

const labelStyle: React.CSSProperties = {
  fontSize: 12,
  fontWeight: 500,
  color: "#555",
};

const inputStyle: React.CSSProperties = {
  padding: "6px 10px",
  border: "1px solid #ccc",
  borderRadius: 4,
  fontSize: 13,
  width: 80,
};

const unitStyle: React.CSSProperties = {
  fontSize: 12,
  color: "#888",
};

const thStyle: React.CSSProperties = {
  padding: "10px 12px",
  textAlign: "left",
  fontWeight: 600,
  fontSize: 12,
  color: "#555",
  whiteSpace: "nowrap",
};

const tdStyle: React.CSSProperties = {
  padding: "10px 12px",
  whiteSpace: "nowrap",
  verticalAlign: "top",
};

const totalsBarStyle: React.CSSProperties = {
  display: "flex",
  gap: 24,
  alignItems: "center",
  padding: "12px 16px",
  background: "#fff",
  borderTop: "2px solid #dee2e6",
  flexWrap: "wrap",
};

const totalItemStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 2,
};

const totalLabelStyle: React.CSSProperties = {
  fontSize: 11,
  color: "#888",
};

const totalValueStyle: React.CSSProperties = {
  fontSize: 14,
  fontWeight: 600,
  fontFamily: "monospace",
};
