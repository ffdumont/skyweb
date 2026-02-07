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
import type { AerodromeInfo, LegAirspaces, SimulationResponse } from "../../api/types";
import { formatHdg } from "../../utils/units";

interface NavigationParams {
  departureTimeUtc: string; // HH:MM format
  tasKt: number;
  fuelFlowLph: number;
  reserveMin: number;
}

// Service types we want to show in the nav log (prioritized order)
// Maps both abbreviated codes and French names from database
const SERVICE_TYPE_PRIORITY: Record<string, number> = {
  // Abbreviated codes
  "SIV": 0, "APP": 1, "TWR": 2, "ATIS": 3, "AFIS": 4, "A/A": 5,
  // French names from database
  "Information": 0, "Approche": 1, "Tour": 2, "Auto-information": 5,
};

// Airspace types that should NOT provide frequencies for VFR navigation
// FIR frequencies are too general; prefer SIV/TMA frequencies for local services
const EXCLUDED_AIRSPACE_TYPES = new Set(["FIR"]);

/**
 * Exception zones that should NOT be treated as red/dangerous zones.
 * Custom frequencies can be specified here for zones missing from database.
 */
interface ZoneException {
  identifier: string;
  customFrequency?: string;
  callsign?: string;
}

const ZONE_EXCEPTIONS: ZoneException[] = [
  { identifier: "R 324", customFrequency: "120.075", callsign: "VEILLE PARIS" },
];

/** Normalize identifier for comparison (remove spaces, uppercase) */
function normalizeIdentifier(id: string): string {
  return id.toUpperCase().replace(/\s+/g, "");
}

/** Get exception zone info if exists */
function getExceptionInfo(identifier: string): ZoneException | null {
  const normalizedId = normalizeIdentifier(identifier);
  return ZONE_EXCEPTIONS.find((ex) => {
    const normalizedEx = normalizeIdentifier(ex.identifier);
    return normalizedId.includes(normalizedEx) || normalizedEx.includes(normalizedId);
  }) ?? null;
}

export default function NavigationTab() {
  const routeData = useDossierStore((s) => s.routeData);
  const airspaceAnalysis = useDossierStore((s) => s.airspaceAnalysis);
  const currentRouteId = useDossierStore((s) => s.currentRouteId);
  const loadAirspaceAnalysis = useDossierStore((s) => s.loadAirspaceAnalysis);

  // Aerodrome info for departure/destination frequencies
  const departureAerodrome = useDossierStore((s) => s.departureAerodrome);
  const destinationAerodrome = useDossierStore((s) => s.destinationAerodrome);

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
    let prevAltitudeFt: number | null = null;
    const departureMinutes = parseTimeToMinutes(params.departureTimeUtc);
    const totalSegments = routeData.segments.length;

    for (let i = 0; i < routeData.segments.length; i++) {
      const seg = routeData.segments[i];
      const legAirspaces = findLegAirspaces(airspaceAnalysis?.legs, seg, i);
      const airspaceFrequencies = extractFrequencies(legAirspaces);

      // Add aerodrome frequencies for first (departure) and last (destination) segments
      const aerodromeFrequencies: { callsign: string; frequency: string; isClassA: boolean }[] = [];
      if (i === 0 && departureAerodrome) {
        aerodromeFrequencies.push(...extractAerodromeFrequencies(departureAerodrome));
      }
      if (i === totalSegments - 1 && destinationAerodrome) {
        aerodromeFrequencies.push(...extractAerodromeFrequencies(destinationAerodrome));
      }

      // Combine frequencies: aerodrome frequencies first, then airspace frequencies
      const frequencies = [...aerodromeFrequencies, ...airspaceFrequencies];

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
        prevAltitudeFt,
        eteMin,
        etaUtc: formatMinutesToTime(etaMinutes),
        cumulativeDistNm,
        cumulativeTimeMin,
        fuelUsedL,
        frequencies,
        hasWindData: windData !== null,
      });

      prevAltitudeFt = seg.altitude_ft;
    }

    return entries;
  }, [routeData, airspaceAnalysis, params, selectedSimulation, currentWeatherModelId, departureAerodrome, destinationAerodrome]);

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
                  {(() => {
                    const { text, arrow } = formatAltitude(entry.altitudeFt, entry.prevAltitudeFt);
                    return (
                      <>
                        {arrow && (
                          <span style={{
                            color: arrow === "↗" ? "#2e7d32" : "#1565c0",
                            marginRight: 4,
                            fontSize: 14,
                          }}>
                            {arrow}
                          </span>
                        )}
                        {text}
                      </>
                    );
                  })()}
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
                      {entry.frequencies.map((freq, j) => (
                        <div key={j} style={{ color: freq.isClassA ? "#c00" : undefined }}>
                          <span style={{ color: freq.isClassA ? "#c00" : "#555" }}>{freq.callsign}</span>
                          <span style={{ color: freq.isClassA ? "#c00" : "#0066cc", marginLeft: 6, fontWeight: freq.isClassA ? 600 : undefined }}>{freq.frequency}</span>
                        </div>
                      ))}
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
  prevAltitudeFt: number | null; // Previous segment altitude for arrow display
  eteMin: number;
  etaUtc: string;
  cumulativeDistNm: number;
  cumulativeTimeMin: number;
  fuelUsedL: number;
  frequencies: { callsign: string; frequency: string; isClassA: boolean }[];
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

