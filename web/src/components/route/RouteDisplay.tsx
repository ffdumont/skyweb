/** Reusable route visualization: 2D map + segment table + altitude profile. */

import { useMemo } from "react";
import RouteMap from "../map/RouteMap";
import RouteProfile from "./RouteProfile";
import { formatNm, formatHdg } from "../../utils/units";
import type { WaypointData, SegmentData, GroundPoint } from "../../data/mockDossier";

interface RouteDisplayProps {
  waypoints: WaypointData[];
  segments: SegmentData[];
  groundProfile?: GroundPoint[];
}

export default function RouteDisplay({ waypoints, segments, groundProfile }: RouteDisplayProps) {
  const totalDist = useMemo(
    () => segments.reduce((s, seg) => s + seg.distance_nm, 0),
    [segments],
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Top: map + segment table */}
      <div style={{ flex: 1, display: "flex", minHeight: 0 }}>
        {/* Map */}
        <div style={{ flex: "1 1 55%", position: "relative", minHeight: 300 }}>
          <RouteMap waypoints={waypoints} />
        </div>

        {/* Right panel: segments */}
        <div
          style={{
            flex: "1 1 45%",
            overflowY: "auto",
            background: "#fff",
            borderLeft: "1px solid #e0e0e0",
            padding: 16,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>Segments</h3>
            <span style={{ fontSize: 12, color: "#888" }}>Total : {formatNm(totalDist)}</span>
          </div>

          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: "2px solid #e0e0e0" }}>
                <th style={thStyle}>De → À</th>
                <th style={{ ...thStyle, textAlign: "right" }}>Dist</th>
                <th style={{ ...thStyle, textAlign: "right" }}>Rv</th>
                <th style={{ ...thStyle, textAlign: "right" }}>Dm</th>
                <th style={{ ...thStyle, textAlign: "right" }}>Rm</th>
                <th style={{ ...thStyle, textAlign: "right" }}>Alt</th>
              </tr>
            </thead>
            <tbody>
              {segments.map((seg, i) => (
                <tr key={i} style={{ borderBottom: "1px solid #eee" }}>
                  <td style={tdStyle}>
                    {seg.from} → {seg.to}
                  </td>
                  <td style={{ ...tdStyle, textAlign: "right", fontFamily: "monospace" }}>
                    {formatNm(seg.distance_nm)}
                  </td>
                  <td style={{ ...tdStyle, textAlign: "right", fontFamily: "monospace" }}>
                    {formatHdg(seg.rv_deg)}
                  </td>
                  <td style={{ ...tdStyle, textAlign: "right", fontFamily: "monospace" }}>
                    {seg.dm_deg > 0 ? "+" : ""}{seg.dm_deg}°
                  </td>
                  <td style={{ ...tdStyle, textAlign: "right", fontFamily: "monospace", fontWeight: 600 }}>
                    {formatHdg(seg.rm_deg)}
                  </td>
                  <td style={{ ...tdStyle, textAlign: "right", fontFamily: "monospace" }}>
                    {seg.altitude_ft} ft
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Bottom: route profile */}
      {groundProfile && groundProfile.length > 0 && (
        <div style={{ height: 180, borderTop: "1px solid #e0e0e0", background: "#fff", flexShrink: 0 }}>
          <RouteProfile waypoints={waypoints} groundProfile={groundProfile} />
        </div>
      )}
    </div>
  );
}

const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "6px 8px",
  fontWeight: 600,
  fontSize: 11,
  color: "#555",
  whiteSpace: "nowrap",
};

const tdStyle: React.CSSProperties = {
  padding: "5px 8px",
  whiteSpace: "nowrap",
};
