import { apiFetch } from "./client";

export interface AirspaceFeature {
  type: "Feature";
  properties: {
    id: number;
    name: string;
    type: string;
    class: string;
    lower_limit: string;
    upper_limit: string;
  };
  geometry: Record<string, unknown>;
}

export interface AirspaceCollection {
  type: "FeatureCollection";
  features: AirspaceFeature[];
}

export async function getAirspacesBbox(
  minLat: number,
  minLon: number,
  maxLat: number,
  maxLon: number,
): Promise<AirspaceCollection> {
  const params = new URLSearchParams({
    min_lat: minLat.toString(),
    min_lon: minLon.toString(),
    max_lat: maxLat.toString(),
    max_lon: maxLon.toString(),
  });
  return apiFetch<AirspaceCollection>(`/airspaces/bbox?${params}`);
}
