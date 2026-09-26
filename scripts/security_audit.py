"""Automated security audit for AURA backend.

Checks:
- Environment variables (.env) for weak or missing secrets
- CORS configuration
- Rate limiting presence
- Security headers (HSTS, X-Frame-Options, etc.)
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATHS = [BASE_DIR / ".env", BASE_DIR / ".env.local", BASE_DIR / ".env.cloud", BASE_DIR / "backend" / ".env.local"]
MAIN_PY = BASE_DIR / "backend" / "main.py"

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"


def check(name: str, condition: bool, detail: str = "") -> tuple[str, str, str]:
    status = PASS if condition else FAIL
    return status, name, detail


def audit_env() -> list[tuple[str, str, str]]:
    findings: list[tuple[str, str, str]] = []

    if load_dotenv:
        for path in ENV_PATHS:
            if path.exists():
                load_dotenv(path, override=False)

    secret = os.getenv("SECRET_KEY", "")
    findings.append(check(
        "SECRET_KEY set",
        bool(secret),
        f"length={len(secret)}",
    ))
    findings.append(check(
        "SECRET_KEY not default",
        secret not in {"", "dev-key-change-in-prod", "change-me"},
        "",
    ))

    db_url = os.getenv("DATABASE_URL", "")
    findings.append(check(
        "DATABASE_URL set",
        bool(db_url),
        "",
    ))

    redis_url = os.getenv("REDIS_URL", "")
    findings.append(check(
        "REDIS_URL set",
        bool(redis_url),
        "",
    ))

    jwt_secret = os.getenv("AURA_JWT_SECRET", "")
    findings.append(check(
        "AURA_JWT_SECRET set",
        bool(jwt_secret),
        f"length={len(jwt_secret)}",
    ))

    cors = os.getenv("AURA_CORS_ORIGINS", "")
    origins = [o.strip() for o in cors.split(",") if o.strip()]
    has_wildcard_origin = "*" in origins
    has_localhost = any(o.startswith("http://localhost") or o.startswith("http://127.0.0.1") for o in origins)
    findings.append(check(
        "CORS restricted",
        not has_wildcard_origin,
        "wildcard origin detected" if has_wildcard_origin else "restricted origins",
    ))
    findings.append(check(
        "CORS includes localhost",
        has_localhost,
        "localhost missing" if not has_localhost else "",
    ))

    debug = os.getenv("DEBUG", "false").lower() == "true"
    env = os.getenv("ENVIRONMENT", "development")
    findings.append(check(
        "DEBUG disabled in production",
        not debug or env != "production",
        f"DEBUG={debug}, ENVIRONMENT={env}",
    ))

    return findings


def audit_backend_config() -> list[tuple[str, str, str]]:
    findings: list[tuple[str, str, str]] = []

    if not MAIN_PY.exists():
        return findings + [(FAIL, "backend/main.py exists", "missing")]

    text = MAIN_PY.read_text(encoding="utf-8")

    findings.append(check(
        "CORSMiddleware present",
        "CORSMiddleware" in text,
        "",
    ))

    findings.append(check(
        "Rate limiting present",
        "RateLimiter" in text or "limiter" in text or "rate_limit" in text,
        "",
    ))

    findings.append(check(
        "HSTS header configured",
        "Strict-Transport-Security" in text,
        "",
    ))

    findings.append(check(
        "X-Frame-Options configured",
        "X-Frame-Options" in text,
        "",
    ))

    findings.append(check(
        "X-Content-Type-Options configured",
        "X-Content-Type-Options" in text,
        "",
    ))

    findings.append(check(
        "Referrer-Policy configured",
        "Referrer-Policy" in text,
        "",
    ))

    findings.append(check(
        "Permissions-Policy configured",
        "Permissions-Policy" in text,
        "",
    ))

    findings.append(check(
        "JWT/SECRET_KEY used",
        "SECRET_KEY" in text or "JWT" in text,
        "",
    ))

    findings.append(check(
        "Health check endpoint present",
        "/health" in text,
        "",
    ))

    return findings


def main() -> int:
    print("AURA Security Audit v1.0")
    print("=" * 60)

    findings = audit_env() + audit_backend_config()
    passed = 0
    failed = 0
    warnings = 0

    for status, name, detail in findings:
        if status == PASS:
            passed += 1
        elif status == WARN:
            warnings += 1
        else:
            failed += 1

        marker = "[PASS]" if status == PASS else ("[WARN]" if status == WARN else "[FAIL]")
        print(f"{marker} {name}")
        if detail:
            print(f"    {detail}")

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {warnings} warnings")

    if failed:
        print("Audit result: FAIL")
        return 1
    print("Audit result: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
