/**
 * Aerodromes tab: displays departure and destination aerodrome info
 * with SIA data (read-only) and user VAC notes (editable).
 *
 * Alternates flow:
 * - "Suggérés": click to preview info, button to add to confirmed
 * - "Confirmés": user-selected alternates, can be removed back to suggested
 */

import React, { useEffect, useState, useCallback } from "react";
import { useDossierStore } from "../../stores/dossierStore";
import * as api from "../../api/client";
import type {
  AerodromeInfo,
  AerodromeNotes,
  AlternateAerodrome,
  SaveAerodromeNotesRequest,
} from "../../api/types";

type AerodromeRole = "departure" | "destination" | "alternate";

interface AerodromeEntry {
  icao: string;
  role: AerodromeRole;
  info: AerodromeInfo | null;
  notes: AerodromeNotes | null;
  loading: boolean;
  error: string | null;
}

// Preview state for suggested alternates (not yet confirmed)
interface AlternatePreview {
  icao: string;
  info: AerodromeInfo | null;
  alternateData: AlternateAerodrome; // Keep the distance info
  loading: boolean;
  error: string | null;
}

const ROLE_LABELS: Record<AerodromeRole, { label: string; color: string }> = {
  departure: { label: "Départ", color: "#2e7d32" },
  destination: { label: "Destination", color: "#c62828" },
  alternate: { label: "Dégagement", color: "#f57c00" },
};

