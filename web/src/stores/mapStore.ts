import { create } from "zustand";

interface MapState {
  /** Current camera rectangle bounds */
  bounds: { west: number; south: number; east: number; north: number } | null;
  /** Active AIRAC cycle identifier */
  airacCycle: string | null;
  /** Visible layer flags */
  layers: {
    airspaces: boolean;
    aerodromes: boolean;
    weather: boolean;
    route: boolean;
  };
  setBounds: (b: MapState["bounds"]) => void;
  setAiracCycle: (c: string) => void;
  toggleLayer: (layer: keyof MapState["layers"]) => void;
}

export const useMapStore = create<MapState>((set) => ({
  bounds: null,
  airacCycle: null,
  layers: {
    airspaces: true,
    aerodromes: true,
    weather: true,
    route: true,
  },
  setBounds: (bounds) => set({ bounds }),
  setAiracCycle: (airacCycle) => set({ airacCycle }),
  toggleLayer: (layer) =>
    set((s) => ({
      layers: { ...s.layers, [layer]: !s.layers[layer] },
    })),
}));
