import { useEffect } from "react";
import { useRouteStore } from "../../stores/routeStore";
import RouteTable from "../route/RouteTable";
import { formatNm } from "../../utils/units";

const panelStyle: React.CSSProperties = {
  position: "absolute",
  right: 0,
  top: 0,
  bottom: 220,
  width: 380,
  background: "rgba(255,255,255,0.95)",
  boxShadow: "-2px 0 8px rgba(0,0,0,0.15)",
  overflowY: "auto",
  zIndex: 20,
  padding: 16,
  display: "flex",
  flexDirection: "column",
  gap: 12,
};

export default function RouteAnalysisPanel() {
  const route = useRouteStore((s) => s.route);
  const analysis = useRouteStore((s) => s.analysis);
  const loading = useRouteStore((s) => s.loading);
  const error = useRouteStore((s) => s.error);
  const loadAnalysis = useRouteStore((s) => s.loadAnalysis);
  const clearRoute = useRouteStore((s) => s.clearRoute);

  useEffect(() => {
    if (route && !analysis) {
      loadAnalysis();
    }
  }, [route, analysis, loadAnalysis]);

  if (!route) return null;

  return (
    <div style={panelStyle}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3 style={{ margin: 0 }}>{route.name}</h3>
        <button
          onClick={clearRoute}
          style={{
            background: "none",
            border: "1px solid #ccc",
            borderRadius: 4,
            padding: "4px 8px",
            cursor: "pointer",
          }}
        >
          Close
        </button>
      </div>

      {route.departure_icao && route.arrival_icao && (
        <div style={{ color: "#666", fontSize: 14 }}>
          {route.departure_icao} → {route.arrival_icao}
        </div>
      )}

      <RouteTable route={route} />

      {loading && <div style={{ color: "#888" }}>Loading analysis...</div>}
      {error && <div style={{ color: "red", fontSize: 13 }}>{error}</div>}

      {analysis && (
        <>
          {analysis.total_distance_nm != null && (
            <div style={{ fontWeight: 600, fontSize: 14 }}>
              Total: {formatNm(analysis.total_distance_nm)}
            </div>
          )}

          <div style={{ fontSize: 13 }}>
            <h4 style={{ margin: "8px 0 4px" }}>Legs</h4>
            {analysis.legs.map((leg, i) => (
              <div
                key={i}
                style={{
                  marginBottom: 8,
                  padding: 8,
                  background: "#f5f5f5",
                  borderRadius: 4,
                }}
              >
                <div style={{ fontWeight: 500 }}>
                  {leg.from_waypoint} → {leg.to_waypoint} ({formatNm(leg.distance_nm)})
                </div>
                {leg.airspaces.length > 0 && (
                  <ul style={{ margin: "4px 0 0", paddingLeft: 20 }}>
                    {leg.airspaces.map((as, j) => (
                      <li key={j} style={{ fontSize: 12, color: "#555" }}>
                        {as.name} ({as.type}) — {as.lower_limit} to {as.upper_limit}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </>
      )}

    </div>
  );
}
