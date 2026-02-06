/** Client-side segment computation from corrected waypoint coordinates. */

import { haversineNm, initialBearing } from "./geo";
import type { CoordinatePoint } from "../api/types";
import type { SegmentData, WaypointData } from "../data/mockDossier";

/** Approximate magnetic declination for metropolitan France (2025).
 *  TODO: Replace with WMM model or backend computation for accuracy. */
const FRANCE_DECLINATION_DEG = -2;

/** Default climb/descent rate (ft/min) for intermediate waypoint calculation */
const DEFAULT_CLIMB_RATE_FPM = 500;

/** Default ground speed (kt) for intermediate waypoint calculation */
const DEFAULT_GROUND_SPEED_KT = 100;

/** Minimum altitude change (ft) to insert an intermediate waypoint */
const MIN_ALT_CHANGE_FT = 100;

/**
 * Compute navigation segments between non-intermediate waypoints.
 *
 * Altitude assignment follows SkyPath logic:
 * - During initial climb (before first level segment): use TO altitude (climb target)
 * - After initial climb, for climbing segments: use FROM altitude (current cruise)
 * - For descending segments: use TO altitude (descent target)
 * - For level segments: same either way
 */
export function computeSegments(coords: CoordinatePoint[]): SegmentData[] {
  const mainWps = coords.filter((c) => !c.is_intermediate);
  const segments: SegmentData[] = [];

  if (mainWps.length < 2) return segments;

  // Find first level segment index (marks end of initial climb)
  let firstLevelIdx = -1;
  for (let i = 0; i < mainWps.length - 1; i++) {
    if (mainWps[i + 1].altitude_ft === mainWps[i].altitude_ft) {
      firstLevelIdx = i;
      break;
    }
  }

  for (let i = 0; i < mainWps.length - 1; i++) {
    const from = mainWps[i];
    const to = mainWps[i + 1];
    const dist = haversineNm(from.lat, from.lon, to.lat, to.lon);
    const rv = initialBearing(from.lat, from.lon, to.lat, to.lon);
    const dm = FRANCE_DECLINATION_DEG;
    const rm = ((rv + dm) % 360 + 360) % 360;

    // Determine segment altitude based on SkyPath rules
    let altitude_ft: number;

    if (to.altitude_ft < from.altitude_ft) {
      // Descending: use TO altitude (descent target)
      altitude_ft = to.altitude_ft;
    } else if (firstLevelIdx < 0 || i <= firstLevelIdx) {
      // Still in initial climb phase or no level segment: use TO altitude
      altitude_ft = to.altitude_ft;
    } else if (to.altitude_ft > from.altitude_ft) {
      // Climbing after initial climb: use FROM altitude (current cruise)
      altitude_ft = from.altitude_ft;
    } else {
      // Level segment after initial climb
      altitude_ft = to.altitude_ft;
    }

    segments.push({
      from: from.name,
      to: to.name,
      distance_nm: Math.round(dist * 10) / 10,
      rv_deg: Math.round(rv),
      dm_deg: dm,
      rm_deg: Math.round(rm),
      altitude_ft,
    });
  }

  return segments;
}

/**
 * Recalculate intermediate CLIMB/DESC waypoints after altitude changes.
 *
 * This mirrors the backend logic in route_corrector.py:
 * - Removes existing intermediate waypoints
 * - Recalculates new intermediates based on altitude transitions
 * - Names them CLIMB_{alt} or DESC_{alt}
 */
export function recalculateIntermediates(
  waypoints: WaypointData[],
  climbRateFpm: number = DEFAULT_CLIMB_RATE_FPM,
  groundSpeedKt: number = DEFAULT_GROUND_SPEED_KT,
): WaypointData[] {
  // Extract main waypoints (non-intermediate)
  const mainWps = waypoints.filter((wp) => !wp.is_intermediate);

  if (mainWps.length < 2) return mainWps;

  const result: WaypointData[] = [];

  for (let i = 0; i < mainWps.length; i++) {
    const wp = mainWps[i];
    result.push(wp);

    // Don't add intermediate after last waypoint
    if (i >= mainWps.length - 1) continue;

    const nextWp = mainWps[i + 1];
    const isLastSegment = i === mainWps.length - 2;

    // Determine target altitude for intermediate
    const targetAlt = isLastSegment ? wp.altitude_ft : nextWp.altitude_ft;

    const intermediate = calcIntermediateWaypoint(
      wp,
      nextWp,
      targetAlt,
      isLastSegment,
      climbRateFpm,
      groundSpeedKt,
    );

    if (intermediate) {
      result.push(intermediate);
    }
  }

  return result;
}

/**
 * Calculate an intermediate waypoint for altitude transition.
 * Returns null if altitude change < 100 ft or climb distance >= segment distance.
 */
function calcIntermediateWaypoint(
  start: WaypointData,
  end: WaypointData,
  targetAlt: number,
  isLastSegment: boolean,
  climbRateFpm: number,
  groundSpeedKt: number,
): WaypointData | null {
  const altDiff = Math.abs(end.altitude_ft - start.altitude_ft);

  // Skip if altitude change is too small
  if (altDiff < MIN_ALT_CHANGE_FT) return null;

  // Time and distance for altitude change
  const timeMin = altDiff / climbRateFpm;
  const climbDistNm = (groundSpeedKt * timeMin) / 60;

  const totalDistNm = haversineNm(start.lat, start.lon, end.lat, end.lon);

  // Skip if climb distance exceeds segment distance
  if (climbDistNm >= totalDistNm) return null;

  // Position ratio along segment
  let ratio: number;
  if (isLastSegment) {
    // For last segment, DESC starts before arrival
    ratio = 1.0 - climbDistNm / totalDistNm;
  } else {
    // For other segments, CLIMB ends after departure
    ratio = climbDistNm / totalDistNm;
  }

  // Linear interpolation for position
  const lat = start.lat + (end.lat - start.lat) * ratio;
  const lon = start.lon + (end.lon - start.lon) * ratio;

  // Determine direction and name
  const direction = end.altitude_ft > start.altitude_ft ? "CLIMB" : "DESC";
  let name: string;

  if (isLastSegment && direction === "DESC") {
    name = `${direction}_${Math.round(end.altitude_ft)}`;
  } else {
    name = `${direction}_${Math.round(targetAlt)}`;
  }

  return {
    name,
    lat,
    lon,
    altitude_ft: Math.round(targetAlt),
    type: "USER",
    is_intermediate: true,
  };
}
