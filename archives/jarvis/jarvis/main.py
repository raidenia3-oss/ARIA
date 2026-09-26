#!/usr/bin/env python3
import os
import sys
import time

# Ensure imports are resolved correctly from the script directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from jarvis_core import JARVISCore

def main():
    jarvis = JARVISCore()
    
    print("""
    ╔════════════════════════════════════╗
    ║   JARVIS v1.0 - Asistente Virtual  ║
    ║      Running on Termux (Celular)    ║
    ╚════════════════════════════════════╝
    """)
    
    print(f"Estado inicial: {'🟢 Online' if not jarvis.offline else '🔴 Offline'}")
    print("Escribe 'salir' para terminar, 'sync' para sincronizar con GitHub, o 'status' para verificar red.\n")
    
    while True:
        try:
            user_input = input("Tú: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() == "salir":
                print("JARVIS: Hasta luego, Raiden.")
                break
            
            if user_input.lower() == "sync":
                print("JARVIS: Sincronizando...")
                jarvis.sync_with_cloud()
                continue
            
            if user_input.lower() == "status":
                jarvis.test_connectivity()
                print(f"JARVIS: Estado actual = {'🟢 Online' if not jarvis.offline else '🔴 Offline'}")
                continue
            
            # Process input
            print("JARVIS: Procesando...", end="", flush=True)
            response = jarvis.process_input(user_input)
            
            # Print response, erasing the "Procesando..." indicator
            print(f"\rJARVIS: {response}\n")
            
            # Send message to Rocket.Chat asynchronously/silently if online
            jarvis.send_to_rocket(user_input, response)
        
        except KeyboardInterrupt:
            print("\n\nJARVIS: Apagándome... Hasta luego, Raiden.")
            break
        except Exception as e:
            print(f"\nError: {e}")

if __name__ == "__main__":
    main()
