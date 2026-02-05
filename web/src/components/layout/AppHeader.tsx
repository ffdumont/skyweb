import { useDossierStore } from "../../stores/dossierStore";
import { useAuthStore } from "../../stores/authStore";

const headerStyle: React.CSSProperties = {
  height: 48,
  background: "#1a1a2e",
  color: "#fff",
  display: "flex",
  alignItems: "center",
  padding: "0 16px",
  gap: 16,
  flexShrink: 0,
};

const logoStyle: React.CSSProperties = {
  fontWeight: 700,
  fontSize: 18,
  letterSpacing: -0.5,
};

const linkStyle: React.CSSProperties = {
  color: "rgba(255,255,255,0.7)",
  cursor: "pointer",
  fontSize: 13,
  textDecoration: "none",
  padding: "4px 8px",
  borderRadius: 4,
};

const logoutButtonStyle: React.CSSProperties = {
  background: "transparent",
  border: "1px solid rgba(255,255,255,0.3)",
  color: "rgba(255,255,255,0.8)",
  padding: "4px 12px",
  borderRadius: 4,
  fontSize: 12,
  cursor: "pointer",
  marginLeft: 12,
};

export default function AppHeader() {
  const viewMode = useDossierStore((s) => s.viewMode);
  const closeDossier = useDossierStore((s) => s.closeDossier);
  const cancelWizard = useDossierStore((s) => s.cancelWizard);
  const user = useAuthStore((s) => s.user);
  const signOut = useAuthStore((s) => s.signOut);

  const goHome = viewMode === "wizard" ? cancelWizard : closeDossier;

  return (
    <header style={headerStyle}>
      <span style={logoStyle}>SkyWeb</span>
      <span
        style={linkStyle}
        onClick={goHome}
        onKeyDown={(e) => e.key === "Enter" && goHome()}
        role="button"
        tabIndex={0}
      >
        Mes dossiers
      </span>
      <div style={{ flex: 1 }} />
      {viewMode === "dossier" && (
        <span style={{ fontSize: 12, color: "rgba(255,255,255,0.5)" }}>
          AIRAC 2602
        </span>
      )}
      {user ? (
        <div style={{ display: "flex", alignItems: "center" }}>
          <span style={{ fontSize: 13, color: "rgba(255,255,255,0.6)" }}>
            {user.email}
          </span>
          <button style={logoutButtonStyle} onClick={signOut}>
            Déconnexion
          </button>
        </div>
      ) : (
        <span style={{ fontSize: 13, color: "rgba(255,255,255,0.6)" }}>
          Pilote VFR
        </span>
      )}
    </header>
  );
}
