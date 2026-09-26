"""BLOQUE 78 - Local Decentralized P2P Mesh & Cross-Device Swarm Synchronization Engine.

Subsistema 100% local, descentralizado y cifrado para comunicacion P2P entre
multiples nodos AURA y sincronizacion de estados distribuidos sin cloud.

Arquitectura:
- MeshCipher: cifrado point-to-point (Fernet/AES) derivado de un secret
  compartido + nonce anti-replay para handshake seguro e intercambio cifrado.
- MeshKV: store distribuido clave->valor con versionado (LWW / last-writer-wins).
- LoopbackTransport: bus en memoria (tests deterministas, sin sockets reales).
- MeshNode (P2P engine): discovery/handshake, envio cifrado, sync de estados,
  deteccion de peers caidos (tolerancia a fallos) y gestion de topologia.

Seguridad:
- Solo nodos que comparten el secret pueden descifrar paquetes (autorizacion).
- Nonce unico por paquete -> rechaza replay.
- no expone tokens ni credenciales en texto plano; 100% offline.
"""
from __future__ import annotations

import base64
import hashlib
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class PeerStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    STALE = "stale"
    TRUSTED = "trusted"


@dataclass
class MeshConfig:
    node_id: str = ""
    node_name: str = "aura-node"
    secret: str = "aura-mesh-dev-placeholder"
    port: int = 47600
    heartbeat_interval_s: float = 5.0
    stale_after_s: float = 30.0
    max_peers: int = 64


@dataclass
class PeerInfo:
    peer_id: str
    name: str = ""
    host: str = ""
    port: int = 0
    last_seen: float = 0.0
    status: str = PeerStatus.OFFLINE
    kv: Dict[str, Any] = field(default_factory=dict)


@dataclass
class KVEntry:
    value: Any
    version: int
    origin: str = ""
    ts: float = 0.0


def derive_key(secret: str) -> bytes:
    return base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())


