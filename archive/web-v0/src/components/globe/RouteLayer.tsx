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
import { useRouteStore } from "../../stores/routeStore";

export default function RouteLayer() {
  const { viewer } = useCesium();
  const route = useRouteStore((s) => s.route);
  const dsRef = useRef<CustomDataSource | null>(null);

  useEffect(() => {
    if (!viewer) return;

    // Remove previous datasource
    if (dsRef.current) {
      viewer.dataSources.remove(dsRef.current, true);
      dsRef.current = null;
    }

    const coords = route?.coordinates;
    if (!coords?.length) return;

    const ds = new CustomDataSource("route");

    // Route polyline
    const positions = Cartesian3.fromDegreesArray(
      coords.flatMap((c) => [c.lon, c.lat]),
    );
    ds.entities.add({
      name: route!.name,
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
    for (const c of coords) {
      const isIntermediate = c.is_intermediate ?? false;
      const name = c.name ?? "";
      const altLabel = c.altitude_ft != null ? `${c.altitude_ft} ft` : "";

      ds.entities.add({
        name,
        position: Cartesian3.fromDegrees(c.lon, c.lat),
        point: {
          pixelSize: isIntermediate ? 6 : 9,
          color: isIntermediate ? Color.ORANGE : Color.DODGERBLUE,
          outlineColor: Color.WHITE,
          outlineWidth: 1,
        },
        label: isIntermediate
          ? undefined
          : {
              text: `${name}\n${altLabel}`,
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
      if (viewer && dsRef.current) {
        viewer.dataSources.remove(dsRef.current, true);
        dsRef.current = null;
      }
    };
  }, [viewer, route]);

  return null;
}
