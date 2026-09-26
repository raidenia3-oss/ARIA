"""
AURA Loop Engine v1.0
Motor de Loop Engineering para desarrollo iterativo con IA.

Inspirado en: "Loop Engineering" (Fazt, 2026)
https://youtu.be/VGBeOj0we6c

Concepto: Ejecutar ciclos automáticos de:
  Prompt → Generación de código → Validación → Feedback → Refinamiento

Integra con:
  - AURA ai_router.py (multi-provider: Ollama, OpenRouter, Groq, Gemini, etc.)
  - AURA code_auditor.py (validación de código)
  - CLI standalone y endpoint API
"""

import os
import re
import json
import time
import hashlib
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field, asdict

# ──────────────────────────────────────────
# Configuración
# ──────────────────────────────────────────
MAX_ITERATIONS = 5
DEFAULT_LANGUAGE = "python"
LOOP_LOG_DIR = Path(__file__).parent / "loop_logs"


@dataclass
class LoopIteration:
    """Resultado de una iteración del loop."""

    iteration: int
    prompt: str
    generated_code: str
    validation_result: Dict[str, Any]
    provider_used: str
    model_used: str
    tokens_used: int = 0
    duration_seconds: float = 0.0
    passed: bool = False
    feedback: str = ""


@dataclass
class LoopResult:
    """Resultado final del loop de engineering."""

    task_id: str
    task_description: str
    status: str  # "completed", "max_iterations", "error"
    total_iterations: int
    final_code: str
    iterations: List[LoopIteration] = field(default_factory=list)
    total_duration: float = 0.0
    total_tokens: int = 0
    best_provider: str = ""
    created_at: str = ""


# ──────────────────────────────────────────
# Funciones de validación
# ──────────────────────────────────────────


def validate_python_code(code: str) -> Dict[str, Any]:
    """Valida código Python: sintaxis + imports básicos."""
    result = {"passed": True, "errors": [], "warnings": []}

    # 1. Check sintaxis con compile()
    try:
        compile(code, "<loop_engine>", "exec")
    except SyntaxError as e:
        result["passed"] = False
        result["errors"].append(f"SyntaxError línea {e.lineno}: {e.msg}")

    # 2. Verificar imports básicos
    imports = re.findall(r"^(?:from|import)\s+(\w+)", code, re.MULTILINE)
    stdlib_modules = {
        "os",
        "sys",
        "json",
        "re",
        "time",
        "datetime",
        "pathlib",
        "subprocess",
        "hashlib",
        "typing",
        "dataclasses",
        "collections",
        "abc",
        "io",
        "math",
        "random",
        "urllib",
        "http",
        "requests",
    }
    for imp in imports:
        if imp not in stdlib_modules:
            try:
                __import__(imp)
            except ImportError:
                result["warnings"].append(f"Módulo '{imp}' podría no estar instalado")

    # 3. Verificar que no tenga code injection obvio
    dangerous_patterns = [
        r"os\.system\s*\(",
        r'subprocess\.call\s*\(\s*["\']rm',
        r'__import__\s*\(\s*["\']os["\']',
        r"eval\s*\(\s*input",
        r"exec\s*\(\s*input",
    ]
    for pattern in dangerous_patterns:
        if re.search(pattern, code):
            result["warnings"].append(f"Patrón sospechoso detectado: {pattern}")

    return result


def validate_javascript_code(code: str) -> Dict[str, Any]:
    """Validación básica de código JavaScript."""
    result = {"passed": True, "errors": [], "warnings": []}

    # Verificar balance de llaves
    opens = code.count("{")
    closes = code.count("}")
    if opens != closes:
        result["passed"] = False
        result["errors"].append(f"Llaves desbalanceadas: {opens} abiertas, {closes} cerradas")

    # Verificar balance de paréntesis
    opens_p = code.count("(")
    closes_p = code.count(")")
    if opens_p != closes_p:
        result["passed"] = False
        result["errors"].append(
            f"Paréntesis desbalanceados: {opens_p} abiertos, {closes_p} cerrados"
        )

    return result


