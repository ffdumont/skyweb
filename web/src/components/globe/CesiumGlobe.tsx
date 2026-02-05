/**
 * CesiumGlobe - Embeddable Cesium globe that fills its parent container.
 * Note: Consider migrating to Leaflet (RouteMap) for simpler 2D display.
 */

import { useEffect, useRef, type ReactNode } from "react";
import {
  Viewer as CesiumViewer,
  OpenStreetMapImageryProvider,
  Cartesian3,
  Ion,
} from "cesium";

// Disable Ion
Ion.defaultAccessToken = "";

interface Props {
  children?: ReactNode;
  onViewerReady?: (viewer: CesiumViewer) => void;
}

export default function CesiumGlobe({ children: _children, onViewerReady }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<CesiumViewer | null>(null);

  useEffect(() => {
    if (!containerRef.current || viewerRef.current) return;

    // Create viewer without default base layer
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
      infoBox: false,
    });

    // Remove default Ion imagery and add OSM
    viewer.imageryLayers.removeAll();
    const osmProvider = new OpenStreetMapImageryProvider({
      url: "https://tile.openstreetmap.org/",
    });
    viewer.imageryLayers.addImageryProvider(osmProvider);

    // Fly to France
    viewer.camera.flyTo({
      destination: Cartesian3.fromDegrees(2.3, 46.6, 1_500_000),
      duration: 0,
    });

    viewerRef.current = viewer;
    onViewerReady?.(viewer);

    return () => {
      if (viewerRef.current && !viewerRef.current.isDestroyed()) {
        viewerRef.current.destroy();
        viewerRef.current = null;
      }
    };
  }, [onViewerReady]);

  return (
    <div
      ref={containerRef}
      style={{ width: "100%", height: "100%", position: "relative" }}
    />
  );
}
