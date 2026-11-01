"""Interactive Codex & World Gazetteer Engine (BLOQUE 45).

Motor local de codex interactivo y gacetera del mundo (*World Gazetteer*).
Cataloga ubicaciones geograficas, artefactos historicos, mitologia y facetas
del lore como entidades interconectadas con referencias cruzadas a
personajes, canon y capitulos.

100% offline: almacenamiento JSON en disco bajo
<store_dir>/codex/work_<id>.codex.json. Sin dependencias de bases de datos
espaciales comerciales ni servicios en la nube.
"""

from __future__ import annotations

import json
import math
import os
import re
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.story_memory.story_storage import StoryStorage
from backend.story_memory.character_bible import CharacterBible


class CodexEntryType(Enum):
    """Tipos de entrada del codex."""

    LOCATION = "location"
    LANDMARK = "landmark"
    ARTIFACT = "artifact"
    CREATURE = "creature"
    MYTH = "myth"
    FACTION_LAIR = "faction_lair"
    EVENT_SITE = "event_site"
    CUSTOM = "custom"


class LocationClimate(Enum):
    """Climas canonicales para validacion espacial."""

    TEMPERATE = "temperate"
    ARID = "arid"
    TROPICAL = "tropical"
    POLAR = "polar"
    VOLCANIC = "volcanic"
    MAGICAL = "magical"
    UNDERWATER = "underwater"
    SUBTERRANEAN = "subterranean"
    UNKNOWN = "unknown"


_SLUG_RE = re.compile(r"[^a-z0-9]+")


@dataclass
class CodexEntry:
    """Ficha de lore del codex / gacetera."""

    entry_id: str
    work_id: str
    title: str
    entry_type: CodexEntryType
    description: str = ""
    x: float = 0.0
    y: float = 0.0
    region: str = ""
    climate: str = LocationClimate.UNKNOWN.value
    controlling_faction: str = ""
    traits: List[str] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)
    characters: List[str] = field(default_factory=list)
    canon_refs: List[str] = field(default_factory=list)
    chapter_refs: List[str] = field(default_factory=list)
    influence_radius: float = 0.0
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id, "work_id": self.work_id,
            "title": self.title, "entry_type": self.entry_type.value,
            "description": self.description, "x": self.x, "y": self.y,
            "region": self.region, "climate": self.climate,
            "controlling_faction": self.controlling_faction,
            "traits": list(self.traits), "artifacts": list(self.artifacts),
            "characters": list(self.characters),
            "canon_refs": list(self.canon_refs),
            "chapter_refs": list(self.chapter_refs),
            "influence_radius": self.influence_radius,
            "tags": list(self.tags), "created_at": self.created_at,
            "updated_at": self.updated_at, "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CodexEntry":
        try:
            et = CodexEntryType(data.get("entry_type", "custom"))
        except ValueError:
            et = CodexEntryType.CUSTOM
        return cls(
            entry_id=data["entry_id"], work_id=data.get("work_id", ""),
            title=data.get("title", ""), entry_type=et,
            description=data.get("description", ""),
            x=float(data.get("x", 0.0)), y=float(data.get("y", 0.0)),
            region=data.get("region", ""),
            climate=data.get("climate", LocationClimate.UNKNOWN.value),
            controlling_faction=data.get("controlling_faction", ""),
            traits=list(data.get("traits", [])),
            artifacts=list(data.get("artifacts", [])),
            characters=list(data.get("characters", [])),
            canon_refs=list(data.get("canon_refs", [])),
            chapter_refs=list(data.get("chapter_refs", [])),
            influence_radius=float(data.get("influence_radius", 0.0)),
            tags=list(data.get("tags", [])),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            metadata=dict(data.get("metadata", {})),
        )


def _slug(text: str) -> str:
    s = _SLUG_RE.sub("-", (text or "").strip().lower()).strip("-")
    return s or f"entry_{int(time.time() * 1000)}"


@dataclass
class WorldCodex:
    """Codex completo de una obra."""

    work_id: str
    entries: Dict[str, CodexEntry] = field(default_factory=dict)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "work_id": self.work_id,
            "entries": {k: v.to_dict() for k, v in self.entries.items()},
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorldCodex":
        codex = cls(work_id=data.get("work_id", ""))
        for eid, edata in (data.get("entries") or {}).items():
            try:
                codex.entries[eid] = CodexEntry.from_dict(edata)
            except Exception:
                continue
        codex.updated_at = data.get("updated_at", time.time())
        return codex


