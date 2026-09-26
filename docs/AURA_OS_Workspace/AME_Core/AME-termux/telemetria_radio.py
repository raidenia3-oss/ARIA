import math
import random
import time
from datetime import datetime
import threading
import os


# Watchdog state
_last_scan_timestamp = None
_watchdog_running = False
_watchdog_lock = threading.Lock()
_last_watchdog_message = None


def _normalize_dbm(dbm_value):
    """Escala valores de potencia dBm a un rango 0-100 para visualización radar."""
    return round(max(0, min(100, 100 + dbm_value)), 1)


def _build_csi_nodes(t, movement_bias):
    """Genera lecturas CSI de 4 antenas con fluctuaciones por movimiento e interferencia."""
    nodes = {
        "ALPHA": round(-42 + math.sin(t * 0.86) * 5 + movement_bias * 1.5 + random.gauss(0, 1.8), 1),
        "BETA":  round(-51 + math.cos(t * 0.77) * 4 + movement_bias * 0.9 + random.gauss(0, 1.5), 1),
        "GAMMA": round(-38 + math.sin(t * 0.65) * 6 + movement_bias * 2.2 + random.gauss(0, 2.0), 1),
        "DELTA": round(-59 + math.cos(t * 0.54) * 6 + movement_bias * 1.0 + random.gauss(0, 2.4), 1),
    }
    return nodes


def _generate_spectrum(t, movement_level):
    """Genera ocupancia de canales Wi-Fi con contenidos dinámicos de interferencia."""
    spectrum = {}
    for ch in range(1, 14):
        base = 24 + abs(math.sin(t + ch * 0.21)) * 18
        movement_effect = (movement_level * 0.6) if ch in (6, 7, 11) else (movement_level * 0.3)
        occupancy = round(base + movement_effect + random.gauss(0, 5), 1)
        spectrum[str(ch)] = min(100, max(0, occupancy))
    return spectrum


def _calculate_presence(perturbation, spectrum, movement_flag):
    """Decide si hay presencia y si la firma es humana."""
    strong_edge = any(spectrum[str(ch)] > 65 for ch in (6, 11))
    is_human = movement_flag and (perturbation > 45 or strong_edge or random.random() < 0.18)
    presence_detected = perturbation > 32 or strong_edge or movement_flag
    return presence_detected, is_human


def generate_wifi_radar_data():
    """Genera datos CSI realistas para el endpoint /api/wifi_radar."""
    t = time.time() * 0.92
    movement_bias = abs(math.sin(t * 0.7)) * 4 + random.gauss(0, 1.2)
    movement_flag = random.random() < 0.18 or movement_bias > 3.5

    nodes = _build_csi_nodes(t, movement_bias if movement_flag else 0)
    rssi_values = list(nodes.values())
    rssi_avg = round(sum(rssi_values) / len(rssi_values), 1)
    rssi_variance = round(sum((x - rssi_avg) ** 2 for x in rssi_values) / len(rssi_values), 2)

    snr = round(22 + math.cos(t * 0.55) * 4 - (movement_bias * 0.35) + random.gauss(0, 1.3), 1)
    snr = max(1, min(60, snr))

    perturbation_index = round(
        14
        + abs(math.sin(t * 1.1)) * 6
        + math.sqrt(rssi_variance) * 2.2
        + movement_bias * 3.5
        + random.gauss(0, 4),
        1
    )
    perturbation_index = min(100, max(0, perturbation_index))

    spectrum = _generate_spectrum(t, movement_bias if movement_flag else 0)
    interference_detected = any(spectrum[str(ch)] > 55 for ch in (5, 6, 7, 11, 12))

    presence_detected, is_human = _calculate_presence(perturbation_index, spectrum, movement_flag)

    link_quality = round(max(0, min(100, 100 - abs(rssi_avg + 40) * 1.3 - (100 - snr) * 0.6)), 1)
    carrier_freq = round(2.412 + (random.random() * 0.088), 3)

    active_channels = [str(ch) for ch, occ in spectrum.items() if occ > 30]
    if len(active_channels) == 0:
        active_channels = [str(ch) for ch in range(1, 14) if spectrum[str(ch)] > 10][:3]

    now = datetime.now()
    timestamp = now.strftime('%Y-%m-%dT%H:%M:%S') + f'.{now.microsecond // 1000:03d}'

    global _last_scan_timestamp
    _last_scan_timestamp = time.time()

    return {
        "status": "SCANNING",
        "timestamp": timestamp,
        "nodes": nodes,
        "rssi_avg": rssi_avg,
        "rssi_variance": rssi_variance,
        "snr_avg": snr,
        "perturbation_index": perturbation_index,
        "presence_detected": presence_detected,
        "is_human": is_human,
        "link_quality": link_quality,
        "carrier_freq": carrier_freq,
        "spectrum": spectrum,
        "interference_detected": interference_detected,
        "active_channels": active_channels,
        "recommended_channel": min(active_channels, key=lambda x: int(x)) if active_channels else "1"
    }


def _is_wifi_watchdog_healthy(max_age=20):
    if _last_scan_timestamp is None:
        return False
    return (time.time() - _last_scan_timestamp) <= max_age


def _watchdog_loop(interval=10, max_age=20):
    global _watchdog_running, _last_watchdog_message
    while _watchdog_running:
        with _watchdog_lock:
            healthy = _is_wifi_watchdog_healthy(max_age=max_age)
            if not healthy:
                _last_watchdog_message = (
                    f"WiFi telemetry stale for {int(time.time() - _last_scan_timestamp)}s"
                    if _last_scan_timestamp is not None else
                    "WiFi telemetry has not produced any scan yet"
                )
            else:
                _last_watchdog_message = None
        time.sleep(interval)


def start_wifi_watchdog(interval=10, max_age=20):
    """Inicia el watchdog que supervisa el proceso de escaneo de radio."""
    global _watchdog_running
    with _watchdog_lock:
        if _watchdog_running:
            return False
        _watchdog_running = True
        thread = threading.Thread(target=_watchdog_loop, args=(interval, max_age), daemon=True)
        thread.start()
    return True


def stop_wifi_watchdog():
    """Detiene el watchdog del escaneo Wi-Fi."""
    global _watchdog_running
    with _watchdog_lock:
        _watchdog_running = False
    return True


def get_wifi_watchdog_status():
    """Retorna el estado actual del watchdog."""
    return {
        "running": _watchdog_running,
        "healthy": _is_wifi_watchdog_healthy(),
        "last_scan_timestamp": _last_scan_timestamp,
        "last_scan_age_seconds": int(time.time() - _last_scan_timestamp) if _last_scan_timestamp is not None else None,
        "last_watchdog_message": _last_watchdog_message,
    }
