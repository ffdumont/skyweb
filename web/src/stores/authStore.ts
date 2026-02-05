/** Authentication state management with Zustand.
 *
 * Integrates with Firebase Auth for login/logout and token management.
 */

import { create } from "zustand";
import type { User } from "firebase/auth";
import {
  signIn as firebaseSignIn,
  signOut as firebaseSignOut,
  onAuthChange,
  isFirebaseConfigured,
} from "../lib/firebase";

interface AuthState {
  user: User | null;
  loading: boolean;
  error: string | null;
  initialized: boolean;

  initialize: () => () => void;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  loading: false,
  error: null,
  initialized: false,

  initialize: () => {
    if (!isFirebaseConfigured()) {
      // No Firebase config - skip auth (dev mode)
      set({ initialized: true, user: null });
      return () => {};
    }

    // Subscribe to Firebase auth state changes
    const unsubscribe = onAuthChange((user) => {
      set({ user, initialized: true, loading: false });
    });

    return unsubscribe;
  },

  signIn: async (email: string, password: string) => {
    set({ loading: true, error: null });
    try {
      const user = await firebaseSignIn(email, password);
      set({ user, loading: false });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Erreur de connexion";
      // Translate common Firebase errors
      let translated = message;
      if (message.includes("invalid-credential") || message.includes("wrong-password")) {
        translated = "Email ou mot de passe incorrect";
      } else if (message.includes("user-not-found")) {
        translated = "Aucun compte associé à cet email";
      } else if (message.includes("too-many-requests")) {
        translated = "Trop de tentatives. Réessayez plus tard.";
      } else if (message.includes("invalid-email")) {
        translated = "Adresse email invalide";
      }
      set({ loading: false, error: translated });
      throw err;
    }
  },

  signOut: async () => {
    set({ loading: true, error: null });
    try {
      await firebaseSignOut();
      set({ user: null, loading: false });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Erreur de déconnexion";
      set({ loading: false, error: message });
    }
  },

  clearError: () => set({ error: null }),
}));
