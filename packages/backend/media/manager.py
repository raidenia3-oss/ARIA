"""AURA Local Asset & Media Gallery Manager (Bloque 47).

Pipeline multimedia 100% local: recibe imagenes (PNG/JPEG/WEBP/GIF/BMP),
genera thumbnail ligero (Pillow), almacena binarios en disco
<store_dir>/media/<work_id>/ y metadatos en JSON
<store_dir>/media/work_<id>.media.json. Asset-to-Lore Mapper vincula
assets con personajes del Character Bible y entradas del Gazetteer.

Sin S3/Cloudinary ni servicios cloud. Streaming por chunks para no
saturar RAM.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, BinaryIO, Dict, Iterator, List, Optional

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None  # type: ignore

from backend.story_memory.story_storage import StoryStorage

_ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
_ALLOWED_MIME = {"image/png", "image/jpeg", "image/webp", "image/gif", "image/bmp"}
_THUMB_SIZE = (256, 256)
_CHUNK = 1024 * 256


def _max_bytes() -> int:
    return int(os.getenv("AURA_MEDIA_MAX_BYTES", str(15 * 1024 * 1024)))


class AssetKind(Enum):
    CONCEPT_ART = "concept_art"
    MAP = "map"
    PORTRAIT = "portrait"
    LOCATION = "location"
    ARTIFACT = "artifact"
    OTHER = "other"


@dataclass
class MediaAsset:
    asset_id: str
    work_id: str
    filename: str
    stored_name: str
    mime: str
    size_bytes: int
    sha256: str
    kind: str = AssetKind.OTHER.value
    title: str = ""
    width: int = 0
    height: int = 0
    thumb_name: str = ""
    char_id: str = ""
    codex_entry_id: str = ""
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id": self.asset_id, "work_id": self.work_id,
            "filename": self.filename, "stored_name": self.stored_name,
            "mime": self.mime, "size_bytes": self.size_bytes,
            "sha256": self.sha256, "kind": self.kind, "title": self.title,
            "width": self.width, "height": self.height,
            "thumb_name": self.thumb_name, "char_id": self.char_id,
            "codex_entry_id": self.codex_entry_id,
            "tags": list(self.tags), "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MediaAsset":
        return cls(
            asset_id=d["asset_id"], work_id=d.get("work_id", ""),
            filename=d.get("filename", ""), stored_name=d.get("stored_name", ""),
            mime=d.get("mime", "application/octet-stream"),
            size_bytes=int(d.get("size_bytes", 0)), sha256=d.get("sha256", ""),
            kind=d.get("kind", AssetKind.OTHER.value), title=d.get("title", ""),
            width=int(d.get("width", 0)), height=int(d.get("height", 0)),
            thumb_name=d.get("thumb_name", ""), char_id=d.get("char_id", ""),
            codex_entry_id=d.get("codex_entry_id", ""),
            tags=list(d.get("tags", [])), created_at=d.get("created_at", time.time()),
        )


def _ext_of(filename: str, mime: str) -> str:
    ext = Path(filename or "").suffix.lower()
    if ext in _ALLOWED_EXT:
        return ext
    return {
        "image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
        "image/gif": ".gif", "image/bmp": ".bmp",
    }.get(mime, ".bin")


class MediaManager:
    """Gestor local de assets multimedia por obra."""

    def __init__(self, store_dir: Optional[str] = None) -> None:
        self.store_dir = Path(
            store_dir or os.getenv("AURA_STORY_DIR", os.path.join(os.getcwd(), "story_memory"))
        )
        self.media_root = self.store_dir / "media"
        self.media_root.mkdir(parents=True, exist_ok=True)
        self.storage = StoryStorage(store_dir=str(self.store_dir))
        self._assets: Dict[str, Dict[str, MediaAsset]] = {}
        self._lock = threading.RLock()

    def _work_dir(self, work_id: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in work_id)
        d = self.media_root / f"work_{safe}"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _index_path(self, work_id: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in work_id)
        return self.media_root / f"work_{safe}.media.json"

    def _load(self, work_id: str) -> Dict[str, MediaAsset]:
        with self._lock:
            if work_id in self._assets:
                return self._assets[work_id]
            idx = self._index_path(work_id)
            assets: Dict[str, MediaAsset] = {}
            if idx.exists():
                try:
                    data = json.loads(idx.read_text(encoding="utf-8"))
                    for aid, ad in (data.get("assets") or {}).items():
                        try:
                            assets[aid] = MediaAsset.from_dict(ad)
                        except Exception:
                            continue
                except Exception:
                    assets = {}
            self._assets[work_id] = assets
            return assets

    def _save(self, work_id: str) -> None:
        with self._lock:
            assets = self._assets.get(work_id, {})
            tmp = self._index_path(work_id).with_suffix(".tmp")
            tmp.write_text(json.dumps(
                {"work_id": work_id,
                 "assets": {k: v.to_dict() for k, v in assets.items()}},
                ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self._index_path(work_id))

    def _gen_thumb(self, src_path: Path, dst_path: Path) -> bool:
        if Image is None:
            return False
        try:
            with Image.open(src_path) as im:
                im.thumbnail(_THUMB_SIZE, Image.LANCZOS)
                if im.mode in ("RGBA", "LA", "P"):
                    bg = Image.new("RGB", im.size, (255, 255, 255))
                    bg.paste(im, mask=im.split()[-1] if im.mode in ("RGBA", "LA") else None)
                    im = bg
                im.save(dst_path, "WEBP", quality=75, method=6)
            return True
        except Exception as exc:
            import logging
            logging.getLogger("AURA.Media").debug("Thumb gen failed: %s", exc)
            return False

    def _read_stream_sha256(self, stream: BinaryIO, size: int) -> str:
        h = hashlib.sha256()
        remaining = size
        while remaining > 0:
            chunk = stream.read(min(_CHUNK, remaining))
            if not chunk:
                break
            h.update(chunk)
            remaining -= len(chunk)
        return h.hexdigest()

    def ingest(
        self,
        work_id: str,
        stream: BinaryIO,
        filename: str,
        mime: str,
        kind: str = AssetKind.OTHER.value,
        title: str = "",
        char_id: str = "",
        codex_entry_id: str = "",
        tags: Optional[List[str]] = None,
        asset_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if mime not in _ALLOWED_MIME:
            return {"status": "error", "error": f"mime_not_allowed: {mime}"}
        ext = _ext_of(filename, mime)
        if not asset_id:
            asset_id = hashlib.sha1(f"{work_id}{filename}{time.time()}".encode()).hexdigest()[:12]
        assets = self._load(work_id)
        if asset_id in assets:
            return {"status": "error", "error": "asset_id_exists"}
        if kind not in [k.value for k in AssetKind]:
            kind = AssetKind.OTHER.value
        wdir = self._work_dir(work_id)
        stored = f"{asset_id}{ext}"
        dst = wdir / stored
        size = 0
        h = hashlib.sha256()
        too_large = False
        with open(dst, "wb") as out:
            while True:
                chunk = stream.read(_CHUNK)
                if not chunk:
                    break
                out.write(chunk)
                h.update(chunk)
                size += len(chunk)
                if size > _max_bytes():
                    too_large = True
                    break
        if too_large:
            try:
                dst.unlink(missing_ok=True)
            except Exception:
                pass
            return {"status": "error", "error": "file_too_large"}
        sha256 = h.hexdigest()
        width = height = 0
        thumb_name = ""
        if Image is not None:
            try:
                with Image.open(dst) as im:
                    width, height = im.size
                thumb_name = f"{asset_id}_thumb.webp"
                self._gen_thumb(dst, wdir / thumb_name)
            except Exception:
                pass
        asset = MediaAsset(
            asset_id=asset_id, work_id=work_id, filename=filename,
            stored_name=stored, mime=mime, size_bytes=size, sha256=sha256,
            kind=kind, title=title, width=width, height=height,
            thumb_name=thumb_name, char_id=char_id, codex_entry_id=codex_entry_id,
            tags=list(tags or []),
        )
        assets[asset_id] = asset
        self._save(work_id)
        return {"status": "created", "work_id": work_id, "asset": asset.to_dict()}

    def get(self, work_id: str, asset_id: str) -> Dict[str, Any]:
        assets = self._load(work_id)
        asset = assets.get(asset_id)
        if not asset:
            return {"status": "error", "error": "asset_not_found"}
        return {"status": "ok", "work_id": work_id, "asset": asset.to_dict()}

    def list(
        self,
        work_id: str,
        kind: Optional[str] = None,
        char_id: Optional[str] = None,
        codex_entry_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        assets = self._load(work_id)
        filtered = list(assets.values())
        if kind:
            filtered = [a for a in filtered if a.kind == kind]
        if char_id:
            filtered = [a for a in filtered if a.char_id == char_id]
        if codex_entry_id:
            filtered = [a for a in filtered if a.codex_entry_id == codex_entry_id]
        filtered.sort(key=lambda a: a.created_at, reverse=True)
        total = len(filtered)
        page = filtered[offset:offset + limit]
        return {"status": "ok", "work_id": work_id, "total": total,
                "limit": limit, "offset": offset,
                "assets": [a.to_dict() for a in page]}

    def update(self, work_id: str, asset_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        assets = self._load(work_id)
        asset = assets.get(asset_id)
        if not asset:
            return {"status": "error", "error": "asset_not_found"}
        allowed = ("kind", "title", "char_id", "codex_entry_id", "tags")
        for k in allowed:
            if k in updates:
                v = updates[k]
                if k == "kind" and v not in [kt.value for kt in AssetKind]:
                    continue
                setattr(asset, k, v)
        self._save(work_id)
        return {"status": "updated", "work_id": work_id, "asset": asset.to_dict()}

    def delete(self, work_id: str, asset_id: str) -> Dict[str, Any]:
        assets = self._load(work_id)
        asset = assets.get(asset_id)
        if not asset:
            return {"status": "error", "error": "asset_not_found"}
        wdir = self._work_dir(work_id)
        (wdir / asset.stored_name).unlink(missing_ok=True)
        if asset.thumb_name:
            (wdir / asset.thumb_name).unlink(missing_ok=True)
        del assets[asset_id]
        self._save(work_id)
        return {"status": "deleted", "work_id": work_id, "asset_id": asset_id}

    def file_path(self, work_id: str, asset_id: str, thumb: bool = False) -> Optional[Path]:
        assets = self._load(work_id)
        asset = assets.get(asset_id)
        if not asset:
            return None
        wdir = self._work_dir(work_id)
        name = asset.thumb_name if thumb and asset.thumb_name else asset.stored_name
        p = wdir / name
        return p if p.exists() else None

    def link_character(self, work_id: str, asset_id: str, char_id: str) -> Dict[str, Any]:
        return self.update(work_id, asset_id, {"char_id": char_id})

    def link_codex(self, work_id: str, asset_id: str, codex_entry_id: str) -> Dict[str, Any]:
        return self.update(work_id, asset_id, {"codex_entry_id": codex_entry_id})

    def unlink_character(self, work_id: str, asset_id: str) -> Dict[str, Any]:
        return self.update(work_id, asset_id, {"char_id": ""})

    def unlink_codex(self, work_id: str, asset_id: str) -> Dict[str, Any]:
        return self.update(work_id, asset_id, {"codex_entry_id": ""})

    def get_by_character(self, work_id: str, char_id: str) -> Dict[str, Any]:
        return self.list(work_id, char_id=char_id)

    def get_by_codex(self, work_id: str, codex_entry_id: str) -> Dict[str, Any]:
        return self.list(work_id, codex_entry_id=codex_entry_id)

    def stats(self, work_id: str) -> Dict[str, Any]:
        assets = self._load(work_id)
        by_kind: Dict[str, int] = {}
        total_bytes = 0
        for a in assets.values():
            by_kind[a.kind] = by_kind.get(a.kind, 0) + 1
            total_bytes += a.size_bytes
        return {"status": "ok", "work_id": work_id, "total_assets": len(assets),
                "total_bytes": total_bytes, "by_kind": by_kind}

    def cleanup(self, work_id: str, max_age_secs: int = 86400 * 30) -> int:
        assets = self._load(work_id)
        now = time.time()
        removed = 0
        for aid, a in list(assets.items()):
            if now - a.created_at > max_age_secs:
                self.delete(work_id, aid)
                removed += 1
        return removed


_media_mgr: Optional[MediaManager] = None
_mgr_lock = threading.Lock()


def get_media_manager(store_dir: Optional[str] = None) -> MediaManager:
    global _media_mgr
    if _media_mgr is None:
        with _mgr_lock:
            if _media_mgr is None:
                _media_mgr = MediaManager(store_dir=store_dir)
    return _media_mgr


def reset_media_manager() -> None:
    global _media_mgr
    with _mgr_lock:
        _media_mgr = None