export default function AerodromesTab() {
  const routeData = useDossierStore((s) => s.routeData);
  const routeId = useDossierStore((s) => s.currentRouteId);
  const setCompletion = useDossierStore((s) => s.setCompletion);

  // Main aerodromes list (departure, destination, confirmed alternates)
  const [aerodromes, setAerodromes] = useState<AerodromeEntry[]>([]);
  const [selectedIcao, setSelectedIcao] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Suggested alternates from API
  const [primaryAlternates, setPrimaryAlternates] = useState<AlternateAerodrome[]>([]);
  const [secondaryAlternates, setSecondaryAlternates] = useState<AlternateAerodrome[]>([]);
  const [alternatesLoading, setAlternatesLoading] = useState(false);

  // Preview state for viewing a suggested alternate (before confirming)
  const [preview, setPreview] = useState<AlternatePreview | null>(null);

  // Track confirmed alternate ICAOs (to filter from suggested list)
  const confirmedAlternateIcaos = aerodromes
    .filter((a) => a.role === "alternate")
    .map((a) => a.icao);

  // Filter suggested alternates to exclude confirmed ones
  const filteredPrimary = primaryAlternates.filter(
    (a) => !confirmedAlternateIcaos.includes(a.icao)
  );
  const filteredSecondary = secondaryAlternates.filter(
    (a) => !confirmedAlternateIcaos.includes(a.icao)
  );

  // Extract ICAO code from waypoint name (e.g., "LFXU - LES MUREAUX" -> "LFXU")
  const extractIcao = (name: string): string => {
    const match = name.match(/^([A-Z]{4})/);
    if (match) return match[1];
    if (name.length >= 4 && /^[A-Z]{4}/.test(name.substring(0, 4))) {
      return name.substring(0, 4);
    }
    return name;
  };

  // Extract aerodrome ICAOs from route waypoints
  const extractAerodromeIcaos = useCallback((): { icao: string; role: AerodromeRole }[] => {
    if (!routeData?.waypoints?.length) return [];

    const result: { icao: string; role: AerodromeRole }[] = [];
    const waypoints = routeData.waypoints;

    const departure = waypoints.find((wp) => wp.type === "AD");
    if (departure) {
      result.push({ icao: extractIcao(departure.name), role: "departure" });
    }

    const destination = [...waypoints].reverse().find((wp) => wp.type === "AD");
    if (destination && destination.name !== departure?.name) {
      result.push({ icao: extractIcao(destination.name), role: "destination" });
    }

    return result;
  }, [routeData]);

  // Track if initial load has been done
  const initialLoadDoneRef = React.useRef(false);

  // Load aerodrome data (only on initial mount, not when selection changes)
  const loadAerodromes = useCallback(async () => {
    // Only load once
    if (initialLoadDoneRef.current) return;

    const icaos = extractAerodromeIcaos();
    if (icaos.length === 0) return;

    initialLoadDoneRef.current = true;

    const entries: AerodromeEntry[] = icaos.map(({ icao, role }) => ({
      icao,
      role,
      info: null,
      notes: null,
      loading: true,
      error: null,
    }));
    setAerodromes(entries);
    setSelectedIcao(entries[0].icao);

    const updatedEntries = await Promise.all(
      entries.map(async (entry) => {
        try {
          const [info, notes] = await Promise.all([
            api.getAerodrome(entry.icao).catch(() => null),
            api.getAerodromeNotes(entry.icao).catch(() => null),
          ]);
          return { ...entry, info, notes, loading: false };
        } catch (err) {
          return {
            ...entry,
            loading: false,
            error: err instanceof Error ? err.message : "Erreur de chargement",
          };
        }
      })
    );

    // Use functional update to preserve any alternates added during loading
    setAerodromes((prev) => {
      const alternates = prev.filter((a) => a.role === "alternate");
      return [...updatedEntries, ...alternates];
    });
  }, [extractAerodromeIcaos]);

  // Update tab completion status
  const updateTabStatus = useCallback(
    (entries: AerodromeEntry[]) => {
      const depDest = entries.filter((e) => e.role === "departure" || e.role === "destination");
      if (depDest.length === 0) {
        setCompletion("aerodromes", "empty");
        return;
      }

      const allComplete = depDest.every((e) => e.notes?.completion_status === "complete");
      const anyPartial = depDest.some(
        (e) => e.notes?.completion_status === "partial" || e.notes?.completion_status === "complete"
      );

      if (allComplete) {
        setCompletion("aerodromes", "complete");
      } else if (anyPartial) {
        setCompletion("aerodromes", "partial");
      } else {
        setCompletion("aerodromes", "alert");
      }
    },
    [setCompletion]
  );

  // Load alternates
  const loadAlternates = useCallback(async () => {
    if (!routeId) return;
    setAlternatesLoading(true);
    try {
      const response = await api.getRouteAlternates(routeId, 15);
      setPrimaryAlternates(response.primary);
      setSecondaryAlternates(response.secondary);
    } catch (err) {
      console.error("Failed to load alternates:", err);
      setPrimaryAlternates([]);
      setSecondaryAlternates([]);
    } finally {
      setAlternatesLoading(false);
    }
  }, [routeId]);

  // Load on mount and when route changes
  useEffect(() => {
    loadAerodromes();
    loadAlternates();
  }, [loadAerodromes, loadAlternates]);

  // Update tab completion status when aerodromes change
  useEffect(() => {
    updateTabStatus(aerodromes);
  }, [aerodromes, updateTabStatus]);

  // Save notes handler
  const handleSaveNotes = async (icao: string, notes: SaveAerodromeNotesRequest) => {
    setSaving(true);
    try {
      const saved = await api.saveAerodromeNotes(icao, notes);
      setAerodromes((prev) =>
        prev.map((e) => (e.icao === icao ? { ...e, notes: saved } : e))
      );
    } catch (err) {
      console.error("Failed to save aerodrome notes:", err);
      alert("Erreur lors de la sauvegarde des notes");
    } finally {
      setSaving(false);
    }
  };

  // Preview a suggested alternate (load info without adding to confirmed list)
  const handlePreviewAlternate = useCallback(async (alternate: AlternateAerodrome) => {
    // Clear main selection, show preview
    setSelectedIcao(null);
    setPreview({
      icao: alternate.icao,
      info: null,
      alternateData: alternate,
      loading: true,
      error: null,
    });

    try {
      const info = await api.getAerodrome(alternate.icao);
      setPreview((prev) =>
        prev?.icao === alternate.icao ? { ...prev, info, loading: false } : prev
      );
    } catch (err) {
      console.error(`Failed to load alternate preview ${alternate.icao}:`, err);
      setPreview((prev) =>
        prev?.icao === alternate.icao
          ? { ...prev, loading: false, error: "Erreur de chargement" }
          : prev
      );
    }
  }, []);

  // Add a previewed alternate to confirmed list
  const handleConfirmAlternate = useCallback(async () => {
    if (!preview) return;

    const { icao, info } = preview;

    // Add to aerodromes list
    const newEntry: AerodromeEntry = {
      icao,
      role: "alternate",
      info,
      notes: null,
      loading: false,
      error: null,
    };

    setAerodromes((prev) => {
      if (prev.some((a) => a.icao === icao)) return prev;
      return [...prev, newEntry];
    });

    // Clear preview, select the new entry
    setPreview(null);
    setSelectedIcao(icao);

    // Load notes in background
    try {
      const notes = await api.getAerodromeNotes(icao);
      setAerodromes((prev) =>
        prev.map((e) => (e.icao === icao ? { ...e, notes } : e))
      );
    } catch {
      // Notes not critical
    }
  }, [preview]);

  // Remove a confirmed alternate (moves back to suggested)
  const handleRemoveAlternate = useCallback((icao: string) => {
    setAerodromes((prev) => prev.filter((a) => a.icao !== icao || a.role !== "alternate"));
    // If this was selected, clear selection
    if (selectedIcao === icao) {
      setSelectedIcao(aerodromes.find((a) => a.role === "departure")?.icao || null);
    }
  }, [selectedIcao, aerodromes]);

  // Select a main aerodrome (departure, destination, or confirmed alternate)
  const handleSelectMain = useCallback((icao: string) => {
    setPreview(null); // Clear any preview
    setSelectedIcao(icao);
  }, []);

  const selectedAerodrome = aerodromes.find((a) => a.icao === selectedIcao);
  const confirmedAlternates = aerodromes.filter((a) => a.role === "alternate");

  return (
    <div style={{ display: "flex", height: "100%" }}>
      {/* Left: AD list + Alternates */}
      <div
        style={{
          width: 260,
          borderRight: "1px solid #e0e0e0",
          background: "#fafafa",
          overflowY: "auto",
          flexShrink: 0,
        }}
      >
        {/* Departure & Destination */}
        <div style={{ padding: "12px 16px", fontWeight: 600, fontSize: 13, color: "#555" }}>
          Aérodromes
        </div>
        {aerodromes.filter((a) => a.role !== "alternate").length === 0 ? (
          <div style={{ padding: "12px 16px", color: "#888", fontSize: 13 }}>
            Aucun aérodrome détecté
          </div>
        ) : (
          aerodromes
            .filter((a) => a.role !== "alternate")
            .map((a) => (
              <AerodromeListItem
                key={a.icao}
                entry={a}
                isSelected={selectedIcao === a.icao && !preview}
                onClick={() => handleSelectMain(a.icao)}
              />
            ))
        )}

        {/* Confirmed Alternates */}
        {confirmedAlternates.length > 0 && (
          <>
            <div
              style={{
                padding: "12px 16px",
                fontWeight: 600,
                fontSize: 13,
                color: "#555",
                borderTop: "1px solid #e0e0e0",
                marginTop: 8,
              }}
            >
              Dégagements
            </div>
            {confirmedAlternates.map((a) => (
              <AerodromeListItem
                key={a.icao}
                entry={a}
                isSelected={selectedIcao === a.icao && !preview}
                onClick={() => handleSelectMain(a.icao)}
                onRemove={() => handleRemoveAlternate(a.icao)}
              />
            ))}
          </>
        )}

        {/* Suggested Alternates */}
        <AlternatesSection
          primary={filteredPrimary}
          secondary={filteredSecondary}
          loading={alternatesLoading}
          onPreview={handlePreviewAlternate}
          previewIcao={preview?.icao || null}
        />
      </div>

      {/* Right: AD detail or Preview */}
      <div style={{ flex: 1, overflowY: "auto", padding: 24 }}>
        {preview ? (
          // Preview mode for suggested alternate
          <AlternatePreviewDetail
            preview={preview}
            onConfirm={handleConfirmAlternate}
            onClose={() => setPreview(null)}
          />
        ) : !selectedAerodrome ? (
          <div style={{ color: "#888", padding: 24 }}>Sélectionnez un aérodrome</div>
        ) : selectedAerodrome.loading ? (
          <div style={{ color: "#888", padding: 24 }}>Chargement...</div>
        ) : selectedAerodrome.error ? (
          <div style={{ color: "#c00", padding: 24 }}>
            Erreur: {selectedAerodrome.error}
          </div>
        ) : (
          <AerodromeDetail
            entry={selectedAerodrome}
            onSave={handleSaveNotes}
            saving={saving}
          />
        )}
      </div>
    </div>
  );
}

