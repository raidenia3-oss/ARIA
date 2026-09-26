import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
TASKS_FILE = BASE / "data" / "tasks.json"


def load_tasks() -> list:
    if not TASKS_FILE.exists():
        TASKS_FILE.write_text(json.dumps([], ensure_ascii=False, indent=2), encoding="utf-8")
    return json.loads(TASKS_FILE.read_text(encoding="utf-8"))


def save_task(horas: str, plataforma: str, ingreso: str) -> None:
    data = {
        "horas": horas,
        "plataforma": plataforma,
        "ingreso": ingreso,
    }
    tasks = load_tasks()
    tasks.append(data)
    TASKS_FILE.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")
