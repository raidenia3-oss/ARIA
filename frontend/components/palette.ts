export const palette = {
  bg: "#080408",
  cardBg: "#1a1a2e",
  border: "#DC143C",
  accent: "#FFD700",
  text: "#F0F0F8",
  textDim: "rgba(240, 240, 248, 0.7)",
  green: "#00C853",
};

export function withHover(
  base: React.CSSProperties,
  hover: React.CSSProperties,
): {
  style: React.CSSProperties;
  onMouseEnter: (e: React.MouseEvent<HTMLElement>) => void;
  onMouseLeave: (e: React.MouseEvent<HTMLElement>) => void;
} {
  return {
    style: base,
    onMouseEnter: (e) => {
      Object.assign(e.currentTarget.style, hover);
    },
    onMouseLeave: (e) => {
      Object.assign(e.currentTarget.style, base);
    },
  };
}