class GazetteerEngine:
    """Gestor local de codex / gacetera por obra."""

    def __init__(self, store_dir: Optional[str] = None) -> None:
        self.store_dir = Path(
            store_dir or os.getenv("AURA_STORY_DIR", os.path.join(os.getcwd(), "story_memory"))
        )
        self.codex_dir = self.store_dir / "codex"
        self.codex_dir.mkdir(parents=True, exist_ok=True)
        self.storage = StoryStorage(store_dir=str(self.store_dir))
        self._codexes: Dict[str, WorldCodex] = {}
        self._lock = threading.RLock()

    def _codex_path(self, work_id: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in work_id)
        return self.codex_dir / f"work_{safe}.codex.json"

    def _load_codex(self, work_id: str) -> WorldCodex:
        with self._lock:
            if work_id in self._codexes:
                return self._codexes[work_id]
            path = self._codex_path(work_id)
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        codex = WorldCodex.from_dict(json.load(f))
                except Exception:
                    codex = WorldCodex(work_id=work_id)
            else:
                codex = WorldCodex(work_id=work_id)
            self._codexes[work_id] = codex
            return codex

    def _save_codex(self, work_id: str) -> None:
        with self._lock:
            codex = self._codexes.get(work_id)
            if not codex:
                return
            codex.updated_at = time.time()
            path = self._codex_path(work_id)
            tmp = path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(codex.to_dict(), f, ensure_ascii=False, indent=2)
            tmp.replace(path)

    def get_or_create_codex(self, work_id: str) -> WorldCodex:
        codex = self._load_codex(work_id)
        if not self._codex_path(work_id).exists():
            self._save_codex(work_id)
        return codex

    def create_entry(
        self, work_id: str, title: str, entry_type: Any = CodexEntryType.LOCATION,
        description: str = "", x: float = 0.0, y: float = 0.0,
        region: str = "", climate: str = LocationClimate.UNKNOWN.value,
        controlling_faction: str = "", traits: Optional[List[str]] = None,
        influence_radius: float = 0.0, tags: Optional[List[str]] = None,
        entry_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not title or not title.strip():
            return {"status": "error", "error": "title_required"}
        if isinstance(entry_type, str):
            try:
                entry_type = CodexEntryType(entry_type)
            except ValueError:
                return {"status": "error", "error": f"invalid:{entry_type}"}
        codex = self._load_codex(work_id)
        eid = entry_id or _slug(title)
        base, n = eid, 2
        while eid in codex.entries:
            eid = f"{base}-{n}"
            n += 1
        entry = CodexEntry(
            entry_id=eid, work_id=work_id, title=title.strip(),
            entry_type=entry_type, description=description,
            x=float(x or 0.0), y=float(y or 0.0), region=region,
            climate=climate or LocationClimate.UNKNOWN.value,
            controlling_faction=controlling_faction,
            traits=list(traits or []),
            influence_radius=float(influence_radius or 0.0),
            tags=list(tags or []),
        )
        codex.entries[eid] = entry
        self._save_codex(work_id)
        return {"status": "created", "work_id": work_id, "entry": entry.to_dict()}

    def get_entry(self, work_id: str, entry_id: str) -> Dict[str, Any]:
        codex = self._load_codex(work_id)
        entry = codex.entries.get(entry_id)
        if not entry:
            return {"status": "error", "error": "entry_not_found"}
        return {"status": "ok", "work_id": work_id, "entry": entry.to_dict()}

    def list_entries(
        self, work_id: str, entry_type: Optional[Any] = None,
        region: Optional[str] = None, limit: int = 100,
    ) -> Dict[str, Any]:
        codex = self._load_codex(work_id)
        out: List[Dict[str, Any]] = []
        for e in codex.entries.values():
            if entry_type:
                want = entry_type.value if isinstance(entry_type, CodexEntryType) else str(entry_type)
                if e.entry_type.value != want:
                    continue
            if region and e.region != region:
                continue
            out.append(e.to_dict())
            if len(out) >= max(1, limit):
                break
        return {"status": "ok", "work_id": work_id, "count": len(out), "entries": out}

    def update_entry(self, work_id: str, entry_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        codex = self._load_codex(work_id)
        entry = codex.entries.get(entry_id)
        if not entry:
            return {"status": "error", "error": "entry_not_found"}
        allowed = ("title", "description", "x", "y", "region", "climate",
                   "controlling_faction", "traits", "artifacts", "characters",
                   "canon_refs", "chapter_refs", "influence_radius", "tags", "metadata")
        for key in allowed:
            if key in updates:
                val = updates[key]
                if key in ("x", "y", "influence_radius"):
                    try:
                        val = float(val)
                    except (TypeError, ValueError):
                        continue
                setattr(entry, key, val)
        if "entry_type" in updates:
            try:
                entry.entry_type = (updates["entry_type"] if isinstance(
                    updates["entry_type"], CodexEntryType)
                    else CodexEntryType(str(updates["entry_type"])))
            except ValueError:
                pass
        entry.updated_at = time.time()
        self._save_codex(work_id)
        return {"status": "updated", "work_id": work_id, "entry": entry.to_dict()}

    def delete_entry(self, work_id: str, entry_id: str) -> Dict[str, Any]:
        codex = self._load_codex(work_id)
        if entry_id not in codex.entries:
            return {"status": "error", "error": "entry_not_found"}
        del codex.entries[entry_id]
        for e in codex.entries.values():
            if entry_id in e.artifacts:
                e.artifacts = [a for a in e.artifacts if a != entry_id]
        self._save_codex(work_id)
        return {"status": "deleted", "work_id": work_id, "entry_id": entry_id}

    def link_artifact(self, work_id: str, entry_id: str, artifact_id: str) -> Dict[str, Any]:
        codex = self._load_codex(work_id)
        entry, art = codex.entries.get(entry_id), codex.entries.get(artifact_id)
        if not entry or not art:
            return {"status": "error", "error": "entry_not_found"}
        if artifact_id not in entry.artifacts:
            entry.artifacts.append(artifact_id)
            entry.updated_at = time.time()
            self._save_codex(work_id)
        return {"status": "linked", "entry_id": entry_id, "artifact_id": artifact_id}

    def link_character(self, work_id: str, entry_id: str, char_id: str) -> Dict[str, Any]:
        codex = self._load_codex(work_id)
        entry = codex.entries.get(entry_id)
        if not entry:
            return {"status": "error", "error": "entry_not_found"}
        if char_id not in entry.characters:
            entry.characters.append(char_id)
            entry.updated_at = time.time()
            self._save_codex(work_id)
        return {"status": "linked", "entry_id": entry_id, "char_id": char_id}

    def link_canon(self, work_id: str, entry_id: str, event_id: str) -> Dict[str, Any]:
        codex = self._load_codex(work_id)
        entry = codex.entries.get(entry_id)
        if not entry:
            return {"status": "error", "error": "entry_not_found"}
        if event_id not in entry.canon_refs:
            entry.canon_refs.append(event_id)
            entry.updated_at = time.time()
            self._save_codex(work_id)
        return {"status": "linked", "entry_id": entry_id, "event_id": event_id}

    def get_cross_references(self, work_id: str, entry_id: str) -> Dict[str, Any]:
        codex = self._load_codex(work_id)
        entry = codex.entries.get(entry_id)
        if not entry:
            return {"status": "error", "error": "entry_not_found"}
        inbound = [e.entry_id for e in codex.entries.values()
                   if entry_id in e.artifacts or entry_id in e.canon_refs]
        cb = CharacterBible()
        char_status = {c: (cb.get(work_id, c) is not None) for c in entry.characters}
        return {
            "status": "ok", "work_id": work_id, "entry_id": entry_id,
            "outbound": {
                "artifacts": list(entry.artifacts),
                "characters": list(entry.characters),
                "canon_refs": list(entry.canon_refs),
                "chapter_refs": list(entry.chapter_refs),
            },
            "inbound_entries": inbound,
            "character_exists": char_status,
        }

    @staticmethod
    def _dist(ax: float, ay: float, bx: float, by: float) -> float:
        return math.hypot(ax - bx, ay - by)

    def search_by_radius(
        self, work_id: str, x: float, y: float, radius: float, limit: int = 50
    ) -> Dict[str, Any]:
        codex = self._load_codex(work_id)
        hits: List[Tuple[float, CodexEntry]] = []
        for e in codex.entries.values():
            d = self._dist(float(x), float(y), e.x, e.y)
            if d <= float(radius):
                hits.append((d, e))
        hits.sort(key=lambda t: t[0])
        results = [{"distance": round(d, 3), "entry": e.to_dict()}
                   for d, e in hits[: max(1, limit)]]
        return {"status": "ok", "work_id": work_id, "count": len(results),
                "x": x, "y": y, "radius": radius, "results": results}

    def find_controlling_entry(self, work_id: str, x: float, y: float) -> Dict[str, Any]:
        codex = self._load_codex(work_id)
        best: Optional[Tuple[float, CodexEntry]] = None
        for e in codex.entries.values():
            if e.influence_radius <= 0:
                continue
            d = self._dist(float(x), float(y), e.x, e.y)
            if d <= e.influence_radius and (best is None or d < best[0]):
                best = (d, e)
        if not best:
            return {"status": "ok", "work_id": work_id, "entry": None}
        return {"status": "ok", "work_id": work_id,
                "entry": best[1].to_dict(), "distance": round(best[0], 3)}

    def get_codex_stats(self, work_id: str) -> Dict[str, Any]:
        codex = self._load_codex(work_id)
        by_type: Dict[str, int] = {}
        regions: Dict[str, int] = {}
        for e in codex.entries.values():
            by_type[e.entry_type.value] = by_type.get(e.entry_type.value, 0) + 1
            if e.region:
                regions[e.region] = regions.get(e.region, 0) + 1
        return {"status": "ok", "work_id": work_id, "total": len(codex.entries),
                "by_type": by_type, "regions": regions}

    def check_spatial_consistency(
        self, work_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Jan Spatial Consistency Checker: escena vs codex."""
        codex = self._load_codex(work_id)
        entry: Optional[CodexEntry] = None
        if payload.get("entry_id"):
            entry = codex.entries.get(str(payload["entry_id"]))
            if not entry:
                return {"status": "error", "error": "entry_not_found"}
        elif "x" in payload and "y" in payload:
            found = self.find_controlling_entry(work_id, float(payload["x"]), float(payload["y"]))
            if found.get("entry"):
                entry = CodexEntry.from_dict(found["entry"])
        if not entry:
            return {"status": "error", "error": "location_not_resolved"}
        issues: List[Dict[str, str]] = []
        exp_climate = payload.get("expected_climate")
        if exp_climate and entry.climate != str(exp_climate):
            issues.append({"type": "climate_mismatch",
                           "message": f"{entry.title} clima '{entry.climate}', esperado '{exp_climate}'."})
        exp_faction = payload.get("expected_faction")
        if exp_faction and entry.controlling_faction != str(exp_faction):
            issues.append({"type": "faction_mismatch",
                           "message": f"{entry.title} bajo '{entry.controlling_faction or 'nadie'}', esperado '{exp_faction}'."})
        for trait in payload.get("expected_traits", []) or []:
            if trait not in entry.traits:
                issues.append({"type": "trait_missing",
                               "message": f"{entry.title} sin rasgo '{trait}'."})
        desc = str(payload.get("scene_description", ""))
        trait_hits = [t for t in entry.traits if t and t.lower() in desc.lower()] if desc else []
        return {
            "status": "ok", "work_id": work_id, "entry_id": entry.entry_id,
            "consistent": len(issues) == 0, "issues": issues,
            "controlling_faction": entry.controlling_faction,
            "climate": entry.climate, "trait_hits": trait_hits,
        }

    def build_codex_context(
        self, work_id: str, entry_ids: Optional[List[str]] = None,
        max_chars: int = 2000,
    ) -> str:
        codex = self._load_codex(work_id)
        entries = ([codex.entries[e] for e in (entry_ids or []) if e in codex.entries]
                   or list(codex.entries.values())[:10])
        if not entries:
            return ""
        lines = ["[CODEX - gacetera local]"]
        total = 0
        for e in entries:
            line = (f"[{e.entry_type.value}:{e.entry_id}] {e.title} "
                    f"({e.region or 'sin region'}, clima={e.climate}) - {e.description}".strip())
            if total + len(line) > max_chars and total > 0:
                break
            lines.append(line)
            total += len(line)
        return " | ".join(lines)

    def export_codex(self, work_id: str) -> Dict[str, Any]:
        codex = self.get_or_create_codex(work_id)
        return {"status": "ok", "work_id": work_id,
                "entries": [e.to_dict() for e in codex.entries.values()],
                "stats": self.get_codex_stats(work_id)}

    def import_codex(self, work_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Importa datos del codex desde un backup (formato export_codex)."""
        try:
            codex = self.get_or_create_codex(work_id)
            
            # Clear existing entries
            codex.entries.clear()
            
            # Import entries
            for entry_data in data.get("entries", []):
                entry = CodexEntry.from_dict(entry_data)
                codex.entries[entry.entry_id] = entry
            
            # Save to disk
            self._save_codex(work_id)
            return {"status": "ok", "work_id": work_id, "imported": True}
        except Exception as e:
            return {"status": "error", "error": str(e)}


_gazetteer: Optional[GazetteerEngine] = None
_lock_init = threading.Lock()


def get_gazetteer(store_dir: Optional[str] = None) -> GazetteerEngine:
    global _gazetteer
    if _gazetteer is None:
        with _lock_init:
            if _gazetteer is None:
                _gazetteer = GazetteerEngine(store_dir=store_dir)
    return _gazetteer


def reset_gazetteer() -> None:
    global _gazetteer
    with _lock_init:
        _gazetteer = None

