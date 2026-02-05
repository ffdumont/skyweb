import { create } from "zustand";
import type { DossierSummary, SectionCompletion, WaypointData, SegmentData, GroundPoint } from "../data/mockDossier";
import type { CoordinatePoint, RouteAirspaceAnalysis, UploadRouteResponse } from "../api/types";
import * as api from "../api/client";
import { computeSegments } from "../utils/segments";

export type TabId =
  | "summary"
  | "route"
  | "aerodromes"
  | "airspaces"
  | "notam"
  | "meteo"
  | "navigation"
  | "fuel"
  | "performance"
  | "documents";

export type ViewMode = "list" | "wizard" | "dossier";

interface WizardState {
  step: 1 | 2 | 3;
  uploadedRoute: UploadRouteResponse | null;
  groundProfile: GroundPoint[] | null;
  computedSegments: SegmentData[] | null;
  computedWaypoints: WaypointData[] | null;
  dossierName: string;
  aircraftId: string | null;
  departureDateTime: string;
  uploading: boolean;
  creating: boolean;
  error: string | null;
}

function getTodayNoon(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}T12:00`;
}

const initialWizard: WizardState = {
  step: 1,
  uploadedRoute: null,
  groundProfile: null,
  computedSegments: null,
  computedWaypoints: null,
  dossierName: "",
  aircraftId: null,
  departureDateTime: getTodayNoon(),
  uploading: false,
  creating: false,
  error: null,
};

function coordsToWaypointData(coords: CoordinatePoint[]): WaypointData[] {
  return coords.map((c, i, arr) => ({
    name: c.name,
    lat: c.lat,
    lon: c.lon,
    altitude_ft: c.altitude_ft,
    type: (i === 0 || i === arr.length - 1) ? "AD" as const : c.is_intermediate ? "USER" as const : "VRP" as const,
    is_intermediate: c.is_intermediate,
  }));
}

// Route data for current dossier (loaded from wizard or API)
interface RouteData {
  waypoints: WaypointData[];
  segments: SegmentData[];
  groundProfile: GroundPoint[] | null;
}

interface DossierState {
  viewMode: ViewMode;
  dossier: DossierSummary | null;
  routeData: RouteData | null;
  currentRouteId: string | null; // Track route_id for airspace analysis
  activeTab: TabId;
  wizard: WizardState;

  // Airspace analysis state
  airspaceAnalysis: RouteAirspaceAnalysis | null;
  airspaceSelection: Record<string, boolean>; // key: "{identifier}_{partie_id}"
  airspaceLoading: boolean;
  airspaceError: string | null;

  startWizard: () => void;
  cancelWizard: () => void;
  uploadKml: (file: File) => Promise<void>;
  loadDemoRoute: () => Promise<void>;
  validateRoute: () => void;
  goBackToUpload: () => void;
  goBackToReview: () => void;
  setDossierName: (name: string) => void;
  setAircraftId: (id: string | null) => void;
  setDepartureDateTime: (dt: string) => void;
  createDossier: () => Promise<void>;

  openDossier: (dossier: DossierSummary, routeId?: string) => Promise<void>;
  deleteDossier: (dossierId: string) => Promise<void>;
  closeDossier: () => void;
  setTab: (tab: TabId) => void;
  setCompletion: (section: string, status: SectionCompletion) => void;

  // Airspace actions
  loadAirspaceAnalysis: (routeId: string) => Promise<void>;
  toggleAirspace: (key: string) => void;
  toggleAllAirspaces: (selected: boolean) => void;
}

export const useDossierStore = create<DossierState>((set, get) => ({
  viewMode: "list",
  dossier: null,
  routeData: null,
  currentRouteId: null,
  activeTab: "summary",
  wizard: { ...initialWizard },

  // Airspace state
  airspaceAnalysis: null,
  airspaceSelection: {},
  airspaceLoading: false,
  airspaceError: null,

  startWizard: () =>
    set({ viewMode: "wizard", wizard: { ...initialWizard } }),

  cancelWizard: () =>
    set({ viewMode: "list", wizard: { ...initialWizard } }),

  uploadKml: async (file: File) => {
    set((s) => ({ wizard: { ...s.wizard, uploading: true, error: null } }));
    try {
      const route = await api.uploadKml(file);
      // Fetch ground profile in parallel with client-side segment computation
      const profilePromise = api.getGroundProfile(route.id).catch(() => null);
      const waypoints = coordsToWaypointData(route.coordinates);
      const segments = computeSegments(route.coordinates);
      const groundProfile = await profilePromise;

      set((s) => ({
        wizard: {
          ...s.wizard,
          step: 2,
          uploading: false,
          uploadedRoute: route,
          computedWaypoints: waypoints,
          computedSegments: segments,
          groundProfile: groundProfile as GroundPoint[] | null,
          dossierName: route.name,
        },
      }));
    } catch (err) {
      set((s) => ({
        wizard: {
          ...s.wizard,
          uploading: false,
          error: err instanceof Error ? err.message : "Erreur lors de l'upload",
        },
      }));
    }
  },

  loadDemoRoute: async () => {
    set((s) => ({ wizard: { ...s.wizard, uploading: true, error: null } }));
    try {
      const route = await api.loadDemoRoute();
      // Fetch ground profile in parallel with client-side segment computation
      const profilePromise = api.getGroundProfile(route.id).catch(() => null);
      const waypoints = coordsToWaypointData(route.coordinates);
      const segments = computeSegments(route.coordinates);
      const groundProfile = await profilePromise;

      set((s) => ({
        wizard: {
          ...s.wizard,
          step: 2,
          uploading: false,
          uploadedRoute: route,
          computedWaypoints: waypoints,
          computedSegments: segments,
          groundProfile: groundProfile as GroundPoint[] | null,
          dossierName: route.name,
        },
      }));
    } catch (err) {
      set((s) => ({
        wizard: {
          ...s.wizard,
          uploading: false,
          error: err instanceof Error ? err.message : "Erreur lors du chargement de la démo",
        },
      }));
    }
  },

  validateRoute: () =>
    set((s) => ({ wizard: { ...s.wizard, step: 3 } })),

  goBackToUpload: () =>
    set((s) => ({ wizard: { ...s.wizard, step: 1 } })),

  goBackToReview: () =>
    set((s) => ({ wizard: { ...s.wizard, step: 2 } })),

  setDossierName: (name) =>
    set((s) => ({ wizard: { ...s.wizard, dossierName: name } })),

  setAircraftId: (id) =>
    set((s) => ({ wizard: { ...s.wizard, aircraftId: id } })),

  setDepartureDateTime: (dt) =>
    set((s) => ({ wizard: { ...s.wizard, departureDateTime: dt } })),

  createDossier: async () => {
    const { wizard } = get();
    if (!wizard.uploadedRoute || !wizard.dossierName || !wizard.departureDateTime) return;

    set((s) => ({ wizard: { ...s.wizard, creating: true, error: null } }));
    try {
      const result = await api.createDossier({
        name: wizard.dossierName,
        route_id: wizard.uploadedRoute.id,
        departure_datetime_utc: new Date(wizard.departureDateTime).toISOString(),
        aircraft_id: wizard.aircraftId ?? undefined,
        sections: { route: "complete" },
      });

      const dossier: DossierSummary = {
        id: result.id,
        name: result.name,
        route: wizard.uploadedRoute.name,
        aircraft: wizard.aircraftId ?? "",
        date: wizard.departureDateTime.split("T")[0],
        status: result.status as DossierSummary["status"],
        sections: result.sections as Record<string, SectionCompletion>,
      };

      set({
        viewMode: "dossier",
        dossier,
        routeData: {
          waypoints: wizard.computedWaypoints!,
          segments: wizard.computedSegments!,
          groundProfile: wizard.groundProfile,
        },
        currentRouteId: wizard.uploadedRoute.id,
        activeTab: "summary",
        wizard: { ...initialWizard },
      });
    } catch (err) {
      set((s) => ({
        wizard: {
          ...s.wizard,
          creating: false,
          error: err instanceof Error ? err.message : "Erreur lors de la création",
        },
      }));
    }
  },

  openDossier: async (dossier, routeId) => {
    set({
      viewMode: "dossier",
      dossier,
      routeData: null,
      currentRouteId: routeId ?? null,
      activeTab: "summary",
      airspaceAnalysis: null,
      airspaceSelection: {},
      airspaceLoading: false,
      airspaceError: null,
    });

    // Load route data if routeId is provided
    if (routeId) {
      try {
        const [route, groundProfile] = await Promise.all([
          api.getRoute(routeId),
          api.getGroundProfile(routeId).catch(() => null),
        ]);
        const waypoints = coordsToWaypointData(route.coordinates);
        const segments = computeSegments(route.coordinates);
        set({
          routeData: {
            waypoints,
            segments,
            groundProfile: groundProfile as GroundPoint[] | null,
          },
        });
      } catch {
        // Route loading failed, keep routeData null
      }
    }
  },

  deleteDossier: async (dossierId) => {
    await api.deleteDossier(dossierId);
    // If we're viewing the deleted dossier, go back to list
    const { dossier } = get();
    if (dossier?.id === dossierId) {
      set({ viewMode: "list", dossier: null, routeData: null, activeTab: "summary" });
    }
  },

  closeDossier: () =>
    set({
      viewMode: "list",
      dossier: null,
      routeData: null,
      currentRouteId: null,
      activeTab: "summary",
      airspaceAnalysis: null,
      airspaceSelection: {},
      airspaceLoading: false,
      airspaceError: null,
    }),

  setTab: (tab) => set({ activeTab: tab }),

  setCompletion: (section, status) =>
    set((s) => {
      if (!s.dossier) return s;
      return {
        dossier: {
          ...s.dossier,
          sections: { ...s.dossier.sections, [section]: status },
        },
      };
    }),

  // Airspace actions
  loadAirspaceAnalysis: async (routeId: string) => {
    const { airspaceAnalysis } = get();
    // Don't reload if already loaded for this route
    if (airspaceAnalysis?.route_id === routeId) return;

    set({ airspaceLoading: true, airspaceError: null });
    try {
      const analysis = await api.getRouteAnalysis(routeId);

      // Build initial selection: all route_airspaces selected
      const selection: Record<string, boolean> = {};
      for (const leg of analysis.legs) {
        for (const as of leg.route_airspaces) {
          const key = `${as.identifier}_${as.partie_id}`;
          selection[key] = true;
        }
      }

      set({
        airspaceAnalysis: analysis,
        airspaceSelection: selection,
        airspaceLoading: false,
        airspaceError: null,
      });
    } catch (err) {
      set({
        airspaceLoading: false,
        airspaceError: err instanceof Error ? err.message : "Failed to load airspace analysis",
      });
    }
  },

  toggleAirspace: (key: string) =>
    set((s) => ({
      airspaceSelection: {
        ...s.airspaceSelection,
        [key]: !s.airspaceSelection[key],
      },
    })),

  toggleAllAirspaces: (selected: boolean) =>
    set((s) => {
      if (!s.airspaceAnalysis) return s;
      const selection: Record<string, boolean> = {};
      for (const leg of s.airspaceAnalysis.legs) {
        for (const as of leg.route_airspaces) {
          const key = `${as.identifier}_${as.partie_id}`;
          selection[key] = selected;
        }
      }
      return { airspaceSelection: selection };
    }),
}));
