import { useEffect } from "react";
import { useAuthStore } from "./stores/authStore";
import { useRouteStore } from "./stores/routeStore";
import CesiumViewer from "./components/globe/CesiumViewer";
import RouteAnalysisPanel from "./components/analysis/RouteAnalysisPanel";
import RouteProfile from "./components/analysis/RouteProfile";
import RouteImport from "./components/route/RouteImport";
import LayerControl from "./components/common/LayerControl";
import AiracBanner from "./components/common/AiracBanner";
import BottomPanel from "./components/common/BottomPanel";

export default function App() {
  const init = useAuthStore((s) => s.init);
  const route = useRouteStore((s) => s.route);
  const groundProfile = useRouteStore((s) => s.groundProfile);
  const loadGroundProfile = useRouteStore((s) => s.loadGroundProfile);

  useEffect(() => {
    init();
  }, [init]);

  useEffect(() => {
    if (route) {
      loadGroundProfile();
    }
  }, [route, loadGroundProfile]);

  return (
    <div style={{ width: "100%", height: "100%", position: "relative" }}>
      <CesiumViewer />
      <div
        style={{
          position: "absolute",
          top: 12,
          left: 12,
          display: "flex",
          flexDirection: "column",
          gap: 8,
          zIndex: 10,
        }}
      >
        <AiracBanner />
        <LayerControl />
        <RouteImport />
      </div>
      <RouteAnalysisPanel />
      {route && (
        <BottomPanel title="Route Profile">
          <RouteProfile route={route} groundProfile={groundProfile ?? undefined} />
        </BottomPanel>
      )}
    </div>
  );
}
