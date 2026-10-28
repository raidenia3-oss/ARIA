# -*- coding: utf-8 -*-
"""ARIA - Autoaprendizaje local (v2). Sin red, sin servidores, sin puertos.

Capas:
  1) Hechos enseñados por Daniel        -> SQLite 'aprendido'.
  2) Skills dinamicas APROBADAS         -> skills/*.py (match/run), hot-reload.
  3) Captura de huecos + borrador        -> skills/_pending/<slug>.py con match() ya
     cableado a las palabras clave (run() queda como TODO). FAIL-CLOSED: nada de
     _pending se ejecuta jamas hasta que Daniel lo apruebe.

Comandos por chat (los entiende teach()):
  - "skills"                      -> lista activas y borradores pendientes
  - "aprueba skill <slug>"        -> activa un borrador (lo mueve a skills/ y recarga)
  - "rechaza skill <slug>"        -> borra un borrador pendiente
  - "aprende: tema => respuesta"  -> enseña un hecho
"""
import os
import re
import sqlite3
import time
import unicodedata


def _norm(s):
    s = (s or "").strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9ñ ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _slug(s):
    s = _norm(s)[:40].strip().replace(" ", "_")
    return re.sub(r"[^a-z0-9_]+", "", s) or "skill"


_STOP = set("que como cual cuales donde cuando porque para por con una unos unas los las "
            "del de la el en es un y o a me te se mi tu su hazme dame dime quiero puedes "
            "cuanto cuanta cuantos cuantas".split())


def _keywords(msg, n=3):
    palabras = [w for w in _norm(msg).split() if len(w) > 3 and w not in _STOP]
    vistos, out = set(), []
    for w in palabras:
        if w not in vistos:
            vistos.add(w)
            out.append(w)
        if len(out) >= n:
            break
    return out


