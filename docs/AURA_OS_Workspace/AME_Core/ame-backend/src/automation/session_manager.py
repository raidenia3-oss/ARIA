"""
SessionManager — Gestor multi-cuenta con sesiones aisladas.
Cada cuenta se almacena en una carpeta numerada (sessions/user_01/, etc.)
para evitar cruce de cookies/estados entre sesiones.
"""

import json
import os
from pathlib import Path

BASE_SESSIONS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "sessions"


def _session_dir(index: int) -> Path:
    folder = BASE_SESSIONS_DIR / f"user_{index:02d}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def list_sessions() -> list[str]:
    if not BASE_SESSIONS_DIR.exists():
        return []
    return sorted([p.name for p in BASE_SESSIONS_DIR.iterdir() if p.is_dir()])


def create_session(index: int, profile_dir: str | None = None) -> dict:
    session_path = _session_dir(index)
    meta = {
        "index": index,
        "profile_dir": profile_dir or str(session_path),
        "active": True,
    }
    (session_path / "metadata.json").write_text(json.dumps(meta, indent=2))
    (session_path / "cookies.json").write_text("[]")
    (session_path / "state.json").write_text("{}")
    return meta


def load_session(index: int) -> dict | None:
    session_path = _session_dir(index)
    meta_file = session_path / "metadata.json"
    if not meta_file.exists():
        return None
    meta = json.loads(meta_file.read_text())
    meta["cookies_path"] = str(session_path / "cookies.json")
    meta["state_path"] = str(session_path / "state.json")
    meta["session_dir"] = str(session_path)
    return meta


def save_cookies(index: int, cookies: list[dict]) -> None:
    session_path = _session_dir(index)
    (session_path / "cookies.json").write_text(json.dumps(cookies, indent=2))


def load_cookies(index: int) -> list[dict]:
    session_path = _session_dir(index)
    cookies_file = session_path / "cookies.json"
    if not cookies_file.exists():
        return []
    return json.loads(cookies_file.read_text())


def save_state(index: int, state: dict) -> None:
    session_path = _session_dir(index)
    (session_path / "state.json").write_text(json.dumps(state, indent=2))


def load_state(index: int) -> dict:
    session_path = _session_dir(index)
    state_file = session_path / "state.json"
    if not state_file.exists():
        return {}
    return json.loads(state_file.read_text())


def get_browser_context_path(index: int) -> str:
    """
    Devuelve la ruta de carpeta que Playwright/Selenium puede usar
    como user_data_dir/profile aislado para esta sesión.
    """
    return str(_session_dir(index))


if __name__ == "__main__":
    print("Sessions:", list_sessions())
    for i in range(1, 3):
        create_session(i)
        print(f"Session user_{i:02d} created.")
    print("Load user_01:", load_session(1))
