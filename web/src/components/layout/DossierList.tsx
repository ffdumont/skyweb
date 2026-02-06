import { useEffect, useState, useCallback } from "react";
import { useDossierStore } from "../../stores/dossierStore";
import { useAuthStore } from "../../stores/authStore";
import * as api from "../../api/client";
import type { DossierSummary } from "../../data/mockDossier";

const STATUS_LABELS: Record<string, string> = {
  draft: "Brouillon",
  preparing: "En préparation",
  ready: "Prêt",
  archived: "Archivé",
};

interface DossierWithRouteId extends DossierSummary {
  routeId?: string;
}

export default function DossierList() {
  const openDossier = useDossierStore((s) => s.openDossier);
  const deleteDossier = useDossierStore((s) => s.deleteDossier);
  const startWizard = useDossierStore((s) => s.startWizard);
  const demoMode = useAuthStore((s) => s.demoMode);
  const [dossiers, setDossiers] = useState<DossierWithRouteId[]>([]);
  const [loading, setLoading] = useState(true);

  const loadDossiers = useCallback(() => {
    if (demoMode) {
      setDossiers([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    api.listDossiers()
      .then((list) => {
        const mapped: DossierWithRouteId[] = list.map((d) => ({
          id: d.id,
          name: d.name,
          route: d.name,
          routeId: d.route_id,
          aircraft: d.aircraft_id ?? "",
          date: d.departure_datetime_utc?.split("T")[0] ?? "",
          status: (d.status ?? "draft") as DossierSummary["status"],
          sections: (d.sections ?? {}) as DossierSummary["sections"],
        }));
        setDossiers(mapped);
      })
      .catch(() => setDossiers([]))
      .finally(() => setLoading(false));
  }, [demoMode]);

  useEffect(() => {
    loadDossiers();
  }, [loadDossiers]);

  const handleDelete = async (e: React.MouseEvent, dossierId: string) => {
    e.stopPropagation(); // Don't trigger row click
    if (!confirm("Supprimer ce dossier ?")) return;
    await deleteDossier(dossierId);
    loadDossiers(); // Refresh list
  };

  return (
    <div style={{ padding: 32, maxWidth: 900, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 600 }}>Mes dossiers de vol</h1>
        <button
          onClick={startWizard}
          style={{
            background: "#1a1a2e",
            color: "#fff",
            border: "none",
            borderRadius: 6,
            padding: "8px 20px",
            fontSize: 14,
            fontWeight: 500,
            cursor: "pointer",
          }}
        >
          + Nouveau dossier
        </button>
      </div>

      {loading ? (
        <div style={{ color: "#888", padding: 24 }}>Chargement...</div>
      ) : demoMode ? (
        <div style={{ color: "#888", padding: 24, textAlign: "center" }}>
          En mode démo, les dossiers ne sont pas sauvegardés.<br />
          Cliquez sur "+ Nouveau dossier" pour tester l'import d'une route.
        </div>
      ) : dossiers.length === 0 ? (
        <div style={{ color: "#888", padding: 24, textAlign: "center" }}>
          Aucun dossier. Cliquez sur "+ Nouveau dossier" pour commencer.
        </div>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: "2px solid #e0e0e0", textAlign: "left" }}>
              <th style={{ padding: "8px 12px", fontWeight: 600, fontSize: 13 }}>Dossier</th>
              <th style={{ padding: "8px 12px", fontWeight: 600, fontSize: 13 }}>Avion</th>
              <th style={{ padding: "8px 12px", fontWeight: 600, fontSize: 13 }}>Date</th>
              <th style={{ padding: "8px 12px", fontWeight: 600, fontSize: 13 }}>Statut</th>
              <th style={{ padding: "8px 12px" }} />
            </tr>
          </thead>
          <tbody>
            {dossiers.map((d) => (
              <tr
                key={d.id}
                onClick={() => openDossier(d, d.routeId)}
                style={{
                  borderBottom: "1px solid #eee",
                  cursor: "pointer",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "#f0f4ff")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
              >
                <td style={{ padding: "10px 12px" }}>
                  <div style={{ fontWeight: 500 }}>{d.name}</div>
                </td>
                <td style={{ padding: "10px 12px", fontSize: 13 }}>{d.aircraft || "—"}</td>
                <td style={{ padding: "10px 12px", fontSize: 13 }}>{d.date}</td>
                <td style={{ padding: "10px 12px" }}>
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      color: "#666",
                      background: "#e8e8e8",
                      padding: "2px 8px",
                      borderRadius: 10,
                    }}
                  >
                    {STATUS_LABELS[d.status] ?? d.status}
                  </span>
                </td>
                <td style={{ padding: "10px 12px", textAlign: "right", display: "flex", gap: 12, justifyContent: "flex-end" }}>
                  <span style={{ color: "#888", fontSize: 12 }}>Ouvrir &rarr;</span>
                  <button
                    onClick={(e) => handleDelete(e, d.id)}
                    style={{
                      background: "none",
                      border: "none",
                      color: "#c62828",
                      cursor: "pointer",
                      fontSize: 14,
                      padding: 0,
                    }}
                    title="Supprimer"
                  >
                    🗑
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
