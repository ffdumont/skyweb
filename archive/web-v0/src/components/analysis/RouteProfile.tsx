import { useMemo } from "react";
import type { RouteResponse } from "../../api/routes";
import { haversineNm } from "../../utils/geo";

interface ProfilePoint {
  dist: number;
  alt: number;
  name: string;
  isIntermediate: boolean;
}

export interface GroundPoint {
  distance_nm: number;
  elevation_ft: number;
}

interface Props {
  route: RouteResponse;
  groundProfile?: GroundPoint[];
}

const PAD = { top: 18, right: 16, bottom: 28, left: 46 };
const GRID_LINES = 4;

function buildProfile(route: RouteResponse): ProfilePoint[] {
  const coords = route.coordinates ?? [];
  if (coords.length < 2) return [];

  let cumDist = 0;
  return coords.map((c, i) => {
    if (i > 0) {
      const prev = coords[i - 1];
      cumDist += haversineNm(prev.lat, prev.lon, c.lat, c.lon);
    }
    return {
      dist: cumDist,
      alt: c.altitude_ft ?? 0,
      name: c.name ?? "",
      isIntermediate: c.is_intermediate ?? false,
    };
  });
}

function shortenName(name: string): string {
  if (name.length <= 10) return name;
  if (name.includes(" - ")) return name.split(" - ")[0];
  return name.slice(0, 8) + "\u2026";
}

