/** Minimal API client for SkyWeb backend.
 *
 * Uses relative URLs — Vite dev server proxies /api to localhost:8000.
 * Automatically adds Firebase auth token when available.
 * Local dev: backend runs with SKYWEB_AUTH_DISABLED=1 (no token needed).
 */

import type {
  AircraftSummary,
  CreateDossierPayload,
  DossierResponse,
  GroundPoint,
  RouteAirspaceAnalysis,
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
  await fetch(`/api/dossiers/${dossierId}`, { method: "DELETE" });
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
