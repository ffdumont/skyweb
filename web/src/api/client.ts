import { useAuthStore } from "../stores/authStore";

const BASE_URL = "/api";

async function authHeaders(): Promise<HeadersInit> {
  const token = await useAuthStore.getState().getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const headers = await authHeaders();
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { ...headers, ...init?.headers },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json();
}

export async function apiUpload<T>(
  path: string,
  formData: FormData,
): Promise<T> {
  const token = await useAuthStore.getState().getToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  // Don't set Content-Type for FormData — browser sets multipart boundary
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers,
    body: formData,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json();
}
