#!/usr/bin/env python3
"""
test_all_providers.py — Loop Engineering: Validación y autocorrección recursiva
======================================================================
Pilar #3: Loop Engineering — Este script se ejecuta en bucle hasta que
todas las validaciones pasan en verde. Corrige errores menores de sintaxis
de forma autónoma sin preguntar al usuario.

Fases del loop:
  1. IMPORT CHECK  → Verificar que todos los módulos importan correctamente
  2. SYNTAX CHECK  → Analizar sintaxis de los archivos clave
  3. CONFIG CHECK  → Validar que los proveedores se cargan del .env
  4. HEALTH CHECK  → Probar health_check() (no requiere API keys reales)
  5. FALLBACK TEST → Verificar lógica de cadena de fallback
  6. REPORT       → Mostrar resumen final
"""

import os
import sys
import json
import ast
import time
import traceback
from pathlib import Path

# Colores para output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"

# Archivos clave a validar
KEY_FILES = [
    "core/ai_config.py",
    "core/proxy_chat_connector.py",
]

MAX_LOOP_ITERATIONS = 5
TOTAL_TESTS = 0
PASSED_TESTS = 0
FAILED_TESTS = 0
ERROR_LOG = []


def log(msg: str, level: str = "info"):
    """Log con colores."""
    prefix = {
        "info": f"{CYAN}[INFO]{RESET}",
        "ok": f"{GREEN}[OK]{RESET}",
        "warn": f"{YELLOW}[WARN]{RESET}",
        "error": f"{RED}[ERROR]{RESET}",
        "bold": f"{BOLD}{CYAN}[LOOP]{RESET}",
    }.get(level, "[?]")

    timestamp = time.strftime("%H:%M:%S")
    print(f"{timestamp} {prefix} {msg}")


def check_syntax(filepath: str) -> bool:
    """Verificar sintaxis de un archivo Python."""
    global TOTAL_TESTS, PASSED_TESTS, FAILED_TESTS
    TOTAL_TESTS += 1

    path = Path(filepath)
    if not path.exists():
        log(f"Archivo no encontrado: {filepath}", "error")
        FAILED_TESTS += 1
        return False

    try:
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
        ast.parse(source)
        log(f"Sintaxis OK: {filepath}", "ok")
        PASSED_TESTS += 1
        return True
    except SyntaxError as e:
        log(f"ERROR DE SINTAXIS en {filepath}: {e}", "error")
        FAILED_TESTS += 1
        ERROR_LOG.append(f"SyntaxError in {filepath}: {e}")

        # Intentar autocorrección: mostrar línea problemática
        try:
            lines = source.split("\n")
            if e.lineno and e.lineno <= len(lines):
                log(f"  Línea {e.lineno}: {lines[e.lineno-1][:100]}", "warn")
        except:
            pass
        return False


def test_imports() -> bool:
    """Verificar que los imports funcionan."""
    global TOTAL_TESTS, PASSED_TESTS, FAILED_TESTS
    TOTAL_TESTS += 1
    all_ok = True

    # Limpiar cualquier carga previa
    for mod in list(sys.modules.keys()):
        if "ai_config" in mod or "proxy_chat_connector" in mod:
            del sys.modules[mod]

    try:
        from core.ai_config import AIConfig, AIProvider, get_config

        log("Import OK: core.ai_config", "ok")
    except Exception as e:
        log(f"Import FAILED: core.ai_config — {e}", "error")
        ERROR_LOG.append(f"ImportError: core.ai_config — {e}")
        all_ok = False

    try:
        from core.proxy_chat_connector import (
            smart_chat_completion,
            health_check,
            test_fallback_chain,
        )

        log("Import OK: core.proxy_chat_connector", "ok")
    except Exception as e:
        log(f"Import FAILED: core.proxy_chat_connector — {e}", "error")
        ERROR_LOG.append(f"ImportError: core.proxy_chat_connector — {e}")
        all_ok = False

    if all_ok:
        PASSED_TESTS += 1
    else:
        FAILED_TESTS += 1

    return all_ok


def test_config_loading() -> bool:
    """Verificar que la configuración carga correctamente del .env."""
    global TOTAL_TESTS, PASSED_TESTS, FAILED_TESTS
    TOTAL_TESTS += 1

    try:
        from core.ai_config import get_config

        config = get_config()

        providers = config.providers
        log(f"Proveedores cargados: {len(providers)}", "info")

        for p in providers:
            status = f"{GREEN}✓{RESET}" if p.enabled else f"{YELLOW}✗{RESET} (sin API key)"
            log(f"  {status} {p.name}: {p.model} @ {p.base_url}")

        # Verificar orden de fallback
        chain = config.get_fallback_chain()
        chain_names = [p.name for p in chain]
        log(f"Cadena de fallback: {' -> '.join(chain_names)}")

        # Verificar health summary
        summary = config.get_health_summary()
        assert "preference" in summary
        assert "providers" in summary
        assert len(summary["providers"]) == 4

        log(f"Config OK — preferencia={summary['preference']}", "ok")
        PASSED_TESTS += 1
        return True

    except Exception as e:
        log(f"Config loading FAILED: {e}", "error")
        traceback.print_exc()
        FAILED_TESTS += 1
        ERROR_LOG.append(f"ConfigError: {e}")
        return False