// ============ Aerodrome List Item ============

interface AerodromeListItemProps {
  entry: AerodromeEntry;
  isSelected: boolean;
  onClick: () => void;
  onRemove?: () => void;
}

function AerodromeListItem({ entry, isSelected, onClick, onRemove }: AerodromeListItemProps) {
  const r = ROLE_LABELS[entry.role];
  const statusIcon =
    entry.notes?.completion_status === "complete"
      ? "✓"
      : entry.notes?.completion_status === "partial"
        ? "◐"
        : "○";
  const statusColor =
    entry.notes?.completion_status === "complete"
      ? "#2e7d32"
      : entry.notes?.completion_status === "partial"
        ? "#f57c00"
        : "#bbb";

  return (
    <div
      onClick={onClick}
      style={{
        padding: "10px 16px",
        cursor: "pointer",
        background: isSelected ? "#e8eaf6" : "transparent",
        borderLeft: isSelected ? "3px solid #1a1a2e" : "3px solid transparent",
        position: "relative",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <span style={{ color: statusColor, fontSize: 12 }}>{statusIcon}</span>
        <span style={{ fontWeight: 600, fontSize: 14 }}>{entry.icao}</span>
        {onRemove && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onRemove();
            }}
            style={{
              marginLeft: "auto",
              background: "none",
              border: "none",
              color: "#999",
              cursor: "pointer",
              fontSize: 14,
              padding: "2px 6px",
            }}
            title="Retirer des dégagements"
          >
            ✕
          </button>
        )}
      </div>
      <div style={{ fontSize: 12, color: "#666" }}>
        {entry.info?.name || entry.icao}
      </div>
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
}

