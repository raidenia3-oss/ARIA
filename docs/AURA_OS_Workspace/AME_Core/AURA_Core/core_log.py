"""
AURA Core Log — core_log.py
Guarda notas del usuario en formato Markdown (para Obsidian)
y simultáneamente envía logs a Firebase.
Conectado al AuraCognitiveRouter para auto-guardado contextual.
"""
import os
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List

# ── Configuración de rutas ──
BASE_DIR = Path(__file__).parent.parent
KNOWLEDGE_BASE = BASE_DIR / "knowledge_base"
KNOWLEDGE_BASE.mkdir(parents=True, exist_ok=True)

# ── Firebase (opcional, se conecta si hay credenciales) ──
_firebase_available = False
try:
    import firebase_admin
    from firebase_admin import credentials, db as firebase_db
    _cred_path = os.environ.get("FIREBASE_CRED_PATH")
    _db_url = os.environ.get("FIREBASE_DATABASE_URL")
    if _cred_path and _db_url:
        if not firebase_admin._apps:
            cred = credentials.Certificate(_cred_path)
            firebase_admin.initialize_app(cred, {"databaseURL": _db_url})
        _firebase_ref = firebase_db.reference("aura/core/logs")
        _firebase_available = True
except Exception:
    pass


def save_note(
    content: str,
    tags: Optional[List[str]] = None,
    source: str = "manual",
    sync_firebase: bool = True,
) -> Dict:
    """
    Guarda una nota en Markdown en /knowledge_base y opcionalmente en Firebase.

    Args:
        content: Texto de la nota
        tags: Lista de etiquetas (ej. ["osint", "observacion"])
        source: Origen de la nota ("manual", "ai_router", "bot")
        sync_firebase: Si True, intenta sincronizar con Firebase

    Returns:
        Dict con: {"status": "ok"|"error", "file_path": "...", "firebase": bool}
    """
    if tags is None:
        tags = []

    timestamp = datetime.now()
    date_str = timestamp.strftime("%Y-%m-%d")
    time_str = timestamp.strftime("%H:%M:%S")
    slug = timestamp.strftime("%Y%m%d_%H%M%S")

    # Sanitizar contenido para filename
    title = content.strip()[:40].replace(" ", "_").replace("/", "-").replace("\\", "-")
    filename = f"{slug}_{title}.md"
    filepath = KNOWLEDGE_BASE / filename

    # Construir frontmatter YAML + body
    tags_yaml = "\n".join([f"  - {t}" for t in tags]) if tags else "  - uncategorized"
    md_content = f"""---
created: {date_str} {time_str}
source: {source}
tags:
{tags_yaml}
---

# Nota - {timestamp.strftime('%d/%m/%Y %H:%M')}

{content}

---
*Guardado automáticamente por AURA Core Log*
"""

    # Guardar archivo Markdown
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md_content)
        file_saved = True
    except Exception as e:
        file_saved = False
        file_error = str(e)

    # Sincronizar con Firebase
    firebase_ok = False
    if sync_firebase and _firebase_available:
        try:
            _firebase_ref.push({
                "content": content,
                "tags": tags,
                "source": source,
                "timestamp": timestamp.isoformat(),
                "filename": filename,
            })
            firebase_ok = True
        except Exception:
            pass

    result = {
        "status": "ok" if file_saved else "error",
        "file_path": str(filepath),
        "filename": filename,
        "firebase_sync": firebase_ok,
        "tags": tags,
    }

    if not file_saved:
        result["error"] = file_error

    return result


def list_notes(tag: Optional[str] = None, limit: int = 20) -> List[Dict]:
    """Lista las notas guardadas en knowledge_base, opcionalmente filtradas por tag."""
    notes = []
    if not KNOWLEDGE_BASE.exists():
        return notes

    files = sorted(KNOWLEDGE_BASE.glob("*.md"), reverse=True)
    for fpath in files[:limit]:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            # Extraer tags simples desde frontmatter (sin parser YAML completo)
            tags = []
            for line in content.split("\n"):
                if line.strip().startswith("- "):
                    tag_candidate = line.strip()[2:]
                    if tag_candidate and not tag_candidate.startswith("categ"):
                        tags.append(tag_candidate)
            notes.append({
                "filename": fpath.name,
                "path": str(fpath),
                "tags": tags,
                "preview": content[:200],
            })
        except Exception:
            continue

    if tag:
        notes = [n for n in notes if tag in n["tags"]]

    return notes


# ── Bloque de prueba ──
if __name__ == "__main__":
    result = save_note(
        "Prueba de integración del módulo Core Log. AURA Core funcionando.",
        tags=["test", "core_log"],
        source="manual",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("\nNotas guardadas:")
    for n in list_notes(limit=5):
        print(f"  - {n['filename']} [{', '.join(n['tags'])}]")