function formatAltitude(ft: number, prevFt: number | null): { text: string; arrow: string | null } {
  const text = ft >= 3000
    ? `FL${Math.round(ft / 100).toString().padStart(3, "0")}`
    : `${ft}ft`;

  // Determine arrow based on altitude change
  let arrow: string | null = null;
  if (prevFt !== null && ft !== prevFt) {
    arrow = ft > prevFt ? "↗" : "↘";
  }

  return { text, arrow };
}

function findLegAirspaces(
  legs: LegAirspaces[] | undefined,
  segment: SegmentData,
  _segmentIndex: number
): LegAirspaces | null {
  if (!legs || legs.length === 0) return null;

  // Try exact name match first
  const byName = legs.find(
    (leg) => leg.from_waypoint === segment.from && leg.to_waypoint === segment.to
  );
  if (byName) return byName;

  // Try matching by destination (most reliable - find leg ending at segment's destination)
  const byDestination = legs.find((leg) =>
    leg.to_waypoint.includes(segment.to) ||
    segment.to.includes(leg.to_waypoint)
  );
  if (byDestination) return byDestination;

  // Try partial name match - require BOTH from AND to to match
  const byPartialName = legs.find((leg) => {
    const fromMatch =
      leg.from_waypoint.includes(segment.from) ||
      segment.from.includes(leg.from_waypoint);
    const toMatch =
      leg.to_waypoint.includes(segment.to) ||
      segment.to.includes(leg.to_waypoint);
    return fromMatch && toMatch;
  });
  if (byPartialName) return byPartialName;

  // Try matching by origin only
  const byOrigin = legs.find((leg) =>
    leg.from_waypoint.includes(segment.from) ||
    segment.from.includes(leg.from_waypoint)
  );
  if (byOrigin) return byOrigin;

  return null;
}

