import { useRouteStore } from "../../stores/routeStore";

/**
 * Meteogram component for displaying multi-model weather forecasts
 * along the route. Shows wind, visibility, cloud cover, and VFR index
 * per waypoint over time.
 *
 * Placeholder — will be connected to the weather simulation API.
 */
export default function Meteogram() {
  const route = useRouteStore((s) => s.route);

  // Only render when a route with simulations is loaded
  if (!route) return null;

  return null;
}
