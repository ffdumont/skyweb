interface Props {
  title: string;
  description: string;
  items?: string[];
  status?: "available" | "planned" | "unavailable";
}

const STATUS_INFO: Record<string, { label: string; color: string; bg: string }> = {
  available: { label: "Disponible", color: "#2e7d32", bg: "#e8f5e9" },
  planned: { label: "Planifié", color: "#f57c00", bg: "#fff3e0" },
  unavailable: { label: "Non disponible", color: "#c62828", bg: "#ffebee" },
};

export default function PlaceholderTab({ title, description, items, status = "planned" }: Props) {
  const info = STATUS_INFO[status];
  return (
    <div style={{ padding: 32, maxWidth: 800 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>{title}</h2>
        <span
          style={{
            fontSize: 11,
            fontWeight: 600,
            color: info.color,
            background: info.bg,
            padding: "2px 10px",
            borderRadius: 10,
          }}
        >
          {info.label}
        </span>
      </div>
      <p style={{ color: "#666", fontSize: 14, lineHeight: 1.5, marginBottom: 20 }}>{description}</p>
      {items && items.length > 0 && (
        <div
          style={{
            background: "#fff",
            border: "1px solid #e0e0e0",
            borderRadius: 8,
            padding: 16,
          }}
        >
          <h4 style={{ margin: "0 0 8px", fontSize: 13, fontWeight: 600, color: "#555" }}>
            Contenu prévu
          </h4>
          <ul style={{ margin: 0, paddingLeft: 20 }}>
            {items.map((item, i) => (
              <li key={i} style={{ fontSize: 13, color: "#666", marginBottom: 4 }}>
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
