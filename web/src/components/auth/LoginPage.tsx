/** Login page component with email/password form. */

import { useState, type FormEvent } from "react";
import { useAuthStore } from "../../stores/authStore";
import { useDossierStore } from "../../stores/dossierStore";

const containerStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  minHeight: "100vh",
  background: "linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)",
  padding: 24,
};

const cardStyle: React.CSSProperties = {
  background: "#fff",
  borderRadius: 12,
  padding: 40,
  width: "100%",
  maxWidth: 400,
  boxShadow: "0 8px 32px rgba(0,0,0,0.2)",
};

const logoStyle: React.CSSProperties = {
  fontWeight: 700,
  fontSize: 32,
  color: "#1a1a2e",
  textAlign: "center",
  marginBottom: 8,
};

const subtitleStyle: React.CSSProperties = {
  color: "#666",
  fontSize: 14,
  textAlign: "center",
  marginBottom: 32,
};

const formStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 16,
};

const labelStyle: React.CSSProperties = {
  fontSize: 13,
  fontWeight: 500,
  color: "#333",
  marginBottom: 4,
  display: "block",
};

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "12px 14px",
  fontSize: 15,
  border: "1px solid #ddd",
  borderRadius: 8,
  outline: "none",
  transition: "border-color 0.2s",
  boxSizing: "border-box",
};

const buttonStyle: React.CSSProperties = {
  width: "100%",
  padding: "14px 20px",
  fontSize: 15,
  fontWeight: 600,
  color: "#fff",
  background: "#1a1a2e",
  border: "none",
  borderRadius: 8,
  cursor: "pointer",
  marginTop: 8,
  transition: "background 0.2s",
};

const buttonDisabledStyle: React.CSSProperties = {
  ...buttonStyle,
  background: "#999",
  cursor: "not-allowed",
};

const errorStyle: React.CSSProperties = {
  background: "#fee",
  color: "#c00",
  padding: "10px 14px",
  borderRadius: 6,
  fontSize: 13,
  marginBottom: 8,
};

const dividerStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 12,
  margin: "20px 0",
  color: "#999",
  fontSize: 13,
};

const lineStyle: React.CSSProperties = {
  flex: 1,
  height: 1,
  background: "#ddd",
};

const demoButtonStyle: React.CSSProperties = {
  width: "100%",
  padding: "14px 20px",
  fontSize: 15,
  fontWeight: 600,
  color: "#1a1a2e",
  background: "#f0f0f5",
  border: "2px solid #1a1a2e",
  borderRadius: 8,
  cursor: "pointer",
  transition: "background 0.2s",
};

const demoButtonDisabledStyle: React.CSSProperties = {
  ...demoButtonStyle,
  color: "#999",
  borderColor: "#ccc",
  cursor: "not-allowed",
};

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [demoLoading, setDemoLoading] = useState(false);

  const signIn = useAuthStore((s) => s.signIn);
  const loading = useAuthStore((s) => s.loading);
  const error = useAuthStore((s) => s.error);
  const clearError = useAuthStore((s) => s.clearError);
  const enterDemoMode = useAuthStore((s) => s.enterDemoMode);

  const startWizard = useDossierStore((s) => s.startWizard);
  const loadDemoRoute = useDossierStore((s) => s.loadDemoRoute);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!email || !password) return;

    try {
      await signIn(email, password);
    } catch {
      // Error is already set in the store
    }
  };

  const handleDemo = async () => {
    setDemoLoading(true);
    try {
      // Enter demo mode (bypasses auth)
      enterDemoMode();
      // Start wizard and load demo route
      startWizard();
      await loadDemoRoute();
    } catch {
      // Error handled in loadDemoRoute
    } finally {
      setDemoLoading(false);
    }
  };

  const isValid = email.includes("@") && password.length >= 6;

  return (
    <div style={containerStyle}>
      <div style={cardStyle}>
        <h1 style={logoStyle}>SkyWeb</h1>
        <p style={subtitleStyle}>Préparation de vol VFR</p>

        <form style={formStyle} onSubmit={handleSubmit}>
          {error && (
            <div style={errorStyle} onClick={clearError} role="alert">
              {error}
            </div>
          )}

          <div>
            <label style={labelStyle} htmlFor="email">
              Adresse email
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={inputStyle}
              placeholder="pilote@example.com"
              autoComplete="email"
              disabled={loading}
            />
          </div>

          <div>
            <label style={labelStyle} htmlFor="password">
              Mot de passe
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={inputStyle}
              placeholder="••••••••"
              autoComplete="current-password"
              disabled={loading}
            />
          </div>

          <button
            type="submit"
            style={loading || !isValid ? buttonDisabledStyle : buttonStyle}
            disabled={loading || !isValid}
          >
            {loading ? "Connexion..." : "Se connecter"}
          </button>
        </form>

        <div style={dividerStyle}>
          <div style={lineStyle} />
          <span>ou</span>
          <div style={lineStyle} />
        </div>

        <button
          type="button"
          onClick={handleDemo}
          style={demoLoading ? demoButtonDisabledStyle : demoButtonStyle}
          disabled={demoLoading}
        >
          {demoLoading ? "Chargement..." : "Essayer la démo"}
        </button>
      </div>
    </div>
  );
}
