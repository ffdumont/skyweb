/** Nautical miles to meters. */
export function nmToMeters(nm: number): number {
  return nm * 1852;
}

/** Meters to nautical miles. */
export function metersToNm(m: number): number {
  return m / 1852;
}

/** Feet to meters. */
export function ftToMeters(ft: number): number {
  return ft * 0.3048;
}

/** Meters to feet. */
export function metersToFt(m: number): number {
  return m / 0.3048;
}

/** Knots to km/h. */
export function ktsToKmh(kts: number): number {
  return kts * 1.852;
}

/** Format a distance in NM with 1 decimal. */
export function formatNm(nm: number): string {
  return `${nm.toFixed(1)} NM`;
}

/** Format altitude in feet. */
export function formatFt(ft: number): string {
  return `${Math.round(ft)} ft`;
}

/** Format heading as 3-digit padded integer with degree symbol. */
export function formatHdg(deg: number): string {
  return `${Math.round(deg).toString().padStart(3, "0")}\u00B0`;
}

/** Format coordinate as decimal degrees (4 decimal places). */
export function formatCoord(deg: number): string {
  return deg.toFixed(4);
}
