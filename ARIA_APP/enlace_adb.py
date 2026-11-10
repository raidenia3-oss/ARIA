# -*- coding: utf-8 -*-
"""ARIA <-> ASAGI: transporte por adb (USB, sin internet, regla v2).

Los mensajes viajan como archivos JSON en el celular:
  /sdcard/Android/data/com.asagi.brain/files/enlace/inbox.json   (ARIA -> ASAGI)
  /sdcard/Android/data/com.asagi.brain/files/enlace/outbox.json  (ASAGI -> ARIA)

ARIA hace: adb push del inbox, adb pull del outbox, reintento al reconectar cable.
Hilo daemon que detecta el celular al enchufarlo. Solo stdlib + subprocess.
Sin HTTP/localhost/servidores.

Espejo logico de enlace.py (gist) pero sobre cable USB local; cifrado opcional.
"""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional

ADB = "adb"
PKG = "com.asagi.brain"
ENLACE_DIR = "/sdcard/Android/data/%s/files/enlace" % PKG
INBOX_REMOTO = "inbox.json"   # ARIA escribe, ASAGI lee
OUTBOX_REMOTO = "outbox.json" # ASAGI escribe, ARIA lee

LOCAL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "enlace_adb")
LOCAL_INBOX = os.path.join(LOCAL_DIR, "inbox.json")     # cola de salida de ARIA
LOCAL_OUTBOX = os.path.join(LOCAL_DIR, "outbox.json")   # copia local del outbox del celular
LOCAL_PROCESADOS = os.path.join(LOCAL_DIR, "procesados.json")  # ids ya entregados al chat

REINTENTO_S = 5
MAX_MSGS = 150
MAX_EDAD_MS = 7 * 24 * 3600 * 1000


def _ahora_ms() -> int:
    return int(time.time() * 1000)


def _nuevo_id(de: str, ts: int) -> str:
    return "%s-%d-%s" % (de, ts, secrets.token_hex(4))


def _adbn(args: List[str], timeout: int = 15):
    """Ejecuta adb <args>; devuelve (codigo, stdout, stderr)."""
    try:
        p = subprocess.run([ADB] + args, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return 127, "", "adb no encontrado"
    except Exception as e:
        return 1, "", str(e)


def disponible() -> bool:
    """True si adb responde y hay un dispositivo en estado 'device'."""
    rc, out, _ = _adbn(["devices"])
    if rc != 0:
        return False
    for linea in out.splitlines():
        if "\tdevice" in linea:
            return True
    return False


def vinculado() -> bool:
    return disponible()


def _ruta_remoto(archivo: str) -> str:
    return "%s/%s" % (ENLACE_DIR, archivo)


def _leer_json(ruta: str, defecto: Any) -> Any:
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return defecto


def _guardar_json(ruta: str, dato: Any) -> None:
    os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dato, f, ensure_ascii=False)
    os.replace(tmp, ruta)


def _pull(remoto: str, local: str) -> bool:
    rc, _, _ = _adbn(["pull", remoto, local])
    return rc == 0 and os.path.exists(local)


def _push(local: str, remoto: str) -> bool:
    rc, _, _ = _adbn(["push", local, remoto])
    return rc == 0


def _push_texto(texto: str, remoto: str) -> bool:
    os.makedirs(LOCAL_DIR, exist_ok=True)
    tmp = os.path.join(LOCAL_DIR, "_push_tmp.json")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(texto)
    ok = _push(tmp, remoto)
    try:
        os.remove(tmp)
    except Exception:
        pass
    return ok


def _filtrar_nuevos(msgs: List[Dict[str, Any]], procesados: List[str]) -> List[Dict[str, Any]]:
    hechos = set(procesados or [])
    nuevos = []
    for m in msgs or []:
        if (isinstance(m, dict) and isinstance(m.get("id"), str)
                and m.get("id") not in hechos and m.get("de") != "aria"):
            nuevos.append({
                "id": m["id"],
                "de": m.get("de", "asagi"),
                "ts": int(m.get("ts", 0) or 0),
                "tipo": str(m.get("tipo", "nota")),
                "cuerpo": str(m.get("cuerpo", "")),
            })
    nuevos.sort(key=lambda m: m["ts"])
    return nuevos[-MAX_MSGS:]