// ============ Alternate Preview Detail ============

interface AlternatePreviewDetailProps {
  preview: AlternatePreview;
  onConfirm: () => void;
  onClose: () => void;
}

function AlternatePreviewDetail({ preview, onConfirm, onClose }: AlternatePreviewDetailProps) {
  const { icao, info, alternateData, loading, error } = preview;

  if (loading) {
    return <div style={{ color: "#888", padding: 24 }}>Chargement...</div>;
  }

  if (error) {
    return (
      <div style={{ color: "#c00", padding: 24 }}>
        Erreur: {error}
        <button onClick={onClose} style={{ marginLeft: 16 }}>
          Fermer
        </button>
      </div>
    );
  }

  return (
    <>
      {/* Header with action buttons */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>{icao}</h2>
        <span style={{ fontSize: 15, color: "#555" }}>{info?.name || ""}</span>
        <span
          style={{
            fontSize: 11,
            fontWeight: 600,
            color: "#1976d2",
            background: "#1976d218",
            padding: "2px 10px",
            borderRadius: 10,
          }}
        >
          Suggéré
        </span>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <button
            onClick={onConfirm}
            style={{
              padding: "8px 16px",
              fontSize: 13,
              fontWeight: 500,
              background: "#2e7d32",
              color: "#fff",
              border: "none",
              borderRadius: 6,
              cursor: "pointer",
            }}
          >
            + Ajouter aux dégagements
          </button>
          <button
            onClick={onClose}
            style={{
              padding: "8px 16px",
              fontSize: 13,
              fontWeight: 500,
              background: "#eee",
              color: "#555",
              border: "none",
              borderRadius: 6,
              cursor: "pointer",
            }}
          >
            Fermer
          </button>
        </div>
      </div>

      {/* Distance info from route analysis */}
      <div style={{ display: "flex", gap: 16, marginBottom: 20 }}>
        <div style={{ background: "#e3f2fd", borderRadius: 6, padding: "8px 12px" }}>
          <div style={{ fontSize: 10, color: "#1976d2", marginBottom: 2 }}>Dist. destination</div>
          <div style={{ fontSize: 14, fontWeight: 600 }}>{alternateData.distance_to_arr_nm} NM</div>
        </div>
        <div style={{ background: "#e3f2fd", borderRadius: 6, padding: "8px 12px" }}>
          <div style={{ fontSize: 10, color: "#1976d2", marginBottom: 2 }}>Position route</div>
          <div style={{ fontSize: 14, fontWeight: 600 }}>{alternateData.route_position_nm} NM</div>
        </div>
      </div>

      {/* SIA Data Section (read-only) */}
      <SectionHeader title="INFORMATIONS SIA" badge="Lecture seule" badgeColor="#888" />

      {info ? (
        <>
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 20 }}>
            <InfoCard label="Altitude" value={info.elevation_ft ? `${info.elevation_ft} ft` : "—"} />
            <InfoCard label="Décl. mag." value={info.mag_variation ? `${info.mag_variation}°` : "—"} />
            <InfoCard label="T. réf." value={info.ref_temperature ? `${info.ref_temperature}°C` : "—"} />
            <InfoCard label="VFR" value={info.vfr ? "Oui" : "Non"} />
            <InfoCard label="Statut" value={info.status || "—"} />
          </div>

          {/* Runways */}
          {info.runways.length > 0 && (
            <>
              <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: "#555" }}>Pistes</h4>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, marginBottom: 20 }}>
                <thead>
                  <tr style={{ borderBottom: "2px solid #e0e0e0" }}>
                    <th style={thStyle}>QFU</th>
                    <th style={{ ...thStyle, textAlign: "right" }}>Dimensions</th>
                    <th style={{ ...thStyle, textAlign: "right" }}>LDA</th>
                    <th style={thStyle}>Surface</th>
                  </tr>
                </thead>
                <tbody>
                  {info.runways.map((rwy, i) => (
                    <tr key={i} style={{ borderBottom: "1px solid #eee" }}>
                      <td style={{ ...tdStyle, fontWeight: 600 }}>{rwy.designator}</td>
                      <td style={{ ...tdStyle, textAlign: "right", fontFamily: "monospace" }}>
                        {rwy.length_m && rwy.width_m
                          ? `${rwy.length_m} x ${rwy.width_m} m`
                          : rwy.length_m
                            ? `${rwy.length_m} m`
                            : "—"}
                      </td>
                      <td style={{ ...tdStyle, textAlign: "right", fontFamily: "monospace" }}>
                        {rwy.lda1_m ? `${rwy.lda1_m} m` : "—"}
                      </td>
                      <td style={tdStyle}>{rwy.surface || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}

          {/* Frequencies */}
          {info.services.length > 0 && (
            <>
              <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: "#555" }}>Fréquences</h4>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, marginBottom: 20 }}>
                <thead>
                  <tr style={{ borderBottom: "2px solid #e0e0e0" }}>
                    <th style={thStyle}>Service</th>
                    <th style={thStyle}>Indicatif</th>
                    <th style={{ ...thStyle, textAlign: "right" }}>Fréquence</th>
                    <th style={thStyle}>Horaires</th>
                  </tr>
                </thead>
                <tbody>
                  {info.services.map((svc, i) =>
                    svc.frequencies.length > 0 ? (
                      svc.frequencies.map((freq, j) => (
                        <tr key={`${i}-${j}`} style={{ borderBottom: "1px solid #eee" }}>
                          <td style={tdStyle}>
                            <span style={{ fontSize: 10, fontWeight: 700, color: "#555" }}>
                              {svc.service_type}
                            </span>
                          </td>
                          <td style={tdStyle}>{svc.callsign || "—"}</td>
                          <td style={{ ...tdStyle, textAlign: "right", fontFamily: "monospace", fontWeight: 600 }}>
                            {freq.frequency_mhz}
                          </td>
                          <td style={tdStyle}>{freq.hours_code || svc.hours_code || "—"}</td>
                        </tr>
                      ))
                    ) : (
                      <tr key={i} style={{ borderBottom: "1px solid #eee" }}>
                        <td style={tdStyle}>
                          <span style={{ fontSize: 10, fontWeight: 700, color: "#555" }}>
                            {svc.service_type}
                          </span>
                        </td>
                        <td style={tdStyle}>{svc.callsign || "—"}</td>
                        <td style={{ ...tdStyle, textAlign: "right", color: "#999" }}>—</td>
                        <td style={tdStyle}>{svc.hours_code || "—"}</td>
                      </tr>
                    )
                  )}
                </tbody>
              </table>
            </>
          )}
        </>
      ) : (
        <div style={{ color: "#888", padding: "12px 0", fontSize: 13 }}>
          Données SIA non disponibles pour cet aérodrome
        </div>
      )}
    </>
  );
}

