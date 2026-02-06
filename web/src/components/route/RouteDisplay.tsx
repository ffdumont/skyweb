/** Reusable route visualization: 2D map + segment table + altitude profile. */

import { useMemo, useState } from "react";
import RouteMap from "../map/RouteMap";
import RouteProfile from "./RouteProfile";
import { formatNm, formatHdg } from "../../utils/units";
import { useDossierStore } from "../../stores/dossierStore";
import type { WaypointData, SegmentData, GroundPoint } from "../../data/mockDossier";

interface RouteDisplayProps {
  waypoints: WaypointData[];
  segments: SegmentData[];
  groundProfile?: GroundPoint[];
  /** Optional callback for altitude changes (used in wizard mode) */
  onAltitudeChange?: (waypointName: string, altitudeFt: number) => void;
  /** Hide the save button (useful in wizard where save is not applicable) */
  hideSaveButton?: boolean;
}

export default function RouteDisplay({ waypoints, segments, groundProfile, onAltitudeChange, hideSaveButton }: RouteDisplayProps) {
  const updateWaypointAltitude = useDossierStore((s) => s.updateWaypointAltitude);
  const recalculateRouteProfile = useDossierStore((s) => s.recalculateRouteProfile);
  const saveRouteAltitudes = useDossierStore((s) => s.saveRouteAltitudes);
  const isRouteModified = useDossierStore((s) => s.isRouteModified);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Handle altitude change for a segment (updates destination waypoint)
  const handleAltitudeChange = (segmentTo: string, newAltitude: number) => {
    if (isNaN(newAltitude) || newAltitude < 0) return;
    // Use provided callback (wizard) or default store method (dossier)
    if (onAltitudeChange) {
      onAltitudeChange(segmentTo, newAltitude);
    } else {
      updateWaypointAltitude(segmentTo, newAltitude);
    }
  };

  // Handle save
  const handleSave = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      await saveRouteAltitudes();
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Erreur lors de la sauvegarde");
    } finally {
      setSaving(false);
    }
  };
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
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>Segments</h3>
              {isRouteModified && (
                <span style={{ fontSize: 10, color: "#f57c00", fontWeight: 500 }}>● Modifié</span>
              )}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 12, color: "#888" }}>Total : {formatNm(totalDist)}</span>
              {!hideSaveButton && (
                <button
                  onClick={recalculateRouteProfile}
                  style={{
                    padding: "4px 12px",
                    fontSize: 12,
                    fontWeight: 500,
                    background: "#f5f5f5",
                    color: "#333",
                    border: "1px solid #ccc",
                    borderRadius: 4,
                    cursor: "pointer",
                  }}
                >
                  Recalculer profil
                </button>
              )}
              {!hideSaveButton && isRouteModified && (
                <button
                  onClick={handleSave}
                  disabled={saving}
                  style={{
                    padding: "4px 12px",
                    fontSize: 12,
                    fontWeight: 500,
                    background: saving ? "#ccc" : "#1976d2",
                    color: "#fff",
                    border: "none",
                    borderRadius: 4,
                    cursor: saving ? "not-allowed" : "pointer",
                  }}
                >
                  {saving ? "Enregistrement..." : "Enregistrer"}
                </button>
              )}
            </div>
          </div>
          {saveError && (
            <div style={{ color: "#c00", fontSize: 12, marginBottom: 8 }}>{saveError}</div>
          )}

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
                  <td style={{ ...tdStyle, textAlign: "right" }}>
                    <input
                      type="number"
                      value={seg.altitude_ft}
                      onChange={(e) => handleAltitudeChange(seg.to, parseInt(e.target.value, 10))}
                      step={500}
                      min={0}
                      max={20000}
                      style={{
                        width: 60,
                        padding: "2px 4px",
                        fontSize: 12,
                        fontFamily: "monospace",
                        textAlign: "right",
                        border: "1px solid #ddd",
                        borderRadius: 3,
                      }}
                    />
                    <span style={{ marginLeft: 2, fontSize: 11, color: "#888" }}>ft</span>
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
