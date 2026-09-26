"use client";

import { palette, withHover } from "./palette";

interface InstallButtonProps {
  connected: boolean;
  href?: string;
  installLabel: string;
  configureLabel: string;
  onClick?: () => void;
}

export default function InstallButton({
  connected,
  href,
  installLabel,
  configureLabel,
  onClick,
}: InstallButtonProps) {
  const label = connected ? configureLabel : installLabel;

  const handleClick = () => {
    if (onClick) {
      onClick();
      return;
    }
    if (href && href !== "#") {
      window.location.href = href;
    }
  };

  const base: React.CSSProperties = {
    width: "100%",
    padding: "12px",
    background: palette.border,
    color: palette.text,
    border: "none",
    borderRadius: "6px",
    fontWeight: 700,
    fontSize: "14px",
    cursor: "pointer",
    transition: "all 0.25s ease",
  };

  const hover: React.CSSProperties = {
    background: palette.accent,
    color: palette.bg,
  };

  const interaction = withHover(base, hover);

  return (
    <button {...interaction} onClick={handleClick}>
      {connected ? "⚙️ " : "➕ "}
      {label}
    </button>
  );
}
