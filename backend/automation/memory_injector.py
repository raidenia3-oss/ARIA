"""BLOQUE 76 - Local Game/App Process Memory Inspector & Direct State Injector Engine.

Subsistema 100% local para inspeccionar, escanear y modificar estados de procesos
del propio sistema operativo sin depender de servicios en la nube.

Arquitectura:
- _BaseBackend / InMemoryBackend / Win32Backend: acceso a memoria de procesos.
  * Win32Backend -> ctypes + Win32 API nativa (OpenProcess, ReadProcessMemory,
    WriteProcessMemory) sin pymem.
  * InMemoryBackend -> backend simulado 100% en RAM, usado por tests y en
    plataformas no-Windows (determinismo y portabilidad).
- SecurityScope: allowlist explicita de PIDs/nombres; valida tamaños y patrones.
- MemoryInspector: API unificada (list/scan/read/write/watch/inject/status),
  thread-safe (lock) con patron singleton.
- parse_pattern/find_pattern: busqueda de firmas byte/hex sobre regiones.
- Watchpoint: vigilancia de direcciones con polling y callbacks on_change.

100% offline. No expone tokens ni credenciales.
"""
from __future__ import annotations

import os
import sys
import platform
import ctypes
import ctypes.wintypes as wintypes
import struct
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class ProcessInfo:
    pid: int
    name: str = ""
    is_64bit: bool = False
    status: str = "running"


@dataclass
class MemoryRegion:
    start: int
    end: int
    protect: int = 0
    data: bytearray = field(default_factory=bytearray)

    @property
    def size(self) -> int:
        if self.data:
            return len(self.data)
        return max(0, self.end - self.start)


@dataclass
class ScanResult:
    address: int
    data_hex: str
    region_start: int = 0


@dataclass
class Watchpoint:
    id: int = 0
    pid: int = 0
    address: int = 0
    size: int = 4
    dtype: str = "int32"
    interval: float = 0.5
    last_value: Any = None
    enabled: bool = True
    on_change: Optional[Callable[[Any, Any], None]] = None


_DTYPE_MAP: Dict[str, Tuple[str, int]] = {
    "int8": ("b", 1), "uint8": ("B", 1),
    "int16": ("h", 2), "uint16": ("H", 2),
    "int32": ("i", 4), "uint32": ("I", 4),
    "int64": ("q", 8), "uint64": ("Q", 8),
    "float32": ("f", 4), "float64": ("d", 8),
}


def encode_value(value: Any, dtype: str = "int32") -> bytes:
    if dtype not in _DTYPE_MAP:
        raise ValueError(f"Unsupported dtype: {dtype}")
    fmt, size = _DTYPE_MAP[dtype]
    if dtype.startswith("float"):
        return struct.pack(fmt, float(value))
    if dtype == "string":
        raise ValueError("Use encode_string for string dtype")
    return struct.pack(fmt, int(value))


def encode_string(value: str, max_size: int = 64) -> bytes:
    raw = value.encode("utf-8", errors="ignore")
    if len(raw) > max_size:
        raw = raw[:max_size]
    return raw + b"\x00" * (max_size - len(raw))


def decode_value(data: bytes, dtype: str = "int32") -> Any:
    if dtype == "string":
        return data.rstrip(b"\x00").decode("utf-8", errors="ignore")
    if dtype not in _DTYPE_MAP:
        raise ValueError(f"Unsupported dtype: {dtype}")
    fmt, size = _DTYPE_MAP[dtype]
    if len(data) < size:
        raise ValueError(f"Not enough bytes ({len(data)}) for dtype {dtype} ({size})")
    if dtype.startswith("float"):
        return struct.unpack(fmt, data[:size])[0]
    return struct.unpack(fmt, data[:size])[0]

