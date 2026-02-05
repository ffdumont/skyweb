/** Mock data for prototyping — LFXU → LFBP (Les Mureaux → Pau) */

export interface WaypointData {
  name: string;
  lat: number;
  lon: number;
  altitude_ft: number;
  type: "AD" | "VRP" | "USER";
  is_intermediate?: boolean;
}

export interface SegmentData {
  from: string;
  to: string;
  distance_nm: number;
  rv_deg: number;
  dm_deg: number;
  rm_deg: number;
  altitude_ft: number;
}

export interface GroundPoint {
  distance_nm: number;
  elevation_ft: number;
}

export interface AirspaceData {
  segment: string;
  zone: string;
  type: string;
  airspace_class: string;
  lower_ft: number;
  upper_ft: number;
}

export interface FrequencyData {
  order: number;
  organism: string;
  service: string;
  frequency_mhz: string;
  segment: string;
}

export interface AerodromeData {
  icao: string;
  name: string;
  role: "departure" | "destination" | "alternate";
  elevation_ft: number;
  runways: Array<{ designator: string; length_m: number; surface: string }>;
  frequencies: Array<{ service: string; callsign: string; mhz: string }>;
}

export const MOCK_WAYPOINTS: WaypointData[] = [
  { name: "LFXU", lat: 48.9878, lon: 1.8814, altitude_ft: 0, type: "AD" },
  { name: "CLIMB", lat: 48.96, lon: 1.85, altitude_ft: 1500, type: "USER", is_intermediate: true },
  { name: "DREUX", lat: 48.6453, lon: 1.3647, altitude_ft: 3500, type: "VRP" },
  { name: "CHATEAUDUN", lat: 48.0581, lon: 1.3767, altitude_ft: 4500, type: "VRP" },
  { name: "LIMOGES", lat: 45.8603, lon: 1.1794, altitude_ft: 4500, type: "VRP" },
  { name: "PERIGUEUX", lat: 45.1986, lon: 0.8156, altitude_ft: 3500, type: "VRP" },
  { name: "DESC", lat: 43.45, lon: -0.35, altitude_ft: 2000, type: "USER", is_intermediate: true },
  { name: "LFBP", lat: 43.3800, lon: -0.4186, altitude_ft: 0, type: "AD" },
];

export const MOCK_SEGMENTS: SegmentData[] = [
  { from: "LFXU", to: "DREUX", distance_nm: 25.1, rv_deg: 228, dm_deg: -2, rm_deg: 226, altitude_ft: 3500 },
  { from: "DREUX", to: "CHATEAUDUN", distance_nm: 38.2, rv_deg: 195, dm_deg: -2, rm_deg: 193, altitude_ft: 4500 },
  { from: "CHATEAUDUN", to: "LIMOGES", distance_nm: 118.5, rv_deg: 197, dm_deg: -2, rm_deg: 195, altitude_ft: 4500 },
  { from: "LIMOGES", to: "PERIGUEUX", distance_nm: 43.7, rv_deg: 210, dm_deg: -2, rm_deg: 208, altitude_ft: 3500 },
  { from: "PERIGUEUX", to: "LFBP", distance_nm: 98.3, rv_deg: 215, dm_deg: -2, rm_deg: 213, altitude_ft: 3500 },
];

export const MOCK_GROUND_PROFILE: GroundPoint[] = Array.from({ length: 60 }, (_, i) => {
  const d = (i / 59) * 323.8;
  // Rough terrain: flat Paris basin, Massif Central bump, Aquitaine descent
  let elev = 400;
  if (d > 80 && d < 200) elev = 800 + Math.sin((d - 80) / 120 * Math.PI) * 1800;
  if (d > 200) elev = 800 - (d - 200) / 123.8 * 500;
  return { distance_nm: d, elevation_ft: Math.max(100, elev + Math.random() * 200 - 100) };
});

