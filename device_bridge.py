"""AURA Device Bridge — cross-device sync and app introspection.

Features:
- Local device discovery via mDNS/Bonjour
- Chrome extension bridge via WebSocket/native messaging
- App introspection: list installed apps, read/write app code
- Cross-device sync: settings, plugins, configurations
- Remote code modification and hot-reload

Usage:
    from device_bridge import DeviceBridge
    bridge = DeviceBridge()
    bridge.start()
    devices = bridge.discover_devices()
    apps = bridge.get_device_apps(devices[0]['id'])
"""

from __future__ import annotations

import json
import os
import platform
import socket
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional, Tuple


class DeviceInfo:
    def __init__(self, device_id: str, name: str, platform: str, ip: str, port: int) -> None:
        self.device_id = device_id
        self.name = name
        self.platform = platform
        self.ip = ip
        self.port = port
        self.last_seen = time.time()
        self.apps: List[Dict[str, Any]] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "platform": self.platform,
            "ip": self.ip,
            "port": self.port,
            "last_seen": self.last_seen,
            "apps": self.apps,
        }


class AppInfo:
    def __init__(self, app_id: str, name: str, path: str, app_type: str, version: str = "1.0.0") -> None:
        self.app_id = app_id
        self.name = name
        self.path = path
        self.app_type = app_type
        self.version = version
        self.code: Optional[str] = None
        self.permissions: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "app_id": self.app_id,
            "name": self.name,
            "path": self.path,
            "app_type": self.app_type,
            "version": self.version,
            "permissions": self.permissions,
        }


