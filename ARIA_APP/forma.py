# -*- coding: utf-8 -*-
"""ARIA - Sistema de formas: ARIA elige su cuerpo (NUCLEO o AVATAR).

ARIA tiene dos cuerpos posibles:
  - 'nucleo'  -> el orbe vivo (nucleo.py), su forma de energia/pensamiento.
  - 'avatar'  -> el chibi (chibi.py), su forma personaje.
Y puede estar en 'ambos' o 'oculto'.

Este manager coordina cual se muestra, lo recuerda entre sesiones (data/forma.json) y
puede ELEGIR sola segun su estado de animo (auto): cuando piensa/procesa tiende al
nucleo; cuando conversa, al avatar. El usuario tambien puede fijarla a mano.

La logica de estado (que forma toca, persistencia, regla de auto-eleccion) es PURA:
no depende de PyQt. Los cuerpos entran como 'fabricas' (callables que devuelven un
widget con show()/hide()), asi es testeable con dobles y no obliga a cargar Qt.
"""
import os
import json

FORMAS = ("nucleo", "avatar", "ambos", "oculto")

# regla de auto-eleccion: estado de ARIA -> forma preferida
_AUTO = {
    "pensando": "nucleo", "procesando": "nucleo", "analizando": "nucleo",
    "hablando": "avatar", "conversando": "avatar", "saludando": "avatar",
    "escuchando": "avatar",
    "idle": None,        # idle -> respeta la ultima elegida / preferencia
}


class Forma:
    def __init__(self, nucleo_factory=None, avatar_factory=None,
                 config_path=None, por_defecto="nucleo"):
        self._fab = {"nucleo": nucleo_factory, "avatar": avatar_factory}
        self._cuerpo = {"nucleo": None, "avatar": None}   # widgets (lazy)
        self.config_path = config_path or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "data", "forma.json")
        self.actual = self._cargar() or por_defecto
        self.preferida = self.actual

    # ---------------------------------------------------------- persistencia
    def _cargar(self):
        try:
            d = json.load(open(self.config_path, encoding="utf-8"))
            f = d.get("forma")
            return f if f in FORMAS else None
        except Exception:
            return None

    def _guardar(self):
        try:
            os.makedirs(os.path.dirname(self.config_path) or ".", exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump({"forma": self.actual, "preferida": self.preferida}, f)
        except Exception:
            pass

    # ---------------------------------------------------------- cuerpos (lazy)
    def _obtener(self, tipo):
        if self._cuerpo.get(tipo) is None and callable(self._fab.get(tipo)):
            try:
                self._cuerpo[tipo] = self._fab[tipo]()
            except Exception:
                self._cuerpo[tipo] = None
        return self._cuerpo.get(tipo)

    def _aplicar(self):
        """Muestra/oculta los cuerpos segun self.actual."""
        quiere = {"nucleo": self.actual in ("nucleo", "ambos"),
                  "avatar": self.actual in ("avatar", "ambos")}
        for tipo, visible in quiere.items():
            w = self._obtener(tipo) if visible else self._cuerpo.get(tipo)
            if w is None:
                continue
            try:
                (w.show if visible else w.hide)()
            except Exception:
                pass

    # ---------------------------------------------------------- API
    def mostrar(self, forma, recordar=True):
        """Fija la forma a mano. forma in FORMAS."""
        if forma not in FORMAS:
            return {"error": "forma invalida: %s (usa %s)" % (forma, ", ".join(FORMAS))}
        self.actual = forma
        if recordar and forma in ("nucleo", "avatar"):
            self.preferida = forma
        self._aplicar()
        self._guardar()
        return {"ok": True, "forma": self.actual}

    def alternar(self):
        """Cambia entre nucleo <-> avatar (atajo)."""
        destino = "avatar" if self.actual == "nucleo" else "nucleo"
        return self.mostrar(destino)

    def auto(self, estado):
        """ARIA elige sola segun su estado de animo. En 'idle' usa la preferida."""
        destino = _AUTO.get(str(estado), None) or self.preferida
        self.actual = destino
        self._aplicar()
        self._guardar()
        return {"ok": True, "forma": self.actual, "por": estado}

    def estado_forma(self):
        return {"actual": self.actual, "preferida": self.preferida}


def crear_forma(nucleo_factory=None, avatar_factory=None, por_defecto="nucleo"):
    return Forma(nucleo_factory, avatar_factory, por_defecto=por_defecto)
