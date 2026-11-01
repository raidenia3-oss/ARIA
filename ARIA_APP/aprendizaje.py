# -*- coding: utf-8 -*-
"""ARIA - Arnes de aprendizaje (de LearnHarness, local, Regla v2).

ARIA ensena a Daniel de verdad, no le da la respuesta masticada. Dos procesos:

  ENSENAR (bucle socratico): predecir -> explicar -> verificar. ARIA hace una
    pregunta de PREDICCION (que crees que pasa?), luego EXPLICA conectando con lo
    que ya sabe, y VERIFICA con una pregunta de chequeo. Cada concepto aprendido se
    guarda como proposicion en el grafo de conocimiento.

  PRACTICAR (recall adaptativo): obliga a RECORDAR, con PISTAS que se ajustan al
    dominio: si dominas poco, mas pista; si dominas, menos. Mide aciertos/intentos.

  SONDEAR: detecta lagunas (proposiciones no vistas o con bajo dominio).

El contenido (preguntas, explicaciones) lo genera el CEREBRO de ARIA, que entra como
un callback responder(texto)->texto. El arnes aporta la ESTRUCTURA y el seguimiento
del dominio (eso es lo testeable y reutilizable). Sin responder, igual rastrea dominio.

100% local: SQLite para el dominio + grafo de conocimiento. Sin servidores ni red.
"""
import os
import sqlite3
import time

_DIR = os.path.dirname(os.path.abspath(__file__))
_DB = os.path.join(_DIR, "data", "aprendizaje.db")

# niveles de pista para el recall (0 = sin pista, 3 = casi la respuesta)
PISTAS = {
    0: "Reconstruyelo de memoria, sin pista.",
    1: "Pista leve: recuerda la idea general.",
    2: "Pista media: te doy la primera parte / una palabra clave.",
    3: "Pista fuerte: casi la respuesta, solo completa el hueco.",
}


