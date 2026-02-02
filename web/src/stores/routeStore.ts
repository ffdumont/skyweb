import { create } from "zustand";
import type { RouteResponse, RouteAnalysis, VerticalPoint, GroundProfilePoint } from "../api/routes";
import {
  uploadKml,
  getRouteAnalysis,
  getRouteProfile,
  getGroundProfile,
  deleteRoute,
} from "../api/routes";

interface RouteState {
  route: RouteResponse | null;
  analysis: RouteAnalysis | null;
  profile: VerticalPoint[] | null;
  groundProfile: GroundProfilePoint[] | null;
  loading: boolean;
  error: string | null;
  importKml: (file: File) => Promise<void>;
  loadAnalysis: () => Promise<void>;
  loadProfile: () => Promise<void>;
  loadGroundProfile: () => Promise<void>;
  clearRoute: () => Promise<void>;
}

export const useRouteStore = create<RouteState>((set, get) => ({
  route: null,
  analysis: null,
  profile: null,
  groundProfile: null,
  loading: false,
  error: null,

  importKml: async (file: File) => {
    set({ loading: true, error: null });
    try {
      const route = await uploadKml(file);
      set({ route, analysis: null, profile: null, groundProfile: null, loading: false });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  loadAnalysis: async () => {
    const { route } = get();
    if (!route) return;
    set({ loading: true, error: null });
    try {
      const analysis = await getRouteAnalysis(route.id);
      set({ analysis, loading: false });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  loadProfile: async () => {
    const { route } = get();
    if (!route) return;
    try {
      const profile = await getRouteProfile(route.id);
      set({ profile });
    } catch {
      // Profile endpoint may not be available yet — ignore silently
    }
  },

  loadGroundProfile: async () => {
    const { route } = get();
    if (!route) return;
    try {
      const groundProfile = await getGroundProfile(route.id);
      set({ groundProfile });
    } catch {
      // Ground profile endpoint may fail without API key — ignore silently
    }
  },

  clearRoute: async () => {
    const { route } = get();
    if (route) {
      try {
        await deleteRoute(route.id);
      } catch {
        // Best-effort delete
      }
    }
    set({ route: null, analysis: null, profile: null, groundProfile: null, error: null });
  },
}));