export default function RouteProfile({ route, groundProfile }: Props) {
  const pts = useMemo(() => buildProfile(route), [route]);

  if (pts.length < 2) return null;

  const maxDist = pts[pts.length - 1].dist || 1;
  const flightAlts = pts.map((p) => p.alt);
  const groundAlts = groundProfile?.map((g) => g.elevation_ft) ?? [];
  const allAlts = [...flightAlts, ...groundAlts];
  const rawMax = Math.max(...allAlts, 500);
  const step = rawMax <= 2000 ? 500 : rawMax <= 5000 ? 1000 : 2000;
  const maxAlt = Math.ceil(rawMax / step) * step;

  // Flight profile: straight lines between all points (diagonals for climbs/descents)
  const flightPathD = pts
    .map((p, i) => `${i === 0 ? "M" : "L"}${toX(p.dist, maxDist)},${toY(p.alt, maxAlt)}`)
    .join(" ");

  const fillD =
    `M${toX(pts[0].dist, maxDist)},${toY(0, maxAlt)} ` +
    pts.map((p) => `L${toX(p.dist, maxDist)},${toY(p.alt, maxAlt)}`).join(" ") +
    ` L${toX(pts[pts.length - 1].dist, maxDist)},${toY(0, maxAlt)}Z`;

  // Ground profile
  const hasGround = groundProfile && groundProfile.length >= 2;
  const groundPathD = hasGround
    ? groundProfile
        .map(
          (g, i) =>
            `${i === 0 ? "M" : "L"}${toX(g.distance_nm, maxDist)},${toY(g.elevation_ft, maxAlt)}`,
        )
        .join(" ")
    : "";

  const groundFillD = hasGround
    ? `M${toX(groundProfile[0].distance_nm, maxDist)},${toY(0, maxAlt)} ` +
      groundProfile
        .map((g) => `L${toX(g.distance_nm, maxDist)},${toY(g.elevation_ft, maxAlt)}`)
        .join(" ") +
      ` L${toX(groundProfile[groundProfile.length - 1].distance_nm, maxDist)},${toY(0, maxAlt)}Z`
    : "";

  return (
    <div style={{ width: "100%", height: "100%", position: "relative" }}>
      <svg
        viewBox="0 0 900 180"
        preserveAspectRatio="none"
        style={{ width: "100%", height: "100%", display: "block" }}
      >
        <defs>
          <linearGradient id="profile-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#0078d7" stopOpacity={0.15} />
            <stop offset="100%" stopColor="#0078d7" stopOpacity={0.03} />
          </linearGradient>
        </defs>

        {/* Grid lines + Y axis labels */}
        {Array.from({ length: GRID_LINES + 1 }, (_, i) => {
          const altVal = maxAlt - (maxAlt / GRID_LINES) * i;
          const y = PAD.top + ((180 - PAD.top - PAD.bottom) / GRID_LINES) * i;
          return (
            <g key={`grid-${i}`}>
              <line
                x1={PAD.left}
                x2={900 - PAD.right}
                y1={y}
                y2={y}
                stroke="#e0e0e0"
                strokeWidth={0.5}
              />
              <text
                x={PAD.left - 4}
                y={y + 3}
                textAnchor="end"
                fontSize={9}
                fill="#999"
              >
                {Math.round(altVal)}
              </text>
            </g>
          );
        })}

        {/* Axis labels */}
        <text x={8} y={PAD.top - 4} fontSize={8} fill="#999" textAnchor="start">
          ft
        </text>
        <text x={900 - PAD.right} y={180 - 4} fontSize={8} fill="#999" textAnchor="end">
          NM
        </text>

        {/* Ground profile fill + line */}
        {hasGround && (
          <>
            <path d={groundFillD} fill="#d2b48c" fillOpacity={0.25} />
            <path
              d={groundPathD}
              fill="none"
              stroke="#8b6914"
              strokeWidth={1.2}
              strokeOpacity={0.7}
            />
          </>
        )}

        {/* Flight profile fill + line */}
        <path d={fillD} fill="url(#profile-fill)" />
        <path
          d={flightPathD}
          fill="none"
          stroke="#0078d7"
          strokeWidth={2}
          strokeLinejoin="round"
        />

        {/* Waypoint markers + labels */}
        {pts.map((p, i) => {
          const x = toX(p.dist, maxDist);
          const y = toY(p.alt, maxAlt);
          const isFirst = i === 0;
          const isLast = i === pts.length - 1;

          // Label above for DEP/ARR/peaks, below otherwise
          const prevAlt = i > 0 ? pts[i - 1].alt : p.alt;
          const nextAlt = i < pts.length - 1 ? pts[i + 1].alt : p.alt;
          const isPeak = p.alt >= prevAlt && p.alt >= nextAlt;
          const labelAbove = p.isIntermediate
            ? false
            : isFirst || isLast || isPeak;
          const labelY = labelAbove ? y - 8 : y + 12;

          return (
            <g key={i}>
              {/* Vertical dashed line at main waypoints */}
              {!p.isIntermediate && (
                <line
                  x1={x}
                  x2={x}
                  y1={PAD.top}
                  y2={180 - PAD.bottom}
                  stroke="#ddd"
                  strokeWidth={0.5}
                  strokeDasharray="3,3"
                />
              )}

              {/* Marker: diamond for intermediate, circle for main */}
              {p.isIntermediate ? (
                <polygon
                  points={`${x},${y - 4} ${x + 3.5},${y + 2} ${x - 3.5},${y + 2}`}
                  fill="#ff9800"
                  stroke="white"
                  strokeWidth={0.8}
                />
              ) : (
                <circle
                  cx={x}
                  cy={y}
                  r={3.5}
                  fill="#0078d7"
                  stroke="white"
                  strokeWidth={1}
                />
              )}

              {/* Label */}
              <text
                x={x}
                y={Math.max(PAD.top + 6, Math.min(180 - PAD.bottom - 2, labelY))}
                textAnchor="middle"
                fontSize={p.isIntermediate ? 7 : 8.5}
                fontWeight={p.isIntermediate ? 400 : 600}
                fill={p.isIntermediate ? "#e65100" : "#333"}
              >
                {shortenName(p.name)}
              </text>

              {/* Altitude below X axis for main waypoints */}
              {!p.isIntermediate && (
                <text
                  x={x}
                  y={180 - PAD.bottom + 12}
                  textAnchor="middle"
                  fontSize={7.5}
                  fill="#888"
                >
                  {p.alt}
                </text>
              )}
            </g>
          );
        })}

        {/* X axis: distance ticks */}
        {distanceTicks(maxDist).map((d) => (
          <text
            key={`xtick-${d}`}
            x={toX(d, maxDist)}
            y={180 - 4}
            textAnchor="middle"
            fontSize={8}
            fill="#aaa"
          >
            {d}
          </text>
        ))}

        {/* Legend */}
        <g transform="translate(60, 10)">
          <line x1={0} y1={4} x2={14} y2={4} stroke="#0078d7" strokeWidth={2} />
          <circle cx={7} cy={4} r={2.5} fill="#0078d7" />
          <text x={18} y={7} fontSize={8} fill="#555">Flight</text>
          {hasGround && (
            <>
              <line x1={55} y1={4} x2={69} y2={4} stroke="#8b6914" strokeWidth={1.2} />
              <text x={73} y={7} fontSize={8} fill="#555">Ground</text>
            </>
          )}
          <polygon points="115,1 118.5,7 111.5,7" fill="#ff9800" />
          <text x={123} y={7} fontSize={8} fill="#555">Intermediate</text>
        </g>
      </svg>
    </div>
  );
}

/* ----- helpers ----- */

function toX(dist: number, maxDist: number): number {
  return PAD.left + (dist / maxDist) * (900 - PAD.left - PAD.right);
}

function toY(alt: number, maxAlt: number): number {
  const h = 180 - PAD.top - PAD.bottom;
  return PAD.top + h - (alt / maxAlt) * h;
}

function distanceTicks(maxDist: number): number[] {
  const step =
    maxDist <= 30 ? 5 : maxDist <= 60 ? 10 : maxDist <= 150 ? 25 : 50;
  const ticks: number[] = [];
  for (let d = step; d < maxDist; d += step) {
    ticks.push(d);
  }
  return ticks;
}
