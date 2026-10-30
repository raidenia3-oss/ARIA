# -*- coding: utf-8 -*-
"""Programador de automatizacion diaria de RollerCoin (tarde)."""
import os
import time
import threading

_target_hour = 15  # 3 PM por defecto
_running = False
_thread = None


def _seconds_until(hour, minute=0):
    now = time.localtime()
    target = time.mktime((now.tm_year, now.tm_mon, now.tm_mday, hour, minute, 0, 0, 0, -1))
    if target <= time.time():
        target += 86400  # siguiente dia
    return target - time.time()


def _loop():
    global _running
    while _running:
        wait = _seconds_until(_target_hour, 0)
        print("[RollerCoin-Sched] proxima ejecucion en %.0f s (hora %d:00)" % (wait, _target_hour), flush=True)
        # dormir en chunks para poder cancelar
        end = time.time() + wait
        while _running and time.time() < end:
            time.sleep(min(60, end - time.time()))
        if not _running:
            break
        # ejecutar
        try:
            from rollercoin_daily import daily_run
            res = daily_run(headless=True)
            print("[RollerCoin-Sched] ejecutado:", res, flush=True)
            # reportar a Discord
            try:
                from remote_discord import enviar_canal
                msg = "ARIA RollerCoin diario (tarde): %s" % res
                enviar_canal("1565541569917096038", msg)
            except Exception:
                pass
        except Exception as exc:
            print("[RollerCoin-Sched] error:", exc, flush=True)
        # evitar re-ejecutar el mismo dia
        time.sleep(3600)


def iniciar(hora=15):
    global _running, _thread, _target_hour
    if _running:
        return {"status": "ya_corriendo"}
    _target_hour = int(hora)
    _running = True
    _thread = threading.Thread(target=_loop, name="rollercoin-sched", daemon=True)
    _thread.start()
    return {"status": "ok", "hora": _target_hour}


def detener():
    global _running
    _running = False
    return {"status": "detenido"}


def estado():
    return {"corriendo": _running, "hora_objetivo": _target_hour}