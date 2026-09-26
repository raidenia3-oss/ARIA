"""Gestión de videos para TikTok/Kwai."""

from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
INBOX = BASE / "data" / "videos_por_renderizar"
READY = BASE / "data" / "listos_para_subir"
INBOX.mkdir(parents=True, exist_ok=True)
READY.mkdir(parents=True, exist_ok=True)


def list_videos() -> list:
    rows = []
    for folder in (INBOX, READY):
        for p in folder.glob("*.mp4"):
            size = p.stat().st_size / (1024 * 1024)
            size_str = f"{size:.1f} MB"
            estado = "Listo" if folder == READY else "Por renderizar"
            rows.append([p.name, size_str, estado])
    if not rows:
        rows.append(["(sin videos)", "0 MB", "N/A"])
    return rows


def optimize_selected() -> None:
    # Mock: en una versión real se invocaría FFmpeg para convertir a vertical/optimizar bitrate
    print("[mock] optimize_selected() called")
