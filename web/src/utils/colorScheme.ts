import { Color } from "cesium";

const COLORS: Record<string, Color> = {
  FIR: Color.fromCssColorString("rgba(100,100,200,0.08)"),
  UIR: Color.fromCssColorString("rgba(100,100,200,0.06)"),
  TMA: Color.fromCssColorString("rgba(0,120,215,0.15)"),
  CTR: Color.fromCssColorString("rgba(0,80,180,0.20)"),
  SIV: Color.fromCssColorString("rgba(34,139,34,0.12)"),
  D: Color.fromCssColorString("rgba(200,50,50,0.18)"),
  R: Color.fromCssColorString("rgba(200,0,0,0.22)"),
  P: Color.fromCssColorString("rgba(180,0,0,0.28)"),
  CTA: Color.fromCssColorString("rgba(0,100,180,0.12)"),
  AWY: Color.fromCssColorString("rgba(150,150,150,0.06)"),
};

const OUTLINE_COLORS: Record<string, Color> = {
  FIR: Color.fromCssColorString("rgba(100,100,200,0.4)"),
  UIR: Color.fromCssColorString("rgba(100,100,200,0.3)"),
  TMA: Color.fromCssColorString("rgba(0,120,215,0.6)"),
  CTR: Color.fromCssColorString("rgba(0,80,180,0.7)"),
  SIV: Color.fromCssColorString("rgba(34,139,34,0.5)"),
  D: Color.fromCssColorString("rgba(200,50,50,0.6)"),
  R: Color.fromCssColorString("rgba(200,0,0,0.7)"),
  P: Color.fromCssColorString("rgba(180,0,0,0.8)"),
};

const DEFAULT_FILL = Color.fromCssColorString("rgba(128,128,128,0.10)");
const DEFAULT_OUTLINE = Color.fromCssColorString("rgba(128,128,128,0.4)");

export function airspaceFillColor(type: string): Color {
  return COLORS[type] ?? DEFAULT_FILL;
}

export function airspaceOutlineColor(type: string): Color {
  return OUTLINE_COLORS[type] ?? DEFAULT_OUTLINE;
}