// ============ Aerodrome Detail Component ============

interface AerodromeDetailProps {
  entry: AerodromeEntry;
  onSave: (icao: string, notes: SaveAerodromeNotesRequest) => Promise<void>;
  saving: boolean;
}

function AerodromeDetail({ entry, onSave, saving }: AerodromeDetailProps) {
  const { icao, role, info, notes } = entry;
  const roleInfo = ROLE_LABELS[role];

  // Local form state for VAC notes
  const [formData, setFormData] = useState<SaveAerodromeNotesRequest>({
    circuit_direction: notes?.circuit_direction ?? {},
    pattern_altitude_ft: notes?.pattern_altitude_ft ?? undefined,
    entry_point: notes?.entry_point ?? "",
    exit_point: notes?.exit_point ?? "",
    special_procedures: notes?.special_procedures ?? "",
    obstacles: notes?.obstacles ?? [],
  });

  const [isDirty, setIsDirty] = useState(false);

  useEffect(() => {
    setFormData({
      circuit_direction: notes?.circuit_direction ?? {},
      pattern_altitude_ft: notes?.pattern_altitude_ft ?? undefined,
      entry_point: notes?.entry_point ?? "",
      exit_point: notes?.exit_point ?? "",
      special_procedures: notes?.special_procedures ?? "",
      obstacles: notes?.obstacles ?? [],
    });
    setIsDirty(false);
  }, [notes]);

  const updateField = <K extends keyof SaveAerodromeNotesRequest>(
    key: K,
    value: SaveAerodromeNotesRequest[K]
  ) => {
    setFormData((prev) => ({ ...prev, [key]: value }));
    setIsDirty(true);
  };

  const handleSave = () => {
    onSave(icao, formData);
  };

  const runwayDesignators: string[] = [];
  if (info?.runways) {
    for (const rwy of info.runways) {
      if (rwy.designator) {
        const parts = rwy.designator.split("/");
        runwayDesignators.push(...parts);
      }
    }
  }

  return (
    <>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>{icao}</h2>
        <span style={{ fontSize: 15, color: "#555" }}>{info?.name || ""}</span>
        <span
          style={{
            fontSize: 11,
            fontWeight: 600,
            color: roleInfo.color,
            background: `${roleInfo.color}18`,
            padding: "2px 10px",
            borderRadius: 10,
          }}
        >
          {roleInfo.label}
        </span>
      </div>

      {/* SIA Data Section */}
      <SectionHeader title="INFORMATIONS SIA" badge="Lecture seule" badgeColor="#888" />

      {info ? (
        <>
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 20 }}>
            <InfoCard label="Altitude" value={info.elevation_ft ? `${info.elevation_ft} ft` : "—"} />
            <InfoCard label="Décl. mag." value={info.mag_variation ? `${info.mag_variation}°` : "—"} />
            <InfoCard label="T. réf." value={info.ref_temperature ? `${info.ref_temperature}°C` : "—"} />
            <InfoCard label="VFR" value={info.vfr ? "Oui" : "Non"} />
            <InfoCard label="Statut" value={info.status || "—"} />
          </div>

          {/* Runways */}
          {info.runways.length > 0 && (
            <>
              <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: "#555" }}>Pistes</h4>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, marginBottom: 20 }}>
                <thead>
                  <tr style={{ borderBottom: "2px solid #e0e0e0" }}>
                    <th style={thStyle}>QFU</th>
                    <th style={{ ...thStyle, textAlign: "right" }}>Dimensions</th>
                    <th style={{ ...thStyle, textAlign: "right" }}>LDA</th>
                    <th style={thStyle}>Surface</th>
                  </tr>
                </thead>
                <tbody>
                  {info.runways.map((rwy, i) => (
                    <tr key={i} style={{ borderBottom: "1px solid #eee" }}>
                      <td style={{ ...tdStyle, fontWeight: 600 }}>{rwy.designator}</td>
                      <td style={{ ...tdStyle, textAlign: "right", fontFamily: "monospace" }}>
                        {rwy.length_m && rwy.width_m
                          ? `${rwy.length_m} x ${rwy.width_m} m`
                          : rwy.length_m
                            ? `${rwy.length_m} m`
                            : "—"}
                      </td>
                      <td style={{ ...tdStyle, textAlign: "right", fontFamily: "monospace" }}>
                        {rwy.lda1_m ? `${rwy.lda1_m} m` : "—"}
                      </td>
                      <td style={tdStyle}>{rwy.surface || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}

          {/* Frequencies */}
          {info.services.length > 0 && (
            <>
              <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: "#555" }}>Fréquences</h4>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, marginBottom: 20 }}>
                <thead>
                  <tr style={{ borderBottom: "2px solid #e0e0e0" }}>
                    <th style={thStyle}>Service</th>
                    <th style={thStyle}>Indicatif</th>
                    <th style={{ ...thStyle, textAlign: "right" }}>Fréquence</th>
                    <th style={thStyle}>Horaires</th>
                  </tr>
                </thead>
                <tbody>
                  {info.services.map((svc, i) =>
                    svc.frequencies.length > 0 ? (
                      svc.frequencies.map((freq, j) => (
                        <tr key={`${i}-${j}`} style={{ borderBottom: "1px solid #eee" }}>
                          <td style={tdStyle}>
                            <span style={{ fontSize: 10, fontWeight: 700, color: "#555" }}>
                              {svc.service_type}
                            </span>
                          </td>
                          <td style={tdStyle}>{svc.callsign || "—"}</td>
                          <td style={{ ...tdStyle, textAlign: "right", fontFamily: "monospace", fontWeight: 600 }}>
                            {freq.frequency_mhz}
                          </td>
                          <td style={tdStyle}>{freq.hours_code || svc.hours_code || "—"}</td>
                        </tr>
                      ))
                    ) : (
                      <tr key={i} style={{ borderBottom: "1px solid #eee" }}>
                        <td style={tdStyle}>
                          <span style={{ fontSize: 10, fontWeight: 700, color: "#555" }}>
                            {svc.service_type}
                          </span>
                        </td>
                        <td style={tdStyle}>{svc.callsign || "—"}</td>
                        <td style={{ ...tdStyle, textAlign: "right", color: "#999" }}>—</td>
                        <td style={tdStyle}>{svc.hours_code || "—"}</td>
                      </tr>
                    )
                  )}
                </tbody>
              </table>
            </>
          )}
        </>
      ) : (
        <div style={{ color: "#888", padding: "12px 0", fontSize: 13 }}>
          Données SIA non disponibles pour cet aérodrome
        </div>
      )}

      {/* VAC Notes Section */}
      <SectionHeader title="INFORMATIONS VAC" badge="Éditable" badgeColor="#1976d2" />

      <div style={{ background: "#f9f9f9", borderRadius: 8, padding: 16, marginBottom: 20 }}>
        {runwayDesignators.length > 0 && (
          <FormField label="Sens du circuit">
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {runwayDesignators.map((rwy) => (
                <div key={rwy} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ width: 40, fontSize: 12, fontWeight: 500 }}>{rwy}:</span>
                  <select
                    value={formData.circuit_direction?.[rwy] || ""}
                    onChange={(e) => {
                      const val = e.target.value as "left" | "right" | "";
                      const newDir = { ...formData.circuit_direction };
                      if (val) {
                        newDir[rwy] = val;
                      } else {
                        delete newDir[rwy];
                      }
                      updateField("circuit_direction", Object.keys(newDir).length > 0 ? newDir : null);
                    }}
                    style={{ ...selectStyle, width: 150 }}
                  >
                    <option value="">Non renseigné</option>
                    <option value="left">Main gauche</option>
                    <option value="right">Main droite</option>
                  </select>
                </div>
              ))}
            </div>
          </FormField>
        )}

        <FormField label="Altitude tour de piste">
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <input
              type="number"
              value={formData.pattern_altitude_ft ?? ""}
              onChange={(e) =>
                updateField("pattern_altitude_ft", e.target.value ? parseInt(e.target.value) : undefined)
              }
              placeholder="Ex: 1600"
              style={{ ...inputStyle, width: 100 }}
            />
            <span style={{ fontSize: 12, color: "#666" }}>ft AMSL</span>
          </div>
        </FormField>

        <FormField label="Point d'entrée">
          <input
            type="text"
            value={formData.entry_point || ""}
            onChange={(e) => updateField("entry_point", e.target.value || null)}
            placeholder="Ex: Verticale château"
            style={inputStyle}
          />
        </FormField>

        <FormField label="Point de sortie">
          <input
            type="text"
            value={formData.exit_point || ""}
            onChange={(e) => updateField("exit_point", e.target.value || null)}
            placeholder="Ex: Cap sud direct"
            style={inputStyle}
          />
        </FormField>

        <FormField label="Consignes particulières">
          <textarea
            value={formData.special_procedures || ""}
            onChange={(e) => updateField("special_procedures", e.target.value || null)}
            placeholder="Ex: PPR weekend, survol ville interdit sous 2000ft..."
            style={{ ...inputStyle, minHeight: 80, resize: "vertical" }}
          />
        </FormField>

        <div style={{ marginTop: 16, display: "flex", alignItems: "center", gap: 12 }}>
          <button
            onClick={handleSave}
            disabled={saving || !isDirty}
            style={{
              padding: "8px 20px",
              fontSize: 13,
              fontWeight: 500,
              background: isDirty ? "#1976d2" : "#ccc",
              color: "#fff",
              border: "none",
              borderRadius: 6,
              cursor: isDirty ? "pointer" : "default",
            }}
          >
            {saving ? "Enregistrement..." : "Enregistrer"}
          </button>
          {isDirty && (
            <span style={{ fontSize: 12, color: "#f57c00" }}>Modifications non sauvegardées</span>
          )}
          {notes?.updated_at && !isDirty && (
            <span style={{ fontSize: 11, color: "#888" }}>
              Dernière mise à jour: {new Date(notes.updated_at).toLocaleString("fr-FR")}
            </span>
          )}
        </div>
      </div>
    </>
  );
}

