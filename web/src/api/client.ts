/** Minimal API client for SkyWeb backend.
 *
 * Uses relative URLs — Vite dev server proxies /api to localhost:8000.
 * Automatically adds Firebase auth token when available.
 * Local dev: backend runs with SKYWEB_AUTH_DISABLED=1 (no token needed).
 */

import type {
  AerodromeInfo,
  AerodromeNotes,
  AircraftSummary,
  AlternatesResponse,
  BriefingResponse,
  CreateDossierPayload,
  DossierResponse,
  GroundPoint,
  NotamData,
  RouteAirspaceAnalysis,
  RouteNotamResponse,
  SaveAerodromeNotesRequest,
  SimulationRequest,
  SimulationResponse,
  UploadRouteResponse,
  WeatherModel,
} from "./types";
import { getIdToken, isFirebaseConfigured } from "../lib/firebase";
import { useAuthStore } from "../stores/authStore";

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function apiFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const headers = new Headers(options?.headers);

  // Check if in demo mode
  const demoMode = useAuthStore.getState().demoMode;
  if (demoMode) {
    headers.set("X-Demo-Mode", "true");
  }

  // Add auth token if Firebase is configured and user is authenticated
  if (isFirebaseConfigured() && !demoMode) {
    const token = await getIdToken();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
  }

  const res = await fetch(url, { ...options, headers });
  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(res.status, `API ${res.status}: ${body}`);
  }
  // Handle 204 No Content or empty responses
  if (res.status === 204 || res.headers.get("content-length") === "0") {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

export async function uploadKml(file: File): Promise<UploadRouteResponse> {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<UploadRouteResponse>("/api/routes/upload", {
    method: "POST",
    body: form,
  });
}

export async function loadDemoRoute(): Promise<UploadRouteResponse> {
  return apiFetch<UploadRouteResponse>("/api/routes/demo", {
    method: "POST",
  });
}

export async function getGroundProfile(routeId: string): Promise<GroundPoint[]> {
  return apiFetch<GroundPoint[]>(`/api/routes/${routeId}/ground-profile`);
}

export async function listAircraft(): Promise<AircraftSummary[]> {
  return apiFetch<AircraftSummary[]>("/api/aircraft");
}

export async function createDossier(
  payload: CreateDossierPayload,
): Promise<DossierResponse> {
  return apiFetch<DossierResponse>("/api/dossiers", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function listDossiers(): Promise<DossierResponse[]> {
  return apiFetch<DossierResponse[]>("/api/dossiers");
}

export async function getRoute(routeId: string): Promise<UploadRouteResponse> {
  return apiFetch<UploadRouteResponse>(`/api/routes/${routeId}`);
}

export async function deleteDossier(dossierId: string): Promise<void> {
  await apiFetch(`/api/dossiers/${dossierId}`, { method: "DELETE" });
}

export async function getRouteAnalysis(
  routeId: string,
): Promise<RouteAirspaceAnalysis> {
  return apiFetch<RouteAirspaceAnalysis>(`/api/routes/${routeId}/analysis`);
}

/** Analyze route with custom altitude overrides (doesn't save to backend) */
export interface LegAltitudeOverride {
  from_seq: number;
  to_seq: number;
  planned_altitude_ft: number;
}

export async function getRouteAnalysisWithAltitudes(
  routeId: string,
  legs: LegAltitudeOverride[],
): Promise<RouteAirspaceAnalysis> {
  return apiFetch<RouteAirspaceAnalysis>(`/api/routes/${routeId}/analysis`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ legs }),
  });
}

/** Save route altitude changes to backend */
export async function updateRouteAltitudes(
  routeId: string,
  legs: LegAltitudeOverride[],
): Promise<void> {
  await apiFetch<{ status: string }>(`/api/routes/${routeId}/altitudes`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ legs }),
  });
}

// ============ Weather API ============

export async function getWeatherModels(): Promise<WeatherModel[]> {
  return apiFetch<WeatherModel[]>("/api/weather/models");
}

export async function runWeatherSimulation(
  request: SimulationRequest,
): Promise<SimulationResponse> {
  return apiFetch<SimulationResponse>("/api/weather/simulations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

// ============ Aerodrome API ============

export async function getAerodrome(icao: string): Promise<AerodromeInfo> {
  return apiFetch<AerodromeInfo>(`/api/aerodromes/${icao.toUpperCase()}`);
}

// ============ Aerodrome Notes API ============

export async function listAerodromeNotes(): Promise<AerodromeNotes[]> {
  return apiFetch<AerodromeNotes[]>("/api/aerodrome-notes");
}

export async function getAerodromeNotes(icao: string): Promise<AerodromeNotes | null> {
  return apiFetch<AerodromeNotes | null>(`/api/aerodrome-notes/${icao.toUpperCase()}`);
}

export async function getMultipleAerodromeNotes(
  icaoCodes: string[],
): Promise<Record<string, AerodromeNotes>> {
  if (icaoCodes.length === 0) return {};
  const codes = icaoCodes.map((c) => c.toUpperCase()).join(",");
  return apiFetch<Record<string, AerodromeNotes>>(`/api/aerodrome-notes/batch/${codes}`);
}

export async function saveAerodromeNotes(
  icao: string,
  notes: SaveAerodromeNotesRequest,
): Promise<AerodromeNotes> {
  return apiFetch<AerodromeNotes>(`/api/aerodrome-notes/${icao.toUpperCase()}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(notes),
  });
}

export async function deleteAerodromeNotes(icao: string): Promise<void> {
  await apiFetch(`/api/aerodrome-notes/${icao.toUpperCase()}`, { method: "DELETE" });
}

// ============ Route Alternates API ============

export async function getRouteAlternates(
  routeId: string,
  bufferNm: number = 15,
): Promise<AlternatesResponse> {
  return apiFetch<AlternatesResponse>(`/api/routes/${routeId}/alternates?buffer_nm=${bufferNm}`);
}

// ============ NOTAM API ============

export async function getRouteNotams(
  routeId: string,
  alternateIcaos?: string[],
  bufferNm: number = 10,
  flightTime?: string,
): Promise<RouteNotamResponse> {
  const params = new URLSearchParams();
  if (alternateIcaos && alternateIcaos.length > 0) {
    params.set("alternate_icaos", alternateIcaos.join(","));
  }
  params.set("buffer_nm", bufferNm.toString());
  if (flightTime) {
    params.set("flight_time", flightTime);
  }
  return apiFetch<RouteNotamResponse>(`/api/notam/${routeId}?${params.toString()}`);
}

export async function generateNotamBriefing(
  departureIcao: string,
  destinationIcao: string,
  departure: NotamData[],
  destination: NotamData[],
  firs: NotamData[],
  enroute: NotamData[],
  flightDate?: string,
): Promise<BriefingResponse> {
  return apiFetch<BriefingResponse>("/api/notam/briefing", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      departure_icao: departureIcao,
      destination_icao: destinationIcao,
      departure,
      destination,
      firs,
      enroute,
      flight_date: flightDate,
    }),
  });
}
