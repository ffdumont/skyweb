/** Wizard step 1: Upload a KML file (drag & drop or file picker). */

import { useCallback, useRef, useState } from "react";
import { useDossierStore } from "../../stores/dossierStore";

export default function StepUpload() {
  const uploadKml = useDossierStore((s) => s.uploadKml);
  const cancelWizard = useDossierStore((s) => s.cancelWizard);
  const uploading = useDossierStore((s) => s.wizard.uploading);
  const error = useDossierStore((s) => s.wizard.error);
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const handleFile = useCallback(
    (file: File) => {
      if (!file.name.toLowerCase().endsWith(".kml")) {
        return;
      }
      uploadKml(file);
    },
    [uploadKml],
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  const onFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 24, padding: 48 }}>
      <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600, color: "#1a1a2e" }}>
        Importer une route
      </h2>
      <p style={{ margin: 0, color: "#666", fontSize: 14, textAlign: "center", maxWidth: 420 }}>
        Glissez un fichier KML exporté depuis SD VFR Next, ou cliquez pour sélectionner un fichier.
      </p>

      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        style={{
          width: 400,
          height: 200,
          border: `2px dashed ${dragOver ? "#1a1a2e" : "#ccc"}`,
          borderRadius: 12,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 12,
          cursor: uploading ? "wait" : "pointer",
          background: dragOver ? "#f0f4ff" : "#fafafa",
          transition: "all 0.15s",
        }}
      >
        {uploading ? (
          <>
            <div style={spinnerStyle} />
            <span style={{ color: "#666", fontSize: 14 }}>Upload et correction en cours...</span>
          </>
        ) : (
          <>
            <span style={{ fontSize: 36, color: "#bbb" }}>+</span>
            <span style={{ color: "#888", fontSize: 14 }}>Fichier .kml</span>
          </>
        )}
      </div>

      <input
        ref={inputRef}
        type="file"
        accept=".kml"
        onChange={onFileChange}
        style={{ display: "none" }}
      />

      {error && (
        <div style={{ color: "#c62828", fontSize: 13, maxWidth: 420, textAlign: "center" }}>
          {error}
        </div>
      )}

      <button onClick={cancelWizard} style={cancelBtnStyle}>
        Annuler
      </button>
    </div>
  );
}

const spinnerStyle: React.CSSProperties = {
  width: 32,
  height: 32,
  border: "3px solid #e0e0e0",
  borderTopColor: "#1a1a2e",
  borderRadius: "50%",
  animation: "spin 0.8s linear infinite",
};

const cancelBtnStyle: React.CSSProperties = {
  background: "none",
  border: "1px solid #ccc",
  borderRadius: 6,
  padding: "8px 24px",
  fontSize: 14,
  color: "#666",
  cursor: "pointer",
};
