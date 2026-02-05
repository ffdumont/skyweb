import { create } from "zustand";
import type { User, Auth } from "firebase/auth";

let _auth: Auth | null = null;
let _fbAuth: typeof import("firebase/auth") | null = null;

interface AuthState {
  user: User | null;
  loading: boolean;
  init: () => void;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
  getToken: () => Promise<string | null>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  loading: true,

  init: () => {
    const apiKey = import.meta.env.VITE_FIREBASE_API_KEY;
    if (!apiKey) {
      console.warn("[auth] VITE_FIREBASE_API_KEY not set — running without auth");
      set({ loading: false });
      return;
    }

    Promise.all([import("firebase/app"), import("firebase/auth")])
      .then(([appMod, authMod]) => {
        _fbAuth = authMod;
        const app = appMod.initializeApp({
          apiKey,
          authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN ?? "",
          projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID ?? "skyweb-dev",
        });
        _auth = authMod.getAuth(app);
        authMod.onAuthStateChanged(_auth, (user) => {
          set({ user, loading: false });
        });
      })
      .catch((err) => {
        console.warn("[auth] Firebase init failed:", err);
        set({ loading: false });
      });
  },

  signIn: async () => {
    if (!_auth || !_fbAuth) return;
    const provider = new _fbAuth.GoogleAuthProvider();
    await _fbAuth.signInWithPopup(_auth, provider);
  },

  signOut: async () => {
    if (!_auth || !_fbAuth) return;
    await _fbAuth.signOut(_auth);
    set({ user: null });
  },

  getToken: async () => {
    const { user } = get();
    if (!user) return null;
    return user.getIdToken();
  },
}));