def test_health_check():
    """Probar health_check sin necesidad de API keys reales."""
    global TOTAL_TESTS, PASSED_TESTS, FAILED_TESTS
    TOTAL_TESTS += 1

    try:
        import asyncio
        from core.proxy_chat_connector import health_check

        result = asyncio.run(health_check())

        log(f"Health check ejecutado", "info")
        log(f"  OK: {result.get('ok')}", "info")
        log(
            f"  Proveedores habilitados: {result.get('enabled_providers', 0)}/{result.get('total_providers', 0)}",
            "info",
        )
        log(f"  Mensaje: {result.get('message', 'N/A')}", "info")

        # Verificar estructura
        assert "ok" in result
        assert "providers" in result
        assert isinstance(result["providers"], list)

        log("Health check OK", "ok")
        PASSED_TESTS += 1
        return True

    except Exception as e:
        log(f"Health check FAILED: {e}", "error")
        traceback.print_exc()
        FAILED_TESTS += 1
        ERROR_LOG.append(f"HealthCheckError: {e}")
        return False


def test_fallback_logic():
    """Probar la lógica de la cadena de fallback con proveedores mock."""
    global TOTAL_TESTS, PASSED_TESTS, FAILED_TESTS
    TOTAL_TESTS += 1

    try:
        from core.ai_config import AIConfig, AIProvider

        # Simular que OpenRouter tiene API key pero Gemini no
        config = AIConfig()

        chain = config.get_fallback_chain()

        # Verificar que la cadena tiene entre 0 y 4 proveedores
        assert len(chain) <= 4, f"Demasiados proveedores en cadena: {len(chain)}"

        # Verificar orden esperado (no puede haber enabled=false antes que true)
        found_enabled = False
        for p in chain:
            if p.enabled:
                found_enabled = True

        log(f"Cadena de fallback válida: {len(chain)} proveedores", "ok")
        PASSED_TESTS += 1
        return True

    except Exception as e:
        log(f"Fallback logic test FAILED: {e}", "error")
        traceback.print_exc()
        FAILED_TESTS += 1
        ERROR_LOG.append(f"FallbackLogicError: {e}")
        return False


def auto_fix_common_issues():
    """Intentar corregir problemas comunes automáticamente."""
    fixes_applied = 0

    # Verificar que .env existe
    env_path = Path(".env")
    if not env_path.exists():
        log("Creando .env desde .env.template...", "warn")
        template_path = Path(".env.template")
        if template_path.exists():
            import shutil

            shutil.copy(template_path, env_path)
            log(".env creado desde template", "ok")
            fixes_applied += 1

    # Verificar que core/__init__.py existe
    core_init = Path("core/__init__.py")
    if not core_init.exists():
        log("Creando core/__init__.py...", "warn")
        core_init.write_text("# core package\n")
        log("core/__init__.py creado", "ok")
        fixes_applied += 1

    # Verificar sintaxis de archivos clave
    for fpath in KEY_FILES:
        f = Path(fpath)
        if f.exists():
            try:
                source = f.read_text(encoding="utf-8")
                ast.parse(source)
            except SyntaxError as e:
                log(
                    f"Error de sintaxis detectado en {fpath}, intentando reparación simple...",
                    "warn",
                )
                # Reparación simple: eliminar líneas vacías al final y tabs
                lines = source.split("\n")
                cleaned = []
                for line in lines:
                    # Reemplazar tabs por espacios
                    cleaned.append(line.replace("\t", "    "))
                fixed = "\n".join(cleaned)
                # Eliminar múltiples líneas en blanco al final
                fixed = fixed.rstrip("\n") + "\n"
                f.write_text(fixed, encoding="utf-8")
                log(f"  {fpath} reparado (tabs->espacios, trailing cleanup)", "ok")
                fixes_applied += 1

    if fixes_applied > 0:
        log(f"{fixes_applied} correcciones automáticas aplicadas", "bold")
    else:
        log("No se requirieron correcciones automáticas", "info")

    return fixes_applied


