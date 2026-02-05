import { useState, useMemo } from "react";
import { useDossierStore } from "../../stores/dossierStore";
import RouteProfile from "../route/RouteProfile";

// Weather models
const MODELS = [
  { id: "arome", name: "AROME", provider: "Météo-France", color: "#0066cc" },
  { id: "arpege", name: "ARPEGE", provider: "Météo-France", color: "#009966" },
  { id: "gfs", name: "GFS", provider: "NOAA", color: "#cc6600" },
  { id: "icon", name: "ICON", provider: "DWD", color: "#9933cc" },
];

// Weather variables
const VARIABLES = [
  { id: "temp_cruise", name: "Température FL", unit: "°C" },
  { id: "wind_cruise", name: "Vent FL", unit: "" },
  { id: "wind_ground", name: "Vent sol", unit: "" },
  { id: "cloud_low", name: "Nuages bas", unit: "%" },
  { id: "cloud_total", name: "Nébulosité", unit: "%" },
  { id: "precip", name: "Précipitations", unit: "mm/h" },
  { id: "visibility", name: "Visibilité", unit: "km" },
  { id: "freezing", name: "Iso 0°C", unit: "ft" },
];

// Mock simulation data
interface WaypointForecast {
  waypoint: string;
  passage_time: string;
  temp_cruise: number;
  wind_cruise_dir: number;
  wind_cruise_speed: number;
  wind_ground_dir: number;
  wind_ground_speed: number;
  cloud_low: number;
  cloud_total: number;
  precip: number;
  visibility: number;
  freezing: number;
}

interface ModelForecast {
  model_run: string;
  horizon: string;
  data: WaypointForecast[];
}

interface Simulation {
  id: string;
  created_at: string;
  departure_datetime: string;
  cruise_speed_kt: number;
  forecasts: Record<string, ModelForecast>;
}

// Generate mock forecast data
function generateMockForecast(waypoints: string[], departureTime: Date, cruiseSpeedKt: number): Simulation {
  const baseTemp = 15 + Math.random() * 10;
  const baseWindDir = 180 + Math.random() * 180;
  const baseWindSpeed = 10 + Math.random() * 30;

  const generateModelData = (modelId: string): ModelForecast => {
    const variation = modelId === "arome" ? 0 : (modelId === "arpege" ? 2 : 4);
    let cumulativeTime = 0;

    return {
      model_run: new Date(Date.now() - 6 * 3600000).toISOString(),
      horizon: modelId === "arome" ? "+42h" : "+102h",
      data: waypoints.map((wp, i) => {
        // Simulate passage time based on distance (rough estimate)
        const passageTime = new Date(departureTime.getTime() + cumulativeTime * 3600000);
        cumulativeTime += 0.75 + Math.random() * 0.5; // ~45-75 min per leg

        return {
          waypoint: wp,
          passage_time: passageTime.toISOString(),
          temp_cruise: Math.round((baseTemp + i * 2 + (Math.random() - 0.5) * variation) * 10) / 10,
          wind_cruise_dir: Math.round(baseWindDir + i * 10 + (Math.random() - 0.5) * 20) % 360,
          wind_cruise_speed: Math.round(baseWindSpeed + (Math.random() - 0.5) * variation * 2),
          wind_ground_dir: Math.round(baseWindDir - 30 + (Math.random() - 0.5) * 40) % 360,
          wind_ground_speed: Math.round(8 + Math.random() * 12),
          cloud_low: Math.round(Math.random() * 60),
          cloud_total: Math.round(20 + Math.random() * 60),
          precip: Math.round(Math.random() * 2 * 10) / 10,
          visibility: Math.round(8 + Math.random() * 12),
          freezing: Math.round(6000 + Math.random() * 4000),
        };
      }),
    };
  };

  return {
    id: `sim_${Date.now()}`,
    created_at: new Date().toISOString(),
    departure_datetime: departureTime.toISOString(),
    cruise_speed_kt: cruiseSpeedKt,
    forecasts: {
      arome: generateModelData("arome"),
      arpege: generateModelData("arpege"),
      gfs: generateModelData("gfs"),
      icon: generateModelData("icon"),
    },
  };
}

