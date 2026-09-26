#!/usr/bin/env python3
"""
SENSOR RADAR WI-FI PASIVO - Receptor UDP CSI + EventBus.
Escucha paquetes UDP en puerto 3000, procesa datos CSI,
y dispara eventos al EventBus central de AURA.
Python 3 puro, todo el ML se ejecuta en la PC.
"""
import socket
import json
import threading
import time
import sys
import os
from datetime import datetime

CSI_UDP_PORT = 3000
EVENTBUS_PORT = 3001
BUFFER_SIZE = 65535
ALERT_THRESHOLD = 0.8

class CSIEventBus:
    def __init__(self):
        self.listeners = {}
        self.log_path = os.path.join("logs", "csi_events.log")
        os.makedirs("logs", exist_ok=True)
    
    def register(self, event_type, callback):
        if event_type not in self.listeners:
            self.listeners[event_type] = []
        self.listeners[event_type].append(callback)
    
    def emit(self, event_type, data):
        event = {
            "event_type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        # Log
        with open(self.log_path, "a") as f:
            f.write(json.dumps(event) + "\n")
        # Notify listeners
        if event_type in self.listeners:
            for cb in self.listeners[event_type]:
                try:
                    cb(event)
                except Exception as e:
                    print(f"[EventBus] Error en callback: {e}")
        print(f"[EventBus] {event_type} - {data.get('summary', {}).get('movement_score', 'N/A')}")
        return event

class CSIDecoder:
    @staticmethod
    def decode_packet(raw_data):
        try:
            payload = raw_data.decode("utf-8").strip()
            data = json.loads(payload)
            
            required = ["sensor_id", "csi_data", "subcarriers"]
            if not all(k in data for k in required):
                return None
            
            csi = data["csi_data"]
            if isinstance(csi, list) and len(csi) > 0:
                amp_mean = sum(abs(x) for x in csi) / len(csi)
                phase_vals = []
                for i, val in enumerate(csi):
                    phase_vals.append((val / (abs(val) + 0.001)) * (i % 2))
                phase_std = (sum(x*x for x in phase_vals) / len(phase_vals)) ** 0.5 if phase_vals else 0
            else:
                amp_mean = 0
                phase_std = 0
            
            data["amplitude_mean"] = round(amp_mean, 4)
            data["phase_std"] = round(phase_std, 4)
            
            prev_mean = getattr(CSIDecoder, "prev_amp_mean", amp_mean)
            delta = abs(amp_mean - prev_mean)
            CSIDecoder.prev_amp_mean = amp_mean
            
            movement_score = min(1.0, delta * 5)
            data["movement_score"] = round(movement_score, 4)
            data["presence_detected"] = movement_score > 0.15
            data["vital_signs"] = CSIDecoder._estimate_vitals(movement_score, csi)
            data["summary"] = {
                "movement_score": round(movement_score, 4),
                "presence": data["presence_detected"],
                "amplitude_mean": round(amp_mean, 4),
                "phase_std": round(phase_std, 4)
            }
            data["timestamp"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            return data
        except Exception as e:
            print(f"[CSI] Error decodificando: {e}")
            return None
    
    @staticmethod
    def _estimate_vitals(movement_score, csi):
        # Simulación de signos vitales basada en variación CSI
        if movement_score > 0.05:
            br = round(12 + (movement_score * 10), 1)
            hr = round(60 + (movement_score * 30), 1)
        else:
            br = round(14 + (hash(str(csi[:5])) % 40) / 10, 1)
            hr = round(65 + (hash(str(csi[:3])) % 60) / 10, 1)
        return {
            "breathing_rate": br,
            "heart_rate": hr,
            "confidence": round(min(0.95, movement_score + 0.1), 2)
        }

class CSIRadarServer:
    def __init__(self):
        self.eventbus = CSIEventBus()
        self.running = True
        self.stats = {"packets": 0, "alerts": 0, "errors": 0}
    
    def start_udp_server(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFFER_SIZE)
        sock.bind(("0.0.0.0", CSI_UDP_PORT))
        sock.settimeout(1.0)
        print(f"[CSI] Servidor UDP escuchando en puerto {CSI_UDP_PORT}")
        
        while self.running:
            try:
                raw_data, addr = sock.recvfrom(BUFFER_SIZE)
                self.stats["packets"] += 1
                decoded = CSIDecoder.decode_packet(raw_data)
                if decoded:
                    self._process_csi_data(decoded, addr)
            except socket.timeout:
                continue
            except Exception as e:
                self.stats["errors"] += 1
                print(f"[CSI] Error: {e}")
        sock.close()
    
    def _process_csi_data(self, data, addr):
        score = data["movement_score"]
        summary = data["summary"]
        
        if score > ALERT_THRESHOLD:
            self.stats["alerts"] += 1
            print(f"\n⚠️  ALERTA: Movimiento detectado ({score:.2f})")
            self.eventbus.emit("PHYSICAL_INTRUSION", {
                "sensor_id": data["sensor_id"],
                "source": str(addr),
                "summary": summary,
                "vital_signs": data.get("vital_signs", {}),
                "alert_level": "CRITICAL" if score > 0.95 else "HIGH"
            })
        
        self.eventbus.emit("CSI_DATA", data)
    
    def start_eventbus_http(self):
        http_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        http_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        http_sock.bind(("127.0.0.1", EVENTBUS_PORT))
        http_sock.listen(5)
        http_sock.settimeout(1.0)
        print(f"[EventBus] HTTP interno en puerto {EVENTBUS_PORT}")
        
        while self.running:
            try:
                conn, addr = http_sock.accept()
                data = conn.recv(1024)
                if data:
                    print(f"[EventBus] Conexion desde {addr}")
                conn.close()
            except socket.timeout:
                continue
        http_sock.close()
    
    def status_printer(self):
        while self.running:
            time.sleep(5)
            print(f"\n📊 [CSI Status] Paquetes: {self.stats['packets']}, "
                  f"Alertas: {self.stats['alerts']}, Errores: {self.stats['errors']}")
    
    def run(self):
        print("╔═══════════════════════════════════════════╗")
        print("║  AURA RADAR WI-FI PASIVO                  ║")
        print("║  Puerto UDP CSI: 3000                     ║")
        print("║  EventBus interno: 3001                   ║")
        print("║  Machine Learning: PC (AURA Core)          ║")
        print("╚═══════════════════════════════════════════╝")
        
        threads = [
            threading.Thread(target=self.start_udp_server, daemon=True),
            threading.Thread(target=self.start_eventbus_http, daemon=True),
            threading.Thread(target=self.status_printer, daemon=True)
        ]
        for t in threads:
            t.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[CSI] Deteniendo servidor...")
            self.running = False

if __name__ == "__main__":
    server = CSIRadarServer()
    server.run()