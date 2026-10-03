# -*- coding: utf-8 -*-
"""AURA OS - Chunk 3: Seguridad (Zero-Trust + Auditoria).

- Zero-trust: cada componente verifica credenciales
- Auditoria: log inmutable de eventos con firma HMAC
- ZKP: stub implementado (a expandir en produccion)
"""
from __future__ import annotations

import hashlib, hmac, json, logging, os, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger('AURA.Security')

AUDIT_LOG_FILE = Path(os.environ.get('AURA_AUDIT_LOG', 'data/audit.log'))

# Fallback de desarrollo: NO es un secreto. Es una constante publicada en el
# codigo fuente, asi que cualquiera que lo lea puede firmar/verificar con ella.
# Se nombra para poder reportarlo honestamente en get_stats() en vez de
# presentarlo como una clave configurada.
DEV_SECRET_FALLBACK = 'dev-secret-change-me-32bytes!!'


class SecurityLevel:
    """Niveles de seguridad para acceso zero-trust."""
    PUBLIC = 'public'
    INTERNAL = 'internal' 
    SECRET = 'secret'
    CRITICAL = 'critical'
    ALL = [PUBLIC, INTERNAL, SECRET, CRITICAL]
    
    @classmethod
    def rank(cls, level: str) -> int:
        try: return cls.ALL.index(level)
        except ValueError: return 0


class SecurityError(Exception): pass
class UnauthorizedError(SecurityError): pass
class PermissionDeniedError(SecurityError): pass