def sincronizar() -> Dict[str, Any]:
    """Un ciclo: pull outbox (nuevos de ASAGI), push inbox (pendientes de ARIA)."""
    resultado: Dict[str, Any] = {
        "ok": False, "nuevos": [], "enviados": 0, "texto": "",
    }
    if not disponible():
        resultado["texto"] = (
            "Celular no detectado por adb. Conecta por USB con depuracion USB activa.")
        return resultado

    # ---- 1) Pull outbox: traer mensajes nuevos de ASAGI ----
    nuevos: List[Dict[str, Any]] = []
    if _pull(_ruta_remoto(OUTBOX_REMOTO), LOCAL_OUTBOX):
        doc = _leer_json(LOCAL_OUTBOX, {"msgs": []})
        msgs = doc.get("msgs", []) if isinstance(doc, dict) else []
        est = _leer_json(LOCAL_PROCESADOS, {"procesados": []})
        if not isinstance(est, dict):
            est = {"procesados": []}
        nuevos = _filtrar_nuevos(msgs, est.get("procesados", []))
        for n in nuevos:
            est.setdefault("procesados", []).append(n["id"])
        est["procesados"] = est["procesados"][-600:]
        _guardar_json(LOCAL_PROCESADOS, est)

    # ---- 2) Push inbox: enviar pendientes de ARIA al celular ----
    est_inbox = _leer_json(LOCAL_INBOX, {"msgs": []})
    if not isinstance(est_inbox, dict):
        est_inbox = {"msgs": []}
    pendientes = est_inbox.get("msgs", [])
    enviados = 0
    if pendientes and isinstance(pendientes, list):
        ok = _push_texto(
            json.dumps({"msgs": pendientes}, ensure_ascii=False),
            _ruta_remoto(INBOX_REMOTO),
        )
        if ok:
            enviados = len(pendientes)
            est_inbox["msgs"] = []
            _guardar_json(LOCAL_INBOX, est_inbox)

    resultado["ok"] = True
    resultado["nuevos"] = nuevos
    resultado["enviados"] = enviados
    resultado["texto"] = (
        "Sincronizado por adb: %d nuevos de ASAGI, %d enviados al celular."
        % (len(nuevos), enviados))
    return resultado


def encolar(tipo: str, cuerpo: str) -> Optional[Dict[str, Any]]:
    """Guarda un mensaje de salida en la cola local (se enviara al celular)."""
    cuerpo = (cuerpo or "").strip()
    if not cuerpo:
        return None
    os.makedirs(LOCAL_DIR, exist_ok=True)
    est = _leer_json(LOCAL_INBOX, {"msgs": []})
    if not isinstance(est, dict):
        est = {"msgs": []}
    ts = _ahora_ms()
    msg = {"id": _nuevo_id("aria", ts), "de": "aria", "ts": ts,
           "tipo": tipo, "cuerpo": cuerpo}
    est.setdefault("msgs", []).append(msg)
    est["msgs"] = est["msgs"][-MAX_MSGS:]
    _guardar_json(LOCAL_INBOX, est)
    return msg


def enviar(texto: str, tipo: str = "nota") -> Dict[str, Any]:
    """Encola un mensaje e intenta enviarlo ahora al celular."""
    if not _encolar(tipo, texto):
        return {"ok": False, "texto": "Falta el texto a enviar."}
    r = sincronizar()
    if r.get("ok"):
        que = "Pendiente enviado al celular" if tipo == "pendiente" else "Nota enviada a ASAGI"
        return {"ok": True, "texto": que + ".", "enviados": r.get("enviados", 0)}
    return {"ok": False, "texto": (
        "Guardado en cola; saldra cuando conectes el celular. " + r.get("texto", ""))}


def recibir() -> Dict[str, Any]:
    """Trae mensajes nuevos de ASAGI desde el celular."""
    r = sincronizar()
    if not r.get("ok"):
        return r
    return {
        "ok": True,
        "nuevos": r.get("nuevos", []),
        "texto": _texto_nuevos(r.get("nuevos", [])),
    }


def _texto_nuevos(nuevos: List[Dict[str, Any]]) -> str:
    if not nuevos:
        return "Nada nuevo de ASAGI."
    lineas = []
    for n in nuevos:
        marca = "pendiente" if n.get("tipo") == "pendiente" else "nota"
        lineas.append("- [%s] %s" % (marca, n.get("cuerpo", "")))
    return "De ASAGI:\n" + "\n".join(lineas)


def estado() -> Dict[str, Any]:
    if not disponible():
        return {"ok": True, "enlazada": False,
                "texto": "Celular no detectado por adb. Conecta por USB con depuracion USB activa."}
    r = sincronizar()
    if not r.get("ok"):
        return {"ok": False, "enlazada": True, "texto": r.get("texto", "")}
    return {"ok": True, "enlazada": True,
            "texto": "Enlace adb activo. %s" % _texto_nuevos(r.get("nuevos", []))}


# ---------------- hilo daemon: detecta celular al enchufar ----------------


class VigiaAdb:
    def __init__(self, callback=None, intervalo_s=30):
        self._callback = callback
        self._intervalo = intervalo_s
        self._activo = False
        self._hilo = None
        self._conectado_previo = False

    def iniciar(self):
        if self._activo:
            return
        self._activo = True
        self._hilo = threading.Thread(target=self._loop, name="aria-enlace-adb-vigia", daemon=True)
        self._hilo.start()

    def _loop(self):
        while self._activo:
            try:
                conectado = disponible()
                if conectado and not self._conectado_previo:
                    try:
                        sincronizar()
                    except Exception:
                        pass
                    if self._callback:
                        try:
                            self._callback()
                        except Exception:
                            pass
                self._conectado_previo = conectado
            except Exception:
                pass
            time.sleep(self._intervalo)

    def detener(self):
        self._activo = False


# ---------------- consola ----------------


def _main(argv: List[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 0
    orden = argv[1].lower()
    resto = " ".join(argv[2:]).strip()
    if orden == "enviar":
        r = enviar(resto, "nota")
    elif orden == "pendiente":
        r = enviar(resto, "pendiente")
    elif orden == "recibir":
        r = recibir()
    elif orden == "estado":
        r = estado()
    else:
        print(__doc__)
        return 1
    print(r.get("texto", r))
    return 0 if r.get("ok") else 2


if __name__ == "__main__":
    import sys
    sys.exit(_main(sys.argv))