def validate_code(code: str, language: str) -> Dict[str, Any]:
    """Dispatcher de validación según lenguaje."""
    validators = {
        "python": validate_python_code,
        "javascript": validate_javascript_code,
        "js": validate_javascript_code,
    }
    validator = validators.get(language, validate_python_code)
    return validator(code)


def extract_code_blocks(response: str) -> List[str]:
    """Extrae bloques de código de una respuesta markdown."""
    # Buscar bloques ```language ... ```
    pattern = r"```(?:python|javascript|js|py)?\s*\n(.*?)```"
    blocks = re.findall(pattern, response, re.DOTALL)

    if not blocks:
        # Si no hay bloques markdown, intentar extraer todo como código
        # si parece código (tiene def, class, import, function, const, etc.)
        code_indicators = ["def ", "class ", "import ", "function ", "const ", "let ", "var "]
        if any(indicator in response for indicator in code_indicators):
            return [response.strip()]

    return [b.strip() for b in blocks if b.strip()]


# ──────────────────────────────────────────
# Motor principal
# ──────────────────────────────────────────


class LoopEngine:
    """
    Motor de Loop Engineering para AURA.

    Ejecuta ciclos iterativos de generación + validación + refinamiento
    usando el ai_router multi-provider existente.
    """

    def __init__(self, language: str = DEFAULT_LANGUAGE, max_iterations: int = MAX_ITERATIONS):
        self.language = language
        self.max_iterations = max_iterations
        self._router = None
        self._init_router()

    def _init_router(self):
        """Inicializa el ai_router de AURA."""
        try:
            sys.path.insert(0, str(Path(__file__).parent))
            from ai_router import AIRouter

            self._router = AIRouter()
        except Exception as e:
            print(f"⚠️ No se pudo cargar AIRouter: {e}")
            self._router = None

    def _query_llm(self, prompt: str, system_prompt: str = "") -> Tuple[str, str, str]:
        """
        Consulta al LLM usando el router de AURA.
        Returns: (response, provider, model)
        """
        if self._router:
            try:
                result = self._router.query(prompt, system_prompt=system_prompt)
                if result.get("response"):
                    return (
                        result["response"],
                        result.get("provider", "unknown"),
                        result.get("model", "unknown"),
                    )
            except Exception as e:
                print(f"⚠️ Error en router: {e}")

        # Fallback: usar Ollama directamente
        return self._query_ollama_fallback(prompt, system_prompt)

    def _query_ollama_fallback(self, prompt: str, system_prompt: str = "") -> Tuple[str, str, str]:
        """Fallback directo a Ollama."""
        import requests

        ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        model = os.environ.get("LOOP_ENGINE_MODEL", "deepseek-r1:8b")

        full_prompt = prompt
        if system_prompt:
            full_prompt = f"[System: {system_prompt}]\n\n{prompt}"

        try:
            resp = requests.post(
                f"{ollama_url}/api/generate",
                json={"model": model, "prompt": full_prompt, "stream": False},
                timeout=120,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("response", ""), "ollama", model
        except Exception as e:
            print(f"⚠️ Ollama fallback error: {e}")

        return "", "none", "none"

    def _build_generation_prompt(
        self, task: str, feedback: str = "", previous_code: str = ""
    ) -> str:
        """Construye el prompt para generación de código."""
        lang_name = "Python" if self.language == "python" else "JavaScript"

        prompt = f"""Eres un ingeniero de software experto. Genera código {lang_name} limpio, modular y documentado.

TAREA: {task}

REGLAS:
- Código completo y funcional
- Incluir docstrings/comentarios explicativos
- Manejo de errores con try/except
- Nombres de variables descriptivos
- Sin código malicioso ni peligroso
"""
        if previous_code:
            prompt += f"""
CÓDIGO ANTERIOR (mejorar esto):
```{self.language}
{previous_code}
```
"""
        if feedback:
            prompt += f"""
FEEDBACK DE VALIDACIÓN (corregir estos errores):
{feedback}
"""
        prompt += f"""
Devuelve SOLO el código {lang_name} dentro de un bloque ```{self.language}```
"""
        return prompt

    def _build_validation_prompt(self, code: str, validation: Dict) -> str:
        """Construye prompt de refinamiento basado en errores de validación."""
        errors = "\n".join(validation.get("errors", []))
        warnings = "\n".join(validation.get("warnings", []))

        return f"""El siguiente código tiene errores de validación. Corrígelos:

CÓDIGO:
```{self.language}
{code}
```

ERRORES:
{errors}

ADVERTENCIAS:
{warnings}

Devuelve el código corregido dentro de un bloque ```{self.language}```
"""

    def run(self, task: str, callback=None) -> LoopResult:
        """
        Ejecuta el loop de engineering completo.

        Args:
            task: Descripción de la tarea a resolver
            callback: Función opcional(iteration_num, result) para notificar progreso

        Returns:
            LoopResult con el resultado final
        """
        task_id = hashlib.md5(f"{task}{time.time()}".encode()).hexdigest()[:12]
        created_at = datetime.now().isoformat()
        start_time = time.time()

        print(f"\n{'='*60}")
        print(f"🔄 AURA LOOP ENGINE - Tarea: {task[:80]}...")
        print(f"   ID: {task_id} | Lenguaje: {self.language} | Max iter: {self.max_iterations}")
        print(f"{'='*60}\n")

        iterations = []
        final_code = ""
        best_provider = ""
        total_tokens = 0

        for i in range(1, self.max_iterations + 1):
            iter_start = time.time()
            print(f"--- Iteración {i}/{self.max_iterations} ---")

            # 1. Generar/refinar código
            feedback = ""
            previous_code = ""
            if iterations:
                last = iterations[-1]
                if not last.passed:
                    feedback = last.feedback or "; ".join(last.validation_result.get("errors", []))
                    previous_code = last.generated_code

            prompt = self._build_generation_prompt(task, feedback, previous_code)
            system_prompt = (
                f"Eres un ingeniero de software experto en {self.language}. "
                "Genera código limpio, funcional y bien documentado. "
                "Responde SOLO con bloques de código, sin explicaciones adicionales."
            )

            print(f"  🤖 Consultando LLM...")
            response, provider, model = self._query_llm(prompt, system_prompt)

            if not response:
                print(f"  ❌ Sin respuesta del LLM")
                iterations.append(
                    LoopIteration(
                        iteration=i,
                        prompt=prompt,
                        generated_code="",
                        validation_result={"passed": False, "errors": ["Sin respuesta del LLM"]},
                        provider_used=provider,
                        model_used=model,
                        duration_seconds=time.time() - iter_start,
                    )
                )
                continue

            # 2. Extraer código
            code_blocks = extract_code_blocks(response)
            code = code_blocks[0] if code_blocks else response.strip()

            print(f"  📝 Código generado ({len(code)} chars) via {provider}/{model}")

            # 3. Validar
            validation = validate_code(code, self.language)
            passed = validation["passed"]

            if passed:
                print(f"  ✅ Validación PASSED")
            else:
                print(f"  ❌ Validación FAILED: {validation['errors']}")

            iter_duration = time.time() - iter_start

            iteration = LoopIteration(
                iteration=i,
                prompt=prompt,
                generated_code=code,
                validation_result=validation,
                provider_used=provider,
                model_used=model,
                duration_seconds=iter_duration,
                passed=passed,
                feedback="; ".join(validation.get("errors", [])),
            )
            iterations.append(iteration)

            if provider not in ("none", "unknown"):
                best_provider = provider

            if callback:
                callback(i, iteration)

            # 4. Si pasó, terminar
            if passed:
                final_code = code
                print(f"\n🎉 Loop completado en {i} iteración(es)")
                break

            final_code = code  # Guardar el último código generado

        total_duration = time.time() - start_time
        status = "completed" if iterations and iterations[-1].passed else "max_iterations"

        result = LoopResult(
            task_id=task_id,
            task_description=task,
            status=status,
            total_iterations=len(iterations),
            final_code=final_code,
            iterations=iterations,
            total_duration=round(total_duration, 2),
            total_tokens=total_tokens,
            best_provider=best_provider,
            created_at=created_at,
        )

        # Guardar log
        self._save_log(result)

        print(f"\n{'='*60}")
        print(f"📊 RESUMEN DEL LOOP")
        print(f"   Estado: {status}")
        print(f"   Iteraciones: {len(iterations)}/{self.max_iterations}")
        print(f"   Duración: {total_duration:.1f}s")
        print(f"   Mejor provider: {best_provider}")
        print(f"   Log guardado: {LOOP_LOG_DIR / f'{task_id}.json'}")
        print(f"{'='*60}\n")

        return result

    def _save_log(self, result: LoopResult):
        """Guarda el resultado del loop en un archivo JSON."""
        LOOP_LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = LOOP_LOG_DIR / f"{result.task_id}.json"

        data = {
            "task_id": result.task_id,
            "task_description": result.task_description,
            "status": result.status,
            "total_iterations": result.total_iterations,
            "final_code": result.final_code,
            "total_duration": result.total_duration,
            "best_provider": result.best_provider,
            "created_at": result.created_at,
            "iterations": [
                {
                    "iteration": it.iteration,
                    "provider_used": it.provider_used,
                    "model_used": it.model_used,
                    "passed": it.passed,
                    "duration_seconds": it.duration_seconds,
                    "errors": it.validation_result.get("errors", []),
                    "warnings": it.validation_result.get("warnings", []),
                    "code_preview": (
                        it.generated_code[:200] + "..."
                        if len(it.generated_code) > 200
                        else it.generated_code
                    ),
                }
                for it in result.iterations
            ],
        }

        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


# ──────────────────────────────────────────
# Función de conveniencia
# ──────────────────────────────────────────


def loop_run(task: str, language: str = "python", max_iterations: int = 5) -> LoopResult:
    """Función de conveniencia para ejecutar un loop rápido."""
    engine = LoopEngine(language=language, max_iterations=max_iterations)
    return engine.run(task)


# ──────────────────────────────────────────
# CLI
# ──────────────────────────────────────────


def main():
    """Punto de entrada CLI para Loop Engine."""
    import argparse

    parser = argparse.ArgumentParser(
        description="AURA Loop Engine - Desarrollo iterativo con IA",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python loop_engine.py "Crear una función que calcule fibonacci"
  python loop_engine.py --lang javascript --max-iter 3 "Crear un componente React"
  python loop_engine.py --interactive
        """,
    )
    parser.add_argument("task", nargs="?", help="Descripción de la tarea")
    parser.add_argument(
        "--lang",
        default="python",
        choices=["python", "javascript", "js"],
        help="Lenguaje de programación (default: python)",
    )
    parser.add_argument(
        "--max-iter", type=int, default=5, help="Máximo de iteraciones (default: 5)"
    )
    parser.add_argument("--interactive", action="store_true", help="Modo interactivo")

    args = parser.parse_args()

    if args.interactive:
        print("🔄 AURA Loop Engine - Modo Interactivo")
        print("   Escribe tu tarea y presiona Enter. Escribe 'salir' para terminar.\n")
        while True:
            task = input("📝 Tarea> ").strip()
            if task.lower() in ("salir", "exit", "quit", "q"):
                print("👋 ¡Hasta luego!")
                break
            if not task:
                continue
            result = loop_run(task, language=args.lang, max_iterations=args.max_iter)
            if result.final_code:
                print(f"\n📋 CÓDIGO FINAL:\n```{args.lang}\n{result.final_code}\n```\n")
    elif args.task:
        result = loop_run(args.task, language=args.lang, max_iterations=args.max_iter)
        if result.final_code:
            print(f"\n📋 CÓDIGO FINAL:\n```{args.lang}\n{result.final_code}\n```\n")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
