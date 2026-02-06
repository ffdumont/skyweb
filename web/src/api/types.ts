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
  | "CTA"
  | "SIV"
  | "D"
  | "R"
  | "P"
  | "TSA"
  | "CBA"
  | "AWY"
  | "FIR"
  | "RMZ"
  | "TMZ"
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

// ============ Weather Simulation Types ============

export interface WeatherModel {
  id: string;
  name: string;
  provider: string;
  horizon_hours: number;
  color: string;
}

export interface WaypointForecastInput {
  name: string;
  lat: number;
  lon: number;
  icao?: string | null;
  altitude_ft?: number | null; // Planned altitude at this waypoint
}

export interface SimulationRequest {
  waypoints: WaypointForecastInput[];
  departure_datetime: string;
  cruise_speed_kt: number;
  cruise_altitude_ft: number;
  models?: string[] | null;
}

export interface WaypointContext {
  waypoint_name: string;
  waypoint_index: number;
  latitude: number;
  longitude: number;
  icao: string | null;
  altitude_ft: number;
  estimated_time_utc: string;
}

export interface ForecastData {
  temperature_2m: number | null;
  dewpoint_2m: number | null;
  wind_speed_10m: number | null;
  wind_direction_10m: number | null;
  wind_gusts_10m: number | null;
  temperature_levels: Record<number, number>;
  wind_speed_levels: Record<number, number>;
  wind_direction_levels: Record<number, number>;
  cloud_cover: number | null;
  cloud_cover_low: number | null;
  cloud_cover_mid: number | null;
  cloud_cover_high: number | null;
  visibility: number | null;
  precipitation: number | null;
  pressure_msl: number | null;
  weather_code: number | null;
}

export type VFRStatus = "green" | "yellow" | "red";

export interface VFRIndex {
  status: VFRStatus;
  visibility_ok: boolean;
  ceiling_ok: boolean;
  wind_ok: boolean;
  details: string;
}

export interface ModelPoint {
  waypoint_index: number;
  forecast: ForecastData;
  vfr_index: VFRIndex;
}

export interface ModelResult {
  model: string;
  model_run_time: string;
  points: ModelPoint[];
}

export interface SimulationResponse {
  simulation_id: string;
  simulated_at: string;
  navigation_datetime: string;
  waypoints: WaypointContext[];
  model_results: ModelResult[];
}

// ============ Aerodrome Types ============

export interface AerodromeFrequency {
  frequency_mhz: number;
  spacing: string | null;
  hours_code?: string | null;
  hours_text?: string | null;
}

export interface AerodromeService {
  service_type: string;
  callsign: string | null;
  hours_code?: string | null;
  hours_text?: string | null;
  frequencies: AerodromeFrequency[];
}

export interface Runway {
  designator: string;
  length_m: number | null;
  width_m: number | null;
  is_main: boolean;
  surface: string | null;
  lda1_m: number | null;
  lda2_m: number | null;
}

export interface AerodromeInfo {
  icao: string;
  name: string;
  status: "CAP" | "MIL" | "RES" | null;
  vfr: boolean;
  private: boolean;
  latitude: number;
  longitude: number;
  elevation_ft: number | null;
  mag_variation: number | null;
  ref_temperature: number | null;
  ats_hours: string | null;
  fuel_available: string | null;
  fuel_remarks: string | null;
  runways: Runway[];
  services: AerodromeService[];
}

// ============ Aerodrome Notes Types ============

export interface Obstacle {
  description: string;
  distance_nm?: number | null;
  direction?: string | null;
  height_ft?: number | null;
  lit?: boolean | null;
}

export interface AerodromeNotes {
  icao: string;
  runway_in_use?: string | null;
  circuit_direction?: Record<string, "left" | "right"> | null;
  pattern_altitude_ft?: number | null;
  entry_point?: string | null;
  exit_point?: string | null;
  special_procedures?: string | null;
  obstacles: Obstacle[];
  updated_at?: string | null;
  completion_status: "empty" | "partial" | "complete";
}

export interface SaveAerodromeNotesRequest {
  runway_in_use?: string | null;
  circuit_direction?: Record<string, string> | null;
  pattern_altitude_ft?: number | null;
  entry_point?: string | null;
  exit_point?: string | null;
  special_procedures?: string | null;
  obstacles?: Obstacle[];
}

// ============ Alternate Aerodromes Types ============

export interface AlternateAerodrome {
  icao: string;
  name: string;
  latitude: number;
  longitude: number;
  elevation_ft: number | null;
  status: string;
  vfr: boolean;
  private: boolean;
  distance_to_arr_nm: number;
  route_position_nm: number;
}

export interface AlternatesResponse {
  route_id: string;
  primary: AlternateAerodrome[];
  secondary: AlternateAerodrome[];
}

// ============ NOTAM Types ============

export interface NotamData {
  id: string;
  raw: string;
  q_code: string | null;
  area: string | null;
  sub_area: string | null;
  subject: string | null;
  modifier: string | null;
  message: string | null;
  location: string | null;
  fir: string | null;
  start_date: string | null;
  end_date: string | null;
  latitude: number | null;
  longitude: number | null;
  radius_nm: number | null;
}

export interface RouteNotamResponse {
  route_id: string;
  departure_icao: string;
  destination_icao: string;
  alternate_icaos: string[];
  firs_crossed: string[];
  departure: NotamData[];
  destination: NotamData[];
  alternates: NotamData[];
  firs: NotamData[];
  enroute: NotamData[];
  total_count: number;
  fetched_at: string;
}

export interface BriefingResponse {
  briefing: string;
  generated_at: string;
}