class DeviceBridge:
    def __init__(self, port: int = 48799) -> None:
        self.port = port
        self.devices: Dict[str, DeviceInfo] = {}
        self.local_device: Optional[DeviceInfo] = None
        self.running = False
        self._lock = threading.Lock()
        self._server_thread: Optional[threading.Thread] = None
        self._discovery_thread: Optional[threading.Thread] = None
        self._callbacks: List[Any] = []
        self._chrome_bridge: Optional[Any] = None

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._server_thread = threading.Thread(target=self._server_loop, daemon=True)
        self._server_thread.start()
        self._discovery_thread = threading.Thread(target=self._discovery_loop, daemon=True)
        self._discovery_thread.start()

    def stop(self) -> None:
        self.running = False
        if self._server_thread:
            self._server_thread.join(timeout=1)
        if self._discovery_thread:
            self._discovery_thread.join(timeout=1)

    def _server_loop(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", self.port))
            sock.listen(5)
            sock.settimeout(1)
            while self.running:
                try:
                    conn, addr = sock.accept()
                    threading.Thread(target=self._handle_connection, args=(conn, addr), daemon=True).start()
                except socket.timeout:
                    continue
                except Exception:
                    break
        except Exception:
            pass
        finally:
            try:
                sock.close()
            except Exception:
                pass

    def _handle_connection(self, conn: socket.socket, addr: Tuple[str, int]) -> None:
        try:
            conn.settimeout(5)
            data = conn.recv(4096)
            if not data:
                return
            try:
                msg = json.loads(data.decode("utf-8"))
                response = self._handle_message(msg)
                conn.sendall(json.dumps(response).encode("utf-8"))
            except Exception:
                pass
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _handle_message(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        action = msg.get("action")
        if action == "ping":
            return {"action": "pong", "device_id": self.local_device.device_id if self.local_device else "unknown"}
        if action == "get_apps":
            device_id = msg.get("device_id")
            return {"action": "apps", "apps": self._get_local_apps()}
        if action == "get_app_code":
            app_path = msg.get("path")
            return {"action": "app_code", "code": self._read_app_code(app_path)}
        if action == "set_app_code":
            app_path = msg.get("path")
            code = msg.get("code")
            return {"action": "app_code_result", "success": self._write_app_code(app_path, code)}
        if action == "list_devices":
            return {"action": "devices", "devices": [d.to_dict() for d in self.devices.values()]}
        return {"action": "error", "message": "unknown action"}

    def _discovery_loop(self) -> None:
        while self.running:
            self._discover_local()
            self._discover_network()
            time.sleep(10)

    def _discover_local(self) -> None:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        system = platform.system()
        device_id = f"local-{hostname}"
        self.local_device = DeviceInfo(device_id, hostname, system, ip, self.port)
        with self._lock:
            self.devices[device_id] = self.local_device

    def _discover_network(self) -> None:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(2)
            sock.sendto(b"AURA_DISCOVER", ("255.255.255.255", self.port))
            while True:
                try:
                    data, addr = sock.recvfrom(1024)
                    msg = json.loads(data.decode("utf-8"))
                    if msg.get("action") == "pong":
                        device_id = msg.get("device_id", addr[0])
                        device = DeviceInfo(device_id, device_id, "unknown", addr[0], self.port)
                        with self._lock:
                            self.devices[device_id] = device
                except socket.timeout:
                    break
                except Exception:
                    break
        except Exception:
            pass
        finally:
            try:
                sock.close()
            except Exception:
                pass

    def _get_local_apps(self) -> List[Dict[str, Any]]:
        apps: List[Dict[str, Any]] = []
        try:
            if platform.system() == "Windows":
                base = os.path.expandvars(r"%LOCALAPPDATA%")
                candidates = [base]
            elif platform.system() == "Darwin":
                candidates = ["/Applications"]
            else:
                candidates = ["/usr/share/applications", os.path.expanduser("~/.local/share/applications")]
            for base in candidates:
                if os.path.isdir(base):
                    for entry in os.listdir(base):
                        if entry.endswith((".py", ".js", ".ts", ".json", ".app", ".exe")):
                            apps.append(AppInfo(entry, entry, os.path.join(base, entry), "app").to_dict())
        except Exception:
            pass
        return apps

    def _read_app_code(self, path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception:
            return ""

    def _write_app_code(self, path: str, code: str) -> bool:
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(code)
            return True
        except Exception:
            return False

    def discover_devices(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [d.to_dict() for d in self.devices.values()]

    def get_device_apps(self, device_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            device = self.devices.get(device_id)
        if not device:
            return []
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((device.ip, device.port))
            msg = {"action": "get_apps", "device_id": device_id}
            sock.sendall(json.dumps(msg).encode("utf-8"))
            data = sock.recv(65536)
            sock.close()
            if not data:
                return []
            msg = json.loads(data.decode("utf-8"))
            return msg.get("apps", [])
        except Exception:
            return []

    def get_app_code(self, device_id: str, app_path: str) -> str:
        with self._lock:
            device = self.devices.get(device_id)
        if not device:
            return ""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((device.ip, device.port))
            msg = {"action": "get_app_code", "path": app_path, "device_id": device_id}
            sock.sendall(json.dumps(msg).encode("utf-8"))
            data = sock.recv(65536)
            sock.close()
            if not data:
                return ""
            msg = json.loads(data.decode("utf-8"))
            return msg.get("code", "")
        except Exception:
            return ""

    def set_app_code(self, device_id: str, app_path: str, code: str) -> bool:
        with self._lock:
            device = self.devices.get(device_id)
        if not device:
            return False
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((device.ip, device.port))
            msg = {"action": "set_app_code", "path": app_path, "code": code, "device_id": device_id}
            sock.sendall(json.dumps(msg).encode("utf-8"))
            data = sock.recv(1024)
            sock.close()
            if not data:
                return False
            msg = json.loads(data.decode("utf-8"))
            return msg.get("success", False)
        except Exception:
            return False

    def add_callback(self, cb) -> None:
        self._callbacks.append(cb)

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            count = len(self.devices)
        return {
            "running": self.running,
            "devices": count,
            "local": self.local_device.to_dict() if self.local_device else None,
        }