function extractFrequencies(legAirspaces: LegAirspaces | null): { callsign: string; frequency: string; isClassA: boolean }[] {
  if (!legAirspaces) return [];

  const frequencies: { callsign: string; frequency: string; priority: number; isClassA: boolean }[] = [];
  const seenCallsigns = new Set<string>(); // Only one frequency per callsign

  // Only use route_airspaces (airspaces actually traversed), not corridor_airspaces
  const airspaces = legAirspaces.route_airspaces || [];

  for (const airspace of airspaces) {
    // Skip FIR and other excluded airspace types - prefer local SIV/TMA frequencies
    if (EXCLUDED_AIRSPACE_TYPES.has(airspace.airspace_type)) continue;

    // Check if this is an exception zone
    const exceptionInfo = getExceptionInfo(airspace.identifier);
    const isException = exceptionInfo !== null;

    // Check if this is a TMA class A (but not if it's an exception)
    const isClassA = !isException && airspace.airspace_type === "TMA" && airspace.airspace_class === "A";

    // If exception zone has a custom frequency, add it
    if (exceptionInfo?.customFrequency && exceptionInfo?.callsign) {
      if (!seenCallsigns.has(exceptionInfo.callsign)) {
        seenCallsigns.add(exceptionInfo.callsign);
        frequencies.push({
          callsign: exceptionInfo.callsign,
          frequency: exceptionInfo.customFrequency,
          priority: 1, // Medium priority (like APP)
          isClassA: false,
        });
      }
    }

    for (const service of airspace.services || []) {
      const priority = SERVICE_TYPE_PRIORITY[service.service_type];
      if (priority === undefined) continue; // Skip irrelevant services

      // For SIV, use the airspace identifier (e.g., "PARIS NORD SIV" -> "PARIS NORD")
      // This preserves sector information that would be lost with just service.callsign
      let callsign = service.callsign;
      if (airspace.airspace_type === "SIV") {
        // Remove " SIV" suffix from identifier to get the sector name
        callsign = airspace.identifier.replace(/\s+SIV$/i, "").trim();
      }

      // Skip if we already have a frequency for this callsign
      if (seenCallsigns.has(callsign)) continue;

      // Find the first VHF frequency (118-137 MHz range), excluding 121.5 (emergency)
      const vhfFreq = (service.frequencies || []).find((f) => {
        const mhz = parseFloat(f.frequency_mhz);
        return mhz >= 118 && mhz <= 137 && Math.abs(mhz - 121.5) > 0.01;
      });

      if (vhfFreq) {
        seenCallsigns.add(callsign);
        frequencies.push({
          callsign,
          frequency: vhfFreq.frequency_mhz,
          priority,
          isClassA,
        });
      }
    }
  }

  // Sort by priority (SIV/Information first, then APP/Approche, then TWR/Tour, etc.)
  frequencies.sort((a, b) => a.priority - b.priority);

  return frequencies.map(({ callsign, frequency, isClassA }) => ({ callsign, frequency, isClassA }));
}

/**
 * Extract frequencies from aerodrome info for the nav log.
 * Prioritizes TWR, AFIS, A/A (auto-information) services.
 */
function extractAerodromeFrequencies(aerodrome: AerodromeInfo): { callsign: string; frequency: string; isClassA: boolean }[] {
  const frequencies: { callsign: string; frequency: string; priority: number }[] = [];

  // Priority for aerodrome services (lower = higher priority)
  const AD_SERVICE_PRIORITY: Record<string, number> = {
    "TWR": 0, "Tour": 0,
    "AFIS": 1,
    "A/A": 2, "Auto-information": 2,
    "ATIS": 3,
    "GND": 4, "Sol": 4,
    "APP": 5, "Approche": 5,
  };

  for (const service of aerodrome.services || []) {
    const priority = AD_SERVICE_PRIORITY[service.service_type];
    if (priority === undefined) continue; // Skip irrelevant services

    // Use callsign if available, otherwise use aerodrome ICAO
    const callsign = service.callsign || `${aerodrome.icao} ${service.service_type}`;

    // Find the first VHF frequency
    const vhfFreq = (service.frequencies || []).find((f) => {
      const mhz = f.frequency_mhz;
      return mhz >= 118 && mhz <= 137 && Math.abs(mhz - 121.5) > 0.01;
    });

    if (vhfFreq) {
      frequencies.push({
        callsign,
        frequency: vhfFreq.frequency_mhz.toFixed(3),
        priority,
      });
    }
  }

  // Sort by priority and take the most relevant frequencies
  frequencies.sort((a, b) => a.priority - b.priority);

  // Return up to 2 most relevant frequencies, never flag as class A
  return frequencies.slice(0, 2).map(({ callsign, frequency }) => ({
    callsign,
    frequency,
    isClassA: false,
  }));
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
