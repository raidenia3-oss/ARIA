"""IPC Client — Comunica UI con backend"""

import json
import os
from typing import Dict


class IPCClient:
    """IPC Client para enviar mensajes al backend"""

    def __init__(self, pipe_name: str = "aria_ipc"):
        self.pipe_name = pipe_name
        self.pipe_path = (
            rf'\\.\pipe\{pipe_name}' if os.name == 'nt' else f'/tmp/{pipe_name}'
        )

    def send_message(self, message: dict) -> dict:
        try:
            if os.name == 'nt':
                return self._send_windows(message)
            return self._send_unix(message)
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def _send_windows(self, message: dict) -> dict:
        try:
            import win32file, win32pipe
            pipe = win32file.CreateFile(
                self.pipe_path,
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0, None, win32file.OPEN_EXISTING, 0, None,
            )
            try:
                win32file.WriteFile(pipe, json.dumps(message).encode('utf-8'))
                hr, data = win32file.ReadFile(pipe, 65536)
                return json.loads(data.decode('utf-8'))
            finally:
                win32file.CloseHandle(pipe)
        except ImportError:
            return {'status': 'error', 'error': 'pywin32 required'}

    def _send_unix(self, message: dict) -> dict:
        try:
            import socket
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.connect(self.pipe_path)
            client.sendall(json.dumps(message).encode('utf-8'))
            data = client.recv(65536)
            client.close()
            return json.loads(data.decode('utf-8'))
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
