#!/usr/bin/env python3
"""
PUENTE EVENTBUS → DISCORD/WHATSAPP.
Escucha eventos del EventBus central y los formatea para alertas.
"""
import json
import os
import time
from datetime import datetime

EVENT_LOG = os.path.join("logs", "csi_alerts.log")
ALERT_THRESHOLD = 0.8

class AlertBridge:
    def __init__(self):
        os.makedirs("logs", exist_ok=True)
        self.alerts_sent = 0
    
    def format_alert(self, event):
        data = event.get("data", {})
        summary = data.get("summary", {})
        vitals = data.get("vital_signs", {})
        score = summary.get("movement_score", 0)
        
        lines = []
        lines.append("```")
        lines.append("⚠️ ALERTA AURA - DETECCION FISICA")
        lines.append("═" * 35)
        lines.append(f"› Evento: {event['event_type']}")
        lines.append(f"› Sensor: {data.get('sensor_id', 'N/A')}")
        lines.append(f"› Score movimiento: {score:.2f}")
        lines.append(f"› Presencia: {'✅ DETECTADA' if summary.get('presence') else '❌ NO'}")
        lines.append("")
        if vitals:
            lines.append("──SIGNOS VITALES──")
            lines.append(f"  Respiración: {vitals.get('breathing_rate', 'N/A')} rpm")
            lines.append(f"  Ritmo cardíaco: {vitals.get('heart_rate', 'N/A')} bpm")
            lines.append(f"  Confianza: {vitals.get('confidence', 0)*100:.0f}%")
        lines.append("")
        if score > 0.95:
            lines.append("🔥 NIVEL: CRITICO - Accion requerida")
        elif score > 0.8:
            lines.append("🔶 NIVEL: ALTO - Monitorear")
        else:
            lines.append("🔷 NIVEL: INFORMATIVO")
        lines.append(f"› Timestamp: {event.get('timestamp', 'N/A')}")
        lines.append("```")
        return "\n".join(lines)
    
    def handle_intrusion(self, event):
        alert_text = self.format_alert(event)
        print(alert_text)
        
        with open(EVENT_LOG, "a") as f:
            f.write(json.dumps(event) + "\n")
        
        self.alerts_sent += 1
        print(f"[AlertBridge] Alerta #{self.alerts_sent} registrada en {EVENT_LOG}")
        
    def handle_csi_data(self, event):
        data = event.get("data", {})
        score = data.get("movement_score", 0)
        if score > ALERT_THRESHOLD:
            self.handle_intrusion(event)

def main():
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
    from wifi_radar_server import CSIEventBus
    
    bridge = AlertBridge()
    eventbus = CSIEventBus()
    
    eventbus.register("PHYSICAL_INTRUSION", bridge.handle_intrusion)
    eventbus.register("CSI_DATA", bridge.handle_csi_data)
    
    print("[EventBus] Escuchando eventos (simulado)...")
    print("[EventBus] Conecta con wifi_radar_server.py para recibir datos reales")
    print()
    
    # Modo simulación
    sample_event = {
        "event_type": "PHYSICAL_INTRUSION",
        "data": {
            "sensor_id": "ESP32_01",
            "source": "192.168.1.100:3000",
            "summary": {"movement_score": 0.92, "presence": True, "amplitude_mean": 0.85, "phase_std": 0.32},
            "vital_signs": {"breathing_rate": 18.5, "heart_rate": 82.3, "confidence": 0.88},
            "alert_level": "HIGH"
        },
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    }
    bridge.handle_intrusion(sample_event)

if __name__ == "__main__":
    main()