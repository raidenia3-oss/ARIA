/**
 * Tema JJK (Jujutsu Kaisen) para AURA UI.
 * Paleta oscura con acentos de energía maldita.
 */

export const JJK = {
  BG: "#05070a",
  PANEL: "#0f1219",
  ACCENT: "#7c4dff",
  ACCENT2: "#00e5ff",
  TEXT: "#e6e9f0",
  CURSED_ENERGY: "#8a2be2",
  RED: "#ff4d4d",
} as const;

export type RGB = { r: number; g: number; b: number };

export function hexToRgb(hex: string): RGB {
  const h = hex.replace("#", "");
  return {
    r: parseInt(h.substring(0, 2), 16),
    g: parseInt(h.substring(2, 4), 16),
    b: parseInt(h.substring(4, 6), 16),
  };
}

export function rgbToHex(r: number, g: number, b: number): string {
  return `#${((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1)}`;
}

export function glowColor(base: string, intensity: number): string {
  const { r, g, b } = hexToRgb(base);
  const factor = Math.max(0, Math.min(1, intensity));
  return `rgba(${r}, ${g}, ${b}, ${factor})`;
}

export function cursedEnergyGradient(step: number, total: number): string {
  const t = total > 0 ? step / total : 0;
  const r = Math.round(124 + (0 - 124) * t);
  const g = Math.round(77 + (229 - 77) * t);
  const b = Math.round(255 + (255 - 255) * t);
  return rgbToHex(r, g, b);
}

export const jjkPanelStyle = {
  backgroundColor: JJK.PANEL,
  border: `1px solid ${JJK.ACCENT}33`,
  boxShadow: `0 0 20px ${glowColor(JJK.ACCENT, 0.15)}`,
  borderRadius: "12px",
} as const;

export const jjkButtonStyle = {
  backgroundColor: "transparent",
  border: `1px solid ${JJK.ACCENT}`,
  color: JJK.TEXT,
  padding: "8px 16px",
  borderRadius: "8px",
  cursor: "pointer",
  transition: "all 0.3s ease",
  ":hover": {
    boxShadow: `0 0 15px ${glowColor(JJK.ACCENT, 0.5)}`,
    backgroundColor: `${JJK.ACCENT}22`,
  },
} as const;

export const jjkTextGlow = {
  color: JJK.TEXT,
  textShadow: `0 0 10px ${glowColor(JJK.ACCENT2, 0.5)}`,
} as const;