# -*- coding: utf-8 -*-
"""Temas personalizados por personaje/anime para ARIA (Linux desktop shell)."""
from __future__ import annotations

THEMES = {
    "cyberpunk": {
        "name": "Cyberpunk",
        "bg0": "#0a0e14", "bg1": "#0d1320", "bg2": "#050816",
        "accent": "#00d9ff", "accent2": "#ff00ff", "text": "#cfe8ff",
        "glass": "rgba(10,14,20,0.75)", "border": "rgba(0,217,255,0.35)",
    },
    "naruto": {
        "name": "Naruto (Uzumaki)",
        "bg0": "#1a0f00", "bg1": "#2a1a05", "bg2": "#0f0800",
        "accent": "#ff8c00", "accent2": "#1e90ff", "text": "#ffe8c0",
        "glass": "rgba(26,15,0,0.75)", "border": "rgba(255,140,0,0.4)",
    },
    "sasuke": {
        "name": "Sasuke (Uchiha)",
        "bg0": "#0a0a14", "bg1": "#14142a", "bg2": "#050510",
        "accent": "#7b68ee", "accent2": "#ff0040", "text": "#d8d8ff",
        "glass": "rgba(10,10,20,0.75)", "border": "rgba(123,104,238,0.4)",
    },
    "goku": {
        "name": "Goku (Dragon Ball)",
        "bg0": "#1a0505", "bg1": "#2a0a0a", "bg2": "#100303",
        "accent": "#ff4500", "accent2": "#ffd700", "text": "#ffe0d0",
        "glass": "rgba(26,5,5,0.75)", "border": "rgba(255,69,0,0.4)",
    },
    "luffy": {
        "name": "Luffy (One Piece)",
        "bg0": "#051520", "bg1": "#0a2030", "bg2": "#030d14",
        "accent": "#ff3333", "accent2": "#ffd700", "text": "#e0f0ff",
        "glass": "rgba(5,21,32,0.75)", "border": "rgba(255,51,51,0.4)",
    },
    "evangelion": {
        "name": "Evangelion (NERV)",
        "bg0": "#0a0000", "bg1": "#1a0505", "bg2": "#050000",
        "accent": "#ff0000", "accent2": "#00ff00", "text": "#ffcccc",
        "glass": "rgba(10,0,0,0.75)", "border": "rgba(255,0,0,0.4)",
    },
    "matrix": {
        "name": "Matrix",
        "bg0": "#000a00", "bg1": "#001400", "bg2": "#000500",
        "accent": "#00ff41", "accent2": "#008f11", "text": "#00ff41",
        "glass": "rgba(0,10,0,0.75)", "border": "rgba(0,255,65,0.4)",
    },
    "sakura": {
        "name": "Sakura (Card Captor)",
        "bg0": "#1a0515", "bg1": "#2a0a20", "bg2": "#10030d",
        "accent": "#ff69b4", "accent2": "#9370db", "text": "#ffe0f0",
        "glass": "rgba(26,5,21,0.75)", "border": "rgba(255,105,180,0.4)",
    },
}

ALIASES = {
    "uzumaki": "naruto", "sasuke": "sasuke", "uchiha": "sasuke",
    "goku": "goku", "son goku": "goku", "luffy": "luffy", "monkey": "luffy",
    "eva": "evangelion", "nerv": "evangelion", "matrix": "matrix",
    "sakura": "sakura", "cyberpunk": "cyberpunk", "neon": "cyberpunk",
}


def resolve_theme(name: str) -> str:
    key = (name or "").strip().lower()
    if key in THEMES:
        return key
    if key in ALIASES:
        return ALIASES[key]
    for k in THEMES:
        if k in key or key in k:
            return k
    return "cyberpunk"


def get_theme(name: str) -> dict:
    return THEMES.get(resolve_theme(name), THEMES["cyberpunk"])