import { useDossierStore } from "../../stores/dossierStore";
import RouteDisplay from "../route/RouteDisplay";
import { MOCK_WAYPOINTS, MOCK_SEGMENTS, MOCK_GROUND_PROFILE } from "../../data/mockDossier";

export default function RouteTab() {
  const routeData = useDossierStore((s) => s.routeData);

  // Use route data from store if available, otherwise fall back to mock
  const waypoints = routeData?.waypoints ?? MOCK_WAYPOINTS;
  const segments = routeData?.segments ?? MOCK_SEGMENTS;
  const groundProfile = routeData?.groundProfile ?? MOCK_GROUND_PROFILE;

  return (
    <RouteDisplay
      waypoints={waypoints}
      segments={segments}
      groundProfile={groundProfile}
    />
  );
}
