/**
 * NOTAM tab: displays NOTAMs for the route.
 *
 * Categories:
 * - Departure airport NOTAMs
 * - Destination airport NOTAMs
 * - Alternate airports NOTAMs
 * - FIR NOTAMs (for FIRs crossed)
 * - En-route NOTAMs (geographic proximity)
 */

import { useEffect, useState, useCallback } from "react";
import { useDossierStore } from "../../stores/dossierStore";
import * as api from "../../api/client";
import type { NotamData, RouteNotamResponse } from "../../api/types";

type NotamCategory = "departure" | "destination" | "alternates" | "firs" | "enroute";

// Empty array constant to avoid re-renders
const EMPTY_ALTERNATES: string[] = [];

const CATEGORY_LABELS: Record<NotamCategory, { label: string; color: string }> = {
  departure: { label: "Depart", color: "#2e7d32" },
  destination: { label: "Destination", color: "#c62828" },
  alternates: { label: "Degagements", color: "#f57c00" },
  firs: { label: "FIR", color: "#1976d2" },
  enroute: { label: "En-route", color: "#7b1fa2" },
};

// Domain labels for area codes
const DOMAIN_LABELS: Record<string, string> = {
  AGA: "Aérodromes",
  CNS: "Communications / Navigation / Surveillance",
  ATM: "Gestion du trafic aérien",
  MET: "Météorologie",
  SAR: "Recherche et sauvetage",
  FAL: "Facilitation",
  MAP: "Cartes",
  GEN: "Général",
};

function getDomainLabel(area: string | null | undefined): string {
  if (!area) return "Autre";
  return DOMAIN_LABELS[area] || area;
}

