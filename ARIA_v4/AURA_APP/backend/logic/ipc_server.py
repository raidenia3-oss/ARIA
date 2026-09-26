"""IPC Server — Escucha desde UI via named pipes"""

import asyncio
import json
import os
import threading
from pathlib import Path
from typing import Dict, Callable


class IPCServer:
    """IPC Server para comunicación UI ↔ Backend"""

    def __init__(self, pipe_name: str = "aria_ipc"):
        self.pipe_name = pipe_name
        self.pipe_path = self._get_pipe_path()
        self.handlers: Dict[str, Callable] = {}
        self.running = False
        self._thread = None

    def _get_pipe_path(self) -> str:
        if os.name == 'nt':
            return rf'\\.\pipe\{self.pipe_name}'
        return f'/tmp/{self.pipe_name}'

    def register_handler(self, event_type: str, handler: Callable):
        self.handlers[event_type] = handler

    async def start(self):
        """Inicia servidor IPC en thread"""
        self.running = True
        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()
        print(f"[IPCServer] Escuchando en {self.pipe_path}")

    def _run_server(self):
        """Loop del servidor IPC"""
        while self.running:
            try:
                if os.name == 'nt':
                    self._run_windows()
                else:
                    self._run_unix()
            except Exception as e:
                if self.running:
                    print(f"[IPCServer] Error: {e}")
                import time
                time.sleep(0.5)

    def _run_windows(self):
        """Windows named pipe server"""
        try:
            import msvcrt
            import win32pipe
            import win32file

            pipe = win32pipe.CreateNamedPipe(
                self.pipe_path,
                win32pipe.PIPE_ACCESS_DUPLEX,
                win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_WAIT,
                1, 65536, 65536, 0, None,
            )
            win32pipe.ConnectNamedPipe(pipe, None)

            try:
                hr, data = win32file.ReadFile(pipe, 65536)
                if hr == 0:
                    message = json.loads(data.decode('utf-8'))
                    response = self._handle_message(message)
                    win32file.WriteFile(pipe, json.dumps(response).encode('utf-8'))
            finally:
                win32pipe.DisconnectNamedPipe(pipe)
        except ImportError:
            pass  # pywin32 no disponible
        except Exception as e:
            print(f"[IPCServer] Win pipe error: {e}")

    def _run_unix(self):
        """Unix socket server"""
        sock_path = self.pipe_path
        if os.path.exists(sock_path):
            os.unlink(sock_path)

        import socket
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(sock_path)
        server.listen(1)
        server.settimeout(1.0)

        try:
            conn, _ = server.accept()
            data = conn.recv(65536)
            if data:
                message = json.loads(data.decode('utf-8'))
                response = self._handle_message(message)
                conn.sendall(json.dumps(response).encode('utf-8'))
            conn.close()
        except socket.timeout:
            pass
        finally:
            server.close()

    def _handle_message(self, message: dict) -> dict:
        """Procesa mensaje IPC"""
        event_type = message.get('type', 'unknown')
        handler = self.handlers.get(event_type)

        if handler:
            try:
                result = handler(message)
                return {'status': 'ok', 'result': result}
            except Exception as e:
                return {'status': 'error', 'error': str(e)}

        return {'status': 'ok', 'result': {'echo': message}}

    async def stop(self):
        self.running = False
        print("[IPCServer] Detenido")


class IPCClient:
    """IPC Client para enviar mensajes al backend"""

    def __init__(self, pipe_name: str = "aria_ipc"):
        self.pipe_name = pipe_name
        self.pipe_path = (
            rf'\\.\pipe\{pipe_name}' if os.name == 'nt' else f'/tmp/{pipe_name}'
        )

    def send_message(self, message: dict) -> dict:
        """Envía mensaje IPC y recibe respuesta"""
        import json as json_lib

        try:
            if os.name == 'nt':
                return self._send_windows(message)
            else:
                return self._send_unix(message)
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def _send_windows(self, message: dict) -> dict:
        try:
            import win32file
            import win32pipe

            pipe = win32file.CreateFile(
                self.pipe_path,
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0, None, win32file.OPEN_EXISTING, 0, None,
            )
            try:
                win32file.WriteFile(pipe, json_lib.dumps(message).encode('utf-8'))
                hr, data = win32file.ReadFile(pipe, 65536)
                return json_lib.loads(data.decode('utf-8'))
            finally:
                win32file.CloseHandle(pipe)
        except ImportError:
            return {'status': 'error', 'error': 'pywin32 required'}

    def _send_unix(self, message: dict) -> dict:
        try:
            import socket
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.connect(self.pipe_path)
            client.sendall(json_lib.dumps(message).encode('utf-8'))
            data = client.recv(65536)
            client.close()
            return json_lib.loads(data.decode('utf-8'))
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