class Arnes:
    def __init__(self, responder=None, grafo=None, db_path=None):
        self.responder = responder          # callable(texto)->texto (cerebro de ARIA)
        self._grafo = grafo
        self.db_path = db_path or _DB
        self._db = None

    # ---------------------------------------------------------- base
    def _conn(self):
        if self._db is None:
            os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
            self._db = sqlite3.connect(self.db_path, check_same_thread=False)
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS dominio("
                "proposicion TEXT PRIMARY KEY, tema TEXT, aciertos INTEGER DEFAULT 0, "
                "intentos INTEGER DEFAULT 0, ultima REAL)")
            self._db.commit()
        return self._db

    def _grafo_mem(self):
        if self._grafo is None:
            try:
                import conocimiento
                self._grafo = conocimiento.grafo()
            except Exception:
                self._grafo = None
        return self._grafo

    def _preguntar(self, prompt):
        """Usa el cerebro si hay; si no, devuelve el prompt como plantilla."""
        if not callable(self.responder):
            return None
        try:
            r = self.responder(prompt)
            if isinstance(r, dict):
                r = r.get("response") or r.get("text") or str(r)
            return str(r)
        except Exception as exc:
            return "(cerebro no respondio: %s)" % exc

    # ---------------------------------------------------------- ENSENAR (socratico)
    def ensenar(self, concepto, tema=""):
        """Bucle predecir -> explicar -> verificar. Devuelve las 3 fases y guarda el
        concepto como proposicion en el grafo."""
        concepto = (concepto or "").strip()
        if not concepto:
            return {"error": "concepto vacio"}
        p_predecir = ("Antes de explicarte, dime: que CREES que significa o como "
                      "funciona '%s'? (una prediccion, aunque no estes seguro)" % concepto)
        p_explicar = ("Explica '%s' de forma simple, conectandolo con algo que la "
                      "persona ya conoce, en pasos que se sientan obviamente ciertos." % concepto)
        p_verificar = ("Hazme UNA pregunta corta para verificar si entendi '%s'." % concepto)

        fases = {
            "predecir": {"prompt": p_predecir, "respuesta_ia": self._preguntar(p_predecir)},
            "explicar": {"prompt": p_explicar, "respuesta_ia": self._preguntar(p_explicar)},
            "verificar": {"prompt": p_verificar, "respuesta_ia": self._preguntar(p_verificar)},
        }
        # registrar en el grafo + crear fila de dominio
        g = self._grafo_mem()
        if g is not None:
            try:
                g.aprender(concepto, tema=tema, fuente="ensenanza")
            except Exception:
                pass
        self._asegurar_dominio(concepto, tema)
        return {"ok": True, "concepto": concepto, "fases": fases}

    # ---------------------------------------------------------- PRACTICAR (recall adaptativo)
    def _asegurar_dominio(self, proposicion, tema=""):
        db = self._conn()
        db.execute("INSERT OR IGNORE INTO dominio(proposicion,tema,ultima) VALUES(?,?,?)",
                   (proposicion, tema, time.time()))
        db.commit()

    def dominio(self, proposicion):
        """Ratio de dominio 0..1 (aciertos/intentos); 0 si nunca se practico."""
        db = self._conn()
        f = db.execute("SELECT aciertos,intentos FROM dominio WHERE proposicion=?",
                       (proposicion,)).fetchone()
        if not f or f[1] == 0:
            return 0.0
        return round(f[0] / f[1], 2)

    def nivel_pista(self, proposicion):
        """Pista adaptativa: menos dominio -> mas pista (nivel 0..3)."""
        d = self.dominio(proposicion)
        if d >= 0.8:
            return 0
        if d >= 0.5:
            return 1
        if d >= 0.25:
            return 2
        return 3

    def practicar(self, proposicion, tema=""):
        """Plantea un recall con la pista ajustada al dominio actual."""
        self._asegurar_dominio(proposicion, tema)
        nivel = self.nivel_pista(proposicion)
        prompt_recall = ("Sin mirar: explica o recuerda '%s'. %s"
                         % (proposicion, PISTAS[nivel]))
        ia = self._preguntar(prompt_recall) if self.responder else None
        return {"proposicion": proposicion, "nivel_pista": nivel,
                "pista": PISTAS[nivel], "prompt": prompt_recall, "ayuda_ia": ia}

    def registrar_resultado(self, proposicion, acierto, tema=""):
        """Guarda si el usuario acerto el recall. Ajusta el dominio."""
        self._asegurar_dominio(proposicion, tema)
        db = self._conn()
        db.execute(
            "UPDATE dominio SET aciertos=aciertos+?, intentos=intentos+1, ultima=? "
            "WHERE proposicion=?", (1 if acierto else 0, time.time(), proposicion))
        db.commit()
        return {"ok": True, "proposicion": proposicion, "dominio": self.dominio(proposicion)}

    # ---------------------------------------------------------- SONDEAR (lagunas)
    def lagunas(self, tema=None, umbral=0.5):
        """Proposiciones con dominio por debajo del umbral (lo que falta reforzar)."""
        db = self._conn()
        if tema:
            filas = db.execute("SELECT proposicion,aciertos,intentos FROM dominio WHERE tema=?",
                               (tema,)).fetchall()
        else:
            filas = db.execute("SELECT proposicion,aciertos,intentos FROM dominio").fetchall()
        out = []
        for prop, ac, it in filas:
            d = (ac / it) if it else 0.0
            if d < umbral:
                out.append({"proposicion": prop, "dominio": round(d, 2), "intentos": it})
        out.sort(key=lambda x: x["dominio"])
        return out

    def sondear(self, tema, n=3):
        """Pide al cerebro n preguntas de opcion multiple para detectar lagunas.
        Devuelve el prompt estructurado (el cerebro genera el contenido)."""
        prompt = ("Hazme %d preguntas de opcion multiple (a/b/c) sobre '%s', de facil "
                  "a dificil, para detectar que NO entiendo. Solo las preguntas." % (n, tema))
        return {"tema": tema, "n": n, "prompt": prompt,
                "preguntas_ia": self._preguntar(prompt)}

    def resumen(self, tema=None):
        db = self._conn()
        if tema:
            filas = db.execute("SELECT aciertos,intentos FROM dominio WHERE tema=?", (tema,)).fetchall()
        else:
            filas = db.execute("SELECT aciertos,intentos FROM dominio").fetchall()
        total = len(filas)
        dominadas = sum(1 for ac, it in filas if it and ac / it >= 0.8)
        return {"conceptos": total, "dominados": dominadas,
                "en_proceso": total - dominadas}


def arnes(responder=None):
    return Arnes(responder=responder)