class MeshCipher:
    """Cifrado point-to-point con Fernet(AES) + nonce anti-replay."""

    def __init__(self, secret: str, max_seen: int = 20000) -> None:
        from cryptography.fernet import Fernet
        self._fernet = Fernet(derive_key(secret))
        self._seen: set = set()
        self._max_seen = max_seen

    def seal(self, payload: Dict[str, Any]) -> str:
        nonce = uuid.uuid4().hex
        data = json.dumps({"nonce": nonce, "payload": payload}).encode("utf-8")
        return self._fernet.encrypt(data).decode("ascii")

    def open(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            data = self._fernet.decrypt(token.encode("ascii"))
            obj = json.loads(data.decode("utf-8"))
        except Exception:
            return None
        nonce = obj.get("nonce")
        if nonce is None or nonce in self._seen:
            return None
        self._seen.add(nonce)
        if len(self._seen) > self._max_seen:
            self._seen = set(list(self._seen)[- (self._max_seen // 2):])
        return obj.get("payload")


class MeshKV:
    """Store distribuido clave->valor con LWW por version."""

    def __init__(self) -> None:
        self._data: Dict[str, KVEntry] = {}
        self._lock = threading.RLock()

    def set(self, key: str, value: Any, origin: str = "",
            version: Optional[int] = None, ts: Optional[float] = None) -> bool:
        with self._lock:
            prev = self._data.get(key)
            new_version = version if version is not None else (prev.version + 1 if prev else 1)
            if prev is not None and new_version <= prev.version:
                return False
            if prev is not None and ts and prev.ts and ts <= prev.ts:
                return False
            self._data[key] = KVEntry(value=value, version=new_version,
                                      origin=origin, ts=ts if ts else time.time())
            return True

    def get(self, key: str) -> Optional[KVEntry]:
        with self._lock:
            return self._data.get(key)

    def get_value(self, key: str, default: Any = None) -> Any:
        e = self.get(key)
        return e.value if e is not None else default

    def merge(self, snapshot: Dict[str, Dict[str, Any]]) -> tuple:
        applied = 0
        conflicts = 0
        with self._lock:
            for key, rec in (snapshot or {}).items():
                entry = KVEntry(value=rec.get("value"),
                                version=int(rec.get("version", 0)),
                                origin=str(rec.get("origin", "")),
                                ts=float(rec.get("ts", 0) or 0))
                if self.set(key, entry.value, entry.origin, entry.version, entry.ts):
                    applied += 1
                else:
                    conflicts += 1
        return applied, conflicts

    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return {k: {"value": v.value, "version": v.version,
                        "origin": v.origin, "ts": v.ts}
                    for k, v in self._data.items()}

class LoopbackTransport:
    """Bus en memoria para unir nodos en tests (sincrono, determinista)."""

    def __init__(self) -> None:
        self._nodes: Dict[str, "MeshNode"] = {}
        self._lock = threading.Lock()

    def attach(self, node: "MeshNode") -> None:
        with self._lock:
            self._nodes[node.config.node_id] = node

    def detach(self, node_id: str) -> None:
        with self._lock:
            self._nodes.pop(node_id, None)

    def broadcast(self, author: "MeshNode", raw: str) -> int:
        delivered = 0
        with self._lock:
            targets = list(self._nodes.values())
        for node in targets:
            if node.config.node_id != author.config.node_id:
                node._on_raw(raw)
                delivered += 1
        return delivered

    def unicast(self, dst_id: str, raw: str) -> bool:
        with self._lock:
            node = self._nodes.get(dst_id)
        if node is not None:
            node._on_raw(raw)
            return True
        return False


class MeshNode:
    """Nodo P2P del mesh: discovery/handshake, sync cifrado y topologia."""

    MSG_ANNOUNCE = "announce"
    MSG_HELLO = "hello"
    MSG_SYNC = "sync"
    MSG_ACK = "ack"

    def __init__(self, config: Optional[MeshConfig] = None,
                 transport: Optional[LoopbackTransport] = None,
                 now_fn: Optional[Callable[[], float]] = None) -> None:
        self.config = config or MeshConfig(node_id=uuid.uuid4().hex[:12])
        if not self.config.node_id:
            self.config.node_id = uuid.uuid4().hex[:12]
        self._cipher = MeshCipher(self.config.secret)
        self._kv = MeshKV()
        self._peers: Dict[str, PeerInfo] = {}
        self._lock = threading.RLock()
        self._now = now_fn or time.time
        self._transport = transport
        if transport is not None:
            transport.attach(self)
        self.packets_sent = 0
        self.packets_received = 0
        self.packets_denied = 0

    def _seal(self, msg: Dict[str, Any]) -> str:
        self.packets_sent += 1
        return self._cipher.seal(msg)

    def _on_raw(self, raw: str) -> None:
        payload = self._cipher.open(raw)
        if payload is None:
            self.packets_denied += 1
            return
        self.packets_received += 1
        self._dispatch(payload)

    def _dispatch(self, msg: Dict[str, Any]) -> None:
        mtype = msg.get("type")
        sender = msg.get("sender") or {}
        peer_id = sender.get("node_id")
        if mtype == self.MSG_SYNC:
            self._on_sync(peer_id, msg.get("kv", {}))
        elif mtype in (self.MSG_ANNOUNCE, self.MSG_HELLO):
            self._touch_peer(peer_id, sender)

    def _touch_peer(self, peer_id: Optional[str], sender: Dict[str, Any]) -> None:
        if not peer_id:
            return
        with self._lock:
            info = self._peers.get(peer_id)
            if info is None:
                if len(self._peers) >= (self.config.max_peers or 64):
                    return
                info = PeerInfo(peer_id=peer_id)
                self._peers[peer_id] = info
                info.name = sender.get("name", "")
                info.host = sender.get("host", "")
                info.port = int(sender.get("port", 0) or 0)
            info.last_seen = self._now()
            info.status = PeerStatus.ONLINE

    def announce(self) -> int:
        msg = {"type": self.MSG_ANNOUNCE, "sender": self._self_info()}
        return self._broadcast(self._seal(msg))

    def hello(self, peer_id: str) -> bool:
        msg = {"type": self.MSG_HELLO, "sender": self._self_info()}
        return self._transport is not None and self._transport.unicast(peer_id, self._seal(msg))

    def set_key(self, key: str, value: Any) -> bool:
        ok = self._kv.set(key, value, origin=self.config.node_id)
        if ok:
            with self._lock:
                for pid in list(self._peers):
                    self._push_sync(pid)
        return ok

    def get_key(self, key: str, default: Any = None) -> Any:
        return self._kv.get_value(key, default)

    def sync_all(self) -> int:
        snap = self._kv.snapshot()
        msg = {"type": self.MSG_SYNC, "sender": self._self_info(), "kv": snap}
        return self._broadcast(self._seal(msg))

    def _push_sync(self, peer_id: str) -> None:
        msg = {"type": self.MSG_SYNC, "sender": self._self_info(), "kv": self._kv.snapshot()}
        if self._transport is not None:
            self._transport.unicast(peer_id, self._seal(msg))

    def _on_sync(self, peer_id: Optional[str], kv: Dict[str, Dict[str, Any]]) -> None:
        self._kv.merge(kv)
        if peer_id:
            self._touch_peer(peer_id, {})

    def _broadcast(self, raw: str) -> int:
        if self._transport is None:
            return 0
        return self._transport.broadcast(self, raw)

    def _self_info(self) -> Dict[str, Any]:
        return {"node_id": self.config.node_id, "name": self.config.node_name,
                "host": "127.0.0.1", "port": self.config.port}

    def peers(self) -> List[PeerInfo]:
        with self._lock:
            return list(self._peers.values())

    def peers_serializable(self) -> List[Dict[str, Any]]:
        return [{"peer_id": p.peer_id, "name": p.name, "host": p.host,
                 "port": p.port, "last_seen": p.last_seen, "status": p.status}
                for p in self.peers()]

    def kv_snapshot(self) -> Dict[str, Any]:
        return self._kv.snapshot()

    def step(self) -> Dict[str, str]:
        now = self._now()
        stale: Dict[str, str] = {}
        with self._lock:
            for pid, p in self._peers.items():
                if now - p.last_seen > (self.config.stale_after_s or 30.0):
                    if p.status != PeerStatus.OFFLINE:
                        p.status = PeerStatus.OFFLINE
                        stale[pid] = "offline"
        return stale

    def status(self) -> Dict[str, Any]:
        return {
            "node_id": self.config.node_id,
            "node_name": self.config.node_name,
            "peers": self.peers_serializable(),
            "peer_count": len(self._peers),
            "kv_entries": len(self._kv.snapshot()),
            "packets_sent": self.packets_sent,
            "packets_received": self.packets_received,
            "packets_denied": self.packets_denied,
            "offline_only": True,
        }


_engine: Optional[MeshNode] = None
_engine_lock = threading.Lock()
_engine_transport: Optional[LoopbackTransport] = None


def get_mesh_engine(config: Optional[MeshConfig] = None,
                    transport: Optional[LoopbackTransport] = None) -> MeshNode:
    global _engine, _engine_transport
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine_transport = transport or LoopbackTransport()
                if config is None:
                    config = MeshConfig(node_id=uuid.uuid4().hex[:12])
                _engine = MeshNode(config=config, transport=_engine_transport)
    return _engine


def reset_mesh_engine() -> None:
    global _engine, _engine_transport
    with _engine_lock:
        if _engine is not None and _engine_transport is not None:
            try:
                _engine_transport.detach(_engine.config.node_id)
            except Exception:
                pass
        _engine = None
        _engine_transport = None


MeshEngine = MeshNode
get_mesh = get_mesh_engine
reset_mesh = reset_mesh_engine
