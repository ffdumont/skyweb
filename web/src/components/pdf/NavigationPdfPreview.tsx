/**
 * NavigationPdfPreview - A5 portrait preview for VFR navigation log PDF export.
 *
 * Uses TRAMER method for segment headers:
 * T = Top (passage time ETA + ETE)
 * R = Route (corrected heading Rc)
 * A = Altitude (FL or ft)
 * M = Moteur (TAS)
 * E = Essence (fuel remaining + consumed)
 * R = Radio (primary frequency)
 */

import { useMemo } from "react";
import { useDossierStore } from "../../stores/dossierStore";
import type { SegmentData } from "../../data/mockDossier";
import type { AerodromeInfo, LegAirspaces, SimulationResponse } from "../../api/types";
import { formatHdg } from "../../utils/units";

interface NavigationParams {
  departureTimeUtc: string;
  tasKt: number;
  fuelFlowLph: number;
  reserveMin: number;
  initialFuelL: number;
}

interface WindData {
  speedKt: number;
  directionDeg: number;
}

interface SegmentPdfData {
  index: number;
  from: string;
  to: string;
  // TRAMER fields
  etaUtc: string;
  eteMin: number;
  rcDeg: number;
  rmDeg: number;
  driftDeg: number | null;
  altitudeFt: number;
  altitudeChange: "up" | "down" | null;
  tasKt: number;
  fuelRemainingL: number;
  fuelConsumedL: number;
  primaryFrequency: { callsign: string; frequency: string } | null;
  // Detailed info
  distanceNm: number;
  windData: WindData | null;
  frequencies: { callsign: string; frequency: string; isClassA: boolean }[];
  airspaces: { identifier: string; type: string; class: string | null; lowerFt: number; upperFt: number; isWarning: boolean }[];
}

// Service types we want to show (prioritized order)
const SERVICE_TYPE_PRIORITY: Record<string, number> = {
  "SIV": 0, "APP": 1, "TWR": 2, "ATIS": 3, "AFIS": 4, "A/A": 5,
  "Information": 0, "Approche": 1, "Tour": 2, "Auto-information": 5,
};

const EXCLUDED_AIRSPACE_TYPES = new Set(["FIR"]);

interface Props {
  params?: NavigationParams;
}

