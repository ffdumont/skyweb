import { useState, useMemo, useEffect } from "react";
import { useDossierStore } from "../../stores/dossierStore";
import RouteProfile from "../route/RouteProfile";
import { runWeatherSimulation, getWeatherModels } from "../../api/client";
import type { SimulationResponse, ModelPoint, WeatherModel } from "../../api/types";

// Weather variables to display
const VARIABLES = [
  { id: "temperature", name: "Température sol", unit: "°C" },
  { id: "wind_ground", name: "Vent sol", unit: "" },
  { id: "wind_altitude", name: "Vent en altitude", unit: "" },
  { id: "wind_gusts", name: "Rafales", unit: "kt" },
  { id: "cloud_low", name: "Nuages bas", unit: "%" },
  { id: "cloud_total", name: "Nébulosité", unit: "%" },
  { id: "precip", name: "Précipitations", unit: "mm" },
  { id: "visibility", name: "Visibilité", unit: "km" },
  { id: "vfr_status", name: "Statut VFR", unit: "" },
];

// Default models if API fails
const DEFAULT_MODELS: WeatherModel[] = [
  { id: "arome", name: "AROME", provider: "Météo-France", horizon_hours: 48, color: "#0066cc" },
  { id: "ecmwf", name: "ECMWF IFS", provider: "ECMWF", horizon_hours: 96, color: "#009966" },
  { id: "gfs", name: "GFS", provider: "NOAA", horizon_hours: 384, color: "#cc6600" },
  { id: "icon", name: "ICON", provider: "DWD", horizon_hours: 180, color: "#9933cc" },
];

interface Simulation {
  id: string;
  created_at: string;
  departure_datetime: string;
  cruise_speed_kt: number;
  response: SimulationResponse;
}

