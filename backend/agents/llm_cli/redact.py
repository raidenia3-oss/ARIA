"""Redacta sensible information de los prompts que salen hacia el CLI.

La salida del CLI es dato NO confiable (puede inyectar texto, instrucciones,
etc.). Pero el riesgo tambien va al revés: lo que le mandamos al CLI no debe
filtrar claves, emails, codigos privados o credenciales. Esta capa limpia el
prompt saliente antes de que llegue al subprocesso.

No es un filtro de salida: es saneamiento de entrada. La salida del CLI se
trata como no confiable en el punto de consumo (ver provider.py).
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

# Patrones que siempre se redactan, independientemente del contexto.
# Orden importa: los mas especificos primero para no dejar restos.
_PATTERNS: List[Tuple[str, re.Pattern]] = [
    (
        "api_key",
        re.compile(
            r"(?i)(api[_-]?key|apikey|token|auth[_-]?token|access[_-]?token|"
            r"secret|client[_-]?secret|password|passwd|pwd|credential|"
            r"bearer|authorization|key)\s*[:=]\s*[\"']?([A-Za-z0-9_\-\.+/=]{8,})[\"']?"
        ),
    ),
    (
        "private_key",
        re.compile(
            r"-----BEGIN (RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----[\s\S]*?"
            r"-----END (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"
        ),
    ),
    (
        "email",
        re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),
    ),
    (
        "url_with_secret",
        re.compile(
            r"(?i)\b((?:https?|ftp)://[^\s\"'<>]+?)(?:[?&](?:key|token|api_key|"
            r"secret|password|auth|access_token)=[^\s\"'<>]+)+"
        ),
    ),
]

# Lo que se deja pasar: texto normal, codigos de usuario (no privados),
# URLs publicas sin credenciales, direcciones de email de dominios internos
# no se tratan como sensibles por defecto — el usuario puede pedir que se
# redacten con una lista personalizada via AURA_CLI_REDACT_PATTERNS.

_PLACEHOLDER = "[REDACTED]"


def redact_prompt(prompt: str, extra_patterns: Dict[str, str] | None = None) -> str:
    """Devuelve una copia del prompt con los patrones sensibles reemplazados.

    Los extra_patterns son un mapeo nombre -> regex (string) que se aplican
    despues de los patrones por defecto. No se almacenan ni logged.
    """
    if not prompt:
        return prompt

    out = prompt

    # Patrones por defecto
    for _name, pattern in _PATTERNS:
        if pattern.search(out):
            if _name == "api_key":
                # Reemplaza solo el valor, no la clave, para no destruir la estructura
                out = pattern.sub(
                    lambda m: _redact_api_key_match(m), out
                )
            elif _name == "private_key":
                out = pattern.sub(_PLACEHOLDER, out)
            elif _name == "email":
                out = pattern.sub(_PLACEHOLDER, out)
            elif _name == "url_with_secret":
                out = pattern.sub(
                    lambda m: m.group(1) + "[REDACTED_QUERY]", out
                )

    # Patrones extra del usuario (string regex)
    if extra_patterns:
        for name, pat_str in extra_patterns.items():
            try:
                rx = re.compile(pat_str)
            except re.error:
                continue
            out = rx.sub(_PLACEHOLDER, out)

    return out


def _redact_api_key_match(m: re.Match) -> str:
    """Redacta solo la parte valor de un par clave=valor, dejando la clave."""
    full = m.group(0)
    # Busca la ultima ocurrencia del separador para cortar el valor
    sep_match = re.search(r"[:=]\s*[\"']?", full)
    if not sep_match:
        return _PLACEHOLDER
    prefix = full[: sep_match.end()]
    return prefix + _PLACEHOLDER


def redaction_report(prompt: str) -> Dict[str, int]:
    """Cuenta cuantas veces cada patron matcheo (para audit, sin exponer contenido)."""
    report: Dict[str, int] = {}
    for name, pattern in _PATTERNS:
        n = len(pattern.findall(prompt))
        if n:
            report[name] = n
    return report