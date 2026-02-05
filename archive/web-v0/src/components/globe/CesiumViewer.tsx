import { useRef, useCallback } from "react";
import { Viewer, CameraFlyTo, ImageryLayer } from "resium";
import {
  Cartesian3,
  Ion,
  Math as CesiumMath,
  OpenStreetMapImageryProvider,
  type Viewer as CesiumViewerType,
} from "cesium";
import { useMapStore } from "../../stores/mapStore";
import AirspaceLayer from "./AirspaceLayer";
import RouteLayer from "./RouteLayer";
import AerodromeLayer from "./AerodromeLayer";
import WeatherOverlay from "./WeatherOverlay";

// Disable Ion default token to avoid failed asset requests
Ion.defaultAccessToken = "";

/** Default camera: centered on France */
const FRANCE_CENTER = Cartesian3.fromDegrees(2.3, 46.6, 1_500_000);

const osmProvider = new OpenStreetMapImageryProvider({
  url: "https://tile.openstreetmap.org/",
});

export default function CesiumViewer() {
  const viewerRef = useRef<CesiumViewerType | null>(null);
  const setBounds = useMapStore((s) => s.setBounds);
  const layers = useMapStore((s) => s.layers);

  const handleMoveEnd = useCallback(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    const rect = viewer.camera.computeViewRectangle();
    if (rect) {
      setBounds({
        west: CesiumMath.toDegrees(rect.west),
        south: CesiumMath.toDegrees(rect.south),
        east: CesiumMath.toDegrees(rect.east),
        north: CesiumMath.toDegrees(rect.north),
      });
    }
  }, [setBounds]);

  return (
    <Viewer
      full
      ref={(e) => {
        if (e?.cesiumElement && !viewerRef.current) {
          const v = e.cesiumElement;
          viewerRef.current = v;

          // Remove default Ion imagery (will fail without token)
          v.imageryLayers.removeAll();

          v.camera.moveEnd.addEventListener(handleMoveEnd);
          handleMoveEnd();
        }
      }}
      timeline={false}
      animation={false}
      baseLayerPicker={false}
      geocoder={false}
      homeButton={false}
      sceneModePicker={false}
      navigationHelpButton={false}
      fullscreenButton={false}
      selectionIndicator={false}
      infoBox={false}
    >
      <ImageryLayer imageryProvider={osmProvider} />
      <CameraFlyTo destination={FRANCE_CENTER} duration={0} />
      {layers.airspaces && <AirspaceLayer />}
      {layers.route && <RouteLayer />}
      {layers.aerodromes && <AerodromeLayer />}
      {layers.weather && <WeatherOverlay />}
    </Viewer>
  );
}
