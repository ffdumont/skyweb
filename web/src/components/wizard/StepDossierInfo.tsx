/** Wizard step 2: Fill dossier metadata (name, aircraft, departure date). */

import { useEffect, useState } from "react";
import { useDossierStore } from "../../stores/dossierStore";
import * as api from "../../api/client";
import type { AircraftSummary } from "../../api/types";

export default function StepDossierInfo() {
  const dossierName = useDossierStore((s) => s.wizard.dossierName);
  const aircraftId = useDossierStore((s) => s.wizard.aircraftId);
  const departureDateTime = useDossierStore((s) => s.wizard.departureDateTime);
  const creating = useDossierStore((s) => s.wizard.creating);
  const error = useDossierStore((s) => s.wizard.error);
  const setDossierName = useDossierStore((s) => s.setDossierName);
  const setAircraftId = useDossierStore((s) => s.setAircraftId);
  const setDepartureDateTime = useDossierStore((s) => s.setDepartureDateTime);
  const goBack = useDossierStore((s) => s.goBackToUpload);
  const create = useDossierStore((s) => s.createDossier);

  const [aircraft, setAircraft] = useState<AircraftSummary[]>([]);

  useEffect(() => {
    api.listAircraft().then(setAircraft).catch(() => {});
  }, []);

  const canCreate = dossierName.trim().length > 0 && departureDateTime.length > 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 24, padding: 48 }}>
      <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600, color: "#1a1a2e" }}>
        Informations du dossier
      </h2>

      <div style={{ width: 400, display: "flex", flexDirection: "column", gap: 16 }}>
        {/* Name */}
        <label style={labelStyle}>
          Nom du dossier
          <input
            type="text"
            value={dossierName}
            onChange={(e) => setDossierName(e.target.value)}
            style={inputStyle}
            placeholder="Ex: LFXU → LFBP"
          />
        </label>

        {/* Aircraft */}
        <label style={labelStyle}>
          Avion (optionnel)
          <select
            value={aircraftId ?? ""}
            onChange={(e) => setAircraftId(e.target.value || null)}
            style={inputStyle}
          >
            <option value="">— Aucun avion sélectionné —</option>
            {aircraft.map((a) => (
              <option key={a.id} value={a.id}>
                {a.registration} — {a.type_name}
              </option>
            ))}
          </select>
        </label>

        {/* Departure datetime */}
        <label style={labelStyle}>
          Date et heure de départ (UTC)
          <input
            type="datetime-local"
            value={departureDateTime}
            onChange={(e) => setDepartureDateTime(e.target.value)}
            style={inputStyle}
          />
        </label>
      </div>

      {error && (
        <div style={{ color: "#c62828", fontSize: 13, maxWidth: 420, textAlign: "center" }}>
          {error}
        </div>
      )}

      <div style={{ display: "flex", gap: 12 }}>
        <button onClick={goBack} disabled={creating} style={secondaryBtnStyle}>
          Retour
        </button>
        <button
          onClick={create}
          disabled={!canCreate || creating}
          style={{
            ...primaryBtnStyle,
            opacity: canCreate && !creating ? 1 : 0.5,
            cursor: canCreate && !creating ? "pointer" : "not-allowed",
          }}
        >
          {creating ? "Création en cours..." : "Créer le dossier"}
        </button>
      </div>
    </div>
  );
}

const labelStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 4,
  fontSize: 13,
  fontWeight: 500,
  color: "#333",
};

const inputStyle: React.CSSProperties = {
  padding: "8px 12px",
  fontSize: 14,
  border: "1px solid #ccc",
  borderRadius: 6,
  outline: "none",
};

const primaryBtnStyle: React.CSSProperties = {
  background: "#1a1a2e",
  color: "#fff",
  border: "none",
  borderRadius: 6,
  padding: "8px 24px",
  fontSize: 14,
  fontWeight: 500,
  cursor: "pointer",
};

const secondaryBtnStyle: React.CSSProperties = {
  background: "none",
  border: "1px solid #ccc",
  borderRadius: 6,
  padding: "8px 24px",
  fontSize: 14,
  color: "#666",
  cursor: "pointer",
};
