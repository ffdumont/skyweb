import { useMemo } from "react";
import type { RouteResponse } from "../../api/routes";
import { haversineNm, initialBearing } from "../../utils/geo";
import { formatNm, formatHdg, formatCoord } from "../../utils/units";

interface Row {
  seq: number;
  name: string;
  role: string;
  lat: number;
  lon: number;
  hdg: number | null;
  dist: number | null;
  alt: number | null;
  isIntermediate: boolean;
}

const ROLE_LABEL: Record<string, string> = {
  departure: "DEP",
  enroute: "ENR",
  arrival: "ARR",
};

function buildRows(route: RouteResponse): Row[] {
  const coords = route.coordinates ?? [];
  if (coords.length === 0) return [];

  // Coordinates are the source of truth (includes intermediate CLIMB/DESC points).
  // Waypoint refs map 1:1 to coordinates by sequence order.
  const wpMap = new Map(
    route.waypoints.map((w) => [w.sequence_order, w]),
  );

  return coords.map((c, i) => {
    const prev = i > 0 ? coords[i - 1] : null;
    const wp = wpMap.get(i + 1);
    const isIntermediate = c.is_intermediate ?? false;

    let hdg: number | null = null;
    let dist: number | null = null;
    if (prev) {
      dist = haversineNm(prev.lat, prev.lon, c.lat, c.lon);
      hdg = initialBearing(prev.lat, prev.lon, c.lat, c.lon);
    }

    let role = "";
    if (isIntermediate) {
      role = c.name?.startsWith("CLIMB") ? "CLB" : "DSC";
    } else if (wp) {
      role = ROLE_LABEL[wp.role] ?? wp.role;
    } else {
      role = "ENR";
    }

    return {
      seq: i + 1,
      name: c.name ?? `WPT${i + 1}`,
      role,
      lat: c.lat,
      lon: c.lon,
      hdg,
      dist,
      alt: c.altitude_ft ?? null,
      isIntermediate,
    };
  });
}

const tableStyle: React.CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: 12,
};

const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "4px 6px",
  borderBottom: "2px solid #ddd",
  fontWeight: 600,
  whiteSpace: "nowrap",
};

const tdStyle: React.CSSProperties = {
  padding: "3px 6px",
  borderBottom: "1px solid #eee",
  fontFamily: "monospace",
  whiteSpace: "nowrap",
};

const roleBadge: Record<string, React.CSSProperties> = {
  DEP: { color: "#2e7d32", fontWeight: 600 },
  ARR: { color: "#c62828", fontWeight: 600 },
  ENR: { color: "#555" },
  CLB: { color: "#1565c0", fontStyle: "italic" },
  DSC: { color: "#e65100", fontStyle: "italic" },
};

export default function RouteTable({ route }: { route: RouteResponse }) {
  const rows = useMemo(() => buildRows(route), [route]);

  if (rows.length === 0) return null;

  const totalDist = rows.reduce((sum, r) => sum + (r.dist ?? 0), 0);

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 4,
        }}
      >
        <h4 style={{ margin: 0, fontSize: 13 }}>Nav Log</h4>
        <span style={{ fontSize: 11, color: "#888" }}>
          {formatNm(totalDist)}
        </span>
      </div>
      <table style={tableStyle}>
        <thead>
          <tr>
            <th style={thStyle}>#</th>
            <th style={thStyle}>WPT</th>
            <th style={thStyle}>Lat</th>
            <th style={thStyle}>Lon</th>
            <th style={{ ...thStyle, textAlign: "right" }}>Cap</th>
            <th style={{ ...thStyle, textAlign: "right" }}>Dist</th>
            <th style={{ ...thStyle, textAlign: "right" }}>Alt</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr
              key={r.seq}
              style={{
                background: r.isIntermediate
                  ? "#f0f4ff"
                  : i % 2 === 0
                    ? "#fafafa"
                    : "transparent",
              }}
            >
              <td style={tdStyle}>{r.seq}</td>
              <td style={{ ...tdStyle, fontFamily: "inherit" }}>
                <span style={roleBadge[r.role] ?? {}}>{r.name}</span>
                <span
                  style={{
                    marginLeft: 4,
                    fontSize: 10,
                    color: "#999",
                  }}
                >
                  {r.role}
                </span>
              </td>
              <td style={tdStyle}>{formatCoord(r.lat)}</td>
              <td style={tdStyle}>{formatCoord(r.lon)}</td>
              <td style={{ ...tdStyle, textAlign: "right" }}>
                {r.hdg != null ? formatHdg(r.hdg) : "—"}
              </td>
              <td style={{ ...tdStyle, textAlign: "right" }}>
                {r.dist != null ? formatNm(r.dist) : "—"}
              </td>
              <td style={{ ...tdStyle, textAlign: "right" }}>
                {r.alt != null ? `${r.alt}` : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
