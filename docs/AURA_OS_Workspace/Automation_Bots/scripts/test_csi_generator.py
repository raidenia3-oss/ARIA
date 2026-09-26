#!/usr/bin/env python3
"""
SIMULADOR DE ENTRADA CSI - Genera paquetes UDP con datos CSI distorsionados.
Emula respiración, movimiento y presencia humana para pruebas del radar WiFi.
"""
import socket
import json
import time
import math
import random
from datetime import datetime

CSI_UDP_PORT = 3000
CSI_UDP_HOST = "127.0.0.1"
SUBCARRIERS = 64

SCENARIOS = {
    "empty": {"name": "Sala vacía", "amplitude": 0.12, "noise": 0.05, "movement_chance": 0.02},
    "breathing": {"name": "Persona respirando", "amplitude": 0.35, "noise": 0.08, "movement_chance": 0.1},
    "walking": {"name": "Persona caminando", "amplitude": 0.75, "noise": 0.15, "movement_chance": 0.6},
    "intrusion": {"name": "INTRUSIÓN - Movimiento brusco", "amplitude": 0.95, "noise": 0.2, "movement_chance": 0.9}
}

def generate_csi_packet(scenario="breathing", sensor_id="ESP32_01"):
    cfg = SCENARIOS.get(scenario, SCENARIOS["breathing"])
    csi_data = []
    t = time.time()
    for i in range(SUBCARRIERS):
        base = cfg["amplitude"] * math.sin(t * (1 + i/SUBCARRIERS) + i * 0.1)
        noise = random.gauss(0, cfg["noise"])
        if random.random() < cfg["movement_chance"]:
            spike = random.uniform(-0.5, 0.5) * cfg["amplitude"]
            csi_data.append(round(base + noise + spike, 4))
        else:
            csi_data.append(round(base + noise, 4))
    
    packet = {
        "sensor_id": sensor_id,
        "subcarriers": SUBCARRIERS,
        "csi_data": csi_data,
        "scenario": scenario,
        "simulated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    }
    return json.dumps(packet)

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print("╔═══════════════════════════════════════════╗")
    print("║  AURA CSI GENERATOR - SIMULADOR           ║")
    print("║  Enviando a puerto 3000                    ║")
    print("╚═══════════════════════════════════════════╝")
    print("")
    print("Escenarios disponibles:")
    for k, v in SCENARIOS.items():
        print(f"  [{k}] {v['name']}")
    print("")
    print("Usa: python test_csi_generator.py [escenario]")
    print("Ejemplo: python test_csi_generator.py intrusion")
    print("")
    
    import sys
    scenario = sys.argv[1] if len(sys.argv) > 1 else "breathing"
    if scenario not in SCENARIOS:
        print(f"Escenario '{scenario}' no valido. Usando 'breathing'")
        scenario = "breathing"
    
    print(f"Enviando escenario: {SCENARIOS[scenario]['name']}")
    print(f"Ráfagas de {SUBCARRIERS} subportadoras cada 0.5s")
    print("Presiona Ctrl+C para detener\n")
    
    try:
        while True:
            packet = generate_csi_packet(scenario)
            sock.sendto(packet.encode(), (CSI_UDP_HOST, CSI_UDP_PORT))
            print(f"📡 Enviado: {scenario} | {len(packet)} bytes")
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[Simulador] Detenido.")
    finally:
        sock.close()

if __name__ == "__main__":
    main()