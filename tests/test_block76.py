"""BLOQUE 76 - Unit tests for Process Memory Inspector engine."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_imports():
    from backend.automation.memory_injector import (
        MemoryInspector,
        PatternScanner,
        SecurityScope,
        StateInjector,
        WatchpointManager,
        decode_value,
        encode_string,
        encode_value,
        get_memory_inspector,
        reset_memory_inspector,
    )

    assert MemoryInspector is not None


def test_encode_decode_int32():
    from backend.automation.memory_injector import decode_value, encode_value

    raw = encode_value(42, "int32")
    assert len(raw) == 4
    assert decode_value(raw, "int32") == 42


def test_encode_decode_float64():
    from backend.automation.memory_injector import decode_value, encode_value

    raw = encode_value(3.14, "float64")
    assert len(raw) == 8
    assert abs(decode_value(raw, "float64") - 3.14) < 1e-9


def test_encode_decode_string():
    from backend.automation.memory_injector import decode_value, encode_string

    raw = encode_string("hello", max_size=16)
    assert len(raw) == 16
    assert decode_value(raw, "string") == "hello"


def test_encode_invalid_dtype():
    from backend.automation.memory_injector import encode_value

    with pytest.raises(ValueError):
        encode_value(1, "bogus")


def test_pattern_parse_wildcards():
    from backend.automation.memory_injector import PatternScanner

    parsed = PatternScanner.parse_pattern("?? 00 FF ??")
    assert parsed == [None, 0x00, 0xFF, None]


def test_pattern_scan():
    from backend.automation.memory_injector import PatternScanner

    data = bytes([0x41, 0x42, 0x00, 0xFF, 0x43, 0x41, 0x42, 0x00, 0xFF])
    offsets = PatternScanner().scan(data, "41 42 ?? FF")
    assert offsets == [0, 5]


def test_security_scope_allowlist():
    from backend.automation.memory_injector import SecurityScope

    s = SecurityScope()
    s.add_pid(100)
    s.add_name("notepad.exe")
    assert s.is_authorized(100) is True
    assert s.is_authorized(200, "Notepad.EXE") is True
    assert s.is_authorized(200) is False
    s.remove_pid(100)
    assert s.is_authorized(100) is False


def test_security_scope_to_dict():
    from backend.automation.memory_injector import SecurityScope

    s = SecurityScope()
    s.add_pid(5)
    s.add_name("foo")
    d = s.to_dict()
    assert d["pids"] == [5]
    assert d["names"] == ["foo"]


def test_inmemory_backend_read_write():
    from backend.automation.memory_backend_inmem import InMemoryBackend
    from backend.automation.memory_injector import MemoryRegion

    b = InMemoryBackend()
    b.add_process(1, "test")
    b.add_region(1, 0x1000, b"\x01\x02\x03\x04")
    h = b.open_process(1)
    assert b.read_memory(h, 0x1000, 4) == b"\x01\x02\x03\x04"
    n = b.write_memory(h, 0x1000, b"\xaa\xbb")
    assert n == 2
    assert b.read_memory(h, 0x1000, 4) == b"\xaa\xbb\x03\x04"
    b.close_process(h)


def test_inmemory_backend_list_processes():
    from backend.automation.memory_backend_inmem import InMemoryBackend

    b = InMemoryBackend()
    b.add_process(1, "a")
    b.add_process(2, "b")
    procs = b.list_processes()
    assert {p.pid for p in procs} == {1, 2}


def test_memory_inspector_with_inmem_backend():
    from backend.automation.memory_backend_inmem import InMemoryBackend
    from backend.automation.memory_injector import MemoryInspector

    backend = InMemoryBackend()
    backend.add_process(42, "game.exe")
    backend.add_region(42, 0x2000, bytes(range(256)))
    ins = MemoryInspector(backend=backend)
    ins.authorize_pid(42)
    val = ins.read(42, 0x2000, 4, "uint8")
    assert val == 0
    written = ins.write(42, 0x2000, 0xFF, "uint8")
    assert written == 1
    assert ins.read(42, 0x2000, 1, "uint8") == 0xFF


def test_memory_inspector_scan_pattern():
    from backend.automation.memory_backend_inmem import InMemoryBackend
    from backend.automation.memory_injector import MemoryInspector

    backend = InMemoryBackend()
    backend.add_process(7, "target")
    backend.add_region(7, 0x5000, b"\xde\xad\xbe\xef\x00\xde\xad\xbe\xef")
    ins = MemoryInspector(backend=backend)
    ins.authorize_pid(7)
    results = ins.scan_pattern(7, "DE AD BE EF")
    assert len(results) == 2
    assert results[0]["address"] == 0x5000
    assert results[1]["address"] == 0x5005


def test_memory_inspector_unauthorized():
    from backend.automation.memory_backend_inmem import InMemoryBackend
    from backend.automation.memory_injector import MemoryInspector

    backend = InMemoryBackend()
    backend.add_process(1, "x")
    ins = MemoryInspector(backend=backend)
    with pytest.raises(PermissionError):
        ins.read(1, 0x1000, 4)


def test_memory_inspector_watchpoint():
    from backend.automation.memory_backend_inmem import InMemoryBackend
    from backend.automation.memory_injector import MemoryInspector

    backend = InMemoryBackend()
    backend.add_process(9, "wp")
    backend.add_region(9, 0x3000, b"\x00\x00\x00\x00")
    ins = MemoryInspector(backend=backend)
    ins.authorize_pid(9)
    wid = ins.add_watchpoint(9, 0x3000, 4)
    assert isinstance(wid, int)
    wps = ins.list_watchpoints()
    assert any(w["id"] == wid for w in wps)
    assert ins.remove_watchpoint(wid) is True
    assert ins.remove_watchpoint(wid) is False


def test_memory_inspector_status():
    from backend.automation.memory_backend_inmem import InMemoryBackend
    from backend.automation.memory_injector import MemoryInspector

    backend = InMemoryBackend()
    backend.add_process(3, "s")
    ins = MemoryInspector(backend=backend)
    st = ins.status()
    assert st["backend"] == "InMemoryBackend"
    assert st["process_count"] == 1


def test_singleton_reset():
    from backend.automation.memory_injector import get_memory_inspector, reset_memory_inspector

    reset_memory_inspector()
    a = get_memory_inspector()
    b = get_memory_inspector()
    assert a is b
    reset_memory_inspector()
