import { useEffect, useMemo, useRef, useCallback, useState } from "react";
import {
  Viewer as CesiumViewer,
  OpenStreetMapImageryProvider,
  Cartesian3,
  Ion,
  CustomDataSource,
  PolygonHierarchy,
  Color,
} from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";
import { useDossierStore } from "../../stores/dossierStore";
import type { AirspaceIntersection, LegAirspaces } from "../../api/types";

// Completely disable Cesium Ion to avoid 401 errors
Ion.defaultAccessToken = undefined as any;
// @ts-ignore - Disable Ion server completely
Ion.defaultServer = undefined;

const TYPE_COLORS: Record<string, string> = {
  TMA: "#0078d7",
  CTR: "#004e92",
  CTA: "#0066aa",
  SIV: "#228b22",
  D: "#c83232",
  R: "#c80000",
  P: "#b40000",
  TSA: "#ff9900",
  CBA: "#ff6600",
  AWY: "#9966cc",
  FIR: "#6464c8",
  RMZ: "#009688",
  TMZ: "#00796b",
  OTHER: "#888888",
};

// Cesium fill colors by airspace type (with transparency)
const FILL_COLORS: Record<string, Color> = {
  FIR: Color.fromCssColorString("rgba(100,100,200,0.08)"),
  TMA: Color.fromCssColorString("rgba(0,120,215,0.15)"),
  CTR: Color.fromCssColorString("rgba(0,80,180,0.20)"),
  CTA: Color.fromCssColorString("rgba(0,100,170,0.15)"),
  SIV: Color.fromCssColorString("rgba(34,139,34,0.12)"),
  D: Color.fromCssColorString("rgba(200,50,50,0.18)"),
  R: Color.fromCssColorString("rgba(200,0,0,0.22)"),
  P: Color.fromCssColorString("rgba(180,0,0,0.28)"),
  TSA: Color.fromCssColorString("rgba(255,153,0,0.18)"),
  CBA: Color.fromCssColorString("rgba(255,102,0,0.18)"),
  AWY: Color.fromCssColorString("rgba(153,102,204,0.12)"),
  RMZ: Color.fromCssColorString("rgba(0,150,136,0.15)"),
  TMZ: Color.fromCssColorString("rgba(0,121,107,0.18)"),
};

const OUTLINE_COLORS: Record<string, Color> = {
  FIR: Color.fromCssColorString("rgba(100,100,200,0.4)"),
  TMA: Color.fromCssColorString("rgba(0,120,215,0.6)"),
  CTR: Color.fromCssColorString("rgba(0,80,180,0.7)"),
  SIV: Color.fromCssColorString("rgba(34,139,34,0.5)"),
  D: Color.fromCssColorString("rgba(200,50,50,0.6)"),
  R: Color.fromCssColorString("rgba(200,0,0,0.7)"),
  P: Color.fromCssColorString("rgba(180,0,0,0.8)"),
  TSA: Color.fromCssColorString("rgba(255,153,0,0.6)"),
};

const DEFAULT_FILL = Color.fromCssColorString("rgba(128,128,128,0.10)");
const DEFAULT_OUTLINE = Color.fromCssColorString("rgba(128,128,128,0.4)");

// TMA class A colors (same as restricted zones)
const TMA_CLASS_A_FILL = Color.fromCssColorString("rgba(200,0,0,0.22)");
const TMA_CLASS_A_OUTLINE = Color.fromCssColorString("rgba(200,0,0,0.7)");

/** Check if airspace is TMA class A (requires clearance like restricted zones) */
function isTmaClassA(as: AirspaceIntersection): boolean {
  return as.airspace_type === "TMA" && as.airspace_class === "A";
}

/** Check if airspace is a "red zone" (D, R, P, or TMA class A) excluding exceptions */
function isRedZone(as: AirspaceIntersection): boolean {
  if (isExceptionZone(as)) return false;
  return (
    as.airspace_type === "D" ||
    as.airspace_type === "R" ||
    as.airspace_type === "P" ||
    isTmaClassA(as)
  );
}

