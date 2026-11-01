# -*- coding: utf-8 -*-
"""ARIA - Grafo de conocimiento persistente (idea de LearnHarness, local, Regla v2).

ARIA no solo guarda frases: construye un MODELO de lo que sabe/han hablado, como
proposiciones (nodos) conectadas por relaciones (aristas), con cadenas de razonamiento.
Asi puede conectar ideas entre sesiones y 'ver' la profundidad de un tema.

  - nodo  = una proposicion ("un Transformer usa auto-atencion")
  - arista = relacion entre dos ("auto-atencion" --parte_de--> "Transformer")
  - cadena = recorrido de razonamiento (BFS) desde una idea

EXPLORAR PARA MEJORAR: si la memoria semantica esta disponible, al aprender una
proposicion nueva el grafo busca las mas parecidas por SIGNIFICADO y las conecta
solo (auto_conectar), de modo que el grafo crece y se enriquece con el tiempo.

100% local: SQLite en proceso, sin servidores ni red (la red solo si un skill la usa).
"""
import os
import sqlite3
import time

_DIR = os.path.dirname(os.path.abspath(__file__))
_DB = os.path.join(_DIR, "data", "conocimiento.db")


class Grafo:
    def __init__(self, db_path=None, semantica=None):
        self.db_path = db_path or _DB
        self._db = None
        # memoria semantica opcional (para auto-conectar por significado)
        self._sem = semantica
        self._sem_intentado = False

    # ---------------------------------------------------------- base
    def _conn(self):
        if self._db is None:
            os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
            self._db = sqlite3.connect(self.db_path, check_same_thread=False)
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS nodos("
                "id INTEGER PRIMARY KEY, texto TEXT UNIQUE, tema TEXT, "
                "fuente TEXT, ts REAL)")
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS aristas("
                "id INTEGER PRIMARY KEY, origen INTEGER, destino INTEGER, "
                "relacion TEXT, peso REAL, ts REAL, "
                "UNIQUE(origen, destino, relacion))")
            self._db.commit()
        return self._db

    def _sem_mem(self):
        """Carga perezosa de la memoria semantica (si esta instalada)."""
        if self._sem is not None or self._sem_intentado:
            return self._sem
        self._sem_intentado = True
        try:
            import memory_semantic as ms
            if ms.disponible():
                self._sem = ms.MemoriaSemantica(
                    os.path.join(_DIR, "data", "conocimiento_sem.db"))
        except Exception:
            self._sem = None
        return self._sem

    # ---------------------------------------------------------- escribir
    def aprender(self, texto, tema="", fuente="", auto=True):
        """Agrega una proposicion (dedupe por texto exacto). Devuelve su id.
        Si auto=True y hay memoria semantica, la conecta con las mas parecidas."""
        texto = (texto or "").strip()
        if not texto:
            return None
        db = self._conn()
        cur = db.execute("SELECT id FROM nodos WHERE texto=?", (texto,))
        fila = cur.fetchone()
        if fila:
            nid = fila[0]
        else:
            cur = db.execute(
                "INSERT INTO nodos(texto,tema,fuente,ts) VALUES(?,?,?,?)",
                (texto, tema, fuente, time.time()))
            nid = cur.lastrowid
            db.commit()
            sem = self._sem_mem()
            if sem is not None:
                try:
                    sem.recordar(texto, meta=str(nid))
                except Exception:
                    pass
        if auto:
            self.auto_conectar(nid)
        return nid

    def conectar(self, id_a, id_b, relacion="relacionado", peso=1.0):
        """Crea una arista dirigida id_a --relacion--> id_b."""
        if id_a is None or id_b is None or id_a == id_b:
            return False
        db = self._conn()
        try:
            db.execute(
                "INSERT OR IGNORE INTO aristas(origen,destino,relacion,peso,ts) "
                "VALUES(?,?,?,?,?)", (id_a, id_b, relacion, peso, time.time()))
            db.commit()
            return True
        except Exception:
            return False

    def auto_conectar(self, nid, k=3, umbral=0.6):
        """EXPLORAR PARA MEJORAR: conecta este nodo con los mas parecidos por
        significado (memoria semantica). umbral = distancia maxima permitida."""
        sem = self._sem_mem()
        if sem is None:
            return 0
        db = self._conn()
        texto = db.execute("SELECT texto FROM nodos WHERE id=?", (nid,)).fetchone()
        if not texto:
            return 0
        n = 0
        try:
            for r in sem.buscar(texto[0], k=k + 1):
                otro = r.get("meta")
                if not (otro or "").isdigit():
                    continue
                oid = int(otro)
                if oid != nid and r.get("dist", 1.0) <= umbral:
                    if self.conectar(nid, oid, "parecido", 1.0 - r["dist"]):
                        self.conectar(oid, nid, "parecido", 1.0 - r["dist"])
                        n += 1
        except Exception:
            pass
        return n

    # ---------------------------------------------------------- leer
    def nodo(self, texto):
        db = self._conn()
        f = db.execute("SELECT id,texto,tema FROM nodos WHERE texto=?", (texto,)).fetchone()
        return {"id": f[0], "texto": f[1], "tema": f[2]} if f else None

    def relacionados(self, nid, limite=10):
        """Vecinos directos de un nodo (en ambos sentidos)."""
        db = self._conn()
        filas = db.execute(
            "SELECT n.id,n.texto,a.relacion,a.peso FROM aristas a "
            "JOIN nodos n ON n.id=a.destino WHERE a.origen=? "
            "ORDER BY a.peso DESC LIMIT ?", (nid, limite)).fetchall()
        return [{"id": i, "texto": t, "relacion": r, "peso": round(p, 2)}
                for i, t, r, p in filas]

    def cadena(self, nid, profundidad=2, max_nodos=20):
        """Recorrido de razonamiento (BFS) desde un nodo hasta cierta profundidad."""
        db = self._conn()
        visto = {nid}
        nivel = [nid]
        camino = []
        for _ in range(profundidad):
            siguiente = []
            for actual in nivel:
                vecinos = db.execute(
                    "SELECT destino,relacion FROM aristas WHERE origen=?", (actual,)).fetchall()
                for dest, rel in vecinos:
                    if dest not in visto:
                        visto.add(dest)
                        t = db.execute("SELECT texto FROM nodos WHERE id=?", (dest,)).fetchone()
                        if t:
                            camino.append({"de": actual, "a": dest, "relacion": rel, "texto": t[0]})
                            siguiente.append(dest)
                    if len(visto) >= max_nodos:
                        return camino
            nivel = siguiente
            if not nivel:
                break
        return camino

    def buscar(self, consulta, k=5):
        """Busca proposiciones: por significado si hay memoria semantica, si no por texto."""
        sem = self._sem_mem()
        if sem is not None:
            res = sem.buscar(consulta, k=k)
            if res:
                return [{"texto": r["texto"], "dist": r.get("dist")} for r in res]
        db = self._conn()
        filas = db.execute(
            "SELECT texto FROM nodos WHERE texto LIKE ? LIMIT ?",
            ("%" + consulta + "%", k)).fetchall()
        return [{"texto": t[0]} for t in filas]

    def exportar_dot(self, tema=None):
        """Exporta el grafo a DOT (Graphviz) para visualizar. Filtra por tema si se da."""
        db = self._conn()
        if tema:
            nodos = db.execute("SELECT id,texto FROM nodos WHERE tema=?", (tema,)).fetchall()
        else:
            nodos = db.execute("SELECT id,texto FROM nodos").fetchall()
        ids = {i for i, _ in nodos}
        lineas = ["digraph conocimiento {", '  rankdir=LR; node [shape=box, style=rounded];']
        for i, t in nodos:
            etq = t.replace('"', "'")[:40]
            lineas.append('  n%d [label="%s"];' % (i, etq))
        for o, d, r in db.execute("SELECT origen,destino,relacion FROM aristas").fetchall():
            if o in ids and d in ids:
                lineas.append('  n%d -> n%d [label="%s"];' % (o, d, r))
        lineas.append("}")
        return "\n".join(lineas)

    def stats(self):
        db = self._conn()
        n = db.execute("SELECT COUNT(*) FROM nodos").fetchone()[0]
        a = db.execute("SELECT COUNT(*) FROM aristas").fetchone()[0]
        temas = [t[0] for t in db.execute(
            "SELECT DISTINCT tema FROM nodos WHERE tema!=''").fetchall()]
        return {"nodos": n, "aristas": a, "temas": temas}


# fabrica
def grafo(db_path=None):
    return Grafo(db_path)
