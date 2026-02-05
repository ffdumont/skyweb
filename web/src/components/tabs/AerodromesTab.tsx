import { useState } from "react";
import { MOCK_AERODROMES } from "../../data/mockDossier";

const ROLE_LABELS: Record<string, { label: string; color: string }> = {
  departure: { label: "Départ", color: "#2e7d32" },
  destination: { label: "Destination", color: "#c62828" },
  alternate: { label: "Dégagement", color: "#f57c00" },
};

export default function AerodromesTab() {
  const [selected, setSelected] = useState(MOCK_AERODROMES[0].icao);
  const ad = MOCK_AERODROMES.find((a) => a.icao === selected) ?? MOCK_AERODROMES[0];
  const role = ROLE_LABELS[ad.role];

  return (
    <div style={{ display: "flex", height: "100%" }}>
      {/* Left: AD list */}
      <div
        style={{
          width: 220,
          borderRight: "1px solid #e0e0e0",
          background: "#fafafa",
          overflowY: "auto",
          flexShrink: 0,
        }}
      >
        <div style={{ padding: "12px 16px", fontWeight: 600, fontSize: 13, color: "#555" }}>
          Aérodromes
        </div>
        {MOCK_AERODROMES.map((a) => {
          const r = ROLE_LABELS[a.role];
          const isActive = a.icao === selected;
          return (
            <div
              key={a.icao}
              onClick={() => setSelected(a.icao)}
              style={{
                padding: "10px 16px",
                cursor: "pointer",
                background: isActive ? "#e8eaf6" : "transparent",
                borderLeft: isActive ? "3px solid #1a1a2e" : "3px solid transparent",
              }}
            >
              <div style={{ fontWeight: 600, fontSize: 14 }}>{a.icao}</div>
              <div style={{ fontSize: 12, color: "#666" }}>{a.name}</div>
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 600,
                  color: r.color,
                  marginTop: 2,
                  display: "inline-block",
                }}
              >
                {r.label}
              </span>
            </div>
          );
        })}
        <div
          style={{
            padding: "10px 16px",
            borderTop: "1px solid #e0e0e0",
            marginTop: 8,
          }}
        >
          <button
            style={{
              width: "100%",
              padding: "6px 0",
              fontSize: 12,
              background: "#f5f5f5",
              border: "1px dashed #bbb",
              borderRadius: 4,
              cursor: "pointer",
              color: "#666",
            }}
          >
            + AD de dégagement
          </button>
        </div>
      </div>

      {/* Right: AD detail */}
      <div style={{ flex: 1, overflowY: "auto", padding: 24 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>{ad.icao}</h2>
          <span style={{ fontSize: 15, color: "#555" }}>{ad.name}</span>
          <span
            style={{
              fontSize: 11,
              fontWeight: 600,
              color: role.color,
              background: `${role.color}18`,
              padding: "2px 10px",
              borderRadius: 10,
            }}
          >
            {role.label}
          </span>
        </div>

        <div style={{ display: "flex", gap: 24, flexWrap: "wrap", marginBottom: 24 }}>
          <InfoCard label="Altitude" value={`${ad.elevation_ft} ft`} />
        </div>

        <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 8 }}>Pistes</h3>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, marginBottom: 24 }}>
          <thead>
            <tr style={{ borderBottom: "2px solid #e0e0e0" }}>
              <th style={thStyle}>QFU</th>
              <th style={{ ...thStyle, textAlign: "right" }}>Longueur</th>
              <th style={thStyle}>Revêtement</th>
            </tr>
          </thead>
          <tbody>
            {ad.runways.map((rwy, i) => (
              <tr key={i} style={{ borderBottom: "1px solid #eee" }}>
                <td style={{ ...tdStyle, fontWeight: 600 }}>{rwy.designator}</td>
                <td style={{ ...tdStyle, textAlign: "right", fontFamily: "monospace" }}>{rwy.length_m} m</td>
                <td style={tdStyle}>{rwy.surface}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 8 }}>Fréquences</h3>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, marginBottom: 24 }}>
          <thead>
            <tr style={{ borderBottom: "2px solid #e0e0e0" }}>
              <th style={thStyle}>Service</th>
              <th style={thStyle}>Indicatif</th>
              <th style={{ ...thStyle, textAlign: "right" }}>Fréquence</th>
            </tr>
          </thead>
          <tbody>
            {ad.frequencies.map((f, i) => (
              <tr key={i} style={{ borderBottom: "1px solid #eee" }}>
                <td style={tdStyle}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: "#555" }}>{f.service}</span>
                </td>
                <td style={tdStyle}>{f.callsign}</td>
                <td style={{ ...tdStyle, textAlign: "right", fontFamily: "monospace", fontWeight: 600 }}>
                  {f.mhz}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 8 }}>Notes VAC</h3>
        <div
          style={{
            background: "#fffde7",
            border: "1px solid #fff9c4",
            borderRadius: 8,
            padding: 16,
            fontSize: 13,
            color: "#666",
            fontStyle: "italic",
          }}
        >
          Aucune note VAC capitalisée pour cet aérodrome.
          Les informations telles que le sens du circuit, la piste préférentielle
          et les consignes particulières peuvent être ajoutées ici.
        </div>
      </div>
    </div>
  );
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ background: "#f5f5f5", borderRadius: 8, padding: "10px 16px", minWidth: 100 }}>
      <div style={{ fontSize: 11, color: "#888", marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 16, fontWeight: 600, fontFamily: "monospace" }}>{value}</div>
    </div>
  );
}

const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "6px 8px",
  fontWeight: 600,
  fontSize: 12,
  color: "#555",
};

const tdStyle: React.CSSProperties = {
  padding: "6px 8px",
};
