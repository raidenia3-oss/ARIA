# -*- coding: utf-8 -*-
"""ARIA - Guardia de autonomia (candado de acciones irreversibles).

ARIA es autonoma AMPLIA: actua sola. Pero en una PC personal, lo IRREVERSIBLE
(escribir/sobrescribir/borrar archivos, instalar, acciones al sistema) NO se ejecuta
solo: se encola y espera el OK de Daniel. Lo seguro (leer, listar, estado, notas) corre
sin pedir permiso. Lo que toca secretos o rutas protegidas se BLOQUEA de plano.

Clasifica cada accion autonoma (skill_id + params) en:
  - 'auto'      -> se ejecuta ya (lectura/consulta/append inocuo)
  - 'aprobar'   -> se encola; corre SOLO si Daniel aprueba
  - 'bloqueado' -> ni con aprobacion (secretos, fuera de la zona permitida)

Se apoya en path_guard (si existe) para decidir rutas. Regla v2: local, sin red.
La clasificacion (_clasificar) es PURA: testeable sin tocar disco.
"""
import os
import json
import time

_DIR = os.path.dirname(os.path.abspath(__file__))
_PEND = os.path.join(_DIR, "data", "autonomia", "pending")
_HECHO = os.path.join(_DIR, "data", "autonomia", "resueltas")

# skills que ARIA puede correr SOLA (leen/consultan/append inocuo)
SEGURAS = {
    "note_add", "note_list", "file_read", "file_list", "conversation_history",
    "system_status", "memory_status", "perception", "say", "status",
}
# skills IRREVERSIBLES -> requieren OK de Daniel
IRREVERSIBLES = {
    "file_write", "file_delete", "file_move", "file_overwrite", "rmdir",
    "install", "pip_install", "run_command", "shell", "exec", "registry_write",
    "settings_write", "uninstall",
}
# palabras en params/goal que delatan algo destructivo aunque la skill parezca inocua
PALABRAS_PELIGRO = ("rm ", "del ", "format", "borra", "elimina", "sobrescrib",
                    "overwrite", "uninstall", "shutdown", "apagar", "kill",
                    "drop table", "--force", "sudo")


def _texto_params(params):
    try:
        return json.dumps(params, ensure_ascii=False).lower()
    except Exception:
        return str(params).lower()


def _ruta_bloqueada(params):
    """True si la accion escribe en una ruta protegida/secreta (via path_guard)."""
    ruta = None
    if isinstance(params, dict):
        ruta = params.get("path") or params.get("ruta") or params.get("archivo")
    if not ruta:
        return False
    try:
        import path_guard
        for nombre in ("puede_escribir", "escritura_permitida", "allow_write", "is_allowed"):
            fn = getattr(path_guard, nombre, None)
            if callable(fn):
                return not bool(fn(ruta))
    except Exception:
        pass
    return False


def _clasificar(skill_id, params=None):
    """skill_id + params -> 'auto' | 'aprobar' | 'bloqueado'. Puro, testeable."""
    sid = str(skill_id or "").strip()
    txt = _texto_params(params or {})
    # 1) secreto / ruta protegida -> bloqueado de plano
    if _ruta_bloqueada(params):
        return "bloqueado"
    # 2) palabras destructivas en los params -> aprobar (aunque la skill parezca safe)
    if any(p in txt for p in PALABRAS_PELIGRO):
        return "aprobar"
    # 3) por tipo de skill
    if sid in IRREVERSIBLES:
        return "aprobar"
    if sid in SEGURAS:
        return "auto"
    # 4) desconocida -> fail-safe: pedir OK (mejor que ejecutar algo no catalogado)
    return "aprobar"


def _guardar(carpeta, item):
    try:
        os.makedirs(carpeta, exist_ok=True)
        with open(os.path.join(carpeta, item["id"] + ".json"), "w", encoding="utf-8") as f:
            json.dump(item, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def guard(skill_id, params, ejecutar, aprobado=False):
    """Punto unico por el que pasa CADA accion autonoma.
      - ejecutar: callable() que realmente corre la skill (lo llama el runtime).
      - aprobado: True solo cuando Daniel ya dio el OK para esta accion.
    Devuelve el resultado, o un dict {pendiente|bloqueado}."""
    clase = _clasificar(skill_id, params)
    if clase == "bloqueado":
        return {"bloqueado": True, "skill": skill_id,
                "motivo": "toca secretos o ruta protegida; ni con aprobacion"}
    if clase == "auto" or aprobado:
        try:
            return {"ok": True, "resultado": ejecutar()}
        except Exception as exc:
            return {"error": str(exc)}
    # aprobar y NO aprobado -> encolar y avisar
    pid = "%d" % int(time.time() * 1000)
    item = {"id": pid, "skill": skill_id, "params": params,
            "estado": "pendiente", "ts": time.time(),
            "motivo": "accion irreversible; espera OK de Daniel"}
    _guardar(_PEND, item)
    return {"pendiente": pid, "skill": skill_id,
            "aviso": "ARIA quiere hacer '%s' pero es irreversible; apruebalo tu." % skill_id}


def listar():
    """Acciones autonomas pendientes de tu OK."""
    if not os.path.isdir(_PEND):
        return []
    out = []
    for fn in sorted(os.listdir(_PEND)):
        if fn.endswith(".json"):
            try:
                out.append(json.load(open(os.path.join(_PEND, fn), encoding="utf-8")))
            except Exception:
                pass
    return out


def _cargar(pid):
    ruta = os.path.join(_PEND, str(pid) + ".json")
    if os.path.isfile(ruta):
        try:
            return json.load(open(ruta, encoding="utf-8"))
        except Exception:
            return None
    return None


def aprobar(pid, ejecutar):
    """Daniel aprueba una accion encolada. 'ejecutar' corre la skill de verdad."""
    item = _cargar(pid)
    if not item:
        return {"error": "pendiente %s no existe" % pid}
    try:
        res = ejecutar()
        item["estado"] = "aprobada"; item["hecho_ts"] = time.time()
    except Exception as exc:
        return {"error": str(exc)}
    _guardar(_HECHO, item)
    try:
        os.remove(os.path.join(_PEND, str(pid) + ".json"))
    except OSError:
        pass
    return {"ok": True, "resultado": res}


def rechazar(pid, motivo=""):
    item = _cargar(pid)
    if not item:
        return {"error": "pendiente %s no existe" % pid}
    item["estado"] = "rechazada"; item["motivo_rechazo"] = motivo
    _guardar(_HECHO, item)
    try:
        os.remove(os.path.join(_PEND, str(pid) + ".json"))
    except OSError:
        pass
    return {"ok": True, "estado": "rechazada"}
