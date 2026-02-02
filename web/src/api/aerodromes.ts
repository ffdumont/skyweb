import { apiFetch } from "./client";

export interface Aerodrome {
  icao: string;
  name: string;
  latitude: number;
  longitude: number;
  elevation_ft?: number;
  runways?: Array<{
    designation: string;
    length_m: number;
    surface: string;
  }>;
}

export async function getAerodrome(icao: string): Promise<Aerodrome> {
  return apiFetch<Aerodrome>(`/aerodromes/${icao}`);
}

export async function getAerodromesBbox(
  minLat: number,
  minLon: number,
  maxLat: number,
  maxLon: number,
): Promise<Aerodrome[]> {
  const params = new URLSearchParams({
    min_lat: minLat.toString(),
    min_lon: minLon.toString(),
    max_lat: maxLat.toString(),
    max_lon: maxLon.toString(),
  });
  return apiFetch<Aerodrome[]>(`/aerodromes/bbox?${params}`);
}