export default function NavigationPdfPreview({ params: externalParams }: Props) {
  const routeData = useDossierStore((s) => s.routeData);
  const airspaceAnalysis = useDossierStore((s) => s.airspaceAnalysis);
  const departureAerodrome = useDossierStore((s) => s.departureAerodrome);
  const destinationAerodrome = useDossierStore((s) => s.destinationAerodrome);
  const weatherSimulations = useDossierStore((s) => s.weatherSimulations);
  const currentWeatherSimulationId = useDossierStore((s) => s.currentWeatherSimulationId);
  const currentWeatherModelId = useDossierStore((s) => s.currentWeatherModelId);

  // Default params if not provided
  const params: NavigationParams = externalParams ?? {
    departureTimeUtc: "12:00",
    tasKt: 100,
    fuelFlowLph: 25,
    reserveMin: 45,
    initialFuelL: 100,
  };

  const selectedSimulation = useMemo(() => {
    if (!currentWeatherSimulationId) return null;
    return weatherSimulations.find((s) => s.simulation_id === currentWeatherSimulationId) ?? null;
  }, [weatherSimulations, currentWeatherSimulationId]);

  // Compute all segment data for PDF
  const segments = useMemo((): SegmentPdfData[] => {
    if (!routeData?.segments) return [];

    const result: SegmentPdfData[] = [];
    let cumulativeTimeMin = 0;
    let cumulativeFuelL = 0;
    let prevAltitudeFt: number | null = null;
    const departureMinutes = parseTimeToMinutes(params.departureTimeUtc);
    const totalSegments = routeData.segments.length;

    for (let i = 0; i < routeData.segments.length; i++) {
      const seg = routeData.segments[i];
      const legAirspaces = findLegAirspaces(airspaceAnalysis?.legs, seg, i);

      // Get frequencies
      const frequencies = extractFrequencies(legAirspaces, departureAerodrome, destinationAerodrome, i, totalSegments);

      // Get airspaces
      const airspaces = extractAirspaces(legAirspaces);

      // Wind and drift
      const windData = getWindDataForSegment(selectedSimulation, currentWeatherModelId, i);
      const { driftDeg, rcDeg, gsKt } = calculateDrift(seg.rm_deg, params.tasKt, windData);

      // Time and fuel calculations
      const groundSpeed = gsKt || params.tasKt;
      const eteMin = (seg.distance_nm / groundSpeed) * 60;
      cumulativeTimeMin += eteMin;
      const fuelSegmentL = (eteMin / 60) * params.fuelFlowLph;
      cumulativeFuelL += fuelSegmentL;

      const etaMinutes = departureMinutes + cumulativeTimeMin;

      // Altitude change indicator
      let altitudeChange: "up" | "down" | null = null;
      if (prevAltitudeFt !== null && seg.altitude_ft !== prevAltitudeFt) {
        altitudeChange = seg.altitude_ft > prevAltitudeFt ? "up" : "down";
      }

      result.push({
        index: i + 1,
        from: seg.from,
        to: seg.to,
        etaUtc: formatMinutesToTime(etaMinutes),
        eteMin,
        rcDeg: rcDeg ?? seg.rm_deg,
        rmDeg: seg.rm_deg,
        driftDeg,
        altitudeFt: seg.altitude_ft,
        altitudeChange,
        tasKt: params.tasKt,
        fuelRemainingL: params.initialFuelL - cumulativeFuelL,
        fuelConsumedL: cumulativeFuelL,
        primaryFrequency: frequencies.length > 0 ? { callsign: frequencies[0].callsign, frequency: frequencies[0].frequency } : null,
        distanceNm: seg.distance_nm,
        windData,
        frequencies,
        airspaces,
      });

      prevAltitudeFt = seg.altitude_ft;
    }

    return result;
  }, [routeData, airspaceAnalysis, params, selectedSimulation, currentWeatherModelId, departureAerodrome, destinationAerodrome]);

  // Totals
  const totals = useMemo(() => {
    if (segments.length === 0) return null;
    const last = segments[segments.length - 1];
    const totalDistNm = segments.reduce((acc, s) => acc + s.distanceNm, 0);
    const totalTimeMin = segments.reduce((acc, s) => acc + s.eteMin, 0);
    const reserveFuelL = (params.reserveMin / 60) * params.fuelFlowLph;
    return {
      distanceNm: totalDistNm,
      flightTimeMin: totalTimeMin,
      fuelFlightL: last.fuelConsumedL,
      fuelReserveL: reserveFuelL,
      fuelTotalL: last.fuelConsumedL + reserveFuelL,
    };
  }, [segments, params]);

  if (!routeData?.segments || routeData.segments.length === 0) {
    return (
      <div style={emptyStyle}>
        Chargez une route pour voir la prévisualisation PDF.
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      {/* Header */}
      <div style={headerStyle}>
        <div style={routeTitleStyle}>
          {routeData.segments[0]?.from} → {routeData.segments[routeData.segments.length - 1]?.to}
        </div>
        <div style={dateStyle}>
          Départ: {params.departureTimeUtc} UTC
        </div>
      </div>

      {/* Segments */}
      {segments.map((seg, idx) => (
        <div key={idx} style={segmentContainerStyle}>
          {/* Segment header */}
          <div style={segmentHeaderStyle}>
            <span style={segmentTitleStyle}>
              {seg.from} → {seg.to}
            </span>
            <span style={segmentDistStyle}>
              {seg.distanceNm.toFixed(1)} NM
            </span>
          </div>

          {/* TRAMER bar */}
          <div style={tramerBarStyle}>
            <div style={tramerItemStyle}>
              <div style={tramerLabelStyle}>T</div>
              <div style={tramerValueStyle}>{seg.etaUtc}</div>
              <div style={tramerSubStyle}>+{formatEte(seg.eteMin)}</div>
            </div>
            <div style={tramerItemStyle}>
              <div style={tramerLabelStyle}>R</div>
              <div style={tramerValueStyle}>{formatHdg(seg.rcDeg)}</div>
              <div style={tramerSubStyle}>
                {seg.driftDeg !== null ? `${seg.driftDeg >= 0 ? "+" : ""}${seg.driftDeg}°` : "—"}
              </div>
            </div>
            <div style={tramerItemStyle}>
              <div style={tramerLabelStyle}>A</div>
              <div style={tramerValueStyle}>
                {seg.altitudeChange === "up" && <span style={arrowUpStyle}>↗</span>}
                {seg.altitudeChange === "down" && <span style={arrowDownStyle}>↘</span>}
                {formatAltitude(seg.altitudeFt)}
              </div>
            </div>
            <div style={tramerItemStyle}>
              <div style={tramerLabelStyle}>M</div>
              <div style={tramerValueStyle}>{seg.tasKt}</div>
              <div style={tramerSubStyle}>kt</div>
            </div>
            <div style={tramerItemStyle}>
              <div style={tramerLabelStyle}>E</div>
              <div style={tramerValueStyle}>{Math.round(seg.fuelRemainingL)}L</div>
              <div style={tramerSubStyle}>-{Math.round(seg.fuelConsumedL)}L</div>
            </div>
            <div style={{ ...tramerItemStyle, flex: 1.5 }}>
              <div style={tramerLabelStyle}>R</div>
              {seg.primaryFrequency ? (
                <>
                  <div style={tramerValueStyle}>{seg.primaryFrequency.frequency}</div>
                  <div style={tramerSubStyle}>{seg.primaryFrequency.callsign}</div>
                </>
              ) : (
                <div style={tramerValueStyle}>—</div>
              )}
            </div>
          </div>

          {/* Details section */}
          <div style={detailsContainerStyle}>
            {/* Left column: Navigation + Wind */}
            <div style={detailColumnStyle}>
              <div style={detailSectionStyle}>
                <div style={detailHeaderStyle}>Navigation</div>
                <div style={detailLineStyle}>
                  Rm {formatHdg(seg.rmDeg)}
                  {seg.driftDeg !== null && (
                    <> − Dérive {seg.driftDeg >= 0 ? "+" : ""}{seg.driftDeg}° → Rc {formatHdg(seg.rcDeg)}</>
                  )}
                </div>
              </div>
              {seg.windData && (
                <div style={detailSectionStyle}>
                  <div style={detailHeaderStyle}>Vent</div>
                  <div style={detailLineStyle}>
                    {seg.windData.directionDeg}° / {Math.round(seg.windData.speedKt)} kt
                  </div>
                </div>
              )}
            </div>

            {/* Right column: Frequencies + Airspaces */}
            <div style={detailColumnStyle}>
              {seg.frequencies.length > 0 && (
                <div style={detailSectionStyle}>
                  <div style={detailHeaderStyle}>Fréquences</div>
                  {seg.frequencies.map((freq, j) => (
                    <div key={j} style={{ ...detailLineStyle, color: freq.isClassA ? "#c00" : undefined }}>
                      <span style={{ minWidth: 100, display: "inline-block" }}>{freq.callsign}</span>
                      <span style={{ fontWeight: 500, fontFamily: "monospace" }}>{freq.frequency}</span>
                    </div>
                  ))}
                </div>
              )}
              {seg.airspaces.length > 0 && (
                <div style={detailSectionStyle}>
                  <div style={detailHeaderStyle}>Espaces</div>
                  {seg.airspaces.map((asp, j) => (
                    <div key={j} style={{ ...detailLineStyle, color: asp.isWarning ? "#c00" : undefined }}>
                      {asp.isWarning && "⚠ "}
                      {asp.type} {asp.identifier}
                      {asp.class && ` (${asp.class})`}
                      <span style={{ color: "#888", marginLeft: 8, fontSize: 11 }}>
                        {formatAltitudeLimit(asp.lowerFt)} - {formatAltitudeLimit(asp.upperFt)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      ))}

      {/* Totals footer */}
      {totals && (
        <div style={totalsStyle}>
          <div style={totalItemStyle}>
            <span style={totalLabelStyle}>Distance totale</span>
            <span style={totalValueStyle}>{totals.distanceNm.toFixed(0)} NM</span>
          </div>
          <div style={totalItemStyle}>
            <span style={totalLabelStyle}>Temps de vol</span>
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
          <div style={{ ...totalItemStyle, background: "#1565c0", color: "#fff", padding: "8px 12px", borderRadius: 4 }}>
            <span style={totalLabelStyle}>Total requis</span>
            <span style={{ ...totalValueStyle, color: "#fff" }}>{totals.fuelTotalL.toFixed(0)} L</span>
          </div>
        </div>
      )}
    </div>
  );
}

// ============ Helper Functions ============

function parseTimeToMinutes(time: string): number {
  const [h, m] = time.split(":").map(Number);
  return (h || 0) * 60 + (m || 0);
}

function formatMinutesToTime(totalMinutes: number): string {
  const mins = totalMinutes % (24 * 60);
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
  return ft >= 3000
    ? `FL${Math.round(ft / 100).toString().padStart(3, "0")}`
    : `${ft}ft`;
}

function formatAltitudeLimit(ft: number): string {
  if (ft === 0) return "SFC";
  if (ft >= 3000) return `FL${Math.round(ft / 100)}`;
  return `${ft}ft`;
}

function findLegAirspaces(
  legs: LegAirspaces[] | undefined,
  segment: SegmentData,
  _segmentIndex: number
): LegAirspaces | null {
  if (!legs || legs.length === 0) return null;
  const byName = legs.find(
    (leg) => leg.from_waypoint === segment.from && leg.to_waypoint === segment.to
  );
  if (byName) return byName;
  const byDestination = legs.find((leg) =>
    leg.to_waypoint.includes(segment.to) || segment.to.includes(leg.to_waypoint)
  );
  if (byDestination) return byDestination;
  return null;
}

function extractFrequencies(
  legAirspaces: LegAirspaces | null,
  departureAerodrome: AerodromeInfo | null,
  destinationAerodrome: AerodromeInfo | null,
  segmentIndex: number,
  totalSegments: number
): { callsign: string; frequency: string; isClassA: boolean }[] {
  const frequencies: { callsign: string; frequency: string; priority: number; isClassA: boolean }[] = [];
  const seenCallsigns = new Set<string>();

  // Add aerodrome frequencies for first/last segments
  if (segmentIndex === 0 && departureAerodrome) {
    addAerodromeFrequencies(departureAerodrome, frequencies, seenCallsigns);
  }
  if (segmentIndex === totalSegments - 1 && destinationAerodrome) {
    addAerodromeFrequencies(destinationAerodrome, frequencies, seenCallsigns);
  }

  // Add airspace frequencies
  if (legAirspaces) {
    for (const airspace of legAirspaces.route_airspaces || []) {
      if (EXCLUDED_AIRSPACE_TYPES.has(airspace.airspace_type)) continue;
      const isClassA = airspace.airspace_type === "TMA" && airspace.airspace_class === "A";

      for (const service of airspace.services || []) {
        const priority = SERVICE_TYPE_PRIORITY[service.service_type];
        if (priority === undefined) continue;

        let callsign = service.callsign;
        if (airspace.airspace_type === "SIV") {
          callsign = airspace.identifier.replace(/\s+SIV$/i, "").trim();
        }
        if (seenCallsigns.has(callsign)) continue;

        const vhfFreq = (service.frequencies || []).find((f) => {
          const mhz = parseFloat(f.frequency_mhz);
          return mhz >= 118 && mhz <= 137 && Math.abs(mhz - 121.5) > 0.01;
        });

        if (vhfFreq) {
          seenCallsigns.add(callsign);
          frequencies.push({ callsign, frequency: vhfFreq.frequency_mhz, priority, isClassA });
        }
      }
    }
  }

  frequencies.sort((a, b) => a.priority - b.priority);
  return frequencies.map(({ callsign, frequency, isClassA }) => ({ callsign, frequency, isClassA }));
}

function addAerodromeFrequencies(
  aerodrome: AerodromeInfo,
  frequencies: { callsign: string; frequency: string; priority: number; isClassA: boolean }[],
  seenCallsigns: Set<string>
) {
  const AD_SERVICE_PRIORITY: Record<string, number> = {
    "TWR": 0, "Tour": 0, "AFIS": 1, "A/A": 2, "Auto-information": 2, "ATIS": 3,
  };

  for (const service of aerodrome.services || []) {
    const priority = AD_SERVICE_PRIORITY[service.service_type];
    if (priority === undefined) continue;
    const callsign = service.callsign || `${aerodrome.icao} ${service.service_type}`;
    if (seenCallsigns.has(callsign)) continue;

    const vhfFreq = (service.frequencies || []).find((f) => {
      const mhz = f.frequency_mhz;
      return mhz >= 118 && mhz <= 137 && Math.abs(mhz - 121.5) > 0.01;
    });

    if (vhfFreq) {
      seenCallsigns.add(callsign);
      frequencies.push({
        callsign,
        frequency: vhfFreq.frequency_mhz.toFixed(3),
        priority,
        isClassA: false,
      });
    }
  }
}

function extractAirspaces(legAirspaces: LegAirspaces | null): { identifier: string; type: string; class: string | null; lowerFt: number; upperFt: number; isWarning: boolean }[] {
  if (!legAirspaces) return [];

  const WARNING_TYPES = new Set(["R", "P", "D", "TSA", "CBA"]);
  const result: { identifier: string; type: string; class: string | null; lowerFt: number; upperFt: number; isWarning: boolean }[] = [];
  const seen = new Set<string>();

  for (const asp of legAirspaces.route_airspaces || []) {
    if (EXCLUDED_AIRSPACE_TYPES.has(asp.airspace_type)) continue;
    if (seen.has(asp.identifier)) continue;
    seen.add(asp.identifier);

    result.push({
      identifier: asp.identifier,
      type: asp.airspace_type,
      class: asp.airspace_class,
      lowerFt: asp.lower_limit_ft,
      upperFt: asp.upper_limit_ft,
      isWarning: WARNING_TYPES.has(asp.airspace_type) || asp.airspace_class === "A",
    });
  }

  return result;
}

function getWindDataForSegment(
  simulation: SimulationResponse | null,
  modelId: string,
  segmentIndex: number
): WindData | null {
  if (!simulation) return null;
  const modelResult = simulation.model_results.find((mr) => mr.model === modelId);
  if (!modelResult) return null;
  const pointIndex = segmentIndex + 1;
  const point = modelResult.points[pointIndex];
  if (!point) return null;

  const speedLevels = Object.values(point.forecast.wind_speed_levels) as number[];
  const dirLevels = Object.values(point.forecast.wind_direction_levels) as number[];
  if (speedLevels.length === 0) return null;

  return { speedKt: speedLevels[0], directionDeg: dirLevels[0] ?? 0 };
}

function calculateDrift(
  trackDeg: number,
  tasKt: number,
  wind: WindData | null
): { driftDeg: number | null; rcDeg: number | null; gsKt: number | null } {
  if (!wind || wind.speedKt === 0) {
    return { driftDeg: null, rcDeg: null, gsKt: null };
  }

  const windAngle = ((wind.directionDeg - trackDeg + 540) % 360) - 180;
  const windAngleRad = (windAngle * Math.PI) / 180;
  const crossWind = wind.speedKt * Math.sin(windAngleRad);
  const driftDeg = Math.round((60 / tasKt) * crossWind);
  const rcDeg = ((trackDeg - driftDeg) % 360 + 360) % 360;
  const headWind = wind.speedKt * Math.cos(windAngleRad);
  const gsKt = Math.round(tasKt - headWind);

  return { driftDeg, rcDeg: Math.round(rcDeg), gsKt };
}

// ============ Styles (A5 Portrait: 148mm x 210mm) ============

const containerStyle: React.CSSProperties = {
  width: "148mm",
  minHeight: "210mm",
  margin: "0 auto",
  padding: "8mm",
  background: "#fff",
  fontFamily: "'Segoe UI', system-ui, sans-serif",
  fontSize: 11,
  color: "#333",
  boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
};

const emptyStyle: React.CSSProperties = {
  padding: 24,
  color: "#888",
  textAlign: "center",
};

const headerStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  marginBottom: 16,
  paddingBottom: 8,
  borderBottom: "2px solid #1565c0",
};

const routeTitleStyle: React.CSSProperties = {
  fontSize: 16,
  fontWeight: 700,
  color: "#1565c0",
};

const dateStyle: React.CSSProperties = {
  fontSize: 12,
  color: "#666",
};

const segmentContainerStyle: React.CSSProperties = {
  marginBottom: 12,
  border: "1px solid #ddd",
  borderRadius: 4,
  overflow: "hidden",
};

const segmentHeaderStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  padding: "6px 10px",
  background: "#1565c0",
  color: "#fff",
};

const segmentTitleStyle: React.CSSProperties = {
  fontWeight: 600,
  fontSize: 12,
};

const segmentDistStyle: React.CSSProperties = {
  fontSize: 11,
  opacity: 0.9,
};

const tramerBarStyle: React.CSSProperties = {
  display: "flex",
  background: "#e3f2fd",
  borderBottom: "1px solid #ddd",
};

const tramerItemStyle: React.CSSProperties = {
  flex: 1,
  padding: "6px 8px",
  borderRight: "1px solid #bbdefb",
  textAlign: "center",
};

const tramerLabelStyle: React.CSSProperties = {
  fontSize: 9,
  fontWeight: 700,
  color: "#1565c0",
  marginBottom: 2,
};

const tramerValueStyle: React.CSSProperties = {
  fontSize: 13,
  fontWeight: 600,
  fontFamily: "monospace",
};

const tramerSubStyle: React.CSSProperties = {
  fontSize: 9,
  color: "#666",
  marginTop: 1,
};

const arrowUpStyle: React.CSSProperties = {
  color: "#2e7d32",
  marginRight: 2,
};

const arrowDownStyle: React.CSSProperties = {
  color: "#1565c0",
  marginRight: 2,
};

const detailsContainerStyle: React.CSSProperties = {
  display: "flex",
  gap: 12,
  padding: "8px 10px",
  background: "#fafafa",
};

const detailColumnStyle: React.CSSProperties = {
  flex: 1,
};

const detailSectionStyle: React.CSSProperties = {
  marginBottom: 6,
};

const detailHeaderStyle: React.CSSProperties = {
  fontSize: 10,
  fontWeight: 600,
  color: "#555",
  marginBottom: 2,
  textTransform: "uppercase",
};

const detailLineStyle: React.CSSProperties = {
  fontSize: 10,
  lineHeight: 1.4,
};

const totalsStyle: React.CSSProperties = {
  display: "flex",
  gap: 12,
  marginTop: 16,
  padding: "10px",
  background: "#f5f5f5",
  borderRadius: 4,
  flexWrap: "wrap",
};

const totalItemStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 2,
};

const totalLabelStyle: React.CSSProperties = {
  fontSize: 9,
  color: "#666",
};

const totalValueStyle: React.CSSProperties = {
  fontSize: 12,
  fontWeight: 600,
  fontFamily: "monospace",
};