export const MOCK_AIRSPACES: AirspaceData[] = [
  { segment: "LFXU → DREUX", zone: "TMA PARIS 1", type: "TMA", airspace_class: "D", lower_ft: 0, upper_ft: 6500 },
  { segment: "LFXU → DREUX", zone: "SIV PARIS", type: "SIV", airspace_class: "G", lower_ft: 0, upper_ft: 6500 },
  { segment: "DREUX → CHATEAUDUN", zone: "SIV PARIS", type: "SIV", airspace_class: "G", lower_ft: 0, upper_ft: 6500 },
  { segment: "CHATEAUDUN → LIMOGES", zone: "R 212", type: "R", airspace_class: "", lower_ft: 0, upper_ft: 4500 },
  { segment: "CHATEAUDUN → LIMOGES", zone: "SIV LIMOGES", type: "SIV", airspace_class: "G", lower_ft: 0, upper_ft: 6500 },
  { segment: "LIMOGES → PERIGUEUX", zone: "SIV BORDEAUX", type: "SIV", airspace_class: "G", lower_ft: 0, upper_ft: 6500 },
  { segment: "PERIGUEUX → LFBP", zone: "TMA PAU", type: "TMA", airspace_class: "D", lower_ft: 1500, upper_ft: 6500 },
];

export const MOCK_FREQUENCIES: FrequencyData[] = [
  { order: 1, organism: "Les Mureaux", service: "A/A", frequency_mhz: "123.500", segment: "LFXU" },
  { order: 2, organism: "PARIS Info", service: "SIV", frequency_mhz: "120.850", segment: "LFXU → DREUX" },
  { order: 3, organism: "PARIS Info", service: "SIV", frequency_mhz: "120.850", segment: "DREUX → CHATEAUDUN" },
  { order: 4, organism: "LIMOGES App", service: "APP", frequency_mhz: "121.250", segment: "CHATEAUDUN → LIMOGES" },
  { order: 5, organism: "BORDEAUX Info", service: "SIV", frequency_mhz: "123.150", segment: "LIMOGES → PERIGUEUX" },
  { order: 6, organism: "PAU App", service: "APP", frequency_mhz: "121.750", segment: "PERIGUEUX → LFBP" },
  { order: 7, organism: "PAU TWR", service: "TWR", frequency_mhz: "118.350", segment: "LFBP" },
];

export const MOCK_AERODROMES: AerodromeData[] = [
  {
    icao: "LFXU",
    name: "Les Mureaux",
    role: "departure",
    elevation_ft: 95,
    runways: [{ designator: "09/27", length_m: 680, surface: "Herbe" }],
    frequencies: [{ service: "A/A", callsign: "Les Mureaux", mhz: "123.500" }],
  },
  {
    icao: "LFBP",
    name: "Pau-Pyrénées",
    role: "destination",
    elevation_ft: 616,
    runways: [{ designator: "13/31", length_m: 2500, surface: "Dur" }],
    frequencies: [
      { service: "TWR", callsign: "Pau Tour", mhz: "118.350" },
      { service: "APP", callsign: "Pau Approche", mhz: "121.750" },
      { service: "ATIS", callsign: "Pau ATIS", mhz: "127.125" },
    ],
  },
  {
    icao: "LFBE",
    name: "Bergerac-Roumanière",
    role: "alternate",
    elevation_ft: 171,
    runways: [{ designator: "10/28", length_m: 2200, surface: "Dur" }],
    frequencies: [{ service: "TWR", callsign: "Bergerac Tour", mhz: "120.100" }],
  },
];

export type DossierStatus = "draft" | "preparing" | "ready" | "archived";

export type SectionCompletion = "empty" | "partial" | "complete" | "alert";

export interface DossierSummary {
  id: string;
  name: string;
  route: string;
  aircraft: string;
  date: string;
  status: DossierStatus;
  sections: Record<string, SectionCompletion>;
}

export const MOCK_DOSSIER: DossierSummary = {
  id: "dossier-001",
  name: "LFXU → LFBP",
  route: "Les Mureaux → Pau",
  aircraft: "F-HBCT CT-LS",
  date: "2026-03-15",
  status: "preparing",
  sections: {
    route: "complete",
    aerodromes: "partial",
    airspaces: "complete",
    notam: "empty",
    meteo: "partial",
    navigation: "partial",
    fuel: "empty",
    performance: "empty",
    documents: "empty",
  },
};