// ============ Helper Components ============

function SectionHeader({
  title,
  badge,
  badgeColor,
}: {
  title: string;
  badge: string;
  badgeColor: string;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        marginBottom: 12,
        marginTop: 20,
        paddingBottom: 8,
        borderBottom: "1px solid #e0e0e0",
      }}
    >
      <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: "#333" }}>{title}</h3>
      <span
        style={{
          fontSize: 10,
          fontWeight: 500,
          color: badgeColor,
          background: `${badgeColor}15`,
          padding: "2px 8px",
          borderRadius: 4,
        }}
      >
        {badge}
      </span>
    </div>
  );
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ background: "#f0f0f0", borderRadius: 6, padding: "8px 12px", minWidth: 80 }}>
      <div style={{ fontSize: 10, color: "#888", marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 14, fontWeight: 600, fontFamily: "monospace" }}>{value}</div>
    </div>
  );
}

function FormField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontSize: 12, fontWeight: 500, color: "#555", marginBottom: 6 }}>{label}</div>
      {children}
    </div>
  );
}

// ============ Alternates Section Component ============

interface AlternatesSectionProps {
  primary: AlternateAerodrome[];
  secondary: AlternateAerodrome[];
  loading: boolean;
  onPreview: (alternate: AlternateAerodrome) => void;
  previewIcao: string | null;
}