/**
 * Exception zones that should NOT be treated as red/dangerous zones.
 * These zones will have gray display instead of red, and won't trigger
 * orange route coloring. Custom frequencies can be specified here.
 */
interface ZoneException {
  identifier: string;        // Zone identifier (e.g., "R 324")
  customFrequency?: string;  // Custom frequency if not in database
  callsign?: string;         // Callsign for the frequency
}

const ZONE_EXCEPTIONS: ZoneException[] = [
  { identifier: "R 324", customFrequency: "120.075", callsign: "VEILLE PARIS" },
];

/** Normalize identifier for comparison (remove spaces, uppercase) */
function normalizeIdentifier(id: string): string {
  return id.toUpperCase().replace(/\s+/g, "");
}

/** Check if an airspace is in the exception list */
function isExceptionZone(as: AirspaceIntersection): boolean {
  const normalizedAs = normalizeIdentifier(as.identifier);
  return ZONE_EXCEPTIONS.some((ex) => {
    const normalizedEx = normalizeIdentifier(ex.identifier);
    return normalizedAs.includes(normalizedEx) || normalizedEx.includes(normalizedAs);
  });
}

/** Get exception zone info if exists */
function getExceptionInfo(as: AirspaceIntersection): ZoneException | null {
  const normalizedAs = normalizeIdentifier(as.identifier);
  return ZONE_EXCEPTIONS.find((ex) => {
    const normalizedEx = normalizeIdentifier(ex.identifier);
    return normalizedAs.includes(normalizedEx) || normalizedEx.includes(normalizedAs);
  }) ?? null;
}

// Exception zone colors (gray)
const EXCEPTION_FILL = Color.fromCssColorString("rgba(128,128,128,0.15)");
const EXCEPTION_OUTLINE = Color.fromCssColorString("rgba(128,128,128,0.5)");

