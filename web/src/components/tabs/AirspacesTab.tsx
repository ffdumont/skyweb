import { useEffect, useMemo, useRef, useCallback } from "react";
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

// Disable Cesium Ion
Ion.defaultAccessToken = "";

const TYPE_COLORS: Record<string, string> = {
  TMA: "#0078d7",
  CTR: "#004e92",
  SIV: "#228b22",
  D: "#c83232",
  R: "#c80000",
  P: "#b40000",
  TSA: "#ff9900",
  FIR: "#6464c8",
  OTHER: "#888888",
};

// Cesium fill colors by airspace type (with transparency)
const FILL_COLORS: Record<string, Color> = {
  FIR: Color.fromCssColorString("rgba(100,100,200,0.08)"),
  TMA: Color.fromCssColorString("rgba(0,120,215,0.15)"),
  CTR: Color.fromCssColorString("rgba(0,80,180,0.20)"),
  SIV: Color.fromCssColorString("rgba(34,139,34,0.12)"),
  D: Color.fromCssColorString("rgba(200,50,50,0.18)"),
  R: Color.fromCssColorString("rgba(200,0,0,0.22)"),
  P: Color.fromCssColorString("rgba(180,0,0,0.28)"),
  TSA: Color.fromCssColorString("rgba(255,153,0,0.15)"),
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

export default function AirspacesTab() {
  const routeData = useDossierStore((s) => s.routeData);
  const currentRouteId = useDossierStore((s) => s.currentRouteId);
  const airspaceAnalysis = useDossierStore((s) => s.airspaceAnalysis);
  const airspaceSelection = useDossierStore((s) => s.airspaceSelection);
  const airspaceLoading = useDossierStore((s) => s.airspaceLoading);
  const loadAirspaceAnalysis = useDossierStore((s) => s.loadAirspaceAnalysis);
  const toggleAirspace = useDossierStore((s) => s.toggleAirspace);
  const toggleAllAirspaces = useDossierStore((s) => s.toggleAllAirspaces);

  // Cesium refs
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<CesiumViewer | null>(null);
  const airspaceDataSourceRef = useRef<CustomDataSource | null>(null);
  const routeDataSourceRef = useRef<CustomDataSource | null>(null);

  // Load analysis when tab opens
  useEffect(() => {
    if (currentRouteId && !airspaceAnalysis && !airspaceLoading) {
      loadAirspaceAnalysis(currentRouteId);
    }
  }, [currentRouteId, airspaceAnalysis, airspaceLoading, loadAirspaceAnalysis]);

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
    if (!containerRef.current || viewerRef.current) return;

    const viewer = new CesiumViewer(containerRef.current, {
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
    });

    // Remove default imagery and add OSM
    viewer.imageryLayers.removeAll();
    const osmProvider = new OpenStreetMapImageryProvider({
      url: "https://tile.openstreetmap.org/",
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

    return () => {
      if (viewerRef.current && !viewerRef.current.isDestroyed()) {
        viewerRef.current.destroy();
        viewerRef.current = null;
      }
    };
  }, []);

  // Update route display
  useEffect(() => {
    const ds = routeDataSourceRef.current;
    if (!ds) return;

    ds.entities.removeAll();

    if (!routeData?.waypoints?.length) return;

    // Add route polyline
    const positions = routeData.waypoints.map((wp) =>
      Cartesian3.fromDegrees(wp.lon, wp.lat, (wp.altitude_ft || 0) * 0.3048)
    );

    ds.entities.add({
      polyline: {
        positions,
        width: 3,
        material: Color.fromCssColorString("#1e90ff"),
        clampToGround: false,
      },
    });

    // Add waypoint markers
    routeData.waypoints.forEach((wp, i) => {
      const isEndpoint = i === 0 || i === routeData.waypoints.length - 1;
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
  }, [routeData]);

  // Update airspace display
  const updateAirspaces = useCallback(() => {
    const ds = airspaceDataSourceRef.current;
    if (!ds) return;

    ds.entities.removeAll();

    for (const as of allAirspaces) {
      const key = `${as.identifier}_${as.partie_id}`;
      if (!selectedKeys.has(key)) continue;
      if (!as.geometry_geojson) continue;

      const fillColor = FILL_COLORS[as.airspace_type] ?? DEFAULT_FILL;
      const outlineColor = OUTLINE_COLORS[as.airspace_type] ?? DEFAULT_OUTLINE;

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
  }, [allAirspaces, selectedKeys]);

  useEffect(() => {
    updateAirspaces();
  }, [updateAirspaces]);

  if (airspaceLoading) {
    return <div style={{ padding: 24, color: "#888" }}>Chargement de l'analyse...</div>;
  }

  return (
    <div style={{ display: "flex", height: "100%" }}>
      {/* 3D Cesium Map */}
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
                  </tr>
                </thead>
                <tbody>
                  {leg.route_airspaces.map((as, i) => {
                    const key = `${as.identifier}_${as.partie_id}`;
                    const isSelected = airspaceSelection[key] ?? false;
                    return (
                      <tr key={i} style={{ borderBottom: "1px solid #eee" }}>
                        <td style={tdStyle}>
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => toggleAirspace(key)}
                          />
                        </td>
                        <td style={{ ...tdStyle, fontWeight: 500 }}>{as.identifier}</td>
                        <td style={tdStyle}>
                          <span
                            style={{
                              fontSize: 10,
                              fontWeight: 700,
                              color: "#fff",
                              background: TYPE_COLORS[as.airspace_type] ?? "#888",
                              padding: "1px 6px",
                              borderRadius: 3,
                            }}
                          >
                            {as.airspace_type}
                          </span>
                        </td>
                        <td style={tdStyle}>{as.airspace_class || "—"}</td>
                        <td style={{ ...tdStyle, textAlign: "right", fontFamily: "monospace" }}>
                          {as.lower_limit_ft === 0 ? "SFC" : `${as.lower_limit_ft} ft`}
                        </td>
                        <td style={{ ...tdStyle, textAlign: "right", fontFamily: "monospace" }}>
                          {as.upper_limit_ft} ft
                        </td>
                        <td style={{ ...tdStyle, textAlign: "right", fontFamily: "monospace", color: "#0066cc" }}>
                          {getPrimaryFrequency(as) || "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ))
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
