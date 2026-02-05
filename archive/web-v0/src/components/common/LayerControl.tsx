import { useMapStore } from "../../stores/mapStore";

const containerStyle: React.CSSProperties = {
  background: "rgba(255,255,255,0.92)",
  borderRadius: 6,
  padding: "8px 12px",
  boxShadow: "0 1px 4px rgba(0,0,0,0.15)",
  fontSize: 13,
};

const LAYER_LABELS: Record<string, string> = {
  airspaces: "Airspaces",
  aerodromes: "Aerodromes",
  weather: "Weather",
  route: "Route",
};

export default function LayerControl() {
  const layers = useMapStore((s) => s.layers);
  const toggleLayer = useMapStore((s) => s.toggleLayer);

  return (
    <div style={containerStyle}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>Layers</div>
      {(Object.keys(layers) as Array<keyof typeof layers>).map((key) => (
        <label
          key={key}
          style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer", padding: "2px 0" }}
        >
          <input
            type="checkbox"
            checked={layers[key]}
            onChange={() => toggleLayer(key)}
          />
          {LAYER_LABELS[key] ?? key}
        </label>
      ))}
    </div>
  );
}
