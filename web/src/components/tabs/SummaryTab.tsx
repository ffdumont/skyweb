import { useDossierStore } from "../../stores/dossierStore";
import type { SectionCompletion } from "../../data/mockDossier";
import type { TabId } from "../../stores/dossierStore";

const SECTION_LABELS: Array<{ section: string; tab: TabId; label: string }> = [
  { section: "route", tab: "route", label: "Route" },
  { section: "aerodromes", tab: "aerodromes", label: "Aérodromes" },
  { section: "airspaces", tab: "airspaces", label: "Espaces & Zones" },
  { section: "notam", tab: "notam", label: "NOTAM" },
  { section: "meteo", tab: "meteo", label: "Météo" },
  { section: "navigation", tab: "navigation", label: "Navigation" },
  { section: "fuel", tab: "fuel", label: "Carburant & Masse" },
  { section: "performance", tab: "performance", label: "Performances" },
  { section: "documents", tab: "documents", label: "Documents" },
];

const COMPLETION_INFO: Record<SectionCompletion, { label: string; color: string; bg: string }> = {
  empty: { label: "Non commencé", color: "#9e9e9e", bg: "#f5f5f5" },
  partial: { label: "En cours", color: "#f57c00", bg: "#fff3e0" },
  complete: { label: "Complet", color: "#2e7d32", bg: "#e8f5e9" },
  alert: { label: "Alerte", color: "#c62828", bg: "#ffebee" },
};

export default function SummaryTab() {
  const dossier = useDossierStore((s) => s.dossier);
  const setTab = useDossierStore((s) => s.setTab);

  if (!dossier) return null;

  const completedCount = Object.values(dossier.sections).filter((s) => s === "complete").length;
  const totalCount = Object.keys(dossier.sections).length;

  return (
    <div style={{ padding: 24, display: "flex", gap: 24, flexWrap: "wrap" }}>
      {/* Left: completion status */}
      <div style={{ flex: "1 1 400px", minWidth: 350 }}>
        <h2 style={{ margin: "0 0 4px", fontSize: 18, fontWeight: 600 }}>
          Tableau de bord
        </h2>
        <p style={{ color: "#666", fontSize: 13, marginBottom: 16 }}>
          {completedCount}/{totalCount} sections complètes
        </p>

        <div
          style={{
            background: "#fff",
            border: "1px solid #e0e0e0",
            borderRadius: 8,
            overflow: "hidden",
          }}
        >
          {SECTION_LABELS.map(({ section, tab, label }) => {
            const status = dossier.sections[section] ?? "empty";
            const info = COMPLETION_INFO[status];
            return (
              <div
                key={section}
                onClick={() => setTab(tab)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "10px 16px",
                  borderBottom: "1px solid #f0f0f0",
                  cursor: "pointer",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "#f8f9ff")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
              >
                <span style={{ fontSize: 14, fontWeight: 500 }}>{label}</span>
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
            );
          })}
        </div>
      </div>

      {/* Right: alerts & TEM */}
      <div style={{ flex: "1 1 300px", minWidth: 280 }}>
        <h3 style={{ margin: "0 0 12px", fontSize: 15, fontWeight: 600 }}>Alertes</h3>
        <div
          style={{
            background: "#fff3e0",
            border: "1px solid #ffe0b2",
            borderRadius: 8,
            padding: 12,
            marginBottom: 16,
            fontSize: 13,
          }}
        >
          <div style={{ fontWeight: 600, color: "#e65100", marginBottom: 4 }}>
            Météo non collectée
          </div>
          <div style={{ color: "#666" }}>
            Les données météo n'ont pas encore été collectées pour ce vol.
          </div>
        </div>

        <div
          style={{
            background: "#ffebee",
            border: "1px solid #ffcdd2",
            borderRadius: 8,
            padding: 12,
            marginBottom: 16,
            fontSize: 13,
          }}
        >
          <div style={{ fontWeight: 600, color: "#c62828", marginBottom: 4 }}>
            Masse & centrage non vérifiés
          </div>
          <div style={{ color: "#666" }}>
            Le bilan carburant et le centrage doivent être calculés avant le vol.
          </div>
        </div>

        <h3 style={{ margin: "20px 0 12px", fontSize: 15, fontWeight: 600 }}>
          Analyse TEM
        </h3>
        <div
          style={{
            background: "#fff",
            border: "1px solid #e0e0e0",
            borderRadius: 8,
            padding: 16,
            fontSize: 13,
            color: "#666",
          }}
        >
          <div style={{ marginBottom: 8 }}>
            <strong style={{ color: "#333" }}>Menaces identifiées :</strong>
          </div>
          <ul style={{ margin: 0, paddingLeft: 20 }}>
            <li>Proximité TMA Paris au départ</li>
            <li>Relief Massif Central (segment CHATEAUDUN → LIMOGES)</li>
            <li>Zone R 212 potentiellement active</li>
          </ul>
          <div style={{ marginTop: 12 }}>
            <strong style={{ color: "#333" }}>Contremesures :</strong>
          </div>
          <ul style={{ margin: 0, paddingLeft: 20 }}>
            <li>Sortie VFR spécial confirmée avant départ</li>
            <li>Altitude 4500ft minimum sur le Massif Central</li>
            <li>Vérifier activation R 212 le jour J (AZBA)</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
