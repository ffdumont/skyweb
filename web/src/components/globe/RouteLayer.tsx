import { useEffect, useRef } from "react";
import { useCesium } from "resium";
import {
  Cartesian2,
  Cartesian3,
  Color,
  CustomDataSource,
  LabelStyle,
  PolylineDashMaterialProperty,
  VerticalOrigin,
} from "cesium";
import type { WaypointData } from "../../data/mockDossier";

interface Props {
  waypoints: WaypointData[];
}

export default function RouteLayer({ waypoints }: Props) {
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

    if (!waypoints.length) return;

    const ds = new CustomDataSource("route");

    // Route polyline
    const positions = Cartesian3.fromDegreesArray(
      waypoints.flatMap((w) => [w.lon, w.lat]),
    );
    ds.entities.add({
      name: "Route",
      polyline: {
        positions,
        width: 3,
        material: new PolylineDashMaterialProperty({
          color: Color.DODGERBLUE,
          dashLength: 16,
        }),
        clampToGround: true,
      },
    });

    // Waypoint markers + labels
    for (const w of waypoints) {
      const isIntermediate = w.is_intermediate ?? false;
      const altLabel = w.altitude_ft ? `${w.altitude_ft} ft` : "";

      ds.entities.add({
        name: w.name,
        position: Cartesian3.fromDegrees(w.lon, w.lat),
        point: {
          pixelSize: isIntermediate ? 6 : 9,
          color: isIntermediate ? Color.ORANGE : Color.DODGERBLUE,
          outlineColor: Color.WHITE,
          outlineWidth: 1,
        },
        label: isIntermediate
          ? undefined
          : {
              text: `${w.name}\n${altLabel}`,
              font: "bold 13px sans-serif",
              fillColor: Color.WHITE,
              outlineColor: Color.BLACK,
              outlineWidth: 2,
              style: LabelStyle.FILL_AND_OUTLINE,
              verticalOrigin: VerticalOrigin.BOTTOM,
              pixelOffset: new Cartesian2(0, -12),
              showBackground: true,
              backgroundColor: new Color(0.1, 0.1, 0.1, 0.6),
            },
      });
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
  }, [viewer, waypoints]);

  return null;
}
