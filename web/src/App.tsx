import { useEffect } from "react";
import { useDossierStore } from "./stores/dossierStore";
import { useAuthStore } from "./stores/authStore";
import { isFirebaseConfigured } from "./lib/firebase";
import AppHeader from "./components/layout/AppHeader";
import DossierHeader from "./components/layout/DossierHeader";
import DossierList from "./components/layout/DossierList";
import CreateDossierWizard from "./components/wizard/CreateDossierWizard";
import LoginPage from "./components/auth/LoginPage";
import SummaryTab from "./components/tabs/SummaryTab";
import RouteTab from "./components/tabs/RouteTab";
import AerodromesTab from "./components/tabs/AerodromesTab";
import AirspacesTab from "./components/tabs/AirspacesTab";
import NotamTab from "./components/tabs/NotamTab";
import MeteoTab from "./components/tabs/MeteoTab";
import NavigationTab from "./components/tabs/NavigationTab";
import DocumentsTab from "./components/tabs/DocumentsTab";
import PlaceholderTab from "./components/tabs/PlaceholderTab";

function TabContent() {
  const tab = useDossierStore((s) => s.activeTab);

  switch (tab) {
    case "summary":
      return <SummaryTab />;
    case "route":
      return <RouteTab />;
    case "aerodromes":
      return <AerodromesTab />;
    case "airspaces":
      return <AirspacesTab />;
    case "notam":
      return <NotamTab />;
    case "meteo":
      return <MeteoTab />;
    case "navigation":
      return <NavigationTab />;
    case "fuel":
      return (
        <PlaceholderTab
          title="Carburant & Masse"
          description="Fiche emport carburant et fiche chargement / masse & centrage avec diagramme interactif."
          items={[
            "Fiche emport carburant (Te, Dpda, Ttve, Dadgt, Mops...)",
            "Tableau des masses (avion vide, passagers, carburant, bagages)",
            "Bras de levier, moments, position CG",
            "Vérification limites centrage départ et arrivée",
            "Diagramme centrage interactif",
          ]}
          status="planned"
        />
      );
    case "performance":
      return (
        <PlaceholderTab
          title="Performances & Limitations"
          description="Distances décollage/atterrissage, limites vent de travers, heure coucher soleil, QFU probable."
          items={[
            "Distances décollage/atterrissage calculées",
            "Comparaison TODA/ASDA/LDA",
            "Vent de travers : vérification limites",
            "Heure coucher soleil / heure limite atterrissage",
            "QFU probable à destination",
          ]}
          status="planned"
        />
      );
    case "documents":
      return <DocumentsTab />;
  }
}

export default function App() {
  const viewMode = useDossierStore((s) => s.viewMode);
  const user = useAuthStore((s) => s.user);
  const initialized = useAuthStore((s) => s.initialized);
  const initialize = useAuthStore((s) => s.initialize);
  const demoMode = useAuthStore((s) => s.demoMode);

  // Initialize auth on mount
  useEffect(() => {
    const unsubscribe = initialize();
    return unsubscribe;
  }, [initialize]);

  // Show loading while initializing auth
  if (!initialized && isFirebaseConfigured()) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          height: "100vh",
          background: "#1a1a2e",
          color: "#fff",
          fontSize: 18,
        }}
      >
        Chargement...
      </div>
    );
  }

  // Show login page if Firebase is configured and user is not authenticated (unless in demo mode)
  if (isFirebaseConfigured() && !user && !demoMode) {
    return <LoginPage />;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "#f5f6fa" }}>
      <AppHeader />
      {viewMode === "wizard" && <CreateDossierWizard />}
      {viewMode === "dossier" && (
        <>
          <DossierHeader />
          <div style={{ flex: 1, minHeight: 0, overflow: "hidden" }}>
            <TabContent />
          </div>
        </>
      )}
      {viewMode === "list" && <DossierList />}
    </div>
  );
}
