"""Win32 backend for memory access using native ctypes + Win32 API."""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import platform
from typing import List, Optional, Tuple

from backend.automation.memory_injector import ProcessInfo, _BaseBackend

_PROCESS_ALL_ACCESS = 0x1F0FFF
_PROCESS_QUERY_INFORMATION = 0x0400
_PROCESS_VM_READ = 0x0010
_PROCESS_VM_WRITE = 0x0020
_PROCESS_VM_OPERATION = 0x0008
_TH32CS_SNAPPROCESS = 0x00000002
_MEM_COMMIT = 0x00001000
_MEM_RESERVE = 0x00002000
_PAGE_READWRITE = 0x04
_PAGE_WRITECOPY = 0x08


class _MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", ctypes.wintypes.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", ctypes.wintypes.DWORD),
        ("Protect", ctypes.wintypes.DWORD),
        ("Type", ctypes.wintypes.DWORD),
    ]


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.wintypes.DWORD),
        ("cntUsage", ctypes.wintypes.DWORD),
        ("th32ProcessID", ctypes.wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_void_p),
        ("th32ModuleID", ctypes.wintypes.DWORD),
        ("cntThreads", ctypes.wintypes.DWORD),
        ("th32ParentProcessID", ctypes.wintypes.DWORD),
        ("pcPriClassBase", ctypes.wintypes.LONG),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


def _is_windows() -> bool:
    return platform.system() == "Windows"


class Win32MemoryBackend(_BaseBackend):
    """Native Windows memory backend using ctypes + Win32 API (no pymem)."""

    def __init__(self) -> None:
        self._kernel32 = ctypes.windll.kernel32
        self._available = _is_windows()

    @property
    def available(self) -> bool:
        return self._available

    def list_processes(self) -> List[ProcessInfo]:
        if not self._available:
            return []
        procs: List[ProcessInfo] = []
        snap = self._kernel32.CreateToolhelp32Snapshot(_TH32CS_SNAPPROCESS, 0)
        if snap == -1 or snap == 0xFFFFFFFF:
            return procs
        try:
            pe = _PROCESSENTRY32W()
            pe.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
            if not self._kernel32.Process32FirstW(snap, ctypes.byref(pe)):
                return procs
            while True:
                pid = pe.th32ProcessID
                name = pe.szExeFile
                procs.append(ProcessInfo(pid=pid, name=name))
                if not self._kernel32.Process32NextW(snap, ctypes.byref(pe)):
                    break
        finally:
            self._kernel32.CloseHandle(snap)
        return procs

    def open_process(self, pid: int) -> int:
        return self._kernel32.OpenProcess(_PROCESS_ALL_ACCESS, False, pid)

    def close_process(self, handle: int) -> None:
        if handle:
            self._kernel32.CloseHandle(handle)

    def read_memory(self, handle: int, address: int, size: int) -> bytes:
        buf = (ctypes.c_char * size)()
        bytes_read = ctypes.c_size_t(0)
        ok = self._kernel32.ReadProcessMemory(
            handle, ctypes.c_void_p(address), buf, size, ctypes.byref(bytes_read)
        )
        if not ok:
            return b""
        return bytes(buf[: bytes_read.value])

    def write_memory(self, handle: int, address: int, data: bytes) -> int:
        bytes_written = ctypes.c_size_t(0)
        ok = self._kernel32.WriteProcessMemory(
            handle, ctypes.c_void_p(address), data, len(data), ctypes.byref(bytes_written)
        )
        return bytes_written.value if ok else 0

    def virtual_query(self, handle: int, address: int) -> Optional[Tuple[int, int, int]]:
        mbi = _MEMORY_BASIC_INFORMATION()
        result = self._kernel32.VirtualQueryEx(
            handle, ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi)
        )
        if not result:
            return None
        return (mbi.BaseAddress, mbi.RegionSize, mbi.Protect)