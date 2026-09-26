"""BLOQUE 69 - AURA Network Proxy & API Interceptor Engine.

Proxy local asíncrono con soporte MITM (HTTP/HTTPS), manipulación de
payloads, WebSockets y reglas de interceptación configurable.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import re
import ssl
import time
import uuid
from asyncio import StreamReader, StreamWriter
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

from backend.network.models import (
    CertificateInfo,
    InterceptAction,
    InterceptRule,
    PayloadManipulation,
    ProxyConfig,
    ProxyMode,
    TrafficEntry,
    WebSocketProxyConfig,
)

logger = logging.getLogger("AURA.Network.Proxy")

DEFAULT_NETWORK_DIR = os.path.join("data", "network_proxy")
DEFAULT_CA_KEY_SIZE = 2048
DEFAULT_CERT_VALIDITY_DAYS = 365


# ============================================================
# ProxyCertificateManager
# ============================================================

class ProxyCertificateManager:
    """Genera y gestiona certificados CA y de servidor para MITM local.

    Usa `cryptography` para generar un CA autofirmado y certificados
    por dominio firmados por ese CA. Los certificados se persisten
    en disco para reutilización entre reinicios.
    """

    def __init__(self, cert_dir: Optional[str] = None):
        self._cert_dir = Path(cert_dir or DEFAULT_NETWORK_DIR)
        self._cert_dir.mkdir(parents=True, exist_ok=True)
        self._ca_key_path = self._cert_dir / "aura_ca.key"
        self._ca_cert_path = self._cert_dir / "aura_ca.pem"
        self._cert_cache: Dict[str, Tuple[Path, Path]] = {}
        self._ca_private_key = None
        self._ca_cert = None
        self._cert_info: Optional[CertificateInfo] = None

    @property
    def info(self) -> Optional[CertificateInfo]:
        return self._cert_info

    @property
    def is_generated(self) -> bool:
        return self._ca_key_path.exists() and self._ca_cert_path.exists()

    def load_or_generate_ca(self, common_name: str = "AURA Local Proxy CA",
                            validity_days: int = DEFAULT_CERT_VALIDITY_DAYS) -> CertificateInfo:
        """Carga el CA existente o genera uno nuevo autofirmado."""
        if self._ca_key_path.exists() and self._ca_cert_path.exists():
            try:
                return self._load_ca_info(common_name, validity_days)
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"[CertManager] CA corrupto, regenerando: {exc}")
        self._generate_ca(common_name, "AURA Local", validity_days)
        return self._load_ca_info(common_name, validity_days)

    def _generate_ca(self, common_name: str, org: str = "AURA Local",
                     validity_days: int = DEFAULT_CERT_VALIDITY_DAYS) -> None:
        ca_key = rsa.generate_private_key(
            public_exponent=65537, key_size=DEFAULT_CA_KEY_SIZE, backend=default_backend())
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "AURA Local"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])
        now = datetime.now(timezone.utc)
        ca_cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + timedelta(days=validity_days))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(
                digital_signature=True, content_commitment=True,
                key_encipherment=True, data_encipherment=True,
                key_cert_sign=True, crl_sign=True, encipher_only=False,
                decipher_only=False), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), False)
            .sign(ca_key, hashes.SHA256(), default_backend())
        )
        ca_key_pem = ca_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption())
        ca_cert_pem = ca_cert.public_bytes(serialization.Encoding.PEM)
        self._ca_key_path.write_bytes(ca_key_pem)
        self._ca_cert_path.write_bytes(ca_cert_pem)
        self._ca_private_key = ca_key
        self._ca_cert = ca_cert
        logger.info(f"[CertManager] CA generado: {common_name}")

    def _load_ca_info(self, common_name: str, validity_days: int) -> CertificateInfo:
        ca_cert_pem = self._ca_cert_path.read_bytes()
        ca_cert = x509.load_pem_x509_certificate(ca_cert_pem, default_backend())
        now = datetime.now(timezone.utc)
        cert_serial = format(ca_cert.serial_number, 'X')
        sha256 = hashlib.sha256(ca_cert_pem).hexdigest()
        try:
            nvb = ca_cert.not_valid_before_utc
            nva = ca_cert.not_valid_after_utc
        except AttributeError:
            nvb = ca_cert.not_valid_before.replace(tzinfo=timezone.utc)
            nva = ca_cert.not_valid_after.replace(tzinfo=timezone.utc)
        info = CertificateInfo(
            cert_path=str(self._ca_cert_path), key_path=str(self._ca_key_path),
            ca_cert_path=str(self._ca_cert_path), cert_serial=cert_serial,
            common_name=common_name, valid_from=nvb.timestamp(),
            valid_until=nva.timestamp(), fingerprint_sha256=sha256, is_trusted=False)
        self._cert_info = info
        self._ca_cert = ca_cert
        self._ca_private_key = serialization.load_pem_private_key(
            self._ca_key_path.read_bytes(), password=None, backend=default_backend())
        logger.info(f"[CertManager] CA cargado desde disco: {common_name}")
        return info

    def generate_server_cert(self, hostname: str, common_name: Optional[str] = None) -> Tuple[Path, Path]:
        if not self._ca_private_key or not self._ca_cert:
            raise RuntimeError("CA no generado. Call load_or_generate_ca() primero.")
        cert_dir = self._cert_dir / "certs"
        cert_dir.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', hostname)[:100]
        cert_path = cert_dir / f"{safe_name}.pem"
        key_path = cert_dir / f"{safe_name}.key.pem"
        if cert_path.exists() and key_path.exists():
            return cert_path, key_path
        server_key = rsa.generate_private_key(
            public_exponent=65537, key_size=DEFAULT_CA_KEY_SIZE, backend=default_backend())
        cn = common_name or hostname
        subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "AURA Local"),
            x509.NameAttribute(NameOID.COMMON_NAME, cn),
        ])
        now = datetime.now(timezone.utc)
        try:
            san = x509.SubjectAlternativeName([x509.DNSName(hostname)])
        except Exception:
            san = x509.SubjectAlternativeName([x509.DNSName(hostname)])
        server_cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(self._ca_cert.subject)
            .public_key(server_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + timedelta(days=DEFAULT_CERT_VALIDITY_DAYS))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(
                digital_signature=True, content_commitment=True,
                key_encipherment=True, data_encipherment=True,
                key_cert_sign=False, crl_sign=False,
                encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(server_key.public_key()), False)
            .add_extension(san, critical=False)
            .sign(self._ca_private_key, hashes.SHA256(), default_backend())
        )
        server_key_pem = server_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption())
        server_cert_pem = server_cert.public_bytes(serialization.Encoding.PEM)
        key_path.write_bytes(server_key_pem)
        cert_path.write_bytes(server_cert_pem)
        self._cert_cache[hostname] = (cert_path, key_path)
        logger.debug(f"[CertManager] Certificado generado para: {hostname}")
        return cert_path, key_path

    def get_ca_cert_pem(self) -> bytes:
        if self._ca_cert_path.exists():
            return self._ca_cert_path.read_bytes()
        return b""

    def create_ssl_context_for_host(self, hostname: str) -> ssl.SSLContext:
        cert_path, key_path = self.generate_server_cert(hostname)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(str(cert_path), str(key_path))
        return ctx

    def load_or_generate_ca_v2(self, common_name: str = "AURA Local Proxy CA",
                               org: str = "AURA Local",
                               validity_days: int = 365) -> CertificateInfo:
        if self._ca_key_path.exists() and self._ca_cert_path.exists():
            return self._load_ca_info(common_name, validity_days)
        self._generate_ca(common_name, org, validity_days)
        return self._load_ca_info(common_name, validity_days)

    def _generate_ca(self, common_name: str, org: str, validity_days: int) -> CertificateInfo:
        ca_key = rsa.generate_private_key(
            public_exponent=65537, key_size=DEFAULT_CA_KEY_SIZE, backend=default_backend())
        ca_subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Local"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "AURA"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, org),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])
        now = datetime.now(timezone.utc)
        ca_cert = (
            x509.CertificateBuilder()
            .subject_name(ca_subject)
            .issuer_name(ca_subject)
            .public_key(ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + timedelta(days=validity_days))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(
                digital_signature=True, content_commitment=False,
                key_encipherment=False, data_encipherment=False,
                key_cert_sign=True, crl_sign=True,
                encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), False)
            .sign(ca_key, hashes.SHA256(), default_backend())
        )
        ca_key_pem = ca_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption())
        self._ca_key_path.write_bytes(ca_key_pem)
        ca_cert_pem = ca_cert.public_bytes(serialization.Encoding.PEM)
        self._ca_cert_path.write_bytes(ca_cert_pem)
        self._ca_private_key = ca_key
        self._ca_cert = ca_cert
        cert_serial = format(ca_cert.serial_number, 'X')
        sha256 = hashlib.sha256(ca_cert_pem).hexdigest()
        info = CertificateInfo(
            cert_path=str(self._ca_cert_path), key_path=str(self._ca_key_path),
            ca_cert_path=str(self._ca_cert_path), cert_serial=cert_serial,
            common_name=common_name, valid_from=now.timestamp(),
            valid_until=(now + timedelta(days=validity_days)).timestamp(),
            fingerprint_sha256=sha256, is_trusted=False)
        self._cert_info = info
        logger.info(f"[CertManager] CA generado: {common_name} (serial={cert_serial})")
        return info