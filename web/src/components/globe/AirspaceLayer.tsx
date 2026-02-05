import { useEffect, useRef } from "react";
import { useCesium } from "resium";
import {
  Cartesian3,
  CustomDataSource,
  PolygonHierarchy,
} from "cesium";
import type { AirspaceIntersection } from "../../api/types";
import { airspaceFillColor, airspaceOutlineColor } from "../../utils/colorScheme";

interface Props {
  airspaces: AirspaceIntersection[];
  selectedKeys: Set<string>;
}

/** Renders 3D extruded airspace volumes on Cesium globe. */
export default function AirspaceLayer({ airspaces, selectedKeys }: Props) {
  const { viewer } = useCesium();
  const dsRef = useRef<CustomDataSource | null>(null);

  useEffect(() => {
    if (!viewer || viewer.isDestroyed()) return;

    // Remove previous datasource
    if (dsRef.current && viewer.dataSources) {
      try {
        viewer.dataSources.remove(dsRef.current, true);
      } catch {
        // Viewer may have been destroyed
      }
      dsRef.current = null;
    }

    const ds = new CustomDataSource("airspaces");

    for (const as of airspaces) {
      const key = `${as.identifier}_${as.partie_id}`;
      if (!selectedKeys.has(key)) continue;
      if (!as.geometry_geojson) continue;

      const fillColor = airspaceFillColor(as.airspace_type);
      const outlineColor = airspaceOutlineColor(as.airspace_type);

      // Convert feet to meters for Cesium
      const floorMeters = as.lower_limit_ft * 0.3048;
      const ceilingMeters = as.upper_limit_ft * 0.3048;

      // Handle Polygon and MultiPolygon
      const geom = as.geometry_geojson;
      const polygonCoords: number[][][] =
        geom.type === "MultiPolygon"
          ? (geom.coordinates as number[][][][]).flat()
          : [geom.coordinates[0] as number[][]];

      for (const ring of polygonCoords) {
        // GeoJSON: [lon, lat], Cesium needs flat array [lon, lat, lon, lat, ...]
        const positions = Cartesian3.fromDegreesArray(
          ring.flatMap(([lon, lat]) => [lon, lat]),
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

    viewer.dataSources.add(ds);
    dsRef.current = ds;

    return () => {
      if (dsRef.current && viewer && !viewer.isDestroyed() && viewer.dataSources) {
        try {
          viewer.dataSources.remove(dsRef.current, true);
        } catch {
          // Viewer already destroyed
        }
        dsRef.current = null;
      }
    };
  }, [viewer, airspaces, selectedKeys]);

  return null;
}
