"""
AURA VOID — void.py
Módulo de memoria persistente para el ecosistema AURA.
Guarda notas en Markdown dentro de /knowledge_base/void/ (compatible con Obsidian)
y opcionalmente sincroniza con Firebase para futuras búsquedas semánticas.
"""
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

# ── Configuración de rutas ──
BASE_DIR = Path(__file__).parent.parent
VOID_DIR = BASE_DIR / "knowledge_base" / "void"
VOID_DIR.mkdir(parents=True, exist_ok=True)

# ── Firebase (opcional) ──
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
        _void_ref = firebase_db.reference("aura/void/notes")
        _firebase_available = True
except Exception:
    pass


def save_to_void(content: str, tags: Optional[List[str]] = None) -> Dict:
    """
    Guarda una nota en Markdown en /knowledge_base/void/ y en Firebase.

    Args:
        content: Texto de la nota
        tags: Etiquetas para categorización (ej. ["osint", "proyecto"])

    Returns:
        Dict con: {"status": "ok"|"error", "file_path": "...", "firebase": bool}
    """
    if tags is None:
        tags = ["void"]

    timestamp = datetime.now()
    date_str = timestamp.strftime("%Y-%m-%d")
    time_str = timestamp.strftime("%H:%M:%S")
    slug = timestamp.strftime("%Y%m%d_%H%M%S")

    # Sanitizar título para filename
    title = content.strip()[:50].replace(" ", "_").replace("/", "-").replace("\\", "-").replace("\n", " ")
    filename = f"void_{slug}_{title}.md"
    filepath = VOID_DIR / filename

    # Frontmatter YAML + cuerpo Markdown
    tags_yaml = "\n".join([f"  - {t}" for t in tags])
    md_content = f"""---
created: {date_str} {time_str}
source: void
tags:
{tags_yaml}
type: note
---

# 🕳️ VOID — {timestamp.strftime('%d/%m/%Y %H:%M')}

{content}

---
*Guardado por AURA VOID — Memoria persistente del ecosistema*
"""

    # Guardar archivo .md
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md_content)
        file_saved = True
    except Exception as e:
        file_saved = False
        file_error = str(e)

    # Sincronizar con Firebase
    firebase_ok = False
    if _firebase_available:
        try:
            _void_ref.push({
                "content": content,
                "tags": tags,
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


def list_void(tag: Optional[str] = None, limit: int = 20) -> List[Dict]:
    """Lista las notas guardadas en VOID, opcionalmente filtradas por tag."""
    notes = []
    if not VOID_DIR.exists():
        return notes

    files = sorted(VOID_DIR.glob("*.md"), reverse=True)
    for fpath in files[:limit]:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            tags = []
            for line in content.split("\n"):
                if line.strip().startswith("- ") and not line.strip().startswith("- type"):
                    tag_candidate = line.strip()[2:]
                    if tag_candidate:
                        tags.append(tag_candidate)
            notes.append({
                "filename": fpath.name,
                "tags": tags,
                "preview": content[:200].replace("\n", " "),
            })
        except Exception:
            continue

    if tag:
        notes = [n for n in notes if tag in n["tags"]]

    return notes


def search_void(query: str) -> List[Dict]:
    """Búsqueda simple por palabra clave en el contenido de las notas."""
    results = []
    if not VOID_DIR.exists():
        return results

    query_lower = query.lower()
    for fpath in VOID_DIR.glob("*.md"):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            if query_lower in content.lower():
                results.append({
                    "filename": fpath.name,
                    "preview": content[:300].replace("\n", " "),
                })
        except Exception:
            continue

    return results


# ── Bloque de prueba ──
if __name__ == "__main__":
    result = save_to_void(
        "Prueba inicial del módulo VOID. Memoria persistente activa.",
        tags=["test", "void"],
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("\nNotas en VOID:")
    for n in list_void(limit=5):
        print(f"  - {n['filename']} [{', '.join(n['tags'])}]")