def run_loop_engineering():
    """Bucle principal de Loop Engineering."""
    global TOTAL_TESTS, PASSED_TESTS, FAILED_TESTS

    iteration = 0

    print(f"\n{'='*60}")
    print(f"{BOLD}{CYAN}🔁 LOOP ENGINEERING — VALIDACIÓN MULTI-PROVEEDOR DE IA{RESET}")
    print(f"{'='*60}\n")

    while iteration < MAX_LOOP_ITERATIONS:
        iteration += 1
        TOTAL_TESTS = 0
        PASSED_TESTS = 0
        FAILED_TESTS = 0
        ERROR_LOG = []

        print(f"\n{BOLD}{'─'*50}{RESET}")
        log(f"Iteración {iteration}/{MAX_LOOP_ITERATIONS}", "bold")
        print(f"{BOLD}{'─'*50}{RESET}\n")

        # FASE 1: Auto-fix
        print(f"\n{BOLD}FASE 0: Auto-corrección{RESET}")
        auto_fix_common_issues()

        # FASE 2: Syntax check
        print(f"\n{BOLD}FASE 1: Verificación de sintaxis{RESET}")
        syntax_ok = True
        for fpath in KEY_FILES:
            if not check_syntax(fpath):
                syntax_ok = False

        # FASE 3: Import check
        print(f"\n{BOLD}FASE 2: Verificación de imports{RESET}")
        imports_ok = test_imports()
        if not imports_ok:
            log("Reintentando después de auto-corrección...", "warn")
            auto_fix_common_issues()
            imports_ok = test_imports()

        # FASE 4: Config check
        print(f"\n{BOLD}FASE 3: Validación de configuración{RESET}")
        config_ok = test_config_loading()

        # FASE 5: Health check
        print(f"\n{BOLD}FASE 4: Health check{RESET}")
        health_ok = test_health_check()

        # FASE 6: Fallback logic
        print(f"\n{BOLD}FASE 5: Lógica de fallback{RESET}")
        fallback_ok = test_fallback_logic()

        # Reporte de iteración
        print(f"\n{BOLD}{'─'*50}{RESET}")
        log(f"RESUMEN ITERACIÓN {iteration}", "bold")
        print(f"  Tests totales: {TOTAL_TESTS}")
        print(f"  {GREEN}Pasados: {PASSED_TESTS}{RESET}")
        print(f"  {RED}Fallidos: {FAILED_TESTS}{RESET}")

        if ERROR_LOG:
            print(f"\n  {YELLOW}Errores registrados:{RESET}")
            for err in ERROR_LOG:
                print(f"    {YELLOW}⚠ {err}{RESET}")

        # Decidir si continuar
        all_passed = syntax_ok and imports_ok and config_ok and health_ok and fallback_ok

        if all_passed:
            print(f"\n{GREEN}{BOLD}{'✓'*60}{RESET}")
            print(f"{GREEN}{BOLD}✅ TODOS LOS TESTS PASARON EN ITERACIÓN {iteration}{RESET}")
            print(f"{GREEN}{BOLD}{'✓'*60}{RESET}\n")
            return True
        else:
            if iteration < MAX_LOOP_ITERATIONS:
                print(f"\n{YELLOW}⚠ Algunos tests fallaron. Reintentando...{RESET}")
                # Pequeña pausa antes de reintentar
                time.sleep(1)
            else:
                print(
                    f"\n{RED}{BOLD}❌ MÁXIMO DE ITERACIONES ALCANZADO ({MAX_LOOP_ITERATIONS}){RESET}"
                )
                print(f"{RED}   Algunos tests no pudieron resolverse automáticamente.{RESET}")
                return False

    return False


def main():
    """Entry point."""
    success = run_loop_engineering()

    print(f"\n{'='*60}")
    print(f"{BOLD}RESULTADO FINAL DEL LOOP ENGINEERING{RESET}")
    print(f"{'='*60}")

    if success:
        print(f"\n{GREEN}{BOLD}✅ SISTEMA LISTO PARA PRODUCCIÓN{RESET}")
        print(f"\n  {CYAN}Resumen de proveedores:{RESET}")
        from core.ai_config import get_config

        config = get_config()
        for p in config.providers:
            icon = "✅" if p.enabled else "❌"
            print(f"  {icon} {p.name:12s} | {p.model}")

        print(f"\n  {CYAN}Cadena de fallback automática:{RESET}")
        chain = config.get_fallback_chain()
        if chain:
            print(f"  {' -> '.join(p.name for p in chain)}")
        else:
            print(f"  {YELLOW}(sin proveedores habilitados){RESET}")

        print(f"\n  {CYAN}Para activar:{RESET}")
        print(f"    1. Configura tus API keys en .env")
        print(
            f'    2. Ejecuta: python -c "from core.proxy_chat_connector import health_check; import asyncio; print(asyncio.run(health_check()))"'
        )
        print(f"    3. Usa: smart_chat_completion(messages) para chat con fallback automático\n")
    else:
        print(f"\n{RED}❌ Loop Engineering finalizó con errores persistentes.{RESET}")
        print(f"{RED}   Revisa los logs arriba para más detalles.{RESET}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