export default function MeteoTab() {
  const routeData = useDossierStore((s) => s.routeData);
  const dossier = useDossierStore((s) => s.dossier);

  // Local state for weather tab
  const [selectedModels, setSelectedModels] = useState<Set<string>>(new Set(["arome", "arpege"]));
  const [selectedVariables, setSelectedVariables] = useState<Set<string>>(
    new Set(["temp_cruise", "wind_cruise", "wind_ground", "cloud_low"])
  );
  const [simulations, setSimulations] = useState<Simulation[]>([]);
  const [currentSimulationId, setCurrentSimulationId] = useState<string | null>(null);
  const [simulationLoading, setSimulationLoading] = useState(false);

  // Simulation parameters
  const [departureDatetime, setDepartureDatetime] = useState(() => {
    if (dossier?.date) {
      return `${dossier.date}T12:00`;
    }
    const now = new Date();
    return now.toISOString().slice(0, 16);
  });
  const [cruiseSpeedKt, setCruiseSpeedKt] = useState(100);

  // Waypoint names for columns
  const waypointNames = useMemo(() => {
    if (!routeData?.waypoints) return [];
    return routeData.waypoints
      .filter((wp) => !wp.is_intermediate)
      .map((wp) => wp.name);
  }, [routeData]);

  // Current simulation
  const currentSimulation = useMemo(() => {
    return simulations.find((s) => s.id === currentSimulationId) ?? null;
  }, [simulations, currentSimulationId]);

  // Toggle functions
  const toggleModel = (modelId: string) => {
    setSelectedModels((prev) => {
      const next = new Set(prev);
      if (next.has(modelId)) {
        next.delete(modelId);
      } else {
        next.add(modelId);
      }
      return next;
    });
  };

  const toggleVariable = (variableId: string) => {
    setSelectedVariables((prev) => {
      const next = new Set(prev);
      if (next.has(variableId)) {
        next.delete(variableId);
      } else {
        next.add(variableId);
      }
      return next;
    });
  };

  // Run simulation
  const runSimulation = async () => {
    if (waypointNames.length === 0) return;

    setSimulationLoading(true);

    // Simulate API call delay
    await new Promise((resolve) => setTimeout(resolve, 1000));

    const departureDate = new Date(departureDatetime);
    const newSimulation = generateMockForecast(waypointNames, departureDate, cruiseSpeedKt);

    setSimulations((prev) => [newSimulation, ...prev]);
    setCurrentSimulationId(newSimulation.id);
    setSimulationLoading(false);
  };

  // Delete simulation
  const deleteSimulation = (simId: string) => {
    setSimulations((prev) => prev.filter((s) => s.id !== simId));
    if (currentSimulationId === simId) {
      setCurrentSimulationId(simulations.length > 1 ? simulations[0].id : null);
    }
  };

  // Format wind display
  const formatWind = (dir: number, speed: number) => `${String(dir).padStart(3, "0")}°/${speed}kt`;

  // Format time for display
  const formatTime = (isoString: string) => {
    const date = new Date(isoString);
    return date.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
  };

  // Get value for display
  const getValue = (data: WaypointForecast, variableId: string): string => {
    switch (variableId) {
      case "temp_cruise":
        return `${data.temp_cruise}°C`;
      case "wind_cruise":
        return formatWind(data.wind_cruise_dir, data.wind_cruise_speed);
      case "wind_ground":
        return formatWind(data.wind_ground_dir, data.wind_ground_speed);
      case "cloud_low":
        return `${data.cloud_low}%`;
      case "cloud_total":
        return `${data.cloud_total}%`;
      case "precip":
        return data.precip > 0 ? `${data.precip} mm/h` : "—";
      case "visibility":
        return `${data.visibility} km`;
      case "freezing":
        return `${data.freezing} ft`;
      default:
        return "—";
    }
  };

  if (!routeData?.waypoints) {
    return (
      <div style={{ padding: 24, color: "#888" }}>
        Chargez d'abord une route pour accéder aux prévisions météo.
      </div>
    );
  }

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      {/* Route Profile */}
      <div style={{ flexShrink: 0, borderBottom: "1px solid #e0e0e0" }}>
        <RouteProfile
          waypoints={routeData.waypoints}
          groundProfile={routeData.groundProfile ?? undefined}
        />
      </div>

      {/* Scrollable content */}
      <div style={{ flex: 1, overflowY: "auto", padding: 16 }}>
        {/* Simulation Controls */}
        <div
          style={{
            display: "flex",
            gap: 16,
            alignItems: "center",
            flexWrap: "wrap",
            marginBottom: 16,
            padding: 12,
            background: "#f8f9fa",
            borderRadius: 8,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <label style={{ fontSize: 13, fontWeight: 500 }}>Départ:</label>
            <input
              type="datetime-local"
              value={departureDatetime}
              onChange={(e) => setDepartureDatetime(e.target.value)}
              style={{
                padding: "6px 10px",
                border: "1px solid #ccc",
                borderRadius: 4,
                fontSize: 13,
              }}
            />
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <label style={{ fontSize: 13, fontWeight: 500 }}>Vitesse:</label>
            <input
              type="number"
              value={cruiseSpeedKt}
              onChange={(e) => setCruiseSpeedKt(Number(e.target.value))}
              style={{
                width: 70,
                padding: "6px 10px",
                border: "1px solid #ccc",
                borderRadius: 4,
                fontSize: 13,
              }}
            />
            <span style={{ fontSize: 13, color: "#666" }}>kt</span>
          </div>

          <button
            onClick={runSimulation}
            disabled={simulationLoading}
            style={{
              padding: "8px 16px",
              background: simulationLoading ? "#ccc" : "#0066cc",
              color: "#fff",
              border: "none",
              borderRadius: 4,
              fontWeight: 500,
              cursor: simulationLoading ? "not-allowed" : "pointer",
            }}
          >
            {simulationLoading ? "Chargement..." : "▶ Lancer simulation"}
          </button>

          {simulations.length > 0 && (
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginLeft: "auto" }}>
              <select
                value={currentSimulationId ?? ""}
                onChange={(e) => setCurrentSimulationId(e.target.value)}
                style={{
                  padding: "6px 10px",
                  border: "1px solid #ccc",
                  borderRadius: 4,
                  fontSize: 13,
                }}
              >
                {simulations.map((sim) => (
                  <option key={sim.id} value={sim.id}>
                    {new Date(sim.departure_datetime).toLocaleString("fr-FR", {
                      day: "2-digit",
                      month: "2-digit",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </option>
                ))}
              </select>
              {currentSimulationId && (
                <button
                  onClick={() => deleteSimulation(currentSimulationId)}
                  style={{
                    padding: "6px 10px",
                    background: "#fff",
                    border: "1px solid #dc3545",
                    borderRadius: 4,
                    color: "#dc3545",
                    cursor: "pointer",
                  }}
                  title="Supprimer cette simulation"
                >
                  🗑
                </button>
              )}
            </div>
          )}
        </div>

        {/* Filters */}
        <div
          style={{
            display: "flex",
            gap: 24,
            marginBottom: 16,
            padding: 12,
            background: "#fff",
            border: "1px solid #e0e0e0",
            borderRadius: 8,
          }}
        >
          {/* Model filters */}
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: "#666", marginBottom: 8 }}>
              Modèles
            </div>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              {MODELS.map((model) => (
                <label
                  key={model.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 4,
                    fontSize: 13,
                    cursor: "pointer",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={selectedModels.has(model.id)}
                    onChange={() => toggleModel(model.id)}
                  />
                  <span
                    style={{
                      display: "inline-block",
                      width: 8,
                      height: 8,
                      borderRadius: "50%",
                      background: model.color,
                      marginRight: 2,
                    }}
                  />
                  {model.name}
                </label>
              ))}
            </div>
          </div>

          {/* Variable filters */}
          <div style={{ borderLeft: "1px solid #e0e0e0", paddingLeft: 24 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: "#666", marginBottom: 8 }}>
              Variables
            </div>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              {VARIABLES.map((variable) => (
                <label
                  key={variable.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 4,
                    fontSize: 13,
                    cursor: "pointer",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={selectedVariables.has(variable.id)}
                    onChange={() => toggleVariable(variable.id)}
                  />
                  {variable.name}
                </label>
              ))}
            </div>
          </div>
        </div>

        {/* No simulation yet */}
        {!currentSimulation && (
          <div
            style={{
              padding: 40,
              textAlign: "center",
              color: "#888",
              background: "#f8f9fa",
              borderRadius: 8,
            }}
          >
            <div style={{ fontSize: 48, marginBottom: 16 }}>🌤</div>
            <div style={{ fontSize: 15 }}>
              Lancez une simulation pour voir les prévisions météo le long de votre route.
            </div>
          </div>
        )}

        {/* Model sections */}
        {currentSimulation &&
          MODELS.filter((m) => selectedModels.has(m.id)).map((model) => {
            const forecast = currentSimulation.forecasts[model.id];
            if (!forecast) return null;

            const activeVariables = VARIABLES.filter((v) => selectedVariables.has(v.id));

            return (
              <div
                key={model.id}
                style={{
                  marginBottom: 20,
                  border: "1px solid #e0e0e0",
                  borderRadius: 8,
                  overflow: "hidden",
                }}
              >
                {/* Model header */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    padding: "10px 12px",
                    background: model.color,
                    color: "#fff",
                  }}
                >
                  <span style={{ fontWeight: 600 }}>{model.name}</span>
                  <span style={{ fontSize: 12, opacity: 0.9 }}>({model.provider})</span>
                  <span style={{ marginLeft: "auto", fontSize: 12, opacity: 0.9 }}>
                    Run {new Date(forecast.model_run).toLocaleTimeString("fr-FR", {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}Z • Horizon {forecast.horizon}
                  </span>
                </div>

                {/* Forecast table */}
                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                    <thead>
                      <tr style={{ background: "#f8f9fa" }}>
                        <th style={thStyle}></th>
                        {forecast.data.map((d) => (
                          <th key={d.waypoint} style={{ ...thStyle, textAlign: "center" }}>
                            <div style={{ fontWeight: 600 }}>{d.waypoint}</div>
                            <div style={{ fontSize: 11, color: "#666", fontWeight: 400 }}>
                              {formatTime(d.passage_time)}
                            </div>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {activeVariables.map((variable) => (
                        <tr key={variable.id} style={{ borderTop: "1px solid #eee" }}>
                          <td style={{ ...tdStyle, fontWeight: 500, color: "#555" }}>
                            {variable.name}
                          </td>
                          {forecast.data.map((d) => (
                            <td
                              key={d.waypoint}
                              style={{
                                ...tdStyle,
                                textAlign: "center",
                                fontFamily: "monospace",
                              }}
                            >
                              {getValue(d, variable.id)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            );
          })}
      </div>
    </div>
  );
}

const thStyle: React.CSSProperties = {
  padding: "10px 12px",
  textAlign: "left",
  whiteSpace: "nowrap",
};

const tdStyle: React.CSSProperties = {
  padding: "8px 12px",
  whiteSpace: "nowrap",
};
