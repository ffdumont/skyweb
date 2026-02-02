import { useRouteStore } from "../../stores/routeStore";

/**
 * Route editor panel for editing waypoints and altitudes.
 * Placeholder — will be expanded with drag-and-drop waypoint reordering
 * and altitude editing.
 */
export default function RouteEditor() {
  const route = useRouteStore((s) => s.route);

  if (!route) return null;

  return (
    <div style={{ fontSize: 13, color: "#666" }}>
      {route.waypoints?.length ?? 0} waypoints
    </div>
  );
}