class Learner:
    def __init__(self, base_dir):
        self.base = base_dir
        self.data_dir = os.path.join(base_dir, "data")
        self.skills_dir = os.path.join(base_dir, "skills")
        self.pending_dir = os.path.join(self.skills_dir, "_pending")
        for d in (self.data_dir, self.skills_dir, self.pending_dir):
            try:
                os.makedirs(d, exist_ok=True)
            except Exception:
                pass
        self.db_path = os.path.join(self.data_dir, "aprendizaje.db")
        self._init_db()
        self._skills = []
        self.reload_skills()

    # ------------------------------------------------------------------ DB
    def _conn(self):
        c = sqlite3.connect(self.db_path)
        c.row_factory = sqlite3.Row
        return c

    def _init_db(self):
        try:
            c = self._conn()
            c.execute("CREATE TABLE IF NOT EXISTS aprendido("
                      "id INTEGER PRIMARY KEY, clave TEXT, respuesta TEXT, ts REAL)")
            c.execute("CREATE TABLE IF NOT EXISTS huecos("
                      "id INTEGER PRIMARY KEY, mensaje TEXT, clave TEXT, veces INTEGER, ts REAL)")
            c.commit()
            c.close()
        except Exception:
            pass

    # --------------------------------------------------------- ENTRADA UNICA
    def teach(self, msg):
        """Comandos de skills + enseñanza de hechos. Devuelve texto o None."""
        cmd = self._commands(msg)
        if cmd is not None:
            return cmd
        return self._learn_fact(msg)

    # ------------------------------------------------------------- COMANDOS
    def _commands(self, msg):
        low = _norm(msg)
        if low in ("skills", "mis skills", "lista de skills", "lista skills", "que skills tienes"):
            return self.list_skills()
        m = re.match(r"^(?:aprueba|aprobar|activa|activar)\s+skill\s+([a-z0-9_]+)$", low)
        if m:
            return self.approve_skill(m.group(1))
        m = re.match(r"^(?:rechaza|rechazar|borra|borrar|elimina|eliminar|descarta)\s+skill\s+([a-z0-9_]+)$", low)
        if m:
            return self.reject_skill(m.group(1))
        return None

    # -------------------------------------------------------------- ENSEÑAR
    _PATRONES = [
        r"^aprende\s*:?\s*(?P<k>.+?)\s*(?:=>|->|==>|:|es que|significa)\s*(?P<v>.+)$",
        r"^(?:recuerda|memoriza|anota|guarda)\s+que\s+(?P<k>.+?)\s+(?:es|son|significa|=)\s+(?P<v>.+)$",
        r"^cuando\s+(?:te\s+)?(?:pregunten|pregunte|diga|digan|pida)\s+(?P<k>.+?)\s*,?\s+(?:responde|di|contesta|responde con)\s+(?P<v>.+)$",
    ]

    def _learn_fact(self, msg):
        low = msg.strip()
        for pat in self._PATRONES:
            m = re.match(pat, low, flags=re.IGNORECASE | re.DOTALL)
            if m:
                clave = _norm(m.group("k"))
                resp = m.group("v").strip()
                if not clave or not resp:
                    return None
                try:
                    c = self._conn()
                    c.execute("INSERT INTO aprendido(clave,respuesta,ts) VALUES(?,?,?)",
                              (clave, resp, time.time()))
                    c.commit()
                    c.close()
                except Exception:
                    return None
                return "Aprendido, Daniel. La proxima que toque \"%s\" ya se que decir." % m.group("k").strip()
        return None

    # -------------------------------------------------------------- RECORDAR
    def recall(self, msg):
        q = _norm(msg)
        if not q:
            return None
        palabras = set(w for w in q.split() if len(w) > 2)
        try:
            c = self._conn()
            filas = c.execute("SELECT clave,respuesta FROM aprendido ORDER BY ts DESC").fetchall()
            c.close()
        except Exception:
            return None
        mejor, score = None, 0.0
        for f in filas:
            clave = f["clave"]
            if not clave:
                continue
            if clave in q or q in clave:
                return f["respuesta"]
            kw = set(w for w in clave.split() if len(w) > 2)
            if not kw:
                continue
            sol = len(palabras & kw) / float(len(kw))
            if sol > score:
                mejor, score = f["respuesta"], sol
        return mejor if score >= 0.6 else None

    # ----------------------------------------------------------------- SKILLS
    def reload_skills(self):
        self._skills = []
        import importlib.util
        try:
            archivos = [f for f in os.listdir(self.skills_dir)
                        if f.endswith(".py") and not f.startswith("_")]
        except Exception:
            archivos = []
        for nombre in sorted(archivos):
            ruta = os.path.join(self.skills_dir, nombre)
            try:
                spec = importlib.util.spec_from_file_location("aria_skill_" + nombre[:-3], ruta)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                if getattr(mod, "SKILL_ENABLED", False) and hasattr(mod, "match") and hasattr(mod, "run"):
                    self._skills.append((nombre[:-3], mod))
            except Exception:
                continue
        return [n for n, _ in self._skills]

    def try_skills(self, msg):
        for nombre, mod in self._skills:
            try:
                if mod.match(msg):
                    out = mod.run(msg)
                    if out:
                        return str(out)
            except Exception:
                continue
        return None

    def list_skills(self):
        activas = [n for n, _ in self._skills]
        try:
            pend = [f[:-3] for f in os.listdir(self.pending_dir) if f.endswith(".py")]
        except Exception:
            pend = []
        t = "Skills activas: " + (", ".join(activas) if activas else "ninguna") + "."
        if pend:
            t += " Borradores por aprobar: " + ", ".join(pend) + ". Usa 'aprueba skill <nombre>'."
        return t

    def approve_skill(self, slug):
        origen = os.path.join(self.pending_dir, slug + ".py")
        if not os.path.isfile(origen):
            return "No encontre el borrador '%s'. Mira 'skills' para ver los pendientes." % slug
        try:
            txt = open(origen, "r", encoding="utf-8").read()
            txt = txt.replace("SKILL_ENABLED = False", "SKILL_ENABLED = True")
            destino = os.path.join(self.skills_dir, slug + ".py")
            with open(destino, "w", encoding="utf-8") as fh:
                fh.write(txt)
            os.remove(origen)
        except Exception as exc:
            return "No pude aprobar '%s': %s" % (slug, exc)
        self.reload_skills()
        activa = slug in [n for n, _ in self._skills]
        if not activa:
            return ("Aprobe '%s', pero aun no hace nada: su run() es un TODO. "
                    "Complatalo (o pideme que lo implemente) y volvera a cargar." % slug)
        if "return \"\"  # TODO" in txt:
            return ("Aprobe y active '%s'. Ojo: su run() todavia es un TODO, "
                    "asi que no respondera hasta implementarlo." % slug)
        return "Listo, Daniel: skill '%s' aprobada y activa." % slug

    def reject_skill(self, slug):
        origen = os.path.join(self.pending_dir, slug + ".py")
        if not os.path.isfile(origen):
            return "No hay borrador '%s' que rechazar." % slug
        try:
            os.remove(origen)
        except Exception as exc:
            return "No pude borrar '%s': %s" % (slug, exc)
        return "Borrador '%s' descartado." % slug

    # ------------------------------------------------------------- HUECO/GAP
    def note_gap(self, msg):
        clave = _norm(msg)
        if not clave:
            return None
        veces = 1
        try:
            c = self._conn()
            fila = c.execute("SELECT id,veces FROM huecos WHERE clave=?", (clave,)).fetchone()
            if fila:
                veces = fila["veces"] + 1
                c.execute("UPDATE huecos SET veces=?,ts=? WHERE id=?", (veces, time.time(), fila["id"]))
            else:
                c.execute("INSERT INTO huecos(mensaje,clave,veces,ts) VALUES(?,?,?,?)",
                          (msg.strip(), clave, 1, time.time()))
            c.commit()
            c.close()
        except Exception:
            return None
        if veces == 2:
            slug = self._draft_skill(msg)
            if slug:
                return ("No supe resolver eso (van 2 veces). Prepare un borrador de skill "
                        "'%s' con el disparador ya puesto; revisalo y, si te sirve, "
                        "escribe 'aprueba skill %s'. — ARIA" % (slug, slug))
        return None

    def _draft_skill(self, msg):
        slug = _slug(msg)
        ruta = os.path.join(self.pending_dir, slug + ".py")
        if os.path.exists(ruta):
            return slug
        kws = _keywords(msg) or [slug]
        patron = "|".join(re.escape(k) for k in kws)
        plantilla = (
            '# -*- coding: utf-8 -*-\n'
            '# BORRADOR de skill autogenerado por ARIA (NO se ejecuta hasta aprobar).\n'
            '# Peticion original de Daniel: %r\n'
            '# match() ya esta cableado a las palabras clave detectadas.\n'
            '# Falta implementar run(). Para activar: "aprueba skill %s".\n\n'
            'SKILL_ENABLED = False\n\n'
            'import re\n\n'
            '_DISPARADOR = re.compile(r"(%s)", re.I)\n\n'
            'def match(msg):\n'
            '    return bool(_DISPARADOR.search(msg))\n\n'
            'def run(msg):\n'
            '    # TODO: implementar la respuesta (sin red ni servidores).\n'
            '    return ""  # TODO\n'
        ) % (msg.strip(), slug, patron)
        try:
            with open(ruta, "w", encoding="utf-8") as fh:
                fh.write(plantilla)
        except Exception:
            return None
        return slug