function AlternatesSection({ primary, secondary, loading, onPreview, previewIcao }: AlternatesSectionProps) {
  const [showSecondary, setShowSecondary] = useState(false);

  if (loading) {
    return (
      <div style={{ padding: "16px", borderTop: "1px solid #e0e0e0", marginTop: 12 }}>
        <div style={{ fontSize: 12, color: "#888" }}>Recherche des dégagements...</div>
      </div>
    );
  }

  const hasAlternates = primary.length > 0 || secondary.length > 0;

  return (
    <div style={{ borderTop: "1px solid #e0e0e0", marginTop: 12 }}>
      <div
        style={{
          padding: "12px 16px",
          fontWeight: 600,
          fontSize: 13,
          color: "#555",
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        Dégagements suggérés
        <span style={{ fontSize: 10, color: "#888", fontWeight: 400 }}>
          (15 NM)
        </span>
      </div>

      {!hasAlternates ? (
        <div style={{ padding: "8px 16px 16px", color: "#888", fontSize: 12 }}>
          Aucun aérodrome à proximité
        </div>
      ) : (
        <>
          {/* Primary alternates (CAP) */}
          {primary.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <div
                style={{
                  padding: "4px 16px",
                  fontSize: 10,
                  fontWeight: 600,
                  color: "#2e7d32",
                  textTransform: "uppercase",
                  letterSpacing: "0.5px",
                }}
              >
                Primaires (CAP)
              </div>
              {primary.map((alt) => (
                <SuggestedAlternateItem
                  key={alt.icao}
                  alternate={alt}
                  type="primary"
                  onClick={() => onPreview(alt)}
                  isSelected={previewIcao === alt.icao}
                />
              ))}
            </div>
          )}

          {/* Secondary alternates */}
          {secondary.length > 0 && (
            <div>
              <div
                onClick={() => setShowSecondary(!showSecondary)}
                style={{
                  padding: "4px 16px",
                  fontSize: 10,
                  fontWeight: 600,
                  color: "#f57c00",
                  textTransform: "uppercase",
                  letterSpacing: "0.5px",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                }}
              >
                <span style={{ fontSize: 8 }}>{showSecondary ? "▼" : "▶"}</span>
                Secondaires ({secondary.length})
              </div>
              {showSecondary &&
                secondary.map((alt) => (
                  <SuggestedAlternateItem
                    key={alt.icao}
                    alternate={alt}
                    type="secondary"
                    onClick={() => onPreview(alt)}
                    isSelected={previewIcao === alt.icao}
                  />
                ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

interface SuggestedAlternateItemProps {
  alternate: AlternateAerodrome;
  type: "primary" | "secondary";
  onClick: () => void;
  isSelected: boolean;
}

function SuggestedAlternateItem({ alternate, type, onClick, isSelected }: SuggestedAlternateItemProps) {
  const statusLabel = alternate.status === "CAP" ? "" : alternate.status;
  const baseColor = type === "primary" ? "#2e7d32" : "#f57c00";

  return (
    <div
      onClick={onClick}
      style={{
        padding: "8px 16px",
        borderLeft: `3px solid ${isSelected ? baseColor : baseColor + "20"}`,
        background: isSelected ? "#f5f5f5" : "transparent",
        cursor: "pointer",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <span style={{ fontWeight: 600, fontSize: 13 }}>{alternate.icao}</span>
        {statusLabel && (
          <span
            style={{
              fontSize: 9,
              fontWeight: 600,
              color: "#f57c00",
              background: "#f57c0018",
              padding: "1px 4px",
              borderRadius: 3,
            }}
          >
            {statusLabel}
          </span>
        )}
      </div>
      <div style={{ fontSize: 11, color: "#666", marginTop: 2 }}>{alternate.name}</div>
      <div style={{ fontSize: 10, color: "#888", marginTop: 4, display: "flex", gap: 12 }}>
        <span title="Distance jusqu'à destination">→ {alternate.distance_to_arr_nm} NM</span>
        <span title="Position le long de la route">@ {alternate.route_position_nm} NM</span>
        {alternate.elevation_ft && (
          <span title="Altitude terrain">{alternate.elevation_ft} ft</span>
        )}
      </div>
    </div>
  );
}

// ============ Styles ============

const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "6px 8px",
  fontWeight: 600,
  fontSize: 11,
  color: "#555",
};

const tdStyle: React.CSSProperties = {
  padding: "6px 8px",
};

const inputStyle: React.CSSProperties = {
  padding: "6px 10px",
  fontSize: 13,
  border: "1px solid #ddd",
  borderRadius: 4,
  width: "100%",
  maxWidth: 300,
};

const selectStyle: React.CSSProperties = {
  padding: "6px 10px",
  fontSize: 13,
  border: "1px solid #ddd",
  borderRadius: 4,
  background: "#fff",
};
