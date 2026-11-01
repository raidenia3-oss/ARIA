"""ARIA Memory SQLite adapter - M2.

Cinco capas (reglas, hechos, experiencias, observaciones, modelos) + indice FTS5.
Dual-write: el JSONL existente sigue siendo la fuente de verdad; aqui queda
una copia consultable. Solo biblioteca estandar, sin red, sin subprocess.

Flag: ARIA_MEMORY_SQLITE (false por defecto). Con el flag apagado, retain()
devuelve None y recall() devuelve []: ARIA se comporta exactamente igual.
"""
from __future__ import annotations

import os
import re
import sqlite3
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


def _data_dir() -> Path:
    """Carpeta donde vive la base. En desarrollo, dentro de ARIA_APP.

    En el EXE congelado (PyInstaller) el directorio de trabajo temporal se
    borra al cerrar, asi que la base va a %LOCALAPPDATA%/ARIA_OS/data/memory
    para que sobreviva a los reinicios.
    """
    if getattr(sys, "frozen", False):
        base = os.environ.get("LOCALAPPDATA") or str(Path.home())
        return Path(base) / "ARIA_OS" / "data" / "memory"
    return Path(__file__).resolve().parent.parent / "data" / "memory"


ARIA_APP = Path(__file__).resolve().parent.parent
MEM_DIR = _data_dir()
MEM_DIR.mkdir(parents=True, exist_ok=True)
#: La base se puede mover con ARIA_MEMORY_DB (util en pruebas).
DB_PATH = Path(os.environ.get("ARIA_MEMORY_DB") or (MEM_DIR / "aria_mem.db"))

#: Capas de memoria y su confianza por defecto.
LAYERS: Dict[str, str] = {
    "reglas": "usuario",
    "hechos": "sistema",
    "experiencias": "sistema",
    "observaciones": "sistema",
    "modelos": "sistema",
}

#: Confianza admitida. Lo que no esta en la lista se degrada a 'sistema'.
CONFIANZAS = ("usuario", "sistema", "web")

#: Evidencia minima para promover una observacion a modelo (capa 5).
EVIDENCIA_MINIMA = 3

#: Interruptor en caliente. None = manda la variable de entorno.
_enabled_override: Optional[bool] = None

#: Texto que huele a credencial: no se guarda, ni siquiera en local.
FORBIDDEN = [
    re.compile(r'(?i)(password|passwd|secret|token|apikey|api_key|private_key|access_token|refresh_token)\s*[:=]\s*[^\s,;]+'),
    re.compile(r'(?i)bearer\s+[A-Za-z0-9\-._~+/]+=*'),
    re.compile(r'\bsk-[A-Za-z0-9]{20,}\b'),
    re.compile(r'\bghp_[A-Za-z0-9]{20,}\b'),
    re.compile(r'\beyJ[A-Za-z0-9_\-\.]+\.[A-Za-z0-9_\-\.]+\.[A-Za-z0-9_\-\.]+\b'),
    re.compile(r'(?i)(ssh-rsa|ssh-ed25519)\s+[A-Za-z0-9+/]{20,}'),
]


