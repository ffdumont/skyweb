import { useDossierStore, type TabId } from "../../stores/dossierStore";
import type { SectionCompletion } from "../../data/mockDossier";

const STATUS_LABELS: Record<string, string> = {
  draft: "Brouillon",
  preparing: "En préparation",
  ready: "Prêt",
  archived: "Archivé",
};

const STATUS_COLORS: Record<string, string> = {
  draft: "#9e9e9e",
  preparing: "#f57c00",
  ready: "#2e7d32",
  archived: "#546e7a",
};

const TABS: Array<{ id: TabId; label: string; section?: string }> = [
  { id: "summary", label: "Résumé" },
  { id: "route", label: "Route", section: "route" },
  { id: "aerodromes", label: "Aérodromes", section: "aerodromes" },
  { id: "airspaces", label: "Espaces & Zones", section: "airspaces" },
  { id: "notam", label: "NOTAM", section: "notam" },
  { id: "meteo", label: "Météo", section: "meteo" },
  { id: "navigation", label: "Navigation", section: "navigation" },
  { id: "fuel", label: "Carburant & Masse", section: "fuel" },
  { id: "performance", label: "Performances", section: "performance" },
  { id: "documents", label: "Documents", section: "documents" },
];

const COMPLETION_COLORS: Record<SectionCompletion, string> = {
  empty: "#bdbdbd",
  partial: "#f57c00",
  complete: "#2e7d32",
  alert: "#c62828",
};

export default function DossierHeader() {
  const dossier = useDossierStore((s) => s.dossier);
  const activeTab = useDossierStore((s) => s.activeTab);
  const setTab = useDossierStore((s) => s.setTab);

  if (!dossier) return null;

  return (
    <div style={{ background: "#fff", borderBottom: "1px solid #e0e0e0", flexShrink: 0 }}>
      {/* Dossier info bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
          padding: "10px 16px 6px",
        }}
      >
        <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>{dossier.name}</h2>
        <span style={{ color: "#666", fontSize: 13 }}>{dossier.aircraft}</span>
        <span style={{ color: "#888", fontSize: 13 }}>{dossier.date}</span>
        <span
          style={{
            fontSize: 11,
            fontWeight: 600,
            color: "#fff",
            background: STATUS_COLORS[dossier.status] ?? "#999",
            padding: "2px 8px",
            borderRadius: 10,
          }}
        >
          {STATUS_LABELS[dossier.status] ?? dossier.status}
        </span>
      </div>

      {/* Tab bar */}
      <div
        style={{
          display: "flex",
          gap: 0,
          padding: "0 8px",
          overflowX: "auto",
        }}
      >
        {TABS.map((tab) => {
          const isActive = activeTab === tab.id;
          const completion = tab.section ? dossier.sections[tab.section] : undefined;
          return (
            <button
              key={tab.id}
              onClick={() => setTab(tab.id)}
              style={{
                background: "none",
                border: "none",
                borderBottom: isActive ? "2px solid #1a1a2e" : "2px solid transparent",
                padding: "8px 14px",
                fontSize: 13,
                fontWeight: isActive ? 600 : 400,
                color: isActive ? "#1a1a2e" : "#666",
                cursor: "pointer",
                whiteSpace: "nowrap",
                display: "flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              {tab.label}
              {completion && (
                <span
                  style={{
                    width: 7,
                    height: 7,
                    borderRadius: "50%",
                    background: COMPLETION_COLORS[completion],
                    display: "inline-block",
                  }}
                />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
