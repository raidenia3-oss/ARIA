"""BLOQUE 69 - AURA Network Proxy & API Interceptor Models."""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class ProxyMode(str, Enum):
    FORWARD = "forward"
    MITM = "mitm"
    TRANSPARENT = "transparent"


class InterceptAction(str, Enum):
    LOG = "log"
    BLOCK = "block"
    MODIFY = "modify"
    INJECT = "inject"
    REDIRECT = "redirect"
    DUPLICATE = "duplicate"


class ProtocolFilter(str, Enum):
    HTTP = "http"
    HTTPS = "https"
    WEBSOCKET = "websocket"
    TCP = "tcp"



@dataclass
class InterceptRule:
    id: str
    name: str
    description: Optional[str] = None
    enabled: bool = True
    priority: int = 50
    match_url_pattern: Optional[str] = None
    match_host_pattern: Optional[str] = None
    match_method: Optional[str] = None
    match_content_type: Optional[str] = None
    protocols: List[str] = field(default_factory=lambda: ["http", "https"])
    action: InterceptAction = InterceptAction.LOG
    block_reason: Optional[str] = None
    inject_status_code: int = 200
    inject_headers: Dict[str, str] = field(default_factory=dict)
    inject_body: Optional[str] = None
    redirect_url: Optional[str] = None
    add_headers: Dict[str, str] = field(default_factory=dict)
    remove_headers: List[str] = field(default_factory=list)
    modify_headers: Dict[str, str] = field(default_factory=dict)
    body_replacements: List[Dict[str, str]] = field(default_factory=list)
    created_at: float = field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    last_triggered: Optional[float] = None
    trigger_count: int = 0

    def matches(self, method: str, host: str, url: str, content_type: str = "") -> bool:
        if not self.enabled:
            return False
        if self.match_method and self.match_method.upper() != method.upper():
            return False
        if self.match_host_pattern:
            if not re.search(self.match_host_pattern, host, re.IGNORECASE):
                return False
        if self.match_url_pattern:
            if not re.search(self.match_url_pattern, url, re.IGNORECASE):
                return False
        if self.match_content_type and content_type:
            if not re.search(self.match_content_type, content_type, re.IGNORECASE):
                return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "InterceptRule":
        av = d.get("action", "log")
        try:
            action = InterceptAction(av)
        except ValueError:
            action = InterceptAction.LOG
        return cls(
            id=d.get("id", ""), name=d.get("name", ""),
            description=d.get("description"), enabled=d.get("enabled", True),
            priority=d.get("priority", 50),
            match_url_pattern=d.get("match_url_pattern"),
            match_host_pattern=d.get("match_host_pattern"),
            match_method=d.get("match_method"),
            match_content_type=d.get("match_content_type"),
            protocols=d.get("protocols", ["http", "https"]),
            action=action, block_reason=d.get("block_reason"),
            inject_status_code=d.get("inject_status_code", 200),
            inject_headers=d.get("inject_headers", {}),
            inject_body=d.get("inject_body"),
            redirect_url=d.get("redirect_url"),
            add_headers=d.get("add_headers", {}),
            remove_headers=d.get("remove_headers", []),
            modify_headers=d.get("modify_headers", {}),
            body_replacements=d.get("body_replacements", []),
            created_at=d.get("created_at", datetime.now(timezone.utc).timestamp()),
            last_triggered=d.get("last_triggered"),
            trigger_count=d.get("trigger_count", 0),
        )

@dataclass
class PayloadManipulation:
    id: str
    name: str
    target_url_pattern: str
    manipulation_type: str = "header_inject"
    headers_to_add: Dict[str, str] = field(default_factory=dict)
    headers_to_remove: List[str] = field(default_factory=list)
    body_replacements: List[Dict[str, str]] = field(default_factory=list)
    body_template: Optional[str] = None
    simulate_status: int = 200
    simulate_headers: Dict[str, str] = field(default_factory=dict)
    simulate_body: Optional[str] = None
    auth_type: str = "bearer"
    auth_value: Optional[str] = None
    enabled: bool = True
    created_at: float = field(default_factory=lambda: datetime.now(timezone.utc).timestamp())

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PayloadManipulation":
        return cls(
            id=d.get("id", ""), name=d.get("name", ""),
            target_url_pattern=d.get("target_url_pattern", ""),
            manipulation_type=d.get("manipulation_type", "header_inject"),
            headers_to_add=d.get("headers_to_add", {}),
            headers_to_remove=d.get("headers_to_remove", []),
            body_replacements=d.get("body_replacements", []),
            body_template=d.get("body_template"),
            simulate_status=d.get("simulate_status", 200),
            simulate_headers=d.get("simulate_headers", {}),
            simulate_body=d.get("simulate_body"),
            auth_type=d.get("auth_type", "bearer"),
            auth_value=d.get("auth_value"),
            enabled=d.get("enabled", True),
            created_at=d.get("created_at", datetime.now(timezone.utc).timestamp()),
        )


