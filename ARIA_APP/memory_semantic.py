# -*- coding: utf-8 -*-
"""ARIA - Memoria semantica local (sqlite-vec + embeddings ligeros). Sin servidores.

Guarda recuerdos y los recupera por SIGNIFICADO, no solo por palabra.
Embeddings: fastembed (ONNX, local, multilingue) — baja el modelo una vez (~220MB).
Encaja con el enfoque SQLite de ARIA; todo en proceso, sin puertos.
"""
import os
import sqlite3

_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
_DIM = 384


def disponible():
    try:
        import sqlite_vec  # noqa
        import fastembed  # noqa
        return True
    except Exception:
        return False


class _Embebedor:
    _inst = None

    @classmethod
    def get(cls):
        if cls._inst is None:
            from fastembed import TextEmbedding
            cls._inst = TextEmbedding(model_name=_MODEL)
        return cls._inst

    @classmethod
    def vec(cls, texto):
        return list(cls.get().embed([texto]))[0].tolist()


class MemoriaSemantica:
    def __init__(self, db_path, embed_fn=None, dim=_DIM):
        self.db_path = db_path
        self.dim = dim
        self.embed_fn = embed_fn or _Embebedor.vec
        self._db = None

    def _conn(self):
        if self._db is None:
            import sqlite_vec
            os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
            self._db = sqlite3.connect(self.db_path, check_same_thread=False)
            self._db.enable_load_extension(True)
            sqlite_vec.load(self._db)
            self._db.enable_load_extension(False)
            self._db.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS recuerdos "
                "USING vec0(id INTEGER PRIMARY KEY, texto TEXT, meta TEXT, v FLOAT[%d])" % self.dim)
        return self._db

    def _ser(self, v):
        import sqlite_vec
        return sqlite_vec.serialize_float32(v)

    def recordar(self, texto, meta=""):
        texto = (texto or "").strip()
        if not texto:
            return None
        try:
            v = self.embed_fn(texto)
            db = self._conn()
            cur = db.execute("INSERT INTO recuerdos(texto,meta,v) VALUES(?,?,?)",
                             (texto, meta, self._ser(v)))
            db.commit()
            return cur.lastrowid
        except Exception:
            return None

    def buscar(self, consulta, k=3, max_dist=None):
        try:
            qv = self._ser(self.embed_fn(consulta))
            db = self._conn()
            filas = db.execute(
                "SELECT texto, meta, distance FROM recuerdos "
                "WHERE v MATCH ? ORDER BY distance LIMIT ?", (qv, k)).fetchall()
        except Exception:
            return []
        out = []
        for texto, meta, dist in filas:
            if max_dist is None or dist <= max_dist:
                out.append({"texto": texto, "meta": meta, "dist": round(float(dist), 3)})
        return out