export default function NotamTab() {
  const routeId = useDossierStore((s) => s.currentRouteId);
  const setCompletion = useDossierStore((s) => s.setCompletion);
  const dossierDate = useDossierStore((s) => s.dossier?.date);
  // TODO: Get confirmed alternates from store when implemented
  const alternateIcaos = EMPTY_ALTERNATES;

  const [notamData, setNotamData] = useState<RouteNotamResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedCategory, setExpandedCategory] = useState<NotamCategory | null>("departure");
  const [selectedNotam, setSelectedNotam] = useState<NotamData | null>(null);
  const [acknowledgedIds, setAcknowledgedIds] = useState<Set<string>>(new Set());

  // Briefing state
  const [briefing, setBriefing] = useState<string | null>(null);
  const [briefingLoading, setBriefingLoading] = useState(false);
  const [briefingError, setBriefingError] = useState<string | null>(null);
  const [showBriefing, setShowBriefing] = useState(false);

  const loadNotams = useCallback(async () => {
    if (!routeId) return;

    setLoading(true);
    setError(null);

    try {
      // Use dossier date as flight time if available, otherwise current time
      const flightTime = dossierDate ? `${dossierDate}T12:00:00Z` : undefined;
      const data = await api.getRouteNotams(routeId, alternateIcaos, 10, flightTime);
      setNotamData(data);

      // Update completion status
      if (data.total_count === 0) {
        setCompletion("notam", "complete");
      } else {
        setCompletion("notam", "partial");
      }
    } catch (err) {
      console.error("Failed to load NOTAMs:", err);
      setError(err instanceof Error ? err.message : "Erreur de chargement");
      setCompletion("notam", "alert");
    } finally {
      setLoading(false);
    }
  }, [routeId, alternateIcaos, dossierDate, setCompletion]);

  useEffect(() => {
    loadNotams();
  }, [loadNotams]);

  // Update completion when all NOTAMs are acknowledged
  useEffect(() => {
    if (!notamData) return;
    const allAcknowledged =
      notamData.total_count > 0 &&
      acknowledgedIds.size >= notamData.total_count;
    if (allAcknowledged) {
      setCompletion("notam", "complete");
    }
  }, [acknowledgedIds, notamData, setCompletion]);

  const handleAcknowledge = (notamId: string) => {
    setAcknowledgedIds((prev) => new Set([...prev, notamId]));
  };

  const handleAcknowledgeAll = (category: NotamCategory) => {
    if (!notamData) return;
    const notams = notamData[category];
    setAcknowledgedIds((prev) => {
      const next = new Set(prev);
      notams.forEach((n) => next.add(n.id));
      return next;
    });
  };

  const handleGenerateBriefing = async () => {
    if (!notamData) return;

    setBriefingLoading(true);
    setBriefingError(null);
    setShowBriefing(true);

    try {
      const response = await api.generateNotamBriefing(
        notamData.departure_icao,
        notamData.destination_icao,
        notamData.departure,
        notamData.destination,
        notamData.firs,
        notamData.enroute,
        dossierDate,
      );
      setBriefing(response.briefing);
    } catch (err) {
      console.error("Failed to generate briefing:", err);
      setBriefingError(err instanceof Error ? err.message : "Erreur de generation");
    } finally {
      setBriefingLoading(false);
    }
  };

  if (loading) {
    return (
      <div style={{ padding: 24, color: "#666" }}>
        Chargement des NOTAM...
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: 24 }}>
        <div style={{ color: "#c00", marginBottom: 16 }}>Erreur: {error}</div>
        <button onClick={loadNotams}>Reessayer</button>
      </div>
    );
  }

  if (!notamData) {
    return (
      <div style={{ padding: 24, color: "#666" }}>
        Selectionnez une route pour voir les NOTAM
      </div>
    );
  }

  const categories: NotamCategory[] = ["departure", "destination", "alternates", "firs", "enroute"];

  return (
    <div style={{ display: "flex", height: "100%" }}>
      {/* Left: NOTAM categories */}
      <div
        style={{
          width: 320,
          borderRight: "1px solid #e0e0e0",
          background: "#fafafa",
          overflowY: "auto",
          flexShrink: 0,
        }}
      >
        {/* Header with summary */}
        <div style={{ padding: "16px", borderBottom: "1px solid #e0e0e0" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div>
              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>
                {notamData.total_count} NOTAM
              </div>
              <div style={{ fontSize: 12, color: "#666" }}>
                FIRs: {notamData.firs_crossed.join(", ") || "N/A"}
              </div>
              <div style={{ fontSize: 11, color: "#888", marginTop: 4 }}>
                {acknowledgedIds.size}/{notamData.total_count} lus
              </div>
            </div>
            {notamData.total_count > 0 && (
              <button
                onClick={handleGenerateBriefing}
                disabled={briefingLoading}
                style={{
                  padding: "6px 12px",
                  fontSize: 11,
                  fontWeight: 500,
                  background: showBriefing ? "#1976d2" : "#fff",
                  color: showBriefing ? "#fff" : "#1976d2",
                  border: "1px solid #1976d2",
                  borderRadius: 4,
                  cursor: briefingLoading ? "wait" : "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                }}
              >
                {briefingLoading ? "..." : "Briefing IA"}
              </button>
            )}
          </div>
        </div>

        {/* Categories */}
        {categories.map((cat) => {
          const notams = notamData[cat];
          const catInfo = CATEGORY_LABELS[cat];
          const unreadCount = notams.filter((n) => !acknowledgedIds.has(n.id)).length;
          const isExpanded = expandedCategory === cat;

          // Get label for category
          let categoryLabel = catInfo.label;
          if (cat === "departure" && notamData.departure_icao) {
            categoryLabel = `${catInfo.label} (${notamData.departure_icao})`;
          } else if (cat === "destination" && notamData.destination_icao) {
            categoryLabel = `${catInfo.label} (${notamData.destination_icao})`;
          }

          return (
            <div key={cat}>
              <div
                onClick={() => setExpandedCategory(isExpanded ? null : cat)}
                style={{
                  padding: "10px 16px",
                  cursor: "pointer",
                  background: isExpanded ? "#e8eaf6" : "transparent",
                  borderLeft: `3px solid ${isExpanded ? catInfo.color : "transparent"}`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 10 }}>{isExpanded ? "v" : ">"}</span>
                  <span style={{ fontWeight: 500, fontSize: 13 }}>{categoryLabel}</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  {unreadCount > 0 && (
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 600,
                        color: "#fff",
                        background: catInfo.color,
                        padding: "2px 6px",
                        borderRadius: 8,
                      }}
                    >
                      {unreadCount}
                    </span>
                  )}
                  <span style={{ fontSize: 12, color: "#888" }}>{notams.length}</span>
                </div>
              </div>

              {/* Expanded NOTAM list - grouped by area */}
              {isExpanded && notams.length > 0 && (
                <div style={{ background: "#fff" }}>
                  {notams.length > 1 && (
                    <div style={{ padding: "4px 16px", borderBottom: "1px solid #f0f0f0" }}>
                      <button
                        onClick={() => handleAcknowledgeAll(cat)}
                        style={{
                          fontSize: 11,
                          color: "#1976d2",
                          background: "none",
                          border: "none",
                          cursor: "pointer",
                          padding: 0,
                        }}
                      >
                        Tout marquer comme lu
                      </button>
                    </div>
                  )}
                  {/* Group notams by area */}
                  {Object.entries(
                    notams.reduce((groups, notam) => {
                      const area = notam.area || "Autre";
                      if (!groups[area]) groups[area] = [];
                      groups[area].push(notam);
                      return groups;
                    }, {} as Record<string, NotamData[]>)
                  ).map(([area, areaNotams]) => (
                    <div key={`${cat}-${area}`}>
                      {/* Area header */}
                      <div
                        style={{
                          padding: "6px 16px",
                          fontSize: 11,
                          fontWeight: 600,
                          color: "#555",
                          background: "#f5f5f5",
                          borderBottom: "1px solid #e0e0e0",
                        }}
                      >
                        {getDomainLabel(area)} ({areaNotams.length})
                      </div>
                      {/* NOTAMs in this area */}
                      {areaNotams.map((notam, index) => (
                        <NotamListItem
                          key={`${cat}-${area}-${notam.id}-${index}`}
                          notam={notam}
                          isSelected={selectedNotam?.id === notam.id}
                          isAcknowledged={acknowledgedIds.has(notam.id)}
                          onClick={() => setSelectedNotam(notam)}
                        />
                      ))}
                    </div>
                  ))}
                </div>
              )}

              {isExpanded && notams.length === 0 && (
                <div style={{ padding: "8px 16px", fontSize: 12, color: "#888", background: "#fff" }}>
                  Aucun NOTAM
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Right: NOTAM detail or Briefing */}
      <div style={{ flex: 1, overflowY: "auto", padding: 24 }}>
        {showBriefing ? (
          <BriefingPanel
            briefing={briefing}
            loading={briefingLoading}
            error={briefingError}
            onClose={() => setShowBriefing(false)}
          />
        ) : selectedNotam ? (
          <NotamDetail
            notam={selectedNotam}
            isAcknowledged={acknowledgedIds.has(selectedNotam.id)}
            onAcknowledge={() => handleAcknowledge(selectedNotam.id)}
          />
        ) : (
          <div style={{ color: "#888", padding: 24, textAlign: "center" }}>
            Selectionnez un NOTAM pour voir les details
          </div>
        )}
      </div>
    </div>
  );
}

// ============ NOTAM List Item ============

interface NotamListItemProps {
  notam: NotamData;
  isSelected: boolean;
  isAcknowledged: boolean;
  onClick: () => void;
}

function NotamListItem({ notam, isSelected, isAcknowledged, onClick }: NotamListItemProps) {
  return (
    <div
      onClick={onClick}
      style={{
        padding: "8px 16px",
        cursor: "pointer",
        background: isSelected ? "#e3f2fd" : "transparent",
        borderBottom: "1px solid #f5f5f5",
        opacity: isAcknowledged ? 0.6 : 1,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <span style={{ fontWeight: 600, fontSize: 12, fontFamily: "monospace" }}>
          {notam.id}
        </span>
        {isAcknowledged && (
          <span style={{ fontSize: 10, color: "#2e7d32" }}>ok</span>
        )}
      </div>
      <div style={{ fontSize: 11, color: "#666", marginTop: 2 }}>
        {notam.subject || notam.area || "NOTAM"}
      </div>
      {notam.end_date && (
        <div style={{ fontSize: 10, color: "#888", marginTop: 2 }}>
          Jusqu'au {formatDate(notam.end_date)}
        </div>
      )}
    </div>
  );
}

// ============ NOTAM Detail ============

interface NotamDetailProps {
  notam: NotamData;
  isAcknowledged: boolean;
  onAcknowledge: () => void;
}

function NotamDetail({ notam, isAcknowledged, onAcknowledge }: NotamDetailProps) {
  return (
    <>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
        <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600, fontFamily: "monospace" }}>
          {notam.id}
        </h2>
        {notam.location && (
          <span
            style={{
              fontSize: 11,
              fontWeight: 600,
              color: "#1976d2",
              background: "#e3f2fd",
              padding: "2px 8px",
              borderRadius: 4,
            }}
          >
            {notam.location}
          </span>
        )}
        {notam.q_code && (
          <span
            style={{
              fontSize: 10,
              color: "#666",
              fontFamily: "monospace",
            }}
          >
            {notam.q_code}
          </span>
        )}
      </div>

      {/* Metadata */}
      <div style={{ display: "flex", gap: 16, marginBottom: 20, flexWrap: "wrap" }}>
        {notam.subject && (
          <InfoCard label="Sujet" value={notam.subject} />
        )}
        {notam.area && (
          <InfoCard label="Domaine" value={notam.area} />
        )}
        {notam.start_date && (
          <InfoCard label="Debut" value={formatDate(notam.start_date)} />
        )}
        {notam.end_date && (
          <InfoCard label="Fin" value={formatDate(notam.end_date)} />
        )}
        {notam.latitude && notam.longitude && (
          <InfoCard
            label="Position"
            value={`${notam.latitude.toFixed(2)}N ${notam.longitude.toFixed(2)}E`}
          />
        )}
        {notam.radius_nm && (
          <InfoCard label="Rayon" value={`${notam.radius_nm} NM`} />
        )}
      </div>

      {/* Message */}
      <div style={{ marginBottom: 20 }}>
        <h4 style={{ fontSize: 12, fontWeight: 600, color: "#555", marginBottom: 8 }}>
          Message
        </h4>
        <div
          style={{
            background: "#f9f9f9",
            padding: 16,
            borderRadius: 6,
            fontFamily: "monospace",
            fontSize: 13,
            lineHeight: 1.6,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}
        >
          {notam.message || "(pas de message)"}
        </div>
      </div>

      {/* Raw NOTAM */}
      <details style={{ marginBottom: 20 }}>
        <summary style={{ fontSize: 12, color: "#666", cursor: "pointer" }}>
          NOTAM brut
        </summary>
        <div
          style={{
            background: "#f5f5f5",
            padding: 12,
            borderRadius: 4,
            fontFamily: "monospace",
            fontSize: 11,
            lineHeight: 1.5,
            whiteSpace: "pre-wrap",
            marginTop: 8,
          }}
        >
          {notam.raw}
        </div>
      </details>

      {/* Acknowledge button */}
      {!isAcknowledged && (
        <button
          onClick={onAcknowledge}
          style={{
            padding: "10px 20px",
            fontSize: 13,
            fontWeight: 500,
            background: "#2e7d32",
            color: "#fff",
            border: "none",
            borderRadius: 6,
            cursor: "pointer",
          }}
        >
          Marquer comme lu
        </button>
      )}
      {isAcknowledged && (
        <div style={{ fontSize: 13, color: "#2e7d32", fontWeight: 500 }}>
          Lu et pris en compte
        </div>
      )}
    </>
  );
}

// ============ Briefing Panel ============

interface BriefingPanelProps {
  briefing: string | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
}

function BriefingPanel({ briefing, loading, error, onClose }: BriefingPanelProps) {
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600, color: "#1976d2" }}>
          Briefing NOTAM
        </h2>
        <button
          onClick={onClose}
          style={{
            padding: "4px 12px",
            fontSize: 12,
            background: "#f5f5f5",
            border: "1px solid #ddd",
            borderRadius: 4,
            cursor: "pointer",
          }}
        >
          Fermer
        </button>
      </div>

      {loading && (
        <div style={{ padding: 24, color: "#666", textAlign: "center" }}>
          <div style={{ marginBottom: 8 }}>Generation du briefing en cours...</div>
          <div style={{ fontSize: 12, color: "#888" }}>Claude analyse les NOTAMs</div>
        </div>
      )}

      {error && (
        <div
          style={{
            padding: 16,
            background: "#ffebee",
            borderRadius: 6,
            color: "#c62828",
            fontSize: 13,
          }}
        >
          <strong>Erreur:</strong> {error}
          <div style={{ marginTop: 8, fontSize: 12, color: "#888" }}>
            Verifiez que la cle API Anthropic est configuree dans .env
          </div>
        </div>
      )}

      {briefing && !loading && (
        <div
          style={{
            background: "#f8f9fa",
            border: "1px solid #e0e0e0",
            borderRadius: 8,
            padding: 20,
            lineHeight: 1.7,
            fontSize: 14,
            whiteSpace: "pre-wrap",
          }}
        >
          {briefing}
        </div>
      )}

      <div style={{ marginTop: 16, fontSize: 11, color: "#888", fontStyle: "italic" }}>
        Briefing genere par Claude (Anthropic). Verifiez toujours les NOTAMs originaux.
      </div>
    </div>
  );
}

// ============ Helpers ============

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ background: "#f0f0f0", borderRadius: 6, padding: "8px 12px", minWidth: 80 }}>
      <div style={{ fontSize: 10, color: "#888", marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 13, fontWeight: 500 }}>{value}</div>
    </div>
  );
}

function formatDate(isoDate: string): string {
  try {
    const date = new Date(isoDate);
    return date.toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return isoDate;
  }
}
