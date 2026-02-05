import { useMemo, useState, useRef, useCallback } from "react";
import type { WaypointData, GroundPoint } from "../../data/mockDossier";
import { haversineNm } from "../../utils/geo";

interface ProfilePoint {
  dist: number;
  alt: number;
  name: string;
  isIntermediate: boolean;
}

interface Props {
  waypoints: WaypointData[];
  groundProfile?: GroundPoint[];
}

const HEIGHT = 180;
const PAD = { top: 24, right: 50, bottom: 36, left: 55 };
const GRID_LINES = 4;

// Zoom levels: pixels per NM
const ZOOM_LEVELS = [6, 10, 16, 24, 36];
const DEFAULT_ZOOM_INDEX = 2; // Start at 16 px/NM

function buildProfile(waypoints: WaypointData[]): ProfilePoint[] {
  if (waypoints.length < 2) return [];

  let cumDist = 0;
  return waypoints.map((w, i) => {
    if (i > 0) {
      const prev = waypoints[i - 1];
      cumDist += haversineNm(prev.lat, prev.lon, w.lat, w.lon);
    }
    return {
      dist: cumDist,
      alt: w.altitude_ft ?? 0,
      name: w.name ?? "",
      isIntermediate: w.is_intermediate ?? false,
    };
  });
}

function shortenName(name: string): string {
  if (name.length <= 12) return name;
  if (name.includes(" - ")) return name.split(" - ")[0];
  return name.slice(0, 10) + "…";
}

