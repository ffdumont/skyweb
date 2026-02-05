/** Client-side segment computation from corrected waypoint coordinates. */

import { haversineNm, initialBearing } from "./geo";
import type { CoordinatePoint } from "../api/types";
import type { SegmentData } from "../data/mockDossier";

/** Approximate magnetic declination for metropolitan France (2025).
 *  TODO: Replace with WMM model or backend computation for accuracy. */
const FRANCE_DECLINATION_DEG = -2;

/** Compute navigation segments between non-intermediate waypoints. */
export function computeSegments(coords: CoordinatePoint[]): SegmentData[] {
  const mainWps = coords.filter((c) => !c.is_intermediate);
  const segments: SegmentData[] = [];

  for (let i = 0; i < mainWps.length - 1; i++) {
    const from = mainWps[i];
    const to = mainWps[i + 1];
    const dist = haversineNm(from.lat, from.lon, to.lat, to.lon);
    const rv = initialBearing(from.lat, from.lon, to.lat, to.lon);
    const dm = FRANCE_DECLINATION_DEG;
    const rm = ((rv + dm) % 360 + 360) % 360;

    segments.push({
      from: from.name,
      to: to.name,
      distance_nm: Math.round(dist * 10) / 10,
      rv_deg: Math.round(rv),
      dm_deg: dm,
      rm_deg: Math.round(rm),
      altitude_ft: to.altitude_ft,
    });
  }

  return segments;
}
