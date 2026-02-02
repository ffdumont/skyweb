import {
  Cartesian3,
  Color,
  GeoJsonDataSource,
} from "cesium";
import { airspaceFillColor, airspaceOutlineColor } from "./colorScheme";

/**
 * Load a GeoJSON FeatureCollection and apply airspace styling.
 */
export async function loadAirspaceGeoJson(
  geojson: object,
  name: string,
): Promise<GeoJsonDataSource> {
  const ds = await GeoJsonDataSource.load(geojson, {
    clampToGround: true,
    stroke: Color.TRANSPARENT,
    fill: Color.TRANSPARENT,
  });
  ds.name = name;

  for (const entity of ds.entities.values) {
    const type = entity.properties?.type?.getValue(new Date()) ?? "";
    if (entity.polygon) {
      entity.polygon.material = airspaceFillColor(type) as any;
      entity.polygon.outlineColor = airspaceOutlineColor(type) as any;
      entity.polygon.outlineWidth = 1 as any;
    }
  }

  return ds;
}

/**
 * Convert an array of [lon, lat, alt?] coordinates to Cesium Cartesian3[].
 */
export function coordsToCartesian3(
  coords: Array<[number, number, number?]>,
): Cartesian3[] {
  return coords.map(([lon, lat, alt]) =>
    Cartesian3.fromDegrees(lon, lat, alt ?? 0),
  );
}