export default function RouteProfile({ waypoints, groundProfile }: Props) {
  const pts = useMemo(() => buildProfile(waypoints), [waypoints]);
  const [zoomIndex, setZoomIndex] = useState(DEFAULT_ZOOM_INDEX);
  const containerRef = useRef<HTMLDivElement>(null);

  const pxPerNm = ZOOM_LEVELS[zoomIndex];

  const zoomIn = useCallback(() => {
    setZoomIndex((i) => Math.min(i + 1, ZOOM_LEVELS.length - 1));
  }, []);

  const zoomOut = useCallback(() => {
    setZoomIndex((i) => Math.max(i - 1, 0));
  }, []);

  const handleWheel = useCallback((e: React.WheelEvent) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      if (e.deltaY < 0) {
        setZoomIndex((i) => Math.min(i + 1, ZOOM_LEVELS.length - 1));
      } else {
        setZoomIndex((i) => Math.max(i - 1, 0));
      }
    }
  }, []);

  if (pts.length < 2) return null;

  const maxDist = pts[pts.length - 1].dist || 1;
  const flightAlts = pts.map((p) => p.alt);
  const groundAlts = groundProfile?.map((g) => g.elevation_ft) ?? [];
  const allAlts = [...flightAlts, ...groundAlts];
  const rawMax = Math.max(...allAlts, 500);
  const step = rawMax <= 2000 ? 500 : rawMax <= 5000 ? 1000 : 2000;
  const maxAlt = Math.ceil(rawMax / step) * step;

  // Dynamic width based on distance and zoom
  const contentWidth = Math.max(600, maxDist * pxPerNm + PAD.left + PAD.right);
  const plotWidth = contentWidth - PAD.left - PAD.right;
  const plotHeight = HEIGHT - PAD.top - PAD.bottom;

  const toX = (dist: number) => PAD.left + (dist / maxDist) * plotWidth;
  const toY = (alt: number) => PAD.top + plotHeight - (alt / maxAlt) * plotHeight;

  const flightPathD = pts
    .map((p, i) => `${i === 0 ? "M" : "L"}${toX(p.dist)},${toY(p.alt)}`)
    .join(" ");

  const fillD =
    `M${toX(0)},${toY(0)} ` +
    pts.map((p) => `L${toX(p.dist)},${toY(p.alt)}`).join(" ") +
    ` L${toX(maxDist)},${toY(0)}Z`;

  const hasGround = groundProfile && groundProfile.length >= 2;
  const groundPathD = hasGround
    ? groundProfile
        .map((g, i) => `${i === 0 ? "M" : "L"}${toX(g.distance_nm)},${toY(g.elevation_ft)}`)
        .join(" ")
    : "";

  const groundFillD = hasGround
    ? `M${toX(groundProfile[0].distance_nm)},${toY(0)} ` +
      groundProfile.map((g) => `L${toX(g.distance_nm)},${toY(g.elevation_ft)}`).join(" ") +
      ` L${toX(groundProfile[groundProfile.length - 1].distance_nm)},${toY(0)}Z`
    : "";

  return (
    <div style={{ position: "relative", background: "#fff" }}>
      {/* Zoom controls */}
      <div style={{ position: "absolute", top: 4, right: 8, zIndex: 10, display: "flex", gap: 4, alignItems: "center" }}>
        <span style={{ fontSize: 10, color: "#888", marginRight: 4 }}>Ctrl+molette pour zoomer</span>
        <button
          onClick={zoomOut}
          disabled={zoomIndex === 0}
          style={{
            width: 24,
            height: 24,
            border: "1px solid #ccc",
            borderRadius: 4,
            background: zoomIndex === 0 ? "#f5f5f5" : "#fff",
            cursor: zoomIndex === 0 ? "not-allowed" : "pointer",
            fontSize: 14,
            fontWeight: 600,
            color: zoomIndex === 0 ? "#bbb" : "#333",
          }}
        >
          −
        </button>
        <span style={{ fontSize: 10, color: "#666", minWidth: 50, textAlign: "center" }}>{pxPerNm} px/NM</span>
        <button
          onClick={zoomIn}
          disabled={zoomIndex === ZOOM_LEVELS.length - 1}
          style={{
            width: 24,
            height: 24,
            border: "1px solid #ccc",
            borderRadius: 4,
            background: zoomIndex === ZOOM_LEVELS.length - 1 ? "#f5f5f5" : "#fff",
            cursor: zoomIndex === ZOOM_LEVELS.length - 1 ? "not-allowed" : "pointer",
            fontSize: 14,
            fontWeight: 600,
            color: zoomIndex === ZOOM_LEVELS.length - 1 ? "#bbb" : "#333",
          }}
        >
          +
        </button>
      </div>

      {/* Scrollable profile area */}
      <div
        ref={containerRef}
        onWheel={handleWheel}
        style={{ width: "100%", height: HEIGHT, overflowX: "auto", overflowY: "hidden" }}
      >
        <svg width={contentWidth} height={HEIGHT} style={{ display: "block" }}>
          <defs>
            <linearGradient id="profile-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#0078d7" stopOpacity={0.18} />
              <stop offset="100%" stopColor="#0078d7" stopOpacity={0.02} />
            </linearGradient>
          </defs>

          {/* Grid lines + Y axis labels */}
          {Array.from({ length: GRID_LINES + 1 }, (_, i) => {
            const altVal = maxAlt - (maxAlt / GRID_LINES) * i;
            const y = PAD.top + (plotHeight / GRID_LINES) * i;
            return (
              <g key={`grid-${i}`}>
                <line x1={PAD.left} x2={contentWidth - PAD.right} y1={y} y2={y} stroke="#eee" strokeWidth={1} />
                <text x={PAD.left - 6} y={y + 4} textAnchor="end" fontSize={10} fill="#888">
                  {Math.round(altVal)}
                </text>
              </g>
            );
          })}

          {/* Y axis label */}
          <text x={12} y={PAD.top - 6} fontSize={10} fill="#888">ft</text>

          {/* Ground profile fill + line */}
          {hasGround && (
            <>
              <path d={groundFillD} fill="#c9a96e" fillOpacity={0.3} />
              <path d={groundPathD} fill="none" stroke="#a07830" strokeWidth={1.5} />
            </>
          )}

          {/* Flight profile fill + line */}
          <path d={fillD} fill="url(#profile-fill)" />
          <path d={flightPathD} fill="none" stroke="#0078d7" strokeWidth={2.5} strokeLinejoin="round" />

          {/* Waypoint markers + labels */}
          {pts.map((p, i) => {
            const x = toX(p.dist);
            const y = toY(p.alt);
            const isFirst = i === 0;
            const isLast = i === pts.length - 1;

            const prevAlt = i > 0 ? pts[i - 1].alt : p.alt;
            const nextAlt = i < pts.length - 1 ? pts[i + 1].alt : p.alt;
            const isPeak = p.alt >= prevAlt && p.alt >= nextAlt;
            const labelAbove = p.isIntermediate ? false : isFirst || isLast || isPeak;
            const labelY = labelAbove ? y - 10 : y + 14;

            return (
              <g key={i}>
                {/* Vertical dashed line for main waypoints */}
                {!p.isIntermediate && (
                  <line
                    x1={x}
                    x2={x}
                    y1={PAD.top}
                    y2={HEIGHT - PAD.bottom}
                    stroke="#ddd"
                    strokeWidth={1}
                    strokeDasharray="4,4"
                  />
                )}

                {/* Marker */}
                {p.isIntermediate ? (
                  <polygon
                    points={`${x},${y - 5} ${x + 4},${y + 3} ${x - 4},${y + 3}`}
                    fill="#ff9800"
                    stroke="#fff"
                    strokeWidth={1}
                  />
                ) : (
                  <circle cx={x} cy={y} r={5} fill="#0078d7" stroke="#fff" strokeWidth={1.5} />
                )}

                {/* Waypoint name label */}
                <text
                  x={x}
                  y={Math.max(PAD.top + 10, Math.min(HEIGHT - PAD.bottom - 4, labelY))}
                  textAnchor="middle"
                  fontSize={p.isIntermediate ? 9 : 11}
                  fontWeight={p.isIntermediate ? 400 : 600}
                  fill={p.isIntermediate ? "#e65100" : "#333"}
                >
                  {shortenName(p.name)}
                </text>

                {/* Altitude label below X axis for main waypoints */}
                {!p.isIntermediate && (
                  <text x={x} y={HEIGHT - PAD.bottom + 14} textAnchor="middle" fontSize={10} fill="#666">
                    {p.alt} ft
                  </text>
                )}
              </g>
            );
          })}

          {/* X axis: distance ticks */}
          {distanceTicks(maxDist, pxPerNm).map((d) => (
            <g key={`xtick-${d}`}>
              <line x1={toX(d)} x2={toX(d)} y1={HEIGHT - PAD.bottom} y2={HEIGHT - PAD.bottom + 4} stroke="#ccc" />
              <text x={toX(d)} y={HEIGHT - 6} textAnchor="middle" fontSize={9} fill="#999">
                {d} NM
              </text>
            </g>
          ))}

          {/* Legend */}
          <g transform={`translate(${PAD.left + 10}, 8)`}>
            <line x1={0} y1={6} x2={16} y2={6} stroke="#0078d7" strokeWidth={2.5} />
            <circle cx={8} cy={6} r={3} fill="#0078d7" />
            <text x={22} y={9} fontSize={10} fill="#555">Vol</text>
            {hasGround && (
              <>
                <line x1={55} y1={6} x2={71} y2={6} stroke="#a07830" strokeWidth={1.5} />
                <text x={77} y={9} fontSize={10} fill="#555">Relief</text>
              </>
            )}
            <polygon points={`${hasGround ? 125 : 70},3 ${hasGround ? 129 : 74},10 ${hasGround ? 121 : 66},10`} fill="#ff9800" />
            <text x={hasGround ? 135 : 80} y={9} fontSize={10} fill="#555">Interm.</text>
          </g>
        </svg>
      </div>
    </div>
  );
}

function distanceTicks(maxDist: number, pxPerNm: number): number[] {
  // Adjust tick spacing based on zoom level
  let step: number;
  if (pxPerNm >= 24) {
    step = maxDist <= 50 ? 5 : 10;
  } else if (pxPerNm >= 12) {
    step = maxDist <= 30 ? 5 : maxDist <= 100 ? 10 : 25;
  } else {
    step = maxDist <= 60 ? 10 : maxDist <= 150 ? 25 : 50;
  }

  const ticks: number[] = [];
  for (let d = step; d < maxDist; d += step) {
    ticks.push(d);
  }
  return ticks;
}