class CredentialVerifier:
    """Verificador de credenciales (Zero-Trust)."""
    
    def __init__(self):
        self._tokens: Dict[str, Dict[str, Any]] = {}
        configured = os.environ.get('AURA_SECRET_KEY') or ''
        self._secret_configured = bool(configured)
        self._secret = configured or DEV_SECRET_FALLBACK
        self._secret_source = 'env' if self._secret_configured else 'development_default'
        self._init = False
        if not self._secret_configured:
            logger.warning('CredentialVerifier: AURA_SECRET_KEY no esta definida — se usa la clave '
                           'de firma de desarrollo (publica, en el codigo fuente); las firmas '
                           'HMAC que se generen con ella son falsificables')
    
    def initialize(self, admin_token: str = ''):
        if self._init: return
        if not admin_token: admin_token = hashlib.sha256(os.urandom(32)).hexdigest()
        self._tokens[admin_token] = dict(level=SecurityLevel.CRITICAL, roles=['admin'], 
                                          created_at=time.time(), expires_at=None)
        self._init = True
        logger.info('CredentialVerifier: initialized with admin token')
    
    def verify(self, token: str, required_level: str = SecurityLevel.PUBLIC) -> bool:
        if not self._init: self.initialize()
        info = self._tokens.get(token)
        if not info: return False
        return SecurityLevel.rank(info['level']) >= SecurityLevel.rank(required_level)
    
    def generate_token(self, level: str = SecurityLevel.INTERNAL, roles: Optional[List[str]] = None) -> str:
        t = hashlib.sha256(os.urandom(32)).hexdigest()
        self._tokens[t] = dict(level=level, roles=roles or [], created_at=time.time(), expires_at=None)
        return t
    
    def revoke_token(self, token: str) -> bool:
        if token in self._tokens: del self._tokens[token]; return True
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Estado del verificador.

        No expone material de clave: ni completo ni por prefijo. Solo booleano
        de configuracion y procedencia, para que un consumidor distinga una clave
        real de la constante de desarrollo publicada en el codigo.
        """
        return dict(initialized=self._init, active_tokens=len(self._tokens),
                    secret_configured=self._secret_configured,
                    secret_source=self._secret_source)


class AuditLogger:
    """Logger de auditoria inmutable.

    Cada evento se registra con:
    - timestamp (UTC)
    - hash del evento anterior (cadena inmutable)
    - firma HMAC con clave secreta
    """
    
    def __init__(self, log_file: Optional[Path] = None):
        self._lf = log_file or AUDIT_LOG_FILE
        self._last_hash = 'genesis'
        self._secret = os.environ.get('AURA_AUDIT_SECRET', 'audit-secret-key-32bytes!!!')
        self._init_log()
        self._resume_last_hash()
    
    def _init_log(self):
        self._lf.parent.mkdir(parents=True, exist_ok=True)
        if not self._lf.exists():
            ev = dict(seq=0, type='system_init',
                      timestamp=datetime.now(timezone.utc).isoformat(),
                      prev_hash='genesis', hash=self._hash('genesis'),
                      signature=self._sign('genesis'),
                      data=dict(message='AURA OS audit log initialized'))
            # JSON-Lines: un evento por linea
            with open(self._lf, 'w', encoding='utf-8') as f:
                f.write(json.dumps(ev, ensure_ascii=False) + chr(10))
            self._last_hash = ev['hash']
            logger.info(f'AuditLogger: initialized at {self._lf}')
    
    def _hash(self, p: str) -> str: return hashlib.sha256(p.encode()).hexdigest()

    def _read_valid_events(self) -> List[Dict[str, Any]]:
        """Lee todos los eventos validos del archivo de auditoria.

        Wrapper sobre get_events() para compatibilidad con _resume_last_hash().
        Ignora lineas corruptas (mismo comportamiento que get_events).
        """
        return self.get_events()

    def _resume_last_hash(self) -> None:
        """Retoma el hash del ultimo evento valido (soporta reinicios del proceso)."""
        existing = self._read_valid_events()
        if existing:
            self._last_hash = existing[-1].get('hash', 'genesis')
    
    def _sign(self, d: str) -> str:
        return hmac.new(self._secret.encode(), d.encode(), hashlib.sha256).hexdigest()
    
    def _write_event(self, event: Dict[str, Any]) -> None:
        # JSON-Lines: un evento por linea (para parseo por linea en get_events)
        with open(self._lf, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event, ensure_ascii=False) + chr(10))
    
    def log_event(self, event_type: str, data: Dict[str, Any], 
                  actor: Optional[str] = None,
                  level: str = SecurityLevel.INTERNAL) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        ev = dict(seq=int(time.time() * 1000), type=event_type, timestamp=now,
                  prev_hash=self._last_hash, actor=actor or 'system', level=level, data=data)
        payload = json.dumps(ev, sort_keys=True, ensure_ascii=False)
        ev['hash'] = self._hash(payload)
        ev['signature'] = self._sign(payload)
        try:
            self._write_event(ev)
            self._last_hash = ev['hash']
            logger.debug(f'Audit: Logged {event_type} [{ev["hash"][:12]}...]')
        except Exception as e:
            logger.error(f'Audit: Write failed: {e}')
        return ev
    
    def verify_chain(self) -> Dict[str, Any]:
        events = []
        try:
            with open(self._lf, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line: events.append(json.loads(line))
        except Exception as e:
            return dict(valid=False, error=str(e), checked=0)
        if not events: return dict(valid=False, error='Empty log', checked=0)
        for i in range(1, len(events)):
            if events[i].get('prev_hash') != events[i-1].get('hash'):
                return dict(valid=False, error=f'Chain broken at event {i}', checked=i,
                            broken_at_index=i)
            # El payload firmado NO incluye hash/signature
            payload_ev = {k: v for k, v in events[i].items()
                          if k not in ('hash', 'signature')}
            payload = json.dumps(payload_ev, sort_keys=True, ensure_ascii=False)
            exp = hmac.new(self._secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
            if events[i].get('signature') != exp:
                return dict(valid=False, error=f'Signature mismatch at event {i}', checked=i,
                            broken_at_index=i)
        return dict(valid=True, checked=len(events),
                    first_event=events[0]['timestamp'], last_event=events[-1]['timestamp'])
    
    def get_events(self, event_type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        events = []
        try:
            with open(self._lf, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue  # linea corrupta/legada: se ignora
        except OSError:
            return []
        if event_type: events = [e for e in events if e.get('type') == event_type]
        return events[-limit:]
    
    def get_stats(self) -> Dict[str, Any]:
        events = self.get_events()
        return dict(total_events=len(events), 
                    last_sequence=events[-1]['seq'] if events else 0,
                    log_file=str(self._lf), log_exists=self._lf.exists())


class ZKPStub:
    """Stub para Zero-Knowledge Proofs.

    En produccion, reemplazar con libreria como py-snark o similar.
    Por ahora, simula el proceso con hashes.
    """
    
    def __init__(self):
        self._proofs: Dict[str, Dict[str, Any]] = {}
    
    def generate_proof(self, claim: str, secret: str) -> Dict[str, Any]:
        pid = hashlib.sha256(f'{claim}:{secret}:{time.time()}'.encode()).hexdigest()[:16]
        proof = dict(proof_id=pid, claim=claim, proof_type='sha256_commitment',
                     commitment=hashlib.sha256(f'{secret}:{time.time()}'.encode()).hexdigest(),
                     generated_at=datetime.now(timezone.utc).isoformat(), valid=True,
                     note='ZKP stub - replace with real lib in production')
        self._proofs[pid] = proof
        return proof
    
    def verify_proof(self, proof_id: str, public_input: str) -> Dict[str, Any]:
        p = self._proofs.get(proof_id)
        if not p: return dict(valid=False, error='not found')
        return dict(valid=True, proof_id=proof_id, 
                    verified_at=datetime.now(timezone.utc).isoformat(),
                    note='ZKP stub - verification simulated')
    
    def get_stats(self) -> Dict[str, Any]:
        return dict(total_proofs=len(self._proofs), proof_ids=list(self._proofs.keys()))


class SecurityManager:
    """Gestor central de seguridad.

    Combina verificacion de credenciales, auditoria y ZKP.
    """
    
    def __init__(self):
        self._verifier = CredentialVerifier()
        self._audit = AuditLogger()
        self._zkp = ZKPStub()
        self._init = False
    
    def initialize(self, admin_token: str = ''):
        if self._init: return
        self._verifier.initialize(admin_token)
        self._audit.log_event('system_init', dict(admin_set=bool(admin_token)), 
                              level=SecurityLevel.CRITICAL)
        self._init = True
        logger.info('SecurityManager: initialized')
    
    def require_auth(self, token: str, required_level: str = SecurityLevel.INTERNAL):
        if not self._verifier.verify(token, required_level):
            # Ni el prefijo del token: el log de auditoria acaba en disco y los
            # 8 primeros caracteres acortan el espacio de busqueda de un token.
            self._audit.log_event('auth_failed',
                                  dict(token_present=bool(token)),
                                  level=SecurityLevel.SECRET)
            raise UnauthorizedError('Unauthorized or insufficient level')
        logger.debug(f'Auth OK: token present={bool(token)}')
    
    def check_permission(self, token: str, perm: str) -> bool:
        if not self._init: self.initialize()
        info = self._verifier._tokens.get(token)
        return bool(info and (perm in info.get('roles', []) or '*' in info.get('roles', [])))
    
    def audit(self, event_type: str, data: Dict[str, Any], 
              actor: Optional[str] = None) -> Dict[str, Any]:
        if not self._init: self.initialize()
        return self._audit.log_event(event_type, data, actor=actor, 
                                     level=SecurityLevel.INTERNAL)
    
    def generate_token(self, level: str = SecurityLevel.INTERNAL,
                       roles: Optional[List[str]] = None) -> str:
        if not self._init: self.initialize()
        return self._verifier.generate_token(level, roles)
    
    def verify_chain(self) -> Dict[str, Any]:
        return self._audit.verify_chain()
    
    def get_audit_events(self, etype: Optional[str] = None, 
                         limit: int = 100) -> List[Dict[str, Any]]:
        return self._audit.get_events(etype, limit)
    
    def get_stats(self) -> Dict[str, Any]:
        return {**self._verifier.get_stats(), 
                **self._audit.get_stats(), 
                **self._zkp.get_stats(),
                'initialized': self._init}


_security: Optional[SecurityManager] = None


def get_security() -> SecurityManager:
    global _security
    if _security is None: _security = SecurityManager()
    return _security


def reset_security() -> None:
    global _security; _security = None


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    sm = get_security()
    sm.initialize('admin-123')
    tok = sm.generate_token(SecurityLevel.INTERNAL, ['user'])
    sm.require_auth(tok)
    sm.audit('test_event', dict(msg='prueba'))
    print(f'Chain: {sm.verify_chain()}')
    print(f'Events: {len(sm.get_audit_events())}')
    print(f'Stats: {sm.get_stats()}')
    print('security.py: OK')