export default function AirspacesTab() {
  const routeData = useDossierStore((s) => s.routeData);
  const currentRouteId = useDossierStore((s) => s.currentRouteId);
  const airspaceAnalysis = useDossierStore((s) => s.airspaceAnalysis);
  const airspaceSelection = useDossierStore((s) => s.airspaceSelection);
  const airspaceLoading = useDossierStore((s) => s.airspaceLoading);
  const airspaceError = useDossierStore((s) => s.airspaceError);
  const loadAirspaceAnalysis = useDossierStore((s) => s.loadAirspaceAnalysis);
  const toggleAirspace = useDossierStore((s) => s.toggleAirspace);
  const toggleAllAirspaces = useDossierStore((s) => s.toggleAllAirspaces);
  const isRouteModified = useDossierStore((s) => s.isRouteModified);
  const acknowledgedRedZones = useDossierStore((s) => s.acknowledgedRedZones);
  const toggleAcknowledgeRedZone = useDossierStore((s) => s.toggleAcknowledgeRedZone);

  // Cesium refs
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<CesiumViewer | null>(null);
  const airspaceDataSourceRef = useRef<CustomDataSource | null>(null);
  const routeDataSourceRef = useRef<CustomDataSource | null>(null);
  const [isViewerReady, setIsViewerReady] = useState(false);

  // Load analysis when tab opens or when altitudes were modified
  // If analysis is null (invalidated by altitude change), reload with current altitudes
  useEffect(() => {
    if (currentRouteId && !airspaceLoading && !airspaceError) {
      if (!airspaceAnalysis) {
        // Analysis is null - load with current altitudes if route was modified
        console.log("[AirspacesTab] Reloading analysis, isRouteModified:", isRouteModified);
        loadAirspaceAnalysis(currentRouteId, isRouteModified);
      }
    }
  }, [currentRouteId, airspaceAnalysis, airspaceLoading, airspaceError, loadAirspaceAnalysis, isRouteModified]);

  // Flatten all unique route_airspaces
  const allAirspaces = useMemo(() => {
    if (!airspaceAnalysis?.legs) return [];
    const seen = new Set<string>();
    const result: AirspaceIntersection[] = [];
    for (const leg of airspaceAnalysis.legs) {
      for (const as of leg.route_airspaces) {
        const key = `${as.identifier}_${as.partie_id}`;
        if (!seen.has(key)) {
          seen.add(key);
          result.push(as);
        }
      }
    }
    return result;
  }, [airspaceAnalysis]);

  // Selected keys as Set
  const selectedKeys = useMemo(() => {
    return new Set(
      Object.entries(airspaceSelection)
        .filter(([, selected]) => selected)
        .map(([key]) => key),
    );
  }, [airspaceSelection]);

  const legAirspaces: LegAirspaces[] = airspaceAnalysis?.legs ?? [];

  // Helper to get primary frequency for an airspace
  const getPrimaryFrequency = (as: AirspaceIntersection): string | null => {
    if (!as.services?.length) return null;
    for (const svc of as.services) {
      if (svc.frequencies?.length) {
        return svc.frequencies[0].frequency_mhz;
      }
    }
    return null;
  };

  // Count selected/total
  const selectedCount = selectedKeys.size;
  const totalCount = allAirspaces.length;
  const allSelected = totalCount > 0 && selectedCount === totalCount;

  // Initialize Cesium viewer
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // Skip if viewer already exists
    if (viewerRef.current) return;

    // Skip if Cesium already in DOM (StrictMode recovery)
    if (container.querySelector('.cesium-viewer')) return;

    // Check container has dimensions
    const rect = container.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) {
      const timer = setTimeout(() => {
        if (!viewerRef.current) initializeViewer();
      }, 50);
      return () => clearTimeout(timer);
    }

    initializeViewer();

    function initializeViewer() {
      if (!container || viewerRef.current) return;
      if (container.querySelector('.cesium-viewer')) return;

      try {
        const viewer = new CesiumViewer(container, {
          baseLayerPicker: false,
          geocoder: false,
          homeButton: false,
          sceneModePicker: false,
          navigationHelpButton: false,
          animation: false,
          timeline: false,
          fullscreenButton: false,
          selectionIndicator: false,
          infoBox: true,
          // Disable Cesium Ion to avoid 401 errors (cast to any for runtime options)
          ...({ imageryProvider: false, baseLayer: false, skyBox: false, skyAtmosphere: false } as Record<string, unknown>),
          terrainProvider: undefined,
        });

        // Add OSM imagery (max zoom 19 to avoid CORS errors)
        const osmProvider = new OpenStreetMapImageryProvider({
          url: "https://tile.openstreetmap.org/",
          maximumLevel: 19,
        });
        viewer.imageryLayers.addImageryProvider(osmProvider);

        // Fly to France
        viewer.camera.flyTo({
          destination: Cartesian3.fromDegrees(2.3, 46.6, 800_000),
          duration: 0,
        });

        viewerRef.current = viewer;

        // Create data sources
        airspaceDataSourceRef.current = new CustomDataSource("airspaces");
        routeDataSourceRef.current = new CustomDataSource("route");
        viewer.dataSources.add(airspaceDataSourceRef.current);
        viewer.dataSources.add(routeDataSourceRef.current);

        // Store initial dimensions for StrictMode fallback
        const initialWidth = rect.width;
        const initialHeight = rect.height;

        // Force canvas size after frame (handles StrictMode dimension issues)
        const forceResize = (attempt: number) => {
          if (viewer.isDestroyed()) return;

          const currentContainer = containerRef.current;
          const containerRect = currentContainer?.getBoundingClientRect() || { width: 0, height: 0 };
          const targetWidth = containerRect.width > 0 ? containerRect.width : initialWidth;
          const targetHeight = containerRect.height > 0 ? containerRect.height : initialHeight;

          // Force canvas dimensions if they're 0
          if (viewer.canvas.width === 0 || viewer.canvas.height === 0) {
            if (targetWidth > 0 && targetHeight > 0) {
              viewer.canvas.width = targetWidth;
              viewer.canvas.height = targetHeight;
            }
          }

          // Always ensure canvas has CSS dimensions
          if (targetWidth > 0 && targetHeight > 0) {
            viewer.canvas.style.width = targetWidth + "px";
            viewer.canvas.style.height = targetHeight + "px";
          }

          viewer.resize();

          if (viewer.canvas.width === 0 || viewer.canvas.height === 0) {
            if (attempt < 10) {
              setTimeout(() => forceResize(attempt + 1), 50);
            } else {
              setIsViewerReady(true);
            }
          } else {
            viewer.scene.requestRender();
            setIsViewerReady(true);
          }
        };

        requestAnimationFrame(() => forceResize(1));
      } catch (error) {
        console.error("[Cesium] Failed to create viewer:", error);
      }
    }

    return () => {
      if (viewerRef.current && !viewerRef.current.isDestroyed()) {
        viewerRef.current.destroy();
        viewerRef.current = null;
        airspaceDataSourceRef.current = null;
        routeDataSourceRef.current = null;
        setIsViewerReady(false);
      }
    };
  }, []);

  // Check if a leg crosses a red zone (D, R, P, or TMA class A), excluding exception zones
  const legCrossesRedZone = useCallback((legIndex: number): boolean => {
    if (!airspaceAnalysis?.legs) return false;
    const leg = airspaceAnalysis.legs[legIndex];
    if (!leg) return false;

    return leg.route_airspaces.some((as) => {
      // Skip exception zones
      if (isExceptionZone(as)) return false;
      return (
        as.airspace_type === "D" ||
        as.airspace_type === "R" ||
        as.airspace_type === "P" ||
        isTmaClassA(as)
      );
    });
  }, [airspaceAnalysis]);

  // Update route display
  useEffect(() => {
    if (!isViewerReady) return;
    const ds = routeDataSourceRef.current;
    if (!ds) return;

    ds.entities.removeAll();

    if (!routeData?.waypoints?.length) return;

    const waypoints = routeData.waypoints;

    // Draw route segment by segment with color based on red zone crossing
    for (let i = 0; i < waypoints.length - 1; i++) {
      const wp1 = waypoints[i];
      const wp2 = waypoints[i + 1];
      const crossesRed = legCrossesRedZone(i);

      const segmentPositions = [
        Cartesian3.fromDegrees(wp1.lon, wp1.lat, (wp1.altitude_ft || 0) * 0.3048),
        Cartesian3.fromDegrees(wp2.lon, wp2.lat, (wp2.altitude_ft || 0) * 0.3048),
      ];

      ds.entities.add({
        polyline: {
          positions: segmentPositions,
          width: crossesRed ? 4 : 3,
          material: Color.fromCssColorString(crossesRed ? "#ff8c00" : "#1e90ff"),
          clampToGround: false,
        },
      });
    }

    // Add waypoint markers
    waypoints.forEach((wp, i) => {
      const isEndpoint = i === 0 || i === waypoints.length - 1;
      if (!wp.is_intermediate) {
        ds.entities.add({
          position: Cartesian3.fromDegrees(wp.lon, wp.lat),
          point: {
            pixelSize: isEndpoint ? 10 : 8,
            color: Color.fromCssColorString("#1e90ff"),
            outlineColor: Color.WHITE,
            outlineWidth: 2,
          },
          label: {
            text: wp.name,
            font: "12px sans-serif",
            fillColor: Color.BLACK,
            outlineColor: Color.WHITE,
            outlineWidth: 2,
            style: 2, // FILL_AND_OUTLINE
            verticalOrigin: 1, // BOTTOM
            pixelOffset: { x: 0, y: -15 } as any,
          },
        });
      }
    });
  }, [routeData, isViewerReady, legCrossesRedZone]);

  // Update airspace display
  const updateAirspaces = useCallback(() => {
    if (!isViewerReady) return;
    const ds = airspaceDataSourceRef.current;
    if (!ds) return;

    ds.entities.removeAll();

    for (const as of allAirspaces) {
      const key = `${as.identifier}_${as.partie_id}`;
      if (!selectedKeys.has(key)) continue;
      if (!as.geometry_geojson) continue;

      // Determine colors: exception zones are gray, TMA class A are red, others use type colors
      const isException = isExceptionZone(as);
      const isClassA = !isException && isTmaClassA(as);
      let fillColor: Color;
      let outlineColor: Color;
      if (isException) {
        fillColor = EXCEPTION_FILL;
        outlineColor = EXCEPTION_OUTLINE;
      } else if (isClassA) {
        fillColor = TMA_CLASS_A_FILL;
        outlineColor = TMA_CLASS_A_OUTLINE;
      } else {
        fillColor = FILL_COLORS[as.airspace_type] ?? DEFAULT_FILL;
        outlineColor = OUTLINE_COLORS[as.airspace_type] ?? DEFAULT_OUTLINE;
      }

      // Convert feet to meters
      const floorMeters = as.lower_limit_ft * 0.3048;
      const ceilingMeters = as.upper_limit_ft * 0.3048;

      // Handle Polygon and MultiPolygon
      const geom = as.geometry_geojson;
      const polygonCoords: number[][][] =
        geom.type === "MultiPolygon"
          ? (geom.coordinates as number[][][][]).flat()
          : [geom.coordinates[0] as number[][]];

      for (const ring of polygonCoords) {
        const positions = Cartesian3.fromDegreesArray(
          ring.flatMap(([lon, lat]) => [lon, lat])
        );

        ds.entities.add({
          name: as.identifier,
          polygon: {
            hierarchy: new PolygonHierarchy(positions),
            height: floorMeters,
            extrudedHeight: ceilingMeters,
            material: fillColor,
            outline: true,
            outlineColor: outlineColor,
          },
          description: `<strong>${as.identifier}</strong><br/>
            Type: ${as.airspace_type}${as.airspace_class ? ` (Class ${as.airspace_class})` : ""}<br/>
            Floor: ${as.lower_limit_ft === 0 ? "SFC" : `${as.lower_limit_ft} ft`}<br/>
            Ceiling: ${as.upper_limit_ft} ft`,
        });
      }
    }
  }, [allAirspaces, selectedKeys, isViewerReady]);

  useEffect(() => {
    updateAirspaces();
  }, [updateAirspaces]);

  return (
    <div style={{ display: "flex", height: "100%" }}>
      {/* 3D Cesium Map - ALWAYS mounted to prevent destroy/recreate cycles */}
      <div
        ref={containerRef}
        style={{ flex: "1 1 50%", position: "relative", minHeight: 300 }}
      />

      {/* Right panel */}
      <div
        style={{
          flex: "1 1 50%",
          overflowY: "auto",
          background: "#fff",
          borderLeft: "1px solid #e0e0e0",
          padding: 16,
        }}
      >
        {airspaceLoading ? (
          <div style={{ padding: 24, color: "#888" }}>Chargement de l'analyse...</div>
        ) : airspaceError ? (
          <div style={{ padding: 24, color: "#c00" }}>
            Erreur : {airspaceError}
            <br />
            <small style={{ color: "#888" }}>Vérifiez que le serveur backend est démarré.</small>
          </div>
        ) : (
          <>
            {/* Airspaces header with select all */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>
            Zones traversées ({selectedCount}/{totalCount})
          </h3>
          <label style={{ fontSize: 12, color: "#666", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={allSelected}
              onChange={(e) => toggleAllAirspaces(e.target.checked)}
              style={{ marginRight: 4 }}
            />
            Tout afficher
          </label>
        </div>

        {legAirspaces.length === 0 ? (
          <div style={{ color: "#888", fontSize: 13, padding: "12px 0" }}>
            Aucune zone traversée détectée.
          </div>
        ) : (
          legAirspaces.map((leg, legIdx) => (
            <div key={legIdx} style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 12, color: "#666", marginBottom: 6, fontWeight: 500 }}>
                {leg.from_waypoint} → {leg.to_waypoint} ({leg.planned_altitude_ft} ft)
              </div>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr style={{ borderBottom: "2px solid #e0e0e0" }}>
                    <th style={{ ...thStyle, width: 30 }}></th>
                    <th style={thStyle}>Zone</th>
                    <th style={thStyle}>Type</th>
                    <th style={thStyle}>Classe</th>
                    <th style={{ ...thStyle, textAlign: "right" }}>Plancher</th>
                    <th style={{ ...thStyle, textAlign: "right" }}>Plafond</th>
                    <th style={{ ...thStyle, textAlign: "right" }}>Fréquence</th>
                    <th style={{ ...thStyle, textAlign: "center" }} title="Acquitter les zones à risque">Acq.</th>
                  </tr>
                </thead>
                <tbody>
                  {leg.route_airspaces.map((as, i) => {
                    const key = `${as.identifier}_${as.partie_id}`;
                    const isSelected = airspaceSelection[key] ?? false;
                    const exceptionInfo = getExceptionInfo(as);
                    const isException = exceptionInfo !== null;
                    const isClassA = !isException && isTmaClassA(as);
                    const isRed = isRedZone(as);
                    const isAcknowledged = acknowledgedRedZones[key] ?? false;

                    // Determine background and text colors
                    const bgColor = isException ? "#e8e8e8" : (isClassA ? "#ffe0e0" : (isRed ? "#fff0e0" : undefined));
                    const textColor = isClassA ? "#c00" : (isRed ? "#c00" : undefined);
                    const badgeColor = isException ? "#888" : (isClassA ? "#c00" : (TYPE_COLORS[as.airspace_type] ?? "#888"));

                    // Get frequency: use custom from exception, or from database
                    const displayFrequency = exceptionInfo?.customFrequency || getPrimaryFrequency(as) || "—";
                    const frequencyColor = isClassA ? "#c00" : "#0066cc";

                    return (
                      <tr key={i} style={{ borderBottom: "1px solid #eee", background: bgColor }}>
                        <td style={tdStyle}>
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => toggleAirspace(key)}
                          />
                        </td>
                        <td style={{ ...tdStyle, fontWeight: 500, color: textColor }}>{as.identifier}</td>
                        <td style={tdStyle}>
                          <span
                            style={{
                              fontSize: 10,
                              fontWeight: 700,
                              color: "#fff",
                              background: badgeColor,
                              padding: "1px 6px",
                              borderRadius: 3,
                            }}
                          >
                            {as.airspace_type}
                          </span>
                        </td>
                        <td style={{ ...tdStyle, color: textColor, fontWeight: isClassA ? 600 : undefined }}>{as.airspace_class || "—"}</td>
                        <td style={{ ...tdStyle, textAlign: "right", fontFamily: "monospace" }}>
                          {as.lower_limit_ft === 0 ? "SFC" : `${as.lower_limit_ft} ft`}
                        </td>
                        <td style={{ ...tdStyle, textAlign: "right", fontFamily: "monospace" }}>
                          {as.upper_limit_ft} ft
                        </td>
                        <td style={{ ...tdStyle, textAlign: "right", fontFamily: "monospace", color: frequencyColor, fontWeight: isClassA ? 600 : undefined }}>
                          {displayFrequency}
                        </td>
                        <td style={{ ...tdStyle, textAlign: "center" }}>
                          {isRed ? (
                            <input
                              type="checkbox"
                              checked={isAcknowledged}
                              onChange={() => toggleAcknowledgeRedZone(key)}
                              title="Acquitter cette zone"
                              style={{ accentColor: "#2e7d32" }}
                            />
                          ) : null}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ))
        )}
          </>
        )}
      </div>
    </div>
  );
}

const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "6px 8px",
  fontWeight: 600,
  fontSize: 11,
  color: "#555",
  whiteSpace: "nowrap",
};

const tdStyle: React.CSSProperties = {
  padding: "5px 8px",
  whiteSpace: "nowrap",
};
