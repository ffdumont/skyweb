/** Minimal API client for SkyWeb backend.
 *
 * Uses relative URLs — Vite dev server proxies /api to localhost:8000.
 * No auth header needed when backend runs with SKYWEB_AUTH_DISABLED=1.
 */

import type {
  AircraftSummary,
  CreateDossierPayload,
  DossierResponse,
  GroundPoint,
  RouteAirspaceAnalysis,
  UploadRouteResponse,
} from "./types";

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
  const res = await fetch(url, options);
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
