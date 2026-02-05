import { useMapStore } from "../../stores/mapStore";

const bannerStyle: React.CSSProperties = {
  background: "rgba(255,255,255,0.92)",
  borderRadius: 6,
  padding: "6px 12px",
  boxShadow: "0 1px 4px rgba(0,0,0,0.15)",
  fontSize: 12,
  color: "#555",
};

export default function AiracBanner() {
  const cycle = useMapStore((s) => s.airacCycle);

  return (
    <div style={bannerStyle}>
      AIRAC {cycle ?? "—"}
    </div>
  );
}
