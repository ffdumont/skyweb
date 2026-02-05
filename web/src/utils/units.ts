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
  return `${Math.round(deg).toString().padStart(3, "0")}°`;
}

/** Format coordinate as decimal degrees (4 decimal places). */
export function formatCoord(deg: number): string {
  return deg.toFixed(4);
}
