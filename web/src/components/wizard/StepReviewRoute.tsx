/** Wizard step 2: Visual review of the corrected route. */

import { useDossierStore } from "../../stores/dossierStore";
import RouteDisplay from "../route/RouteDisplay";

export default function StepReviewRoute() {
  const waypoints = useDossierStore((s) => s.wizard.computedWaypoints);
  const segments = useDossierStore((s) => s.wizard.computedSegments);
  const groundProfile = useDossierStore((s) => s.wizard.groundProfile);
  const routeName = useDossierStore((s) => s.wizard.uploadedRoute?.name ?? "");
  const goBack = useDossierStore((s) => s.goBackToUpload);
  const validate = useDossierStore((s) => s.validateRoute);

  if (!waypoints || !segments) return null;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "12px 16px",
          background: "#fff",
          borderBottom: "1px solid #e0e0e0",
          flexShrink: 0,
        }}
      >
        <div>
          <span style={{ fontSize: 15, fontWeight: 600, color: "#1a1a2e" }}>
            Route importée : {routeName}
          </span>
          <span style={{ marginLeft: 12, fontSize: 12, color: "#888" }}>
            {waypoints.filter((w) => !w.is_intermediate).length} waypoints · {segments.length} segments
          </span>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={goBack} style={secondaryBtnStyle}>
            Retour
          </button>
          <button onClick={validate} style={primaryBtnStyle}>
            Valider la route
          </button>
        </div>
      </div>

      {/* Route visualization */}
      <div style={{ flex: 1, minHeight: 0 }}>
        <RouteDisplay
          waypoints={waypoints}
          segments={segments}
          groundProfile={groundProfile ?? undefined}
        />
      </div>
    </div>
  );
}

const primaryBtnStyle: React.CSSProperties = {
  background: "#1a1a2e",
  color: "#fff",
  border: "none",
  borderRadius: 6,
  padding: "8px 20px",
  fontSize: 14,
  fontWeight: 500,
  cursor: "pointer",
};

const secondaryBtnStyle: React.CSSProperties = {
  background: "none",
  border: "1px solid #ccc",
  borderRadius: 6,
  padding: "8px 20px",
  fontSize: 14,
  color: "#666",
  cursor: "pointer",
};