class SQLiteMemoryAdapter:
    """Memoria de ARIA en SQLite: 5 capas + FTS5. Hilo seguro."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = Path(db_path)
        self._lock = threading.RLock()
        self._db: Optional[sqlite3.Connection] = None

    @property
    def db(self) -> sqlite3.Connection:
        """Conexion perezosa: con la memoria apagada no se toca el disco."""
        if self._db is None:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self._db = conn
            try:
                self._pragma()
                self._init()
            except Exception:
                try:
                    self._db.close()
                except Exception:
                    pass
                self._db = None
                raise
        return self._db

    def _pragma(self) -> None:
        """Ajustes de duracion: WAL + synchronous NORMAL.

        Sigue siendo crash-safe (WAL), pero cada escritura no fuerza un fsync.
        En una app de escritorio esto baja de ~10 ms a ~1 ms por guardar.
        """
        try:
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=NORMAL")
            self.db.execute("PRAGMA temp_store=MEMORY")
        except Exception:
            pass

    # -- esquema --------------------------------------------------------------
    def _init(self) -> None:
        cur = self.db.cursor()
        cur.execute(
            """CREATE TABLE IF NOT EXISTS reglas(
                   id INTEGER PRIMARY KEY,
                   texto TEXT NOT NULL,
                   fuente TEXT,
                   confianza TEXT CHECK(confianza IN ('usuario','sistema','web')) DEFAULT 'usuario',
                   created_at REAL NOT NULL)"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS hechos(
                   id INTEGER PRIMARY KEY,
                   texto TEXT NOT NULL,
                   fuente TEXT,
                   confianza TEXT CHECK(confianza IN ('usuario','sistema','web')) DEFAULT 'sistema',
                   created_at REAL NOT NULL)"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS experiencias(
                   id INTEGER PRIMARY KEY,
                   texto TEXT NOT NULL,
                   fuente TEXT,
                   confianza TEXT CHECK(confianza IN ('usuario','sistema','web')) DEFAULT 'sistema',
                   created_at REAL NOT NULL)"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS observaciones(
                   id INTEGER PRIMARY KEY,
                   texto TEXT NOT NULL,
                   fuente TEXT,
                   confianza TEXT CHECK(confianza IN ('usuario','sistema','web')) DEFAULT 'sistema',
                   evidencia INTEGER DEFAULT 1,
                   consolidado INTEGER DEFAULT 0,
                   created_at REAL NOT NULL,
                   updated_at REAL)"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS modelos(
                   id INTEGER PRIMARY KEY,
                   texto TEXT NOT NULL,
                   fuente TEXT,
                   confianza TEXT CHECK(confianza IN ('usuario','sistema','web')) DEFAULT 'sistema',
                   evidencia INTEGER DEFAULT 1,
                   created_at REAL NOT NULL)"""
        )
        # Columnas nuevas en bases ya creadas.
        self._ensure_column(cur, "observaciones", "consolidado", "INTEGER DEFAULT 0")
        self._ensure_column(cur, "modelos", "evidencia", "INTEGER DEFAULT 1")
        # Mapa capa -> id del indice. Cada capa reinicia su id, asi que el
        # FTS necesita un namespace propio: fts_id unico por documento.
        cur.execute(
            """CREATE TABLE IF NOT EXISTS mem_map(
                   fts_id INTEGER PRIMARY KEY AUTOINCREMENT,
                   capa TEXT NOT NULL,
                   ref_id INTEGER NOT NULL,
                   created_at REAL NOT NULL)"""
        )
        cur.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS mem_fts USING fts5(texto, tokenize='unicode61')"
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_obs_evid ON observaciones(evidencia DESC)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_obs_cons ON observaciones(consolidado)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_map_capa ON mem_map(capa, ref_id)")
        # El indice de texto hace que la deduplicacion de observaciones no
        # tenga que recorrer la tabla entera.
        self._ensure_index(cur, "observaciones", "idx_obs_texto", "texto")
        # Indice de texto en el resto de capas: la importacion comprueba si
        # una entrada ya existe (reimportar el mismo archivo no duplica).
        for capa in LAYERS:
            self._ensure_index(cur, capa, f"idx_{capa}_texto", "texto")
        self.db.commit()
        self._rebuild_index()

    @staticmethod
    def _ensure_index(cur: sqlite3.Cursor, table: str, name: str, column: str) -> None:
        try:
            cur.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table}({column})")
        except Exception:
            pass

    def _rebuild_index(self) -> None:
        """Reconstruye el indice si el mapa no cuadra con el FTS.

        Necesario cuando la base ya existia sin el namespace propio: los
        rowids antiguos colisionaban entre capas y el FTS perdia documentos.
        """
        try:
            cur = self.db.cursor()
            cur.execute("SELECT COUNT(*) FROM mem_map")
            mapeados = int(cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM mem_fts")
            indexados = int(cur.fetchone()[0])
            cur.execute(
                "SELECT COUNT(*) FROM (SELECT DISTINCT capa, ref_id FROM mem_map)"
            )
            unicos = int(cur.fetchone()[0])
            if mapeados == indexados == unicos and mapeados > 0:
                return
            cur.execute("DELETE FROM mem_fts")
            cur.execute("DELETE FROM mem_map")
            for capa in LAYERS:
                try:
                    cur.execute(f"SELECT id, texto FROM {capa}")
                except Exception:
                    continue
                for r in cur.fetchall():
                    self._index_row(cur, capa, int(r["id"]), r["texto"])
            self.db.commit()
        except Exception:
            pass

    @staticmethod
    def _index_row(cur: sqlite3.Cursor, capa: str, ref_id: int, texto: str) -> Optional[int]:
        """ mete un documento en el indice con un rowid propio."""
        try:
            cur.execute(
                "INSERT INTO mem_map(capa, ref_id, created_at) VALUES(?,?,?)",
                (capa, int(ref_id), time.time()),
            )
            fts_id = int(cur.lastrowid)
            cur.execute("INSERT INTO mem_fts(rowid, texto) VALUES(?,?)", (fts_id, texto))
            return fts_id
        except Exception:
            return None

    @staticmethod
    def _ensure_column(cur: sqlite3.Cursor, table: str, column: str, ddl: str) -> None:
        try:
            cur.execute(f"PRAGMA table_info({table})")
            cols = {r[1] for r in cur.fetchall()}
            if column not in cols:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
        except Exception:
            pass

    # -- interruptor -----------------------------------------------------------
    def _enabled(self) -> bool:
        if _enabled_override is not None:
            return bool(_enabled_override)
        return os.environ.get("ARIA_MEMORY_SQLITE", "false").strip().lower() in (
            "1", "true", "yes", "on",
        )

    # -- saneado --------------------------------------------------------------
    def _sanitize(self, texto: str) -> Optional[str]:
        """None si el texto parece llevar una credencial o esta vacio."""
        if texto is None:
            return None
        t = str(texto).strip()
        if not t:
            return None
        for patron in FORBIDDEN:
            if patron.search(t):
                return None
        if len(t) > 4096:
            t = t[:4096]
        return t

    # -- retain ---------------------------------------------------------------
    def _insert_row(
        self,
        cur: sqlite3.Cursor,
        tipo: str,
        t: str,
        fuente: str,
        confianza: str,
        now: float,
    ) -> tuple:
        """Inserta una fila ya saneada. Devuelve (id, es_nueva).

        En 'observaciones' el texto repetido no crea una fila nueva: sube la
        evidencia de la que ya habia (y no se reindexa, para no duplicar el
        documento en el FTS).
        """
        if tipo == "observaciones":
            cur.execute(
                "SELECT id FROM observaciones WHERE texto = ? LIMIT 1", (t,)
            )
            row = cur.fetchone()
            if row is not None:
                cur.execute(
                    "UPDATE observaciones SET evidencia = evidencia + 1, updated_at = ?"
                    " WHERE id = ?",
                    (now, int(row["id"])),
                )
                return int(row["id"]), False
            cur.execute(
                "INSERT INTO observaciones"
                "(texto, fuente, confianza, evidencia, consolidado, created_at, updated_at)"
                " VALUES(?,?,?,?,0,?,?)",
                (t, fuente, confianza, 1, now, now),
            )
            return int(cur.lastrowid), True
        if tipo == "modelos":
            cur.execute(
                "INSERT INTO modelos(texto, fuente, confianza, evidencia, created_at)"
                " VALUES(?,?,?,?,?)",
                (t, fuente, confianza, 1, now),
            )
            return int(cur.lastrowid), True
        cur.execute(
            f"INSERT INTO {tipo}(texto, fuente, confianza, created_at) VALUES(?,?,?,?)",
            (t, fuente, confianza, now),
        )
        return int(cur.lastrowid), True

    def retain(
        self,
        texto: str,
        tipo: str = "observaciones",
        fuente: str = "sistema",
        confianza: str = "sistema",
    ) -> Optional[int]:
        """Guarda en la capa indicada. Devuelve el id, o None si no se guardo."""
        if not self._enabled():
            return None
        t = self._sanitize(texto)
        if t is None:
            return None
        if tipo not in LAYERS:
            tipo = "observaciones"
        if confianza not in CONFIANZAS:
            confianza = LAYERS[tipo]

        now = time.time()
        with self._lock:
            cur = self.db.cursor()
            try:
                oid, nuevo = self._insert_row(cur, tipo, t, fuente, confianza, now)
                # Todas las capas van al indice: la ventana Memoria tiene que
                # poder buscar tambien en las reglas.
                if nuevo:
                    self._index_row(cur, tipo, oid, t)
                self.db.commit()
                return oid
            except Exception:
                try:
                    self.db.rollback()
                except Exception:
                    pass
                return None

    def retain_many(self, entradas: List[Dict[str, Any]]) -> Dict[str, int]:
        """Guarda muchas entradas en una sola transaccion.

        Pensado para importar: cada entrada es un dict con 'texto' y, opcional,
        'capa'/'tipo', 'fuente' y 'confianza'. Devuelve
        {'importadas': n, 'omitidas': m, 'duplicadas': d}: lo que no se guardo
        (vacio o con credenciales) va a 'omitidas' y lo que ya estaba en esa
        capa, a 'duplicadas' (reimportar el mismo archivo no duplica nada).
        """
        resultado = {"importadas": 0, "omitidas": 0, "duplicadas": 0}
        if not self._enabled():
            return resultado
        now = time.time()
        with self._lock:
            cur = self.db.cursor()
            try:
                for entrada in entradas or []:
                    if not isinstance(entrada, dict):
                        resultado["omitidas"] += 1
                        continue
                    texto = entrada.get("texto")
                    if texto is None:
                        texto = entrada.get("text")
                    t = self._sanitize(texto)
                    if t is None:
                        resultado["omitidas"] += 1
                        continue
                    tipo = entrada.get("capa") or entrada.get("tipo") or "hechos"
                    if tipo not in LAYERS:
                        tipo = "hechos"
                    fuente = str(entrada.get("fuente") or "importado")
                    confianza = str(entrada.get("confianza") or LAYERS[tipo])
                    if confianza not in CONFIANZAS:
                        confianza = LAYERS[tipo]
                    cur.execute(
                        f"SELECT id FROM {tipo} WHERE texto = ? LIMIT 1", (t,)
                    )
                    if cur.fetchone() is not None:
                        resultado["duplicadas"] += 1
                        continue
                    oid, nuevo = self._insert_row(cur, tipo, t, fuente, confianza, now)
                    if nuevo:
                        self._index_row(cur, tipo, oid, t)
                    resultado["importadas"] += 1
                self.db.commit()
                return resultado
            except Exception:
                try:
                    self.db.rollback()
                except Exception:
                    pass
                return {"importadas": 0, "omitidas": resultado["omitidas"],
                        "duplicadas": resultado["duplicadas"]}

    # -- recall ---------------------------------------------------------------
    @staticmethod
    def _fts_query(consulta: str) -> str:
        """Convierte la consulta en una expresion FTS5 segura.

        Cada palabra va entre comillas dobles: los signos raros (? ! - ( ) ...)
        dejan de ser sintaxis y pasan a ser texto buscado. Se unen con OR
        para que una pregunta no exija que esten TODAS las palabras: el
        ranking BM25 deja arriba lo que de verdad encaja.
        """
        limpio = str(consulta or "").replace('"', " ")
        partes = [p for p in limpio.split() if p]
        if not partes:
            return ""
        return " OR ".join(f'"{p}"' for p in partes)

    def recall(self, consulta: str, k: int = 5) -> List[Dict[str, Any]]:
        """Busca por texto. BM25 de FTS5, ordenado por relevancia."""
        if not self._enabled():
            return []
        q = self._fts_query(consulta)
        if not q:
            return []
        with self._lock:
            cur = self.db.cursor()
            try:
                # Sin alias: este build de SQLite no acepta "f MATCH ?" con
                # la tabla renombrada. El subselect trae el bm25 ya calculado.
                cur.execute(
                    "SELECT s.rowid AS rowid, s.texto AS texto, s.bm25 AS bm25,"
                    " m.capa AS capa, m.ref_id AS ref_id"
                    " FROM (SELECT rowid, texto, bm25(mem_fts) AS bm25 FROM mem_fts"
                    "       WHERE mem_fts MATCH ? ORDER BY bm25 LIMIT ?) AS s"
                    " JOIN mem_map m ON m.fts_id = s.rowid",
                    (q, max(1, int(k))),
                )
                return [
                    {
                        "rowid": int(r["rowid"]),
                        "texto": r["texto"],
                        "bm25": r["bm25"],
                        "capa": r["capa"],
                        "id": int(r["ref_id"]),
                        "ref_id": int(r["ref_id"]),
                    }
                    for r in cur.fetchall()
                ]
            except Exception:
                return []

    # -- reflect --------------------------------------------------------------
    def reflect_basico(self) -> int:
        """Consolida sin LLM: las observaciones repetidas se vuelven modelos.

        Una observacion con evidencia >= EVIDENCIA_MINIMA genera un modelo
        (resumen de lo repetido) y queda marcada como consolidada.
        Devuelve cuantas observaciones se promovieron.
        """
        if not self._enabled():
            return 0
        now = time.time()
        with self._lock:
            cur = self.db.cursor()
            try:
                cur.execute(
                    "SELECT id, texto, evidencia FROM observaciones"
                    " WHERE evidencia >= ? AND consolidado = 0 ORDER BY evidencia DESC LIMIT 50",
                    (EVIDENCIA_MINIMA,),
                )
                rows = cur.fetchall()
                promovidas = 0
                for r in rows:
                    texto = r["texto"]
                    resumen = f"Patron observado {int(r['evidencia'])} veces: {texto}"
                    cur.execute(
                        "INSERT INTO modelos(texto, fuente, confianza, evidencia, created_at)"
                        " VALUES(?,?,?,?,?)",
                        (resumen, "sistema", "sistema", int(r["evidencia"]), now),
                    )
                    self._index_row(cur, "modelos", int(cur.lastrowid), resumen)
                    cur.execute(
                        "UPDATE observaciones SET consolidado = 1, updated_at = ? WHERE id = ?",
                        (now, int(r["id"])),
                    )
                    promovidas += 1
                self.db.commit()
                return promovidas
            except Exception:
                try:
                    self.db.rollback()
                except Exception:
                    pass
                return 0

    # -- lectura para la interfaz --------------------------------------------
    def listar(self, capa: str = "", limite: int = 50) -> List[Dict[str, Any]]:
        """Lista entradas de una capa (o de todas), de la mas nueva a la vieja."""
        if not self._enabled():
            return []
        capas = [capa] if capa in LAYERS else list(LAYERS.keys())
        out: List[Dict[str, Any]] = []
        with self._lock:
            cur = self.db.cursor()
            for c in capas:
                try:
                    if c == "observaciones":
                        cur.execute(
                            "SELECT id, texto, fuente, confianza, evidencia, created_at"
                            " FROM observaciones ORDER BY created_at DESC LIMIT ?",
                            (limite,),
                        )
                    elif c == "modelos":
                        cur.execute(
                            "SELECT id, texto, fuente, confianza, evidencia, created_at"
                            " FROM modelos ORDER BY created_at DESC LIMIT ?",
                            (limite,),
                        )
                    else:
                        cur.execute(
                            f"SELECT id, texto, fuente, confianza, created_at FROM {c}"
                            " ORDER BY created_at DESC LIMIT ?",
                            (limite,),
                        )
                    for r in cur.fetchall():
                        fila = {"capa": c, "id": int(r["id"]), "texto": r["texto"],
                                "fuente": r["fuente"], "confianza": r["confianza"],
                                "created_at": r["created_at"]}
                        if "evidencia" in r.keys():
                            fila["evidencia"] = int(r["evidencia"])
                        out.append(fila)
                except Exception:
                    continue
        out.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        return out[:limite]

    def borrar(self, capa: str, id_: int) -> bool:
        """Borra una entrada concreta de una capa (y su ficha de indice)."""
        if capa not in LAYERS:
            return False
        with self._lock:
            cur = self.db.cursor()
            try:
                cur.execute(
                    "SELECT fts_id FROM mem_map WHERE capa = ? AND ref_id = ?",
                    (capa, int(id_)),
                )
                filas = cur.fetchall()
                for f in filas:
                    try:
                        cur.execute("DELETE FROM mem_fts WHERE rowid = ?", (int(f["fts_id"]),))
                    except Exception:
                        pass
                cur.execute("DELETE FROM mem_map WHERE capa = ? AND ref_id = ?", (capa, int(id_)))
                cur.execute(f"DELETE FROM {capa} WHERE id = ?", (int(id_),))
                n = cur.rowcount
                self.db.commit()
                return n > 0
            except Exception:
                try:
                    self.db.rollback()
                except Exception:
                    pass
                return False

    def exportar(self) -> List[Dict[str, Any]]:
        """Todo el contenido, para exportarlo a JSON."""
        return self.listar(limite=100000)

    def conteo(self) -> Dict[str, int]:
        """Cuantas entradas hay en cada capa."""
        out: Dict[str, int] = {c: 0 for c in LAYERS}
        if not self._enabled():
            return out
        with self._lock:
            cur = self.db.cursor()
            for c in LAYERS:
                try:
                    cur.execute(f"SELECT COUNT(*) FROM {c}")
                    out[c] = int(cur.fetchone()[0])
                except Exception:
                    out[c] = 0
        return out


def set_enabled(activo: Optional[bool]) -> None:
    """Activa o desactiva la memoria en caliente, sin reiniciar ARIA.

    None devuelve el control a la variable de entorno ARIA_MEMORY_SQLITE.
    """
    global _enabled_override
    _enabled_override = None if activo is None else bool(activo)


def is_enabled() -> bool:
    """Si la memoria esta activa ahora mismo (override o variable de entorno)."""
    if _enabled_override is not None:
        return bool(_enabled_override)
    return os.environ.get("ARIA_MEMORY_SQLITE", "false").strip().lower() in (
        "1", "true", "yes", "on",
    )


_adapter: Optional[SQLiteMemoryAdapter] = None
_adapter_lock = threading.Lock()


def get_adapter() -> SQLiteMemoryAdapter:
    """Instancia unica del adaptador."""
    global _adapter
    if _adapter is None:
        with _adapter_lock:
            if _adapter is None:
                _adapter = SQLiteMemoryAdapter()
    return _adapter
