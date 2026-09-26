#!/usr/bin/env python3
"""ARIA v4.0 Phase 5 UI Overhaul - Epic Orb + Serpantinum x Caelestia Interface."""
import ast
from pathlib import Path

FILE = Path(__file__).resolve().parent / "desktop_ui.py"
src = FILE.read_text(encoding="utf-8")
lines = src.split("\n")

# Step 1: Add new color constants after line 52 (C_ELEVATION_3)
insert_after = 52
new_colors = """
# ── Phase 5: Epic Orb + Serpantinum x Caelestia Palette ────────────────────────
# Orb colors (Serpantinum vibrant)
C_ORB_BRIGHT    = "#00d4ff"
C_ORB_BASE      = "#38bdf8"
C_ORB_DARK      = "#0ea5e9"
C_ORB_GLOW_1    = "rgba(56, 189, 248, 0.9)"
C_ORB_GLOW_2    = "rgba(56, 189, 248, 0.6)"
C_ORB_GLOW_3    = "rgba(56, 189, 248, 0.3)"
C_ORB_TALKING   = "#00d4ff"
C_ORB_LEARNING  = "#c084fc"
C_ORB_ERROR     = "#ef4444"
# Backgrounds (Serpantinum dark aesthetic)
C_BG_DARK_0     = "#0a0e27"
C_BG_DARK_1     = "#0f172a"
C_BG_DARK_2     = "#141e3f"
C_BG_GLASS      = "rgba(15, 23, 42, 0.7)"
# Accents (Serpantinum vibrant)
C_ACCENT_CYAN_BRIGHT = "#00d4ff"
C_ACCENT_PURPLE  = "#b066ff"
C_ACCENT_GREEN   = "#00ff88"
C_ACCENT_ORANGE  = "#ff6b4a"
# Text (Caelestia readability)
C_TEXT_PRIMARY   = "#ffffff"
C_TEXT_SECONDARY = "#cbd5e1"
C_TEXT_TERTIARY  = "#94a3b8"
# Global animation timing
C_EASE_MATERIAL = "cubic-bezier(0.4, 0.0, 0.2, 1)"
C_TRANS_FAST     = "all 150ms cubic-bezier(0.4, 0.0, 0.2, 1)"
C_TRANS_NORMAL   = "all 200ms cubic-bezier(0.4, 0.0, 0.2, 1)"
C_TRANS_SLOW     = "all 300ms cubic-bezier(0.4, 0.0, 0.2, 1)"
"""
lines.insert(insert_after, new_colors)
FILE.write_text("\n".join(lines), encoding="utf-8")
print("[Phase5] Step 1 done: color constants added")