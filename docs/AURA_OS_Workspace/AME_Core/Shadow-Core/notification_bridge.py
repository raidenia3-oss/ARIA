#!/usr/bin/env python3
"""
notification_bridge.py — AURA Channel-Agnostic Notification Bridge
===================================================================
Sistema de notificaciones multicanal que reemplaza la dependencia de Telegram.
Ahora soporta Discord (Webhooks con embeds) y WhatsApp (CallMeBot API).

Arquitectura:
  [Eventos AURA] → [ChannelDispatcher] → [Discord Webhook] (logs, telemetría)
                                       → [WhatsApp CallMeBot] (alertas críticas)

Configuración: channels.yaml — cambia destinos sin modificar código.
"""

import os
import sys
import json
import time
import logging
import threading
import yaml
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from pathlib import Path
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [NOTIFICATION-BRIDGE] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('notification_bridge.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ─── Constantes ───
CONFIG_PATH = Path(__file__).resolve().parent / "channels.yaml"
NOTIFICATION_LOG = Path("notification_history.json")
TELEMETRY_CACHE = Path("telemetry_cache.json")
MAX_EVENTS_RETENTION = 500

# ─── Eventos y Severidad ───
class EventType(Enum):
    NODE_DISCONNECTED = "node_disconnected"
    INTRUSION_DETECTED = "intrusion_detected"
    TASK_COMPLETED = "task_completed"
    THREAT_BLOCKED = "threat_blocked"
    NODE_JOINED = "node_joined"
    SYSTEM_ERROR = "system_error"
    DAILY_SUMMARY = "daily_summary"

class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    INFO = "info"

EMOJIS = {
    EventType.NODE_DISCONNECTED: "\U0001f534",
    EventType.INTRUSION_DETECTED: "\U0001f6a8",
    EventType.TASK_COMPLETED: "\u2705",
    EventType.THREAT_BLOCKED: "\U0001f6e1\ufe0f",
    EventType.NODE_JOINED: "\U0001f7e2",
    EventType.SYSTEM_ERROR: "\u26a0\ufe0f",
    EventType.DAILY_SUMMARY: "\U0001f4ca"
}

@dataclass
class Notification:
    event_type: EventType
    severity: Severity
    title: str
    message: str
    node_id: Optional[str] = None
    source: str = "AURA"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict = field(default_factory=dict)
    sent_channels: List[str] = field(default_factory=list)


# ═══════════════════════════════════════════════
# CHANNEL DISPATCHER
# ═══════════════════════════════════════════════

class ChannelDispatcher:
    """
    Enruta notificaciones a los canales configurados según su tipo y severidad.
    Configuración vía channels.yaml — agnóstico al canal.
    """

    def __init__(self, config_path: str = None):
        self.config_path = config_path or str(CONFIG_PATH)
        self.config = self._load_config()
        self.active_channels = self.config.get("active_channels", ["discord"])
        logger.info(f"ChannelDispatcher activo. Canales: {self.active_channels}")

    def _load_config(self) -> Dict:
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    cfg = yaml.safe_load(f) or {}
                logger.info(f"Configuración cargada desde {self.config_path}")
                return cfg
            else:
                default = self._default_config()
                os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
                with open(self.config_path, 'w') as f:
                    yaml.dump(default, f, default_flow_style=False)
                logger.info(f"Configuración por defecto creada en {self.config_path}")
                return default
        except Exception as e:
            logger.error(f"Error cargando configuración: {e}")
            return self._default_config()

    def _default_config(self) -> Dict:
        return {
            "version": "1.0",
            "active_channels": ["discord"],
            "discord": {
                "enabled": True,
                "webhook_url": "",
                "username": "AURA Notification Bridge",
                "routes": [
                    {"event_types": ["*"], "severity": ["*"], "format": "embed"}
                ]
            },
            "whatsapp": {
                "enabled": False,
                "phone": "",
                "api_key": "",
                "api_base": "https://api.callmebot.com/whatsapp.php",
                "routes": [
                    {"event_types": ["intrusion_detected", "node_disconnected"], "severity": ["critical", "high"], "format": "text"}
                ]
            },
            "rate_limit": {"max_per_hour": 30, "max_per_day": 200}
        }

    def should_route_to_channel(self, channel: str, notification: Notification) -> bool:
        """Determina si una notificación debe ser enrutada a un canal."""
        channel_cfg = self.config.get(channel, {})
        if not channel_cfg.get("enabled", False):
            return False

        routes = channel_cfg.get("routes", [])
        event_val = notification.event_type.value
        severity_val = notification.severity.value

        for route in routes:
            event_types = route.get("event_types", [])
            severities = route.get("severity", [])

            if "*" in event_types or event_val in event_types:
                if "*" in severities or severity_val in severities:
                    return True
        return False

    def get_channel_config(self, channel: str) -> Dict:
        return self.config.get(channel, {})

    def get_discord_color(self, severity: str) -> int:
        colors = self.config.get("discord_colors", {})
        return colors.get(severity, 0x3498DB)

    def get_rate_limits(self) -> Dict:
        return self.config.get("rate_limit", {"max_per_hour": 30, "max_per_day": 200})


# ═══════════════════════════════════════════════
# DESTINOS (adaptadores de canal)
# ═══════════════════════════════════════════════

class DiscordWebhook:
    """Envía notificaciones a Discord usando Webhooks con formato embed."""

    def __init__(self, dispatcher: ChannelDispatcher):
        self.dispatcher = dispatcher
        self.config = dispatcher.get_channel_config("discord")
        self.webhook_url = self.config.get("webhook_url", "")
        self.username = self.config.get("username", "AURA")

    def send(self, notification: Notification) -> bool:
        if not self.webhook_url or "AQUI_VA_TU_WEBHOOK" in self.webhook_url:
            logger.debug(f"[Discord] No configurado — omitiendo: {notification.title}")
            return False

        embed = self._build_embed(notification)
        payload = {
            "username": self.username,
            "embeds": [embed]
        }
        if notification.avatar_url:
            payload["avatar_url"] = notification.avatar_url

        try:
            resp = requests.post(self.webhook_url, json=payload, timeout=10)
            if resp.status_code in (200, 204):
                logger.info(f"[Discord] Enviado: {notification.title}")
                return True
            else:
                logger.warning(f"[Discord] HTTP {resp.status_code}: {resp.text[:100]}")
                return False
        except Exception as e:
            logger.error(f"[Discord] Error: {e}")
            return False

    def _build_embed(self, notification: Notification) -> Dict:
        emoji = EMOJIS.get(notification.event_type, "\U0001f514")
        color_map = {
            Severity.CRITICAL: 0xDC143C, Severity.HIGH: 0xFF4500,
            Severity.MEDIUM: 0xFFA500, Severity.INFO: 0x3498DB
        }
        color = color_map.get(notification.severity, 0x3498DB)

        try:
            ts = datetime.fromisoformat(notification.timestamp).strftime('%Y-%m-%d %H:%M:%S')
        except:
            ts = notification.timestamp

        embed = {
            "title": f"{emoji} {notification.title}",
            "description": notification.message,
            "color": color,
            "timestamp": notification.timestamp,
            "footer": {"text": f"AURA | {notification.source} | {notification.event_type.value}"},
            "fields": []
        }

        if notification.node_id:
            embed["fields"].append({"name": "Nodo", "value": f"`{notification.node_id}`", "inline": True})

        severity_labels = {Severity.CRITICAL: "CRÍTICO", Severity.HIGH: "ALTA", Severity.MEDIUM: "MEDIA", Severity.INFO: "INFO"}
        embed["fields"].append({"name": "Severidad", "value": f"`{severity_labels.get(notification.severity, '?')}`", "inline": True})
        embed["fields"].append({"name": "Hora", "value": ts, "inline": True})

        if notification.metadata:
            for key, value_list in list(notification.metadata.items())[:5]:
                val = str(value_list)[:100]
                embed["fields"].append({"name": key.capitalize(), "value": f"`{val}`", "inline": True})

        return embed


class WhatsAppCallMeBot:
    """Envía alertas de emergencia vía WhatsApp usando CallMeBot API."""

    def __init__(self, dispatcher: ChannelDispatcher):
        self.dispatcher = dispatcher
        self.config = dispatcher.get_channel_config("whatsapp")
        self.phone = self.config.get("phone", "")
        self.api_key = self.config.get("api_key", "")
        self.api_base = self.config.get("api_base", "https://api.callmebot.com/whatsapp.php")

    def send(self, notification: Notification) -> bool:
        if not self.phone or "AQUI_VA_TU" in self.phone:
            logger.debug(f"[WhatsApp] No configurado — omitiendo: {notification.title}")
            return False

        message = self._format_message(notification)
        params = {
            "phone": self.phone,
            "text": message,
            "apikey": self.api_key
        }

        try:
            resp = requests.get(self.api_base, params=params, timeout=15)
            if resp.status_code == 200:
                logger.info(f"[WhatsApp] Alerta enviada: {notification.title}")
                return True
            else:
                logger.warning(f"[WhatsApp] HTTP {resp.status_code}: {resp.text[:100]}")
                return False
        except Exception as e:
            logger.error(f"[WhatsApp] Error: {e}")
            return False

    def _format_message(self, notification: Notification) -> str:
        emoji = EMOJIS.get(notification.event_type, "\U0001f514")
        severity_label = {Severity.CRITICAL: "CRÍTICO", Severity.HIGH: "ALTA", Severity.MEDIUM: "MEDIA", Severity.INFO: "INFO"}
        sev = severity_label.get(notification.severity, "?")

        lines = [
            f"{emoji} *AURA — {notification.title}*",
            f"_{sev}_",
            "",
            notification.message[:500]
        ]

        if notification.node_id:
            lines.append(f"\nNodo: {notification.node_id}")

        if notification.metadata:
            for k, v in list(notification.metadata.items())[:3]:
                lines.append(f"{k}: {str(v)[:80]}")

        lines.append(f"\n{datetime.now().strftime('%H:%M:%S')}")
        return "\n".join(lines)


# ═══════════════════════════════════════════════
# TELEMETRÍA Y RATE LIMITER
# ═══════════════════════════════════════════════

class RateLimiter:
    def __init__(self, max_per_hour: int = 30, max_per_day: int = 200):
        self.max_per_hour = max_per_hour
        self.max_per_day = max_per_day
        self.hourly: deque = deque(maxlen=3600)
        self.daily: deque = deque(maxlen=86400)

    def can_send(self) -> bool:
        now = time.time()
        while self.hourly and now - self.hourly[0] > 3600:
            self.hourly.popleft()
        while self.daily and now - self.daily[0] > 86400:
            self.daily.popleft()
        return len(self.hourly) < self.max_per_hour and len(self.daily) < self.max_per_day

    def register_send(self):
        now = time.time()
        self.hourly.append(now)
        self.daily.append(now)

    def get_stats(self) -> Dict:
        return {"sent_this_hour": len(self.hourly), "max_per_hour": self.max_per_hour,
                "sent_today": len(self.daily), "max_per_day": self.max_per_day}


class TelemetryCollector:
    def __init__(self, cache_path: Path = TELEMETRY_CACHE):
        self.cache_path = cache_path
        self.data = self._load()

    def _load(self) -> Dict:
        if self.cache_path.exists():
            try:
                with open(self.cache_path, 'r') as f:
                    return json.load(f)
            except: pass
        return {"started_at": datetime.now().isoformat(), "nodes_total": 0, "nodes_online": 0,
                "nodes_offline": 0, "tasks_completed": 0, "tasks_failed": 0, "threats_blocked": 0,
                "intrusions_detected": 0, "notifications_sent": 0, "uptime_hours": 0}

    def _save(self):
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_path, 'w') as f:
                json.dump(self.data, f, indent=2)
        except: pass

    def record_event(self, event_type: EventType, node_id: str = None):
        if event_type == EventType.TASK_COMPLETED: self.data["tasks_completed"] += 1
        elif event_type == EventType.INTRUSION_DETECTED: self.data["intrusions_detected"] += 1
        elif event_type == EventType.THREAT_BLOCKED: self.data["threats_blocked"] += 1
        elif event_type == EventType.NODE_DISCONNECTED: self.data["nodes_offline"] += 1
        elif event_type == EventType.NODE_JOINED: self.data["nodes_online"] += 1; self.data["nodes_total"] += 1
        self.data["notifications_sent"] += 1
        started = datetime.fromisoformat(self.data["started_at"])
        self.data["uptime_hours"] = round((datetime.now() - started).total_seconds() / 3600, 1)
        self._save()

    def get_summary(self) -> str:
        now = datetime.now()
        return (
            f"**AURA — Resumen Diario de Telemetría**\n"
            f"Fecha: {now.strftime('%d/%m/%Y')} {now.strftime('%H:%M:%S')}\n"
            f"Uptime: {self.data.get('uptime_hours', 0):.1f}h\n\n"
            f"**ESTADO DE NODOS**\n"
            f"Online: {self.data.get('nodes_online', 0)} | "
            f"Offline: {self.data.get('nodes_offline', 0)} | "
            f"Total: {self.data.get('nodes_total', 0)}\n\n"
            f"**ACTIVIDAD**\n"
            f"Tareas OK: {self.data.get('tasks_completed', 0)} | "
            f"Fallidas: {self.data.get('tasks_failed', 0)}\n"
            f"Amenazas: {self.data.get('threats_blocked', 0)} | "
            f"Intrusiones: {self.data.get('intrusions_detected', 0)}\n\n"
            f"_AURA Notification Bridge v2.0_"
        )


# ═══════════════════════════════════════════════
# NOTIFICATION BRIDGE (CHANNEL-AGNOSTIC)
# ═══════════════════════════════════════════════

class NotificationBridge:
    """
    Puente de notificaciones multicanal.
    - Sin dependencia de Telegram
    - Usa ChannelDispatcher + canales configurables
    - Priorización: alertas críticas → WhatsApp, logs → Discord
    """

    def __init__(self, config_path: str = None):
        self.dispatcher = ChannelDispatcher(config_path)
        self.rate_limiter = RateLimiter(**self.dispatcher.get_rate_limits())
        self.telemetry = TelemetryCollector()
        self.running = False
        self.scheduler_thread = None
        self.lock = threading.Lock()
        self.event_handlers: Dict[str, List[Callable]] = {}

        # Inicializar destinos según configuración
        self.channels = {}
        if "discord" in self.dispatcher.active_channels:
            self.channels["discord"] = DiscordWebhook(self.dispatcher)
        if "whatsapp" in self.dispatcher.active_channels:
            self.channels["whatsapp"] = WhatsAppCallMeBot(self.dispatcher)

        logger.info(f"NotificationBridge v2.0 — Canales activos: {list(self.channels.keys())}")
        if not self.channels:
            logger.warning("NINGÚN canal configurado. Solo logging local.")

    def _dispatch_to_channels(self, notification: Notification):
        """Envía la notificación a los canales que correspondan según routes."""
        for channel_name, channel in self.channels.items():
            if self.dispatcher.should_route_to_channel(channel_name, notification):
                if self.rate_limiter.can_send():
                    try:
                        success = channel.send(notification)
                        if success:
                            notification.sent_channels.append(channel_name)
                            self.rate_limiter.register_send()
                    except Exception as e:
                        logger.error(f"[{channel_name}] Error: {e}")
                else:
                    logger.warning(f"Rate limit alcanzado para {channel_name}")

    def _dispatch(self, notification: Notification):
        with self.lock:
            self.telemetry.record_event(notification.event_type, notification.node_id)

            log_msg = f"[{notification.severity.value.upper()}] {notification.title}"
            if notification.severity == Severity.CRITICAL: logger.critical(log_msg)
            elif notification.severity == Severity.HIGH: logger.error(log_msg)
            elif notification.severity == Severity.MEDIUM: logger.warning(log_msg)
            else: logger.info(log_msg)

            self._dispatch_to_channels(notification)
            self._save_to_history(notification)
            self._run_handlers(notification)

    def _save_to_history(self, notification: Notification):
        try:
            history = []
            if NOTIFICATION_LOG.exists():
                with open(NOTIFICATION_LOG, 'r') as f:
                    history = json.load(f)
            history.append({
                "event_type": notification.event_type.value, "severity": notification.severity.value,
                "title": notification.title, "message": notification.message[:200],
                "node_id": notification.node_id, "timestamp": notification.timestamp,
                "sent_channels": notification.sent_channels
            })
            if len(history) > MAX_EVENTS_RETENTION:
                history = history[-MAX_EVENTS_RETENTION:]
            with open(NOTIFICATION_LOG, 'w') as f:
                json.dump(history, f, indent=2)
        except Exception as e:
            logger.error(f"Error guardando historial: {e}")

    def _run_handlers(self, notification: Notification):
        event_name = notification.event_type.value
        handlers = self.event_handlers.get("*", []) + self.event_handlers.get(event_name, [])
        for handler in handlers:
            try: handler(notification)
            except Exception as e: logger.error(f"Error en handler: {e}")

    # ─── Eventos Públicos ───

    def notify_node_disconnected(self, node_id: str, ip: str = None, last_seen: str = None) -> Notification:
        n = Notification(event_type=EventType.NODE_DISCONNECTED, severity=Severity.HIGH,
            title="NODO DESCONECTADO",
            message=f"El nodo `{node_id}` perdió conexión con AURA." +
                    (f"\nIP: `{ip}`" if ip else "") + (f"\nÚltimo avistamiento: {last_seen}" if last_seen else ""),
            node_id=node_id, metadata={"ip": ip, "last_seen": last_seen})
        self._dispatch(n); return n

    def notify_intrusion_detected(self, device_mac: str, device_ip: str, network: str, vendor: str = "Desconocido") -> Notification:
        n = Notification(event_type=EventType.INTRUSION_DETECTED, severity=Severity.CRITICAL,
            title="INTRUSIÓN DETECTADA",
            message=f"Dispositivo NO AUTORIZADO en `{network}`\nMAC: `{device_mac}`\nIP: `{device_ip}`\nVendor: {vendor}",
            metadata={"mac": device_mac, "ip": device_ip, "network": network, "vendor": vendor})
        self._dispatch(n); return n

    def notify_task_completed(self, task_id: str, module: str, node_id: str, result: str = "Éxito") -> Notification:
        n = Notification(event_type=EventType.TASK_COMPLETED, severity=Severity.INFO,
            title="TAREA COMPLETADA",
            message=f"Módulo: {module}\nNodo: `{node_id}`\nResultado: {result}",
            node_id=node_id, metadata={"task_id": task_id, "module": module})
        self._dispatch(n); return n

    def notify_threat_blocked(self, threat_type: str, source: str, target: str, severity: Severity = Severity.HIGH) -> Notification:
        n = Notification(event_type=EventType.THREAT_BLOCKED, severity=severity,
            title="AMENAZA BLOQUEADA",
            message=f"Gatekeeper bloqueó amenaza.\nTipo: {threat_type}\nOrigen: `{source}`\nDestino: `{target}`",
            metadata={"threat_type": threat_type, "source": source, "target": target})
        self._dispatch(n); return n

    def notify_node_joined(self, node_id: str, ip: str, role: str = "mobile") -> Notification:
        n = Notification(event_type=EventType.NODE_JOINED, severity=Severity.INFO,
            title="NODO CONECTADO",
            message=f"Nuevo nodo en el swarm.\nID: `{node_id}`\nIP: `{ip}`\nRol: {role}",
            node_id=node_id, metadata={"ip": ip, "role": role})
        self._dispatch(n); return n

    # ─── Handlers e integración ───

    def register_handler(self, event_type: str, handler: Callable):
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)

    def listen_event_manager(self, event_manager=None):
        if event_manager is None:
            try:
                sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "AURA_Core"))
                from event_manager import EventManager
                event_manager = EventManager()
            except ImportError:
                logger.warning("EventManager no disponible.")
                return
        event_manager.on("device_new", lambda e: self._handle_aura_event(e))
        event_manager.on("device_disappeared", lambda e: self._handle_aura_event(e))
        event_manager.on("threat_detected", lambda e: self._handle_aura_event(e))
        event_manager.on("task_completed", lambda e: self._handle_aura_event(e))
        logger.info("Conectado al EventManager de AURA")

    def _handle_aura_event(self, event: Dict):
        et = event.get("type", "")
        try:
            if et == "device_new":
                d = event.get("device", {})
                self.notify_intrusion_detected(d.get("mac", "?"), d.get("ip", "?"),
                    event.get("network", {}).get("name", "?"), d.get("vendor", "?"))
            elif et == "device_disappeared":
                d = event.get("device", {})
                self.notify_node_disconnected(d.get("mac", "?"), d.get("ip"), event.get("timestamp"))
            elif et == "task_completed":
                t = event.get("task", {})
                self.notify_task_completed(t.get("id", "?"), t.get("module", "?"), t.get("node_id", "?"),
                    "Éxito" if t.get("success", True) else "Fallo")
            elif et == "threat_detected":
                t = event.get("threat", {})
                sev = Severity.CRITICAL if t.get("severity") == "critical" else Severity.HIGH
                self.notify_threat_blocked(t.get("type", "?"), t.get("source", "?"),
                    event.get("device", {}).get("mac", "?"), sev)
        except Exception as e:
            logger.error(f"Error manejando evento AURA: {e}")

    # ─── Resumen Diario ───

    def send_daily_summary(self) -> bool:
        logger.info("Generando resumen diario...")
        summary_text = self.telemetry.get_summary()
        success = False

        # Enviar a Discord (embed) y WhatsApp (texto, si está configurado)
        for channel_name, channel in self.channels.items():
            try:
                if channel_name == "discord":
                    # Simular notificación para el embed
                    n = Notification(event_type=EventType.DAILY_SUMMARY, severity=Severity.INFO,
                        title="Resumen Diario de Telemetría", message=summary_text)
                    if channel.send(n):
                        success = True
                elif channel_name == "whatsapp":
                    # WhatsApp solo recibe resumen si es el único canal
                    pass
            except Exception as e:
                logger.error(f"[{channel_name}] Error enviando resumen: {e}")
        return success

    def _daily_summary_scheduler(self):
        while self.running:
            try:
                now = datetime.now()
                target = now.replace(hour=23, minute=59, second=0, microsecond=0)
                if now >= target: target += timedelta(days=1)
                secs = (target - now).total_seconds()
                if secs < 60:
                    time.sleep(secs)
                    self.send_daily_summary()
                    time.sleep(120)
                else:
                    time.sleep(min(3600, secs - 60))
            except Exception as e:
                logger.error(f"Error en scheduler: {e}")
                time.sleep(60)

    # ─── Ciclo de Vida ───

    def start(self):
        if self.running: return
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._daily_summary_scheduler, daemon=True)
        self.scheduler_thread.start()
        logger.info("NotificationBridge v2.0 iniciado")
        logger.info(f"  Canales: {list(self.channels.keys()) or 'NINGUNO — solo logging'}")
        logger.info(f"  Discord: {'✅' if 'discord' in self.channels else '❌'}  WhatsApp: {'✅' if 'whatsapp' in self.channels else '❌'}")
        logger.info("  Resumen diario: programado a las 23:59")

    def stop(self):
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        logger.info("NotificationBridge detenido")

    def get_status(self) -> Dict:
        active = [n for n, c in self.channels.items()]
        return {"running": self.running, "active_channels": active,
                "rate_limiter": self.rate_limiter.get_stats()}


