# -*- coding: utf-8 -*-
"""ARIA - Loop de auto-mejora SEGURO (propose-probe-compose de Harness2, acotado).

Harness2 deja al agente correr sus propios scripts; su propio video exige Docker para
eso. Aqui NO: en tu PC personal ARIA NUNCA ejecuta sola lo que propone. El loop es:

  1) PROPONER  - ARIA escribe una propuesta (skill nueva, ajuste, leccion). Queda
                 PENDIENTE en data/mejoras/pending/. No se ejecuta nada.
  2) PROBAR    - Se evalua por ANALISIS ESTATICO (sin ejecutar): sintaxis valida,
                 interfaz correcta, y ESCANEO DE PELIGROS (subprocess, eval, sockets,
                 borrado de archivos, etc.). Devuelve un veredicto.
  3) APROBAR   - SOLO tu apruebas. Recien ahi se aplica (se escribe la skill vIa
                 path_guard) y se registra la leccion. Fail-closed: sin aprobacion,
                 nada se aplica.

Regla v2: sin subprocess, sin red. El 'probe' es AST puro, nunca exec/eval.
"""
import os
import re
import ast
import json
import time

_DIR = os.path.dirname(os.path.abspath(__file__))
_PEND = os.path.join(_DIR, "data", "mejoras", "pending")
_APLIC = os.path.join(_DIR, "data", "mejoras", "aplicadas")
_SKILLS = os.path.join(_DIR, "skills")

# llamadas/modulos que NO puede traer una skill propuesta (peligro en PC personal)
_MODULOS_PROHIBIDOS = {"subprocess", "socket", "ctypes", "multiprocessing",
                       "pty", "fcntl", "winreg", "_winreg"}
_LLAMADAS_PROHIBIDAS = {"eval", "exec", "compile", "__import__", "system",
                        "popen", "fork", "remove", "rmdir", "unlink", "rmtree"}


def _ids_peligrosos(arbol):
    """Escanea el AST en busca de imports/llamadas peligrosas. Devuelve lista."""
    hallazgos = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for a in nodo.names:
                raiz = a.name.split(".")[0]
                if raiz in _MODULOS_PROHIBIDOS:
                    hallazgos.append("import %s" % a.name)
        elif isinstance(nodo, ast.ImportFrom):
            raiz = (nodo.module or "").split(".")[0]
            if raiz in _MODULOS_PROHIBIDOS:
                hallazgos.append("from %s import ..." % nodo.module)
        elif isinstance(nodo, ast.Call):
            f = nodo.func
            nombre = getattr(f, "id", None) or getattr(f, "attr", None)
            if nombre in _LLAMADAS_PROHIBIDAS:
                hallazgos.append("llamada %s()" % nombre)
    return hallazgos


# ---------------------------------------------------------------- proponer
def proponer(tipo, contenido, descripcion="", nombre=""):
    """Registra una propuesta PENDIENTE (no ejecuta nada). tipo: 'skill' | 'leccion' | 'nota'."""
    contenido = contenido or ""
    if tipo == "skill" and not contenido.strip():
        return {"error": "skill sin contenido"}
    os.makedirs(_PEND, exist_ok=True)
    pid = "%d" % int(time.time() * 1000)
    prop = {"id": pid, "tipo": tipo, "nombre": nombre or ("skill_%s" % pid),
            "descripcion": descripcion[:300], "contenido": contenido,
            "estado": "pendiente", "ts": time.time()}
    ruta = os.path.join(_PEND, pid + ".json")
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(prop, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        return {"error": str(exc)}
    return {"ok": True, "id": pid, "ruta": ruta, "nota": "pendiente; probar() y luego tu aprobar()"}


# ---------------------------------------------------------------- probar (sin ejecutar)
def probar(pid):
    """Analiza ESTATICAMENTE una propuesta. NO la ejecuta. Devuelve veredicto."""
    prop = _cargar(pid)
    if not prop:
        return {"error": "propuesta %s no existe" % pid}
    if prop["tipo"] != "skill":
        return {"ok": True, "veredicto": "aprobable", "tipo": prop["tipo"],
                "nota": "no es codigo; revisa el texto y aprueba tu"}
    codigo = prop["contenido"]
    problemas = []
    # 1) sintaxis
    try:
        arbol = ast.parse(codigo)
    except SyntaxError as exc:
        return {"ok": False, "veredicto": "rechazable", "problemas": ["sintaxis: %s" % exc]}
    # 2) interfaz de skill esperada
    nombres = {n.name for n in ast.walk(arbol)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    asignados = {t.id for n in ast.walk(arbol) if isinstance(n, ast.Assign)
                 for t in n.targets if isinstance(t, ast.Name)}
    if "match" not in nombres:
        problemas.append("falta funcion match()")
    if "run" not in nombres:
        problemas.append("falta funcion run()")
    if "SKILL_ENABLED" not in asignados:
        problemas.append("falta SKILL_ENABLED")
    # 3) escaneo de peligros
    peligros = _ids_peligrosos(arbol)
    if peligros:
        problemas.append("peligros: " + ", ".join(peligros))
    veredicto = "aprobable" if not problemas else "rechazable"
    return {"ok": not problemas, "veredicto": veredicto, "problemas": problemas,
            "peligros": peligros}


# ---------------------------------------------------------------- aprobar / rechazar
def aprobar(pid, forzar=False, reload_fn=None):
    """APLICA una propuesta. SOLO el usuario llama esto. Reprueba si el probe fallo
    (salvo forzar=True, que deja constancia). Para skill: escribe en skills/ vIa
    path_guard y la HOTLOADEA (de Brahma 'Skill Forge') llamando reload_fn sin
    reiniciar ARIA. reload_fn = normalmente learner.reload_skills."""
    prop = _cargar(pid)
    if not prop:
        return {"error": "propuesta %s no existe" % pid}
    v = probar(pid)
    if prop["tipo"] == "skill" and not v.get("ok") and not forzar:
        return {"error": "el probe la marco rechazable", "problemas": v.get("problemas"),
                "nota": "arregla la propuesta o usa forzar=True a tu riesgo"}

    aplicado = None
    activas = None
    if prop["tipo"] == "skill":
        destino = os.path.join(_SKILLS, prop["nombre"] + ".py")
        # escribir SOLO dentro de skills/ via path_guard si esta disponible
        try:
            import path_guard
            ok = path_guard.puede_escribir(destino) if hasattr(path_guard, "puede_escribir") else True
        except Exception:
            ok = True
        if not ok:
            return {"error": "path_guard bloqueo la escritura en %s" % destino}
        try:
            os.makedirs(_SKILLS, exist_ok=True)
            with open(destino, "w", encoding="utf-8") as f:
                f.write(prop["contenido"])
            aplicado = destino
        except Exception as exc:
            return {"error": "no pude escribir la skill: %s" % exc}
        # HOTLOAD: recarga las skills en vivo (sin reiniciar ARIA)
        if callable(reload_fn):
            try:
                activas = reload_fn()
            except Exception as exc:
                activas = "reload fallo: %s" % exc

    # mover a aplicadas + registrar leccion
    prop["estado"] = "aplicada"
    prop["aplicado_en"] = aplicado
    prop["aprobado_ts"] = time.time()
    _mover_a_aplicadas(pid, prop)
    try:
        import experiencia
        experiencia.registrar(
            "Mejora aplicada: %s" % (prop["descripcion"] or prop["nombre"]),
            contexto=prop["tipo"], resultado="exito", tema="auto-mejora")
    except Exception:
        pass
    return {"ok": True, "aplicado": aplicado, "tipo": prop["tipo"],
            "hotload": activas, "nota": ("skill viva sin reiniciar" if activas else None)}


def rechazar(pid, motivo=""):
    prop = _cargar(pid)
    if not prop:
        return {"error": "propuesta %s no existe" % pid}
    prop["estado"] = "rechazada"
    prop["motivo"] = motivo
    _mover_a_aplicadas(pid, prop)
    try:
        import experiencia
        experiencia.registrar("Mejora rechazada: %s (%s)" % (prop["nombre"], motivo or "s/motivo"),
                              contexto=prop["tipo"], resultado="nota", tema="auto-mejora")
    except Exception:
        pass
    return {"ok": True, "estado": "rechazada"}


def listar(estado="pendiente"):
    """Lista propuestas por estado."""
    carpeta = _PEND if estado == "pendiente" else _APLIC
    if not os.path.isdir(carpeta):
        return []
    out = []
    for fn in sorted(os.listdir(carpeta)):
        if fn.endswith(".json"):
            try:
                p = json.load(open(os.path.join(carpeta, fn), encoding="utf-8"))
                out.append({"id": p["id"], "tipo": p["tipo"], "nombre": p.get("nombre"),
                            "descripcion": p.get("descripcion"), "estado": p.get("estado")})
            except Exception:
                pass
    return out


# ---------------------------------------------------------------- internos
def _cargar(pid):
    for carpeta in (_PEND, _APLIC):
        ruta = os.path.join(carpeta, str(pid) + ".json")
        if os.path.isfile(ruta):
            try:
                return json.load(open(ruta, encoding="utf-8"))
            except Exception:
                return None
    return None


def _mover_a_aplicadas(pid, prop):
    os.makedirs(_APLIC, exist_ok=True)
    try:
        with open(os.path.join(_APLIC, str(pid) + ".json"), "w", encoding="utf-8") as f:
            json.dump(prop, f, ensure_ascii=False, indent=2)
        viejo = os.path.join(_PEND, str(pid) + ".json")
        if os.path.isfile(viejo):
            os.remove(viejo)
    except Exception:
        pass
