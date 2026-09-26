#!/usr/bin/env python3
"""
AURA Loop Engine - CLI Wrapper
Uso rápido desde la línea de comandos.

Ejemplos:
  python scripts/loop_engine_cli.py "Crear función fibonacci"
  python scripts/loop_engine_cli.py --lang js --max 3 "Crear componente React"
  python scripts/loop_engine_cli.py --interactive
"""

import sys
import os
from pathlib import Path

# Agregar AURA_Core al path
sys.path.insert(0, str(Path(__file__).parent.parent / "AURA_Core"))

from loop_engine import loop_run, LoopEngine


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="AURA Loop Engine CLI - Generación iterativa de código con IA",
        epilog="Ejemplo: python scripts/loop_engine_cli.py 'Crear un endpoint FastAPI para usuarios'",
    )
    parser.add_argument("task", nargs="*", help="Descripción de la tarea de código")
    parser.add_argument(
        "--lang",
        "-l",
        default="python",
        choices=["python", "javascript", "js"],
        help="Lenguaje (default: python)",
    )
    parser.add_argument("--max", "-m", type=int, default=5, help="Máx iteraciones (default: 5)")
    parser.add_argument("--interactive", "-i", action="store_true", help="Modo interactivo")
    parser.add_argument("--quiet", "-q", action="store_true", help="Modo silencioso")

    args = parser.parse_args()

    if args.interactive:
        print("🔄 AURA Loop Engine - Modo Interactivo")
        print("   Escribe tu tarea y presiona Enter. 'salir' para terminar.\n")
        while True:
            try:
                task = input("📝 Tarea> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n👋 ¡Hasta luego!")
                break
            if task.lower() in ("salir", "exit", "quit", "q"):
                print("👋 ¡Hasta luego!")
                break
            if not task:
                continue

            result = loop_run(task, language=args.lang, max_iterations=args.max)

            if result.final_code and not args.quiet:
                print(f"\n{'='*60}")
                print(f"📋 CÓDIGO FINAL ({result.status}):")
                print(f"{'='*60}")
                print(f"```{args.lang}")
                print(result.final_code)
                print("```")
                print()

    elif args.task:
        task = " ".join(args.task)
        result = loop_run(task, language=args.lang, max_iterations=args.max)

        if result.final_code:
            print(f"\n{'='*60}")
            print(f"📋 CÓDIGO FINAL ({result.status}):")
            print(f"{'='*60}")
            print(f"```{args.lang}")
            print(result.final_code)
            print("```")
        else:
            print("❌ No se pudo generar código válido")
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
