/**
 * DocumentsTab - Document generation and preview.
 *
 * Currently features:
 * - Navigation log PDF preview (A5 portrait, TRAMER method)
 *
 * Planned:
 * - Fiche préparation 4120
 * - Export FPL Garmin
 * - Checklists
 */

import { useState } from "react";
import NavigationPdfPreview from "../pdf/NavigationPdfPreview";

type DocumentType = "navlog" | "prep4120" | "fpl" | "checklist";

interface DocumentOption {
  id: DocumentType;
  label: string;
  description: string;
  available: boolean;
}

const DOCUMENT_OPTIONS: DocumentOption[] = [
  { id: "navlog", label: "Journal de navigation", description: "Log de nav A5 avec méthode TRAMER", available: true },
  { id: "prep4120", label: "Fiche préparation 4120", description: "Formulaire de préparation de vol", available: false },
  { id: "fpl", label: "Export FPL Garmin", description: "Plan de vol pour GPS Garmin", available: false },
  { id: "checklist", label: "Checklist documents", description: "Liste des éléments à emporter", available: false },
];

export default function DocumentsTab() {
  const [selectedDoc, setSelectedDoc] = useState<DocumentType>("navlog");
  const [showPreview, setShowPreview] = useState(true);

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      {/* Document selector bar */}
      <div style={selectorBarStyle}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {DOCUMENT_OPTIONS.map((doc) => (
            <button
              key={doc.id}
              onClick={() => doc.available && setSelectedDoc(doc.id)}
              disabled={!doc.available}
              style={{
                ...docButtonStyle,
                ...(selectedDoc === doc.id ? docButtonActiveStyle : {}),
                ...(doc.available ? {} : docButtonDisabledStyle),
              }}
              title={doc.description}
            >
              {doc.label}
              {!doc.available && <span style={badgeStyle}>Bientôt</span>}
            </button>
          ))}
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
            <input
              type="checkbox"
              checked={showPreview}
              onChange={(e) => setShowPreview(e.target.checked)}
            />
            Prévisualisation
          </label>
          <button style={exportButtonStyle} disabled>
            Exporter PDF
          </button>
        </div>
      </div>

      {/* Preview area */}
      <div style={previewAreaStyle}>
        {showPreview && selectedDoc === "navlog" && (
          <div style={previewScrollStyle}>
            <NavigationPdfPreview />
          </div>
        )}
        {!showPreview && (
          <div style={noPreviewStyle}>
            Prévisualisation désactivée. Activez-la pour voir le document.
          </div>
        )}
      </div>
    </div>
  );
}

// ============ Styles ============

const selectorBarStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  padding: "12px 16px",
  background: "#f8f9fa",
  borderBottom: "1px solid #e0e0e0",
  flexWrap: "wrap",
  gap: 12,
};

const docButtonStyle: React.CSSProperties = {
  padding: "8px 16px",
  border: "1px solid #ddd",
  borderRadius: 6,
  background: "#fff",
  cursor: "pointer",
  fontSize: 13,
  fontWeight: 500,
  color: "#333",
  transition: "all 0.15s",
  display: "flex",
  alignItems: "center",
  gap: 8,
};

const docButtonActiveStyle: React.CSSProperties = {
  background: "#1565c0",
  color: "#fff",
  borderColor: "#1565c0",
};

const docButtonDisabledStyle: React.CSSProperties = {
  opacity: 0.6,
  cursor: "not-allowed",
  background: "#f5f5f5",
};

const badgeStyle: React.CSSProperties = {
  fontSize: 9,
  padding: "2px 6px",
  background: "#e0e0e0",
  borderRadius: 10,
  color: "#666",
  textTransform: "uppercase",
  fontWeight: 600,
};

const exportButtonStyle: React.CSSProperties = {
  padding: "8px 20px",
  border: "none",
  borderRadius: 6,
  background: "#1565c0",
  color: "#fff",
  cursor: "pointer",
  fontSize: 13,
  fontWeight: 600,
  opacity: 0.5,
};

const previewAreaStyle: React.CSSProperties = {
  flex: 1,
  overflow: "hidden",
  background: "#e0e0e0",
};

const previewScrollStyle: React.CSSProperties = {
  height: "100%",
  overflow: "auto",
  padding: 24,
};

const noPreviewStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  height: "100%",
  color: "#666",
  fontSize: 14,
};
