import { useRef } from "react";
import { useRouteStore } from "../../stores/routeStore";

const buttonStyle: React.CSSProperties = {
  padding: "8px 14px",
  background: "#0078d7",
  color: "#fff",
  border: "none",
  borderRadius: 4,
  cursor: "pointer",
  fontSize: 13,
  fontWeight: 500,
};

export default function RouteImport() {
  const inputRef = useRef<HTMLInputElement>(null);
  const importKml = useRouteStore((s) => s.importKml);
  const loading = useRouteStore((s) => s.loading);
  const route = useRouteStore((s) => s.route);

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      await importKml(file);
    }
    // Reset input so the same file can be re-selected
    if (inputRef.current) inputRef.current.value = "";
  };

  if (route) return null; // Hide when a route is loaded

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept=".kml,.kmz"
        onChange={handleFile}
        style={{ display: "none" }}
      />
      <button
        style={buttonStyle}
        onClick={() => inputRef.current?.click()}
        disabled={loading}
      >
        {loading ? "Importing..." : "Import KML"}
      </button>
    </>
  );
}