# ═══════════════════════════════════════════════
# PUNTO DE ENTRADA
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AURA Notification Bridge v2.0")
    parser.add_argument("--config", help="Ruta a channels.yaml")
    parser.add_argument("--test", action="store_true", help="Enviar notificaciones de prueba")
    parser.add_argument("--summary", action="store_true", help="Enviar resumen diario ahora")
    args = parser.parse_args()

    bridge = NotificationBridge(config_path=args.config)

    if args.test:
        print("Enviando notificaciones de prueba...")
        print(f"  Canales activos: {list(bridge.channels.keys())}")
        bridge.notify_node_disconnected("nodo-test-01", "192.168.1.100")
        bridge.notify_intrusion_detected("AA:BB:CC:DD:EE:FF", "10.0.0.55", "Red Corporativa", "Huawei")
        bridge.notify_task_completed("task-001", "Venice OSINT", "nodo-test-02")
        bridge.notify_threat_blocked("Port Scan", "203.0.113.1", "nodo-test-01", Severity.CRITICAL)
        bridge.notify_node_joined("nodo-demo", "192.168.1.50", "mobile")
        print("Notificaciones enviadas. Revisa Discord/WhatsApp según configuración.")

    elif args.summary:
        bridge.send_daily_summary()

    else:
        print("=" * 55)
        print("  AURA Notification Bridge v2.0")
        print("  (Sin dependencia de Telegram)")
        print("=" * 55)
        print()
        print(f"  Canales activos: {list(bridge.channels.keys()) or 'NINGUNO'}")
        print(f"  Config: {args.config or CONFIG_PATH}")
        print()
        print("  Para probar:")
        print("    python notification_bridge.py --test")
        print("    python notification_bridge.py --summary")
        print("    python notification_bridge.py --config /ruta/channels.yaml")
        print()

        bridge.start()
        bridge.notify_node_joined("nodo-inicio", "127.0.0.1", "test")

        try:
            while True: time.sleep(1)
        except KeyboardInterrupt:
            bridge.stop()