import asyncio  
import websockets  
import subprocess  
import os  
  
SERVER_HOST = "192.168.3.10"  
SERVER_PORT = 8765  
  
async def handler(websocket):  
    print(f"Cliente conectado: {websocket.remote_address}")  
    try:  
        async for message in websocket:  
            print(f"Mensaje recibido: {message}")  
            if message.startswith("run:"):  
                command = message[4:]  
                print(f"Ejecutando en PC: {command}")  
                try:  
                    result = subprocess.run(command, shell=True, capture_output=True, text=True, encoding='utf-8', errors='ignore')  
                    output = result.stdout + result.stderr  
                    await websocket.send(f"Salida del comando:\n{output}")  
                except Exception as e:  
                    await websocket.send(f"Error al ejecutar: {e}")  
            else:  
                response = f"AURA (PC) recibe: {message}"  
                await websocket.send(response)  
    except websockets.exceptions.ConnectionClosed:  
        print("Cliente desconectado")  
  
async def main():  
    print(f"Servidor AURA (con ejecucion) iniciado en ws://{SERVER_HOST}:{SERVER_PORT}")  
    print("Esperando conexiones...")  
    async with websockets.serve(handler, SERVER_HOST, SERVER_PORT):  
        await asyncio.Future()  
  
asyncio.run(main()) 
