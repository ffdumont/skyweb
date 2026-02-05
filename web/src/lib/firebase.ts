/** Firebase client SDK initialization.
 *
 * Uses environment variables for configuration (VITE_FIREBASE_*).
 * Provides auth state management and token retrieval for API calls.
 */

import { initializeApp, type FirebaseApp } from "firebase/app";
import {
  getAuth,
  signInWithEmailAndPassword,
  signOut as firebaseSignOut,
  onAuthStateChanged,
  type Auth,
  type User,
} from "firebase/auth";

// Firebase config from environment variables
const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
};

let app: FirebaseApp | null = null;
let auth: Auth | null = null;

/** Initialize Firebase (lazy initialization). */
function getFirebaseApp(): FirebaseApp {
  if (!app) {
    if (!firebaseConfig.apiKey) {
      throw new Error("Firebase config missing. Set VITE_FIREBASE_* env vars.");
    }
    app = initializeApp(firebaseConfig);
  }
  return app;
}

/** Get Firebase Auth instance. */
export function getFirebaseAuth(): Auth {
  if (!auth) {
    auth = getAuth(getFirebaseApp());
  }
  return auth;
}

/** Get current user or null. */
export function getCurrentUser(): User | null {
  return getFirebaseAuth().currentUser;
}

/** Get ID token for API authentication. */
export async function getIdToken(): Promise<string | null> {
  const user = getCurrentUser();
  if (!user) return null;
  return user.getIdToken();
}

/** Sign in with email/password. */
export async function signIn(
  email: string,
  password: string,
): Promise<User> {
  const auth = getFirebaseAuth();
  const result = await signInWithEmailAndPassword(auth, email, password);
  return result.user;
}

/** Sign out current user. */
export async function signOut(): Promise<void> {
  const auth = getFirebaseAuth();
  await firebaseSignOut(auth);
}

/** Subscribe to auth state changes. */
export function onAuthChange(callback: (user: User | null) => void): () => void {
  const auth = getFirebaseAuth();
  return onAuthStateChanged(auth, callback);
}

/** Check if Firebase is configured. */
export function isFirebaseConfigured(): boolean {
  return Boolean(import.meta.env.VITE_FIREBASE_API_KEY);
}