class _BaseBackend:
    def list_processes(self) -> List[ProcessInfo]:
        raise NotImplementedError

    def open_process(self, pid: int) -> Any:
        raise NotImplementedError

    def close_process(self, handle: Any) -> None:
        raise NotImplementedError

    def read_memory(self, handle: Any, address: int, size: int) -> bytes:
        raise NotImplementedError

    def write_memory(self, handle: Any, address: int, data: bytes) -> int:
        raise NotImplementedError

    def virtual_query(self, handle: Any, address: int) -> Optional[Tuple[int, int, int]]:
        raise NotImplementedError


class InMemoryBackend(_BaseBackend):
    """Backend simulado 100% en RAM para tests y plataformas no-Windows."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._processes: Dict[int, ProcessInfo] = {}
        self._regions: Dict[int, List[MemoryRegion]] = {}

    def add_process(self, pid: int, name: str = "process", is_64bit: bool = False) -> ProcessInfo:
        with self._lock:
            info = ProcessInfo(pid=pid, name=name, is_64bit=is_64bit)
            self._processes[pid] = info
            self._regions.setdefault(pid, [])
            return info

    def add_region(self, pid: int, address: int, data: bytes, protect: int = 0x04) -> None:
        with self._lock:
            self._ensure(pid)
            self._regions[pid].append(MemoryRegion(start=address, end=address + len(data),
                                                    protect=protect, data=bytearray(data)))

    def _ensure(self, pid: int) -> None:
        self._processes.setdefault(pid, ProcessInfo(pid=pid))
        self._regions.setdefault(pid, [])

    def remove_process(self, pid: int) -> bool:
        with self._lock:
            if pid not in self._processes:
                return False
            self._processes.pop(pid, None)
            self._regions.pop(pid, None)
            return True

    def list_processes(self) -> List[ProcessInfo]:
        with self._lock:
            return list(self._processes.values())

    def open_process(self, pid: int) -> int:
        with self._lock:
            if pid not in self._processes:
                raise ProcessLookupError(f"Process not found: pid={pid}")
            return pid

    def close_process(self, handle: Any) -> None:
        try:
            int(handle)
        except (TypeError, ValueError):
            pass

    def _region_containing(self, pid: int, address: int, size: int) -> Optional[MemoryRegion]:
        for r in self._regions.get(pid, []):
            if r.data and r.start <= address and address + size <= r.end:
                return r
        return None

    def read_memory(self, handle: Any, address: int, size: int) -> bytes:
        pid = int(handle)
        with self._lock:
            region = self._region_containing(pid, address, size)
            if region is None:
                raise PermissionError(f"Cannot read 0x{address:x} ({size}B) of pid={pid}")
            return bytes(region.data[address - region.start: address - region.start + size])

    def write_memory(self, handle: Any, address: int, data: bytes) -> int:
        pid = int(handle)
        with self._lock:
            region = self._region_containing(pid, address, len(data))
            if region is None:
                raise PermissionError(f"Cannot write 0x{address:x} ({len(data)}B) of pid={pid}")
            region.data[address - region.start: address - region.start + len(data)] = data
            return len(data)

    def virtual_query(self, handle: Any, address: int) -> Optional[Tuple[int, int, int]]:
        pid = int(handle)
        with self._lock:
            for r in self._regions.get(pid, []):
                if r.start <= address < r.end:
                    return (r.start, r.end, r.protect)
        return None

    def reset(self) -> None:
        with self._lock:
            self._processes.clear()
            self._regions.clear()

class Win32Backend(_BaseBackend):
    """Backend nativo Windows usando ctypes + Win32 API (sin pymem)."""
    _PROC_RIGHTS = 0x0010 | 0x0020 | 0x0008 | 0x0400

    def __init__(self) -> None:
        if platform.system() != "Windows":
            raise RuntimeError("Win32Backend requires Windows")
        self._kernel32 = ctypes.windll.kernel32
        self._kernel32.OpenProcess.restype = wintypes.HANDLE
        self._kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self._kernel32.ReadProcessMemory.restype = wintypes.BOOL
        self._kernel32.WriteProcessMemory.restype = wintypes.BOOL
        self._kernel32.CloseHandle.restype = wintypes.BOOL

    def list_processes(self) -> List[ProcessInfo]:
        procs: List[ProcessInfo] = []
        snapshot = self._kernel32.CreateToolhelp32Snapshot(0x00000004, 0)
        if not snapshot:
            return procs
        entry = wintypes.PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        if self._kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
            while True:
                name = entry.szExeFile.decode("utf-16le", errors="ignore").rstrip("\x00")
                procs.append(ProcessInfo(pid=int(entry.th32ProcessID), name=name))
                if not self._kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                    break
        self._kernel32.CloseHandle(snapshot)
        return procs

    def open_process(self, pid: int) -> Any:
        handle = self._kernel32.OpenProcess(self._PROC_RIGHTS, False, pid)
        if not handle:
            raise ProcessLookupError(f"Cannot open pid={pid} (error {_get_last_error()})")
        return handle

    def close_process(self, handle: Any) -> None:
        if handle:
            self._kernel32.CloseHandle(handle)

    def read_memory(self, handle: Any, address: int, size: int) -> bytes:
        buf = (ctypes.c_ubyte * size)()
        written = wintypes.SIZE_T(0)
        ok = self._kernel32.ReadProcessMemory(handle, address, buf, size, ctypes.byref(written))
        if not ok:
            raise PermissionError(f"ReadProcessMemory failed (error {_get_last_error()})")
        return bytes(buf[:size])

    def write_memory(self, handle: Any, address: int, data: bytes) -> int:
        n = len(data)
        buf = (ctypes.c_ubyte * n).from_buffer_copy(data)
        written = wintypes.SIZE_T(0)
        ok = self._kernel32.WriteProcessMemory(handle, address, buf, n, ctypes.byref(written))
        if not ok:
            raise PermissionError(f"WriteProcessMemory failed (error {_get_last_error()})")
        return int(written.value)

    def virtual_query(self, handle: Any, address: int) -> Optional[Tuple[int, int, int]]:
        mbi = wintypes.MEMORY_BASIC_INFORMATION()
        res = self._kernel32.VirtualQueryEx(handle, address, ctypes.byref(mbi), ctypes.sizeof(mbi))
        if not res:
            return None
        return (mbi.BaseAddress, mbi.BaseAddress + mbi.RegionSize, mbi.Protect)


def _get_last_error() -> int:
    return int(ctypes.windll.kernel32.GetLastError())


@dataclass
class SecurityScope:
    """Limites de seguridad: proceso allowlist + tamano/patron maximo."""
    allowed_pids: set = field(default_factory=set)
    allowed_names: set = field(default_factory=set)
    max_read_bytes: int = 1024 * 1024
    max_write_bytes: int = 1024 * 256
    max_pattern_length: int = 1024

    def authorize(self, pid: int, name: str = "") -> None:
        if self.allowed_pids and pid not in self.allowed_pids:
            raise PermissionError(f"PID {pid} not in allowlist")
        if self.allowed_names and name and name not in self.allowed_names:
            raise PermissionError(f"Process '{name}' not in allowlist")

    def validate_size(self, size: int, kind: str = "read") -> None:
        cap = self.max_read_bytes if kind == "read" else self.max_write_bytes
        if size <= 0:
            raise ValueError("size must be positive")
        if size > cap:
            raise ValueError(f"size {size} exceeds {kind} cap {cap}")

    def validate_pattern(self, pattern_len: int) -> None:
        if pattern_len <= 0:
            raise ValueError("pattern is empty")
        if pattern_len > self.max_pattern_length:
            raise ValueError(f"pattern length {pattern_len} exceeds cap {self.max_pattern_length}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pids": sorted(self.allowed_pids),
            "names": sorted(self.allowed_names),
            "allowed_pids": sorted(self.allowed_pids),
            "allowed_names": sorted(self.allowed_names),
            "max_read_bytes": self.max_read_bytes,
            "max_write_bytes": self.max_write_bytes,
            "max_pattern_length": self.max_pattern_length,
        }

    def is_authorized(self, pid: int, name: str = "") -> bool:
        if int(pid) in self.allowed_pids:
            return True
        if name and name.lower() in self.allowed_names:
            return True
        return False

    def add_pid(self, pid: int) -> None:
        self.allowed_pids.add(int(pid))

    def remove_pid(self, pid: int) -> None:
        self.allowed_pids.discard(int(pid))

    def add_name(self, name: str) -> None:
        self.allowed_names.add(name.lower())

    def remove_name(self, name: str) -> None:
        self.allowed_names.discard(name.lower())

def parse_pattern(pattern: str) -> bytes:
    """Parsea un patron hex ('41 42 ?? 43' o '0xAABBCCDD'); 0xFF = wildcard."""
    p = pattern.strip()
    if p.startswith("0x") or p.startswith("0X"):
        p = p[2:]
    tokens = p.replace(",", " ").replace("\t", " ").split()
    out = bytearray()
    for tok in tokens:
        if tok in ("?", "??"):
            out.append(0xFF)
            continue
        parts = [tok[i:i + 2] for i in range(0, len(tok), 2)]
        if len(tok) % 2 == 1:
            parts = [tok] if len(tok) == 1 else ["0" + tok[i:i + 1] for i in range(0, len(tok), 1)]
        for pair in parts:
            if pair == "??":
                out.append(0xFF)
            else:
                try:
                    b = int(pair, 16)
                except ValueError as exc:
                    raise ValueError(f"Invalid hex token: {pair}") from exc
                out.append(b & 0xFF)
    return bytes(out)


def find_pattern(data: bytes, pattern: bytes) -> List[int]:
    """Busca patron (0xFF = wildcard) en data; devuelve offsets relativos."""
    if not pattern:
        return []
    results: List[int] = []
    plen = len(pattern)
    for i in range(len(data) - plen + 1):
        chunk = data[i:i + plen]
        if all((pb == 0xFF) or (pb == cb) for pb, cb in zip(pattern, chunk)):
            results.append(i)
    return results


# ---------------------------------------------------------------------------
# Pattern scanner: byte/hex signature search over memory regions
# ---------------------------------------------------------------------------
class PatternScanner:
    """Searches for byte patterns (with wildcard support) in memory regions."""

    @staticmethod
    def parse_pattern(pattern: str) -> List[Optional[int]]:
        tokens = pattern.replace(",", " ").split()
        out: List[Optional[int]] = []
        for t in tokens:
            t = t.strip()
            if not t:
                continue
            if t in ("?", "??"):
                out.append(None)
            else:
                try:
                    out.append(int(t, 16))
                except ValueError as exc:
                    raise ValueError(f"Invalid hex token: {t}") from exc
        return out

    @staticmethod
    def matches(data: bytes, pattern: List[Optional[int]]) -> bool:
        if len(data) < len(pattern):
            return False
        for i, p in enumerate(pattern):
            if p is None:
                continue
            if data[i] != p:
                return False
        return True

    def scan(self, data: bytes, pattern: str) -> List[int]:
        parsed = self.parse_pattern(pattern)
        if not parsed:
            return []
        found: List[int] = []
        for i in range(0, len(data) - len(parsed) + 1):
            if self.matches(data[i:i + len(parsed)], parsed):
                found.append(i)
        return found


# ---------------------------------------------------------------------------
# State injector: encode and write typed values into process memory
# ---------------------------------------------------------------------------
class StateInjector:
    """Writes typed values (int/float/string) into process memory."""

    def __init__(self, backend: _BaseBackend, scope: SecurityScope) -> None:
        self._backend = backend
        self._scope = scope

    def inject(self, pid: int, address: int, value: Any, dtype: str = "int32") -> int:
        if dtype == "string":
            data = encode_string(str(value))
        else:
            data = encode_value(value, dtype)
        handle = self._backend.open_process(pid)
        if not handle:
            raise RuntimeError(f"Cannot open process {pid}")
        try:
            return self._backend.write_memory(handle, address, data)
        finally:
            self._backend.close_process(handle)

    def read(self, pid: int, address: int, size: int = 4, dtype: str = "int32") -> Any:
        handle = self._backend.open_process(pid)
        if not handle:
            raise RuntimeError(f"Cannot open process {pid}")
        try:
            data = self._backend.read_memory(handle, address, size)
        finally:
            self._backend.close_process(handle)
        if not data:
            raise RuntimeError(f"Cannot read memory at 0x{address:x}")
        return decode_value(data, dtype)


# ---------------------------------------------------------------------------
# Watchpoint manager: poll addresses and fire callbacks on change
# ---------------------------------------------------------------------------
class WatchpointManager:
    """Polls memory addresses and notifies on value changes."""

    def __init__(self, backend: _BaseBackend, inspector: "MemoryInspector") -> None:
        self._backend = backend
        self._inspector = inspector
        self._watchpoints: Dict[int, Watchpoint] = {}
        self._lock = threading.Lock()
        self._next_id = 1
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def add(self, pid: int, address: int, size: int = 4, dtype: str = "int32",
            interval: float = 0.5, on_change: Optional[Callable] = None) -> int:
        with self._lock:
            wid = self._next_id
            self._next_id += 1
            self._watchpoints[wid] = Watchpoint(
                pid=pid, address=address, size=size, dtype=dtype,
                interval=interval, on_change=on_change,
            )
            return wid

    def remove(self, wid: int) -> bool:
        with self._lock:
            return self._watchpoints.pop(wid, None) is not None

    def list_watchpoints(self) -> List[dict]:
        with self._lock:
            return [
                {"id": w.id, "pid": w.pid, "address": w.address, "size": w.size,
                 "dtype": w.dtype, "enabled": w.enabled}
                for w in self._watchpoints.values()
            ]

    def _poll_once(self) -> None:
        with self._lock:
            wps = list(self._watchpoints.values())
        for w in wps:
            if not w.enabled:
                continue
            try:
                data = self._backend.read_memory(w.pid, w.address, w.size)
                if not data or len(data) < w.size:
                    continue
                cur = decode_value(data, w.dtype)
                if w.last_value is None:
                    w.last_value = cur
                elif cur != w.last_value:
                    old = w.last_value
                    w.last_value = cur
                    if w.on_change:
                        try:
                            w.on_change(old, cur)
                        except Exception:
                            pass
            except Exception:
                pass

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="AURA-Watchpoints")
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)

    def _loop(self) -> None:
        while self._running:
            self._poll_once()
            time.sleep(0.1)


class MemoryInspector:
    """API unificada 100% local para escanear, leer, escribir y vigilar memoria."""

    def __init__(self, backend: Optional[_BaseBackend] = None,
                 scope: Optional[SecurityScope] = None) -> None:
        self._lock = threading.RLock()
        self._scope = scope or SecurityScope()
        if backend is not None:
            self._backend: _BaseBackend = backend
        elif self._is_test_env() or platform.system() != "Windows":
            self._backend = InMemoryBackend()
        else:
            self._backend = Win32Backend()
        self._watchpoints: Dict[str, Watchpoint] = {}
        self._handles: Dict[int, Any] = {}
        self._scanner = PatternScanner()
        self._watchpoint_mgr = WatchpointManager(self._backend, self)

    def add_watchpoint(self, pid: int, address: int, size: int = 4, dtype: str = "int32",
                       interval: float = 0.5, on_change: Optional[Callable] = None) -> int:
        if not self._scope.is_authorized(pid):
            raise PermissionError(f"PID {pid} not authorized")
        with self._lock:
            wid = self._watchpoint_mgr._next_id
            self._watchpoint_mgr._next_id += 1
            wp = Watchpoint(id=wid, pid=pid, address=address, size=size,
                            dtype=dtype, interval=interval, on_change=on_change)
            self._watchpoints[str(wid)] = wp
            return wid

    def remove_watchpoint(self, wid: int) -> bool:
        with self._lock:
            return self._watchpoints.pop(str(wid), None) is not None

    def list_watchpoints(self) -> List[dict]:
        with self._lock:
            return [
                {"id": w.id, "pid": w.pid, "address": w.address, "size": w.size,
                 "dtype": w.dtype, "enabled": w.enabled}
                for w in self._watchpoints.values()
            ]

    def start_watchpoints(self) -> None:
        self._watchpoint_mgr.start()

    def stop_watchpoints(self) -> None:
        self._watchpoint_mgr.stop()

    @staticmethod
    def _is_test_env() -> bool:
        if os.environ.get("PYTEST_CURRENT_TEST"):
            return True
        try:
            return "pytest" in sys.argv[0].lower()
        except Exception:
            return False

    @property
    def backend(self) -> _BaseBackend:
        return self._backend

    @property
    def scope(self) -> SecurityScope:
        return self._scope

    def _open(self, pid: int, name: str) -> Any:
        self._scope.authorize(pid, name)
        if pid not in self._handles:
            self._handles[pid] = self._backend.open_process(pid)
        return self._handles[pid]

    def list_processes(self) -> List[ProcessInfo]:
        with self._lock:
            return self._backend.list_processes()

    def get_process(self, pid: int) -> Optional[ProcessInfo]:
        for p in self.list_processes():
            if p.pid == pid:
                return p
        return None

    def read_memory(self, pid: int, address: int, size: int) -> bytes:
        self._scope.validate_size(size, "read")
        with self._lock:
            info = self.get_process(pid)
            name = info.name if info else ""
            handle = self._open(pid, name)
            return self._backend.read_memory(handle, address, size)

    def write_memory(self, pid: int, address: int, data: bytes) -> int:
        if isinstance(data, str):
            data = data.encode("utf-8")
        self._scope.validate_size(len(data), "write")
        with self._lock:
            info = self.get_process(pid)
            name = info.name if info else ""
            handle = self._open(pid, name)
            return self._backend.write_memory(handle, address, data)

    def scan_process(self, pid: int, pattern: str, max_results: int = 1000) -> List[ScanResult]:
        raw = parse_pattern(pattern)
        self._scope.validate_pattern(len(raw))
        with self._lock:
            info = self.get_process(pid)
            name = info.name if info else ""
            handle = self._open(pid, name)
            results: List[ScanResult] = []
            for region in self._regions_for(handle, pid):
                base = region.start
                data = self._backend.read_memory(handle, base, region.size)
                for off in find_pattern(data, raw):
                    results.append(ScanResult(address=base + off,
                                              data_hex=data[off:off + len(raw)].hex(),
                                              region_start=base))
                    if len(results) >= max_results:
                        return results
            return results

    def _regions_for(self, handle: Any, pid: int) -> List[MemoryRegion]:
        if isinstance(self._backend, InMemoryBackend):
            return list(self._backend._regions.get(pid, []))
        return [MemoryRegion(start=0x00000000, end=0x7FFFFFFF, protect=0x04)]

    def create_watchpoint(self, pid: int, address: int, size: int,
                          callback: Optional[Callable[[int, bytes, bytes], None]] = None) -> str:
        self._scope.validate_size(size, "read")
        with self._lock:
            current = self.read_memory(pid, address, size)
            wp_id = uuid.uuid4().hex[:12]
            wp = Watchpoint(pid=pid, address=address, size=size,
                            last_value=current)
            self._watchpoints[wp_id] = wp
            return wp_id

    def check_watchpoints(self) -> List[Watchpoint]:
        triggered: List[Watchpoint] = []
        with self._lock:
            for wp in list(self._watchpoints.values()):
                try:
                    current = self.read_memory(wp.pid, wp.address, wp.size)
                except Exception:
                    continue
                if current != wp.last_value:
                    old = wp.last_value
                    wp.last_value = current
                    if wp.callback:
                        try:
                            wp.callback(wp.pid, old, current)
                        except Exception:
                            pass
                    triggered.append(wp)
        return triggered

    def inject_state(self, pid: int, address: int, value: Any, dtype: str = "int32") -> bool:
        if dtype == "string":
            payload = encode_string(str(value))
        else:
            payload = encode_value(value, dtype)
        written = self.write_memory(pid, address, payload)
        return written == len(payload)

    def status(self) -> Dict[str, Any]:
        with self._lock:
            backend_name = type(self._backend).__name__
            procs = self._backend.list_processes()
        return {
            "enabled": True,
            "backend": backend_name,
            "platform": platform.system(),
            "process_count": len(procs),
            "watchpoint_count": len(self._watchpoints),
            "authorized": self._scope.to_dict(),
            "security_scope": self._scope.to_dict(),
            "pids_known": [p.pid for p in procs],
        }

    # -- Unified REST-friendly API -----------------------------------------
    def authorize_pid(self, pid: int) -> None:
        self._scope.add_pid(int(pid))

    def authorize_name(self, name: str) -> None:
        self._scope.add_name(str(name))

    def revoke_pid(self, pid: int) -> None:
        self._scope.remove_pid(int(pid))

    def authorize_name(self, name: str) -> None:
        self._scope.add_name(str(name))

    def scan_pattern(self, pid: int, pattern: str, max_regions: int = 100) -> List[dict]:
        if not self._scope.is_authorized(pid):
            raise PermissionError(f"PID {pid} not authorized")
        handle = self._backend.open_process(pid)
        if not handle:
            raise RuntimeError(f"Cannot open process {pid}")
        results: List[dict] = []
        try:
            regions = self._regions_for(handle, pid)
            for region in regions:
                base = region.start
                size = region.size
                if size <= 0:
                    continue
                data = self._backend.read_memory(handle, base, min(size, 4096))
                if data:
                    offsets = self._scanner.scan(data, pattern)
                    for off in offsets:
                        results.append({
                            "address": base + off,
                            "data_hex": data[off:off + 16].hex(),
                            "region_start": base,
                        })
                        if len(results) >= max_regions:
                            return results
        finally:
            self._backend.close_process(handle)
        return results

    def read(self, pid: int, address: int, size: int = 4, dtype: str = "int32") -> Any:
        if not self._scope.is_authorized(pid):
            raise PermissionError(f"PID {pid} not authorized")
        handle = self._backend.open_process(pid)
        if not handle:
            raise RuntimeError(f"Cannot open process {pid}")
        try:
            data = self._backend.read_memory(handle, address, size)
        finally:
            self._backend.close_process(handle)
        if not data:
            raise RuntimeError(f"Cannot read memory at 0x{address:x}")
        return decode_value(data, dtype)

    def write(self, pid: int, address: int, value: Any, dtype: str = "int32") -> int:
        if not self._scope.is_authorized(pid):
            raise PermissionError(f"PID {pid} not authorized")
        if dtype == "string":
            data = encode_string(str(value))
        else:
            data = encode_value(value, dtype)
        handle = self._backend.open_process(pid)
        if not handle:
            raise RuntimeError(f"Cannot open process {pid}")
        try:
            return self._backend.write_memory(handle, address, data)
        finally:
            self._backend.close_process(handle)

    def reset_watchpoints(self) -> None:
        with self._lock:
            self._watchpoints.clear()

    def close(self) -> None:
        with self._lock:
            for handle in self._handles.values():
                try:
                    self._backend.close_process(handle)
                except Exception:
                    pass
            self._handles.clear()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


_engine: Optional[MemoryInspector] = None
_engine_lock = threading.Lock()


def get_memory_inspector(backend: Optional[_BaseBackend] = None,
                         scope: Optional[SecurityScope] = None) -> MemoryInspector:
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = MemoryInspector(backend=backend, scope=scope)
    return _engine


def reset_memory_inspector() -> None:
    global _engine
    with _engine_lock:
        if _engine is not None:
            try:
                _engine.close()
            except Exception:
                pass
        _engine = None


MemoryInjector = MemoryInspector
get_memory_engine = get_memory_inspector
reset_memory_engine = reset_memory_inspector
