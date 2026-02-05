/** TypeScript interfaces for SkyWeb API request/response shapes. */

export interface CoordinatePoint {
  lat: number;
  lon: number;
  name: string;
  altitude_ft: number;
  is_intermediate: boolean;
}

export interface UploadRouteResponse {
  id: string;
  name: string;
  waypoints: unknown[];
  legs: unknown[];
  coordinates: CoordinatePoint[];
}

export interface GroundPoint {
  distance_nm: number;
  elevation_ft: number;
}

export interface AircraftSummary {
  id: string;
  registration: string;
  type_name: string;
  [key: string]: unknown;
}

export interface CreateDossierPayload {
  name: string;
  route_id: string;
  departure_datetime_utc: string;
  aircraft_id?: string;
  sections?: Record<string, string>;
}

export interface DossierResponse {
  id: string;
  name: string;
  route_id: string;
  aircraft_id: string | null;
  departure_datetime_utc: string;
  status: string;
  sections: Record<string, string>;
  alternate_icao: string[];
  tem_threats: string[];
  tem_mitigations: string[];
  created_at: string;
  updated_at: string | null;
}

// ============ Airspace Analysis Types ============

export interface FrequencyInfo {
  frequency_mhz: string;
  spacing: string | null;
  hours_code?: string | null;
  hours_text?: string | null;
}

export interface ServiceInfo {
  callsign: string;
  service_type: string;
  language?: string | null;
  frequencies: FrequencyInfo[];
}

export type AirspaceType =
  | "TMA"
  | "CTR"
  | "SIV"
  | "D"
  | "R"
  | "P"
  | "TSA"
  | "CBA"
  | "AWY"
  | "FIR"
  | "OTHER";

export type IntersectionType =
  | "crosses"
  | "inside"
  | "entry"
  | "exit"
  | "nearby";

export interface GeoJSONPolygon {
  type: "Polygon" | "MultiPolygon";
  coordinates: number[][][] | number[][][][];
}

export interface AirspaceIntersection {
  identifier: string;
  airspace_type: AirspaceType;
  airspace_class: string | null;
  lower_limit_ft: number;
  upper_limit_ft: number;
  intersection_type: IntersectionType;
  color_html?: string | null;
  services: ServiceInfo[];
  partie_id: string | null;
  volume_id: string | null;
  geometry_geojson: GeoJSONPolygon | null;
}

export interface LegAirspaces {
  from_waypoint: string;
  to_waypoint: string;
  from_seq: number;
  to_seq: number;
  planned_altitude_ft: number;
  route_airspaces: AirspaceIntersection[];
  corridor_airspaces: AirspaceIntersection[];
}

export interface RouteAirspaceAnalysis {
  route_id: string;
  legs: LegAirspaces[];
  analyzed_at: string | null;
}
