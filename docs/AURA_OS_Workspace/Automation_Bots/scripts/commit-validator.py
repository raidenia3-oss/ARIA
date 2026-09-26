#!/usr/bin/env python3
"""
CONVENTIONAL COMMITS VALIDATOR — Hook de git para validar mensajes de commit
============================================================================
Estándar: Conventional Commits v1.0.0
Tipos soportados: feat, fix, refactor, test, build, chore, docs, style, perf, ci, revert

Uso:
  1. Como prepare-commit-msg hook (automático):
     Copiar a .git/hooks/prepare-commit-msg
     chmod +x .git/hooks/prepare-commit-msg

  2. Como script independiente:
     python scripts/commit-validator.py
"""

import re
import sys
import os
from pathlib import Path
from typing import Optional

# ─── Configuración ───
TYPES = [
    "feat",  # Nueva funcionalidad
    "fix",  # Corrección de bug
    "refactor",  # Refactorización de código
    "test",  # Adición o modificación de tests
    "build",  # Cambios en sistema de build o dependencias
    "chore",  # Tareas de mantenimiento
    "docs",  # Cambios en documentación
    "style",  # Cambios de formato (espacios, puntuación, etc)
    "perf",  # Mejoras de rendimiento
    "ci",  # Cambios en CI/CD
    "revert",  # Reversión de cambios anteriores
]

SCOPES = [
    "core",
    "api",
    "frontend",
    "mobile",
    "deploy",
    "config",
    "docker",
    "docs",
    "deps",
    "security",
    "test",
    "ci",
    "script",
]

PATTERN = re.compile(
    r"^(?P<type>" + "|".join(TYPES) + r")"
    r"(\((?P<scope>[a-z0-9_-]+)\))?"
    r"(?P<breaking>!)?"
    r":\s(?P<subject>[A-Z].*)$",
    re.MULTILINE,
)

FOOTER_PATTERN = re.compile(
    r"^(BREAKING CHANGE|Reviewed-by|Refs|Closes|Fixes|Resolves|Co-authored-by):\s.+$", re.MULTILINE
)

# ─── Colores ANSI ───
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def validate_message(message: str) -> tuple[bool, list[str]]:
    """
    Validar mensaje de commit contra el estándar Conventional Commits.
    Retorna: (es_válido, lista_de_errores)
    """
    errors = []
    lines = message.strip().split("\n")
    first_line = lines[0].strip()

    if not first_line:
        errors.append("El mensaje de commit está vacío")
        return False, errors

    # Validar primera línea
    match = PATTERN.match(first_line)
    if not match:
        errors.append(
            f"Formato incorrecto. Debe ser: {YELLOW}tipo(alcance): asunto{RESET}\n"
            f"  Tipos válidos: {', '.join(TYPES)}\n"
            f"  Ejemplo: {CYAN}feat(api): agregar endpoint de autenticación{RESET}"
        )
        return False, errors

    # Validar tipo
    commit_type = match.group("type")
    if commit_type not in TYPES:
        errors.append(f"Tipo '{commit_type}' no reconocido. Usa uno de: {', '.join(TYPES)}")
        return False, errors

    # Validar scope (opcional pero si está, debe ser válido)
    scope = match.group("scope")
    if scope and scope not in SCOPES:
        errors.append(
            f"Scope '{scope}' no reconocido. Usa uno de: {', '.join(SCOPES)}\n"
            f"  O agrega un scope personalizado si es necesario."
        )

    # Validar que el asunto empiece con mayúscula
    subject = match.group("subject")
    if subject and subject[0].islower():
        errors.append(f"El asunto debe comenzar con mayúscula: '{subject}'")

    # Validar longitud de línea
    if len(first_line) > 72:
        errors.append(f"Línea de asunto muy larga ({len(first_line)} chars, máximo 72)")

    # Validar línea en blanco después del asunto
    if len(lines) > 1 and lines[1].strip() != "":
        errors.append("Debe haber una línea en blanco después del asunto")

    # Validar que la descripción (si existe) tenga líneas <= 72 caracteres
    for i, line in enumerate(lines[2:], 3):
        stripped = line.strip()
        if not stripped:
            continue
        if len(stripped) > 72 and not FOOTER_PATTERN.match(stripped):
            errors.append(f"Línea {i} muy larga ({len(stripped)} chars, máximo 72)")

    return len(errors) == 0, errors


