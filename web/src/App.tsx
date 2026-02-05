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
import MeteoTab from "./components/tabs/MeteoTab";
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
      return (
        <PlaceholderTab
          title="NOTAM"
          description="Consultation des NOTAM par aérodrome, par zone (FIR, espaces traversés), AZBA et SUP AIP. Filtrage par pertinence et période."
          items={[
            "NOTAM par AD (départ, destination, dégagements)",
            "NOTAM par zone (FIR, espaces traversés)",
            "AZBA / Activités Défense",
            "SUP AIP",
            "Filtrage par pertinence",
          ]}
          status="unavailable"
        />
      );
    case "meteo":
      return <MeteoTab />;
    case "navigation":
      return (
        <PlaceholderTab
          title="Navigation"
          description="Tableau log de navigation pré-rempli par segment avec les éléments variables calculés à partir de la météo."
          items={[
            "Rv, Dm, Rm, X (dérive), Cm par segment",
            "Tsv, Te, Vsol, distance cumulée",
            "Profil de vol annoté (altitudes, calages, radiocoms)",
            "Temps d'anticipation descente (Tad, Dia)",
            "Heure estimée d'arrivée (HEA)",
          ]}
          status="planned"
        />
      );
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
      return (
        <PlaceholderTab
          title="Documents"
          description="Génération et aperçu des documents de vol prêts à imprimer."
          items={[
            "Journal de navigation (lognav)",
            "Fiche préparation 4120",
            "Export FPL Garmin",
            "Checklist documents et éléments à emporter",
            "Export PDF / impression",
          ]}
          status="planned"
        />
      );
  }
}

export default function App() {
  const viewMode = useDossierStore((s) => s.viewMode);
  const user = useAuthStore((s) => s.user);
  const initialized = useAuthStore((s) => s.initialized);
  const initialize = useAuthStore((s) => s.initialize);

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

  // Show login page if Firebase is configured and user is not authenticated
  if (isFirebaseConfigured() && !user) {
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
