import { apiFetch, apiUpload } from "./client";

export interface RouteCoord {
  lat: number;
  lon: number;
  name?: string;
  altitude_ft?: number;
  is_intermediate?: boolean;
}

export interface RouteWaypointRef {
  waypoint_id: string;
  sequence_order: number;
  role: "departure" | "enroute" | "arrival";
}

export interface RouteLegRef {
  from_seq: number;
  to_seq: number;
  planned_altitude_ft: number;
}

export interface RouteResponse {
  id: string;
  name: string;
  departure_icao?: string;
  arrival_icao?: string;
  waypoints: RouteWaypointRef[];
  legs: RouteLegRef[];
  distance_nm?: number;
  coordinates?: RouteCoord[];
}

export interface AnalysisLeg {
  from_waypoint: string;
  to_waypoint: string;
  distance_nm: number;
  airspaces: Array<{
    name: string;
    type: string;
    lower_limit: string;
    upper_limit: string;
  }>;
}

export interface RouteAnalysis {
  route_id: string;
  total_distance_nm: number;
  legs: AnalysisLeg[];
}

export interface VerticalPoint {
  distance_nm: number;
  altitude_ft: number;
  waypoint_name?: string;
}

export async function uploadKml(file: File): Promise<RouteResponse> {
  const fd = new FormData();
  fd.append("file", file);
  return apiUpload<RouteResponse>("/routes/upload", fd);
}

export async function getRoute(id: string): Promise<RouteResponse> {
  return apiFetch<RouteResponse>(`/routes/${id}`);
}

export async function deleteRoute(id: string): Promise<void> {
  await apiFetch(`/routes/${id}`, { method: "DELETE" });
}

export async function getRouteAnalysis(id: string): Promise<RouteAnalysis> {
  return apiFetch<RouteAnalysis>(`/routes/${id}/analysis`);
}

export async function getRouteProfile(id: string): Promise<VerticalPoint[]> {
  return apiFetch<VerticalPoint[]>(`/routes/${id}/profile`);
}

export interface GroundProfilePoint {
  distance_nm: number;
  elevation_ft: number;
}

export async function getGroundProfile(id: string): Promise<GroundProfilePoint[]> {
  return apiFetch<GroundProfilePoint[]>(`/routes/${id}/ground-profile`);
}
