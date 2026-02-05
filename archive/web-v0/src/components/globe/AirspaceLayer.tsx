import { useEffect, useRef } from "react";
import { useCesium } from "resium";
import type { GeoJsonDataSource } from "cesium";
import { useMapStore } from "../../stores/mapStore";
import { getAirspacesBbox } from "../../api/airspaces";
import { loadAirspaceGeoJson } from "../../utils/cesiumHelpers";

export default function AirspaceLayer() {
  const { viewer } = useCesium();
  const bounds = useMapStore((s) => s.bounds);
  const dsRef = useRef<GeoJsonDataSource | null>(null);

  useEffect(() => {
    if (!viewer || !bounds) return;

    let cancelled = false;

    (async () => {
      try {
        const geojson = await getAirspacesBbox(
          bounds.south,
          bounds.west,
          bounds.north,
          bounds.east,
        );

        if (cancelled) return;

        // Remove previous datasource
        if (dsRef.current) {
          viewer.dataSources.remove(dsRef.current, true);
        }

        const ds = await loadAirspaceGeoJson(geojson, "airspaces");
        if (cancelled) return;

        viewer.dataSources.add(ds);
        dsRef.current = ds;
      } catch {
        // Silently ignore fetch errors (e.g. offline)
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [viewer, bounds]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (viewer && dsRef.current) {
        viewer.dataSources.remove(dsRef.current, true);
      }
    };
  }, [viewer]);

  return null;
}