def interactive_commit_builder() -> str:
    """Asistente interactivo para construir un mensaje de commit válido."""
    print(f"\n{BOLD}{CYAN}=== ASISTENTE DE CONVENTIONAL COMMITS ==={RESET}\n")
    print("Tipos disponibles:")
    for t in TYPES:
        print(f"  {GREEN}{t}{RESET}")
    print()

    # Tipo
    while True:
        commit_type = (
            input(f"{BOLD}Tipo{RESET} (feat/fix/refactor/test/build/chore): ").strip().lower()
        )
        if commit_type in TYPES:
            break
        print(f"{RED}Tipo inválido. Usa uno de: {', '.join(TYPES)}{RESET}")

    # Scope
    scope = input(f"{BOLD}Scope{RESET} (opcional, ej: core/api/mobile/deploy): ").strip().lower()
    if scope and scope not in SCOPES:
        if (
            input(
                f"  {YELLOW}Scope '{scope}' no estándar. ¿Usarlo de todas formas? (s/N):{RESET} "
            ).lower()
            != "s"
        ):
            scope = ""

    # Breaking change
    breaking = input(f"{BOLD}¿Breaking change?{RESET} (s/N): ").strip().lower() == "s"
    breaking_mark = "!" if breaking else ""

    # Asunto
    while True:
        subject = input(f"{BOLD}Asunto{RESET} (en presente, primera mayúscula): ").strip()
        if subject:
            subject = subject[0].upper() + subject[1:]  # Capitalizar primera letra
            if len(subject) > 72:
                print(f"{RED}Muy largo ({len(subject)} chars). Máximo 72.{RESET}")
                continue
            break
        print(f"{RED}El asunto no puede estar vacío.{RESET}")

    # Construir primera línea
    if scope:
        first_line = f"{commit_type}({scope}){breaking_mark}: {subject}"
    else:
        first_line = f"{commit_type}{breaking_mark}: {subject}"

    # Descripción
    print(f"\n{BOLD}Descripción{RESET} (opcional, líneas de <72 chars, vacío para terminar):")
    description_lines = []
    for i in range(1, 11):
        line = input(f"  [{i}]: ")
        if not line:
            break
        description_lines.append(line)
        if i == 10:
            break

    # Footers
    print(f"\n{BOLD}Footers{RESET} (opcional, ej: Closes #42, BREAKING CHANGE: ...)")
    footer_lines = []
    for i in range(1, 4):
        line = input(f"  [{i}]: ")
        if not line:
            break
        footer_lines.append(line)
        if i == 3:
            break

    # Construir mensaje completo
    lines = [first_line, ""]  # asunto + línea en blanco
    if description_lines:
        lines.extend(description_lines)
        lines.append("")  # línea en blanco después de descripción
    if footer_lines:
        lines.extend(footer_lines)

    message = "\n".join(lines)
    return message


def main():
    """Entry point."""
    # Modo hook: leer mensaje del archivo de commit
    if len(sys.argv) > 1:
        commit_file = sys.argv[1]
        if os.path.exists(commit_file):
            with open(commit_file, "r", encoding="utf-8") as f:
                message = f.read()

            # Ignorar merge commits y commits de git
            if message.startswith("Merge") or message.strip().startswith("#"):
                sys.exit(0)

            is_valid, errors = validate_message(message)
            if is_valid:
                sys.exit(0)
            else:
                print(f"\n{RED}{BOLD}❌ Mensaje de commit inválido:{RESET}")
                for err in errors:
                    print(f"  {err}")
                print(f"\n{YELLOW}Usa el asistente: python scripts/commit-validator.py{RESET}")
                sys.exit(1)

    # Modo interactivo: construir commit
    print(f"\n{BOLD}{CYAN}🔧 ASISTENTE DE COMMITS — AURA ECOSYSTEM{RESET}")
    print(f"{'─'*55}")

    message = interactive_commit_builder()

    print(f"\n{BOLD}Mensaje generado:{RESET}")
    print(f"{CYAN}{message}{RESET}")

    is_valid, errors = validate_message(message)
    if is_valid:
        print(f"\n{GREEN}{BOLD}✅ Mensaje válido según Conventional Commits{RESET}")
        # Guardar para usar con git commit -F
        output_file = Path(".git/COMMIT_EDITMSG")
        output_file.write_text(message, encoding="utf-8")
        print(f"\n{YELLOW}Usa este comando para commitear:{RESET}")
        print(f"  git commit -F .git/COMMIT_EDITMSG\n")
    else:
        print(f"\n{RED}{BOLD}❌ Errores encontrados:{RESET}")
        for err in errors:
            print(f"  {err}")
        print()
        sys.exit(1)


if __name__ == "__main__":
    main()