export default function MeteoTab() {
  const routeData = useDossierStore((s) => s.routeData);
  const dossier = useDossierStore((s) => s.dossier);

  // Shared weather simulation state from store
  const weatherSimulations = useDossierStore((s) => s.weatherSimulations);
  const currentWeatherSimulationId = useDossierStore((s) => s.currentWeatherSimulationId);
  const addWeatherSimulation = useDossierStore((s) => s.addWeatherSimulation);
  const setCurrentWeatherSimulation = useDossierStore((s) => s.setCurrentWeatherSimulation);
  const deleteWeatherSimulation = useDossierStore((s) => s.deleteWeatherSimulation);

  // Available models from API
  const [availableModels, setAvailableModels] = useState<WeatherModel[]>(DEFAULT_MODELS);

  // Local UI state
  const [selectedModels, setSelectedModels] = useState<Set<string>>(new Set(["arome", "ecmwf"]));
  const [selectedVariables, setSelectedVariables] = useState<Set<string>>(
    new Set(["temperature", "wind_ground", "wind_altitude", "cloud_low", "vfr_status"])
  );
  const [simulationLoading, setSimulationLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Simulation parameters
  const [departureDatetime, setDepartureDatetime] = useState(() => {
    if (dossier?.date) {
      // dossier.date is in YYYY-MM-DD format, add default time
      return `${dossier.date}T12:00`;
    }
    const now = new Date();
    now.setHours(now.getHours() + 1, 0, 0, 0);
    return now.toISOString().slice(0, 16);
  });
  const [cruiseSpeedKt, setCruiseSpeedKt] = useState(100);

  // Load available models on mount
  useEffect(() => {
    getWeatherModels()
      .then(setAvailableModels)
      .catch(() => setAvailableModels(DEFAULT_MODELS));
  }, []);

  // Waypoints for API call (include per-waypoint altitude)
  const waypoints = useMemo(() => {
    if (!routeData?.waypoints) return [];
    return routeData.waypoints
      .filter((wp) => !wp.is_intermediate)
      .map((wp) => ({
        name: wp.name,
        lat: wp.lat,
        lon: wp.lon,
        altitude_ft: wp.altitude_ft || 3500, // Default fallback
      }));
  }, [routeData]);

  // Current simulation (mapped from shared store)
  const currentSimulation = useMemo((): Simulation | null => {
    if (!currentWeatherSimulationId) return null;
    const response = weatherSimulations.find((s) => s.simulation_id === currentWeatherSimulationId);
    if (!response) return null;
    return {
      id: response.simulation_id,
      created_at: response.simulated_at,
      departure_datetime: response.navigation_datetime,
      cruise_speed_kt: cruiseSpeedKt,
      response,
    };
  }, [weatherSimulations, currentWeatherSimulationId, cruiseSpeedKt]);

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
    if (waypoints.length === 0) return;

    setSimulationLoading(true);
    setError(null);

    try {
      const response = await runWeatherSimulation({
        waypoints,
        departure_datetime: new Date(departureDatetime).toISOString(),
        cruise_speed_kt: cruiseSpeedKt,
        cruise_altitude_ft: 3500, // Default fallback (per-waypoint altitudes are in waypoints)
        models: Array.from(selectedModels),
      });

      // Add to shared store (will also set as current)
      addWeatherSimulation(response);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur lors de la simulation");
    } finally {
      setSimulationLoading(false);
    }
  };

  // Format wind display
  const formatWind = (dir: number | null, speed: number | null) => {
    if (dir === null || speed === null) return "—";
    return `${String(Math.round(dir)).padStart(3, "0")}°/${Math.round(speed)}kt`;
  };

  // Format time for display
  const formatTime = (isoString: string) => {
    const date = new Date(isoString);
    return date.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
  };

  // Get value for display from ModelPoint
  const getValue = (point: ModelPoint, variableId: string): string => {
    const f = point.forecast;
    switch (variableId) {
      case "temperature":
        return f.temperature_2m !== null ? `${f.temperature_2m.toFixed(1)}°C` : "—";
      case "wind_ground":
        return formatWind(f.wind_direction_10m, f.wind_speed_10m);
      case "wind_altitude": {
        // Get wind at planned altitude (from pressure levels)
        const speedLevels = Object.values(f.wind_speed_levels);
        const dirLevels = Object.values(f.wind_direction_levels);
        if (speedLevels.length === 0) return "—";
        const speed = speedLevels[0];
        const dir = dirLevels[0] ?? 0;
        return formatWind(dir, speed);
      }
      case "wind_gusts":
        return f.wind_gusts_10m !== null ? `${Math.round(f.wind_gusts_10m)}kt` : "—";
      case "cloud_low":
        return f.cloud_cover_low !== null ? `${f.cloud_cover_low}%` : "—";
      case "cloud_total":
        return f.cloud_cover !== null ? `${f.cloud_cover}%` : "—";
      case "precip":
        return f.precipitation !== null && f.precipitation > 0 ? `${f.precipitation.toFixed(1)}mm` : "—";
      case "visibility":
        if (f.visibility === null) return "—";
        const visKm = f.visibility / 1000;
        return visKm >= 10 ? ">10km" : `${visKm.toFixed(1)}km`;
      case "vfr_status":
        const status = point.vfr_index.status;
        const icon = status === "green" ? "✅" : status === "yellow" ? "⚠️" : "🔴";
        return icon;
      default:
        return "—";
    }
  };

  // Get VFR row background color
  const getVfrBackground = (status: string) => {
    switch (status) {
      case "green": return "#d4edda";
      case "yellow": return "#fff3cd";
      case "red": return "#f8d7da";
      default: return "transparent";
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
        {/* Error message */}
        {error && (
          <div style={{
            padding: 12,
            marginBottom: 16,
            background: "#f8d7da",
            color: "#721c24",
            borderRadius: 8,
          }}>
            {error}
          </div>
        )}

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
            {simulationLoading ? "Chargement..." : "Lancer simulation"}
          </button>

          {weatherSimulations.length > 0 && (
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginLeft: "auto" }}>
              <select
                value={currentWeatherSimulationId ?? ""}
                onChange={(e) => setCurrentWeatherSimulation(e.target.value)}
                style={{
                  padding: "6px 10px",
                  border: "1px solid #ccc",
                  borderRadius: 4,
                  fontSize: 13,
                }}
              >
                {weatherSimulations.map((sim) => (
                  <option key={sim.simulation_id} value={sim.simulation_id}>
                    {new Date(sim.navigation_datetime).toLocaleString("fr-FR", {
                      day: "2-digit",
                      month: "2-digit",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </option>
                ))}
              </select>
              {currentWeatherSimulationId && (
                <button
                  onClick={() => deleteWeatherSimulation(currentWeatherSimulationId)}
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
                  X
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
              {availableModels.map((model) => (
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
            <div style={{ fontSize: 48, marginBottom: 16 }}>*</div>
            <div style={{ fontSize: 15 }}>
              Lancez une simulation pour voir les prévisions météo le long de votre route.
            </div>
          </div>
        )}

        {/* Model sections */}
        {currentSimulation &&
          currentSimulation.response.model_results
            .filter((mr) => selectedModels.has(mr.model))
            .map((modelResult) => {
              const modelConfig = availableModels.find((m) => m.id === modelResult.model)
                ?? { name: modelResult.model, color: "#666", provider: "", horizon_hours: 0 };

              const activeVariables = VARIABLES.filter((v) => selectedVariables.has(v.id));

              return (
                <div
                  key={modelResult.model}
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
                      background: modelConfig.color,
                      color: "#fff",
                    }}
                  >
                    <span style={{ fontWeight: 600 }}>{modelConfig.name}</span>
                    <span style={{ fontSize: 12, opacity: 0.9 }}>({modelConfig.provider})</span>
                    <span style={{ marginLeft: "auto", fontSize: 12, opacity: 0.9 }}>
                      {modelConfig.horizon_hours}h horizon
                    </span>
                  </div>

                  {/* Forecast table */}
                  <div style={{ overflowX: "auto" }}>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                      <thead>
                        <tr style={{ background: "#f8f9fa" }}>
                          <th style={thStyle}></th>
                          {modelResult.points.map((pt, idx) => {
                            const wp = currentSimulation.response.waypoints[pt.waypoint_index];
                            return (
                              <th key={idx} style={{ ...thStyle, textAlign: "center" }}>
                                <div style={{ fontWeight: 600 }}>{wp?.waypoint_name ?? `WP${idx}`}</div>
                                <div style={{ fontSize: 11, color: "#666", fontWeight: 400 }}>
                                  {wp ? `${formatTime(wp.estimated_time_utc)} · FL${Math.round(wp.altitude_ft / 100)}` : ""}
                                </div>
                              </th>
                            );
                          })}
                        </tr>
                      </thead>
                      <tbody>
                        {activeVariables.map((variable) => (
                          <tr key={variable.id} style={{ borderTop: "1px solid #eee" }}>
                            <td style={{ ...tdStyle, fontWeight: 500, color: "#555" }}>
                              {variable.name}
                            </td>
                            {modelResult.points.map((pt, idx) => (
                              <td
                                key={idx}
                                style={{
                                  ...tdStyle,
                                  textAlign: "center",
                                  fontFamily: "monospace",
                                  background: variable.id === "vfr_status"
                                    ? getVfrBackground(pt.vfr_index.status)
                                    : "transparent",
                                }}
                                title={variable.id === "vfr_status" ? pt.vfr_index.details : undefined}
                              >
                                {getValue(pt, variable.id)}
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