@dataclass
class TrafficEntry:
    id: str
    timestamp: float = field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    protocol: str = "http"
    method: str = "GET"
    host: str = ""
    url: str = ""
    path: str = ""
    status_code: int = 0
    request_headers: Dict[str, str] = field(default_factory=dict)
    request_body: Optional[str] = None
    response_headers: Dict[str, str] = field(default_factory=dict)
    response_body: Optional[str] = None
    response_time_ms: float = 0.0
    intercepted: bool = False
    rule_id: Optional[str] = None
    action_taken: Optional[str] = None
    size_bytes: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TrafficEntry":
        return cls(
            id=d.get("id", ""),
            timestamp=d.get("timestamp", datetime.now(timezone.utc).timestamp()),
            protocol=d.get("protocol", "http"),
            method=d.get("method", "GET"),
            host=d.get("host", ""),
            url=d.get("url", ""),
            path=d.get("path", ""),
            status_code=d.get("status_code", 0),
            request_headers=d.get("request_headers", {}),
            request_body=d.get("request_body"),
            response_headers=d.get("response_headers", {}),
            response_body=d.get("response_body"),
            response_time_ms=d.get("response_time_ms", 0.0),
            intercepted=d.get("intercepted", False),
            rule_id=d.get("rule_id"),
            action_taken=d.get("action_taken"),
            size_bytes=d.get("size_bytes", 0),
            error=d.get("error"),
        )

@dataclass
class CertificateInfo:
    cert_path: str
    key_path: str
    ca_cert_path: str
    cert_serial: str
    common_name: str
    valid_from: float
    valid_until: float
    fingerprint_sha256: str
    is_trusted: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class ProxyConfig:
    host: str = "127.0.0.1"
    port: int = 8080
    ssl_port: int = 8443
    mode: ProxyMode = ProxyMode.FORWARD
    enabled: bool = False
    bypass_hosts: List[str] = field(default_factory=list)
    blocked_hosts: List[str] = field(default_factory=list)
    block_by_default: bool = False
    log_level: str = "info"
    max_buffer_size: int = 10 * 1024 * 1024
    idle_timeout: float = 30.0
    generate_cert: bool = True
    cert_common_name: str = "AURA Local Proxy"
    cert_org: str = "AURA Local"
    cert_validity_days: int = 365
    rate_limit_enabled: bool = False
    rate_limit_rps: int = 1000

    def to_dict(self) -> Dict[str, Any]:
        return {
            "host": self.host, "port": self.port, "ssl_port": self.ssl_port,
            "mode": self.mode.value, "enabled": self.enabled,
            "bypass_hosts": self.bypass_hosts, "blocked_hosts": self.blocked_hosts,
            "block_by_default": self.block_by_default, "log_level": self.log_level,
            "max_buffer_size": self.max_buffer_size, "idle_timeout": self.idle_timeout,
            "generate_cert": self.generate_cert,
            "cert_common_name": self.cert_common_name,
            "cert_org": self.cert_org,
            "cert_validity_days": self.cert_validity_days,
            "rate_limit_enabled": self.rate_limit_enabled,
            "rate_limit_rps": self.rate_limit_rps,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ProxyConfig":
        mv = d.get("mode", "forward")
        try:
            mode = ProxyMode(mv)
        except ValueError:
            mode = ProxyMode.FORWARD
        return cls(
            host=d.get("host", "127.0.0.1"),
            port=d.get("port", 8080),
            ssl_port=d.get("ssl_port", 8443),
            mode=mode,
            enabled=d.get("enabled", False),
            bypass_hosts=d.get("bypass_hosts", []),
            blocked_hosts=d.get("blocked_hosts", []),
            block_by_default=d.get("block_by_default", False),
            log_level=d.get("log_level", "info"),
            max_buffer_size=d.get("max_buffer_size", 10 * 1024 * 1024),
            idle_timeout=d.get("idle_timeout", 30.0),
            generate_cert=d.get("generate_cert", True),
            cert_common_name=d.get("cert_common_name", "AURA Local Proxy"),
            cert_org=d.get("cert_org", "AURA Local"),
            cert_validity_days=d.get("cert_validity_days", 365),
            rate_limit_enabled=d.get("rate_limit_enabled", False),
            rate_limit_rps=d.get("rate_limit_rps", 1000),
        )


@dataclass
class WebSocketProxyConfig:
    enabled: bool = True
    max_message_size: int = 10 * 1024 * 1024
    ping_interval: float = 30.0
    ping_timeout: float = 10.0
    auto_accept: bool = False
    log_frames: bool = True
    frame_log_limit: int = 1000

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WebSocketProxyConfig":
        return cls(
            enabled=d.get("enabled", True),
            max_message_size=d.get("max_message_size", 10 * 1024 * 1024),
            ping_interval=d.get("ping_interval", 30.0),
            ping_timeout=d.get("ping_timeout", 10.0),
            auto_accept=d.get("auto_accept", False),
            log_frames=d.get("log_frames", True),
            frame_log_limit=d.get("frame_log_limit", 1000),
        )

