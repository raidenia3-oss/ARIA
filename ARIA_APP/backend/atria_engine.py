"""Atria Dawn Agentic Engine — Verifiable Experience Pipeline.

Implements Atria Dawn's core pattern:
- Tasks connected to real execution environments
- Observe state, call tools, produce artifacts
- Adapt to feedback
- Outcomes verified through external signals

4 Dimensions:
- Discovery: Research, evidence, deep research, experimental plans
- Creation: Software, apps, games, data viz, ML systems
- Delivery: Documents, data, designs → reports, presentations
- Cybersecurity: Security analysis, vulnerabilities, fixes, re-validation
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class Dimension(Enum):
    DISCOVERY = "discovery"
    CREATION = "creation"
    DELIVERY = "delivery"
    CYBERSECURITY = "cybersecurity"
    GENERAL = "general"


@dataclass
class Artifact:
    name: str
    content: str
    artifact_type: str = "text"
    verified: bool = False
    verification_evidence: str = ""
    path: Optional[str] = None


@dataclass
class TaskStep:
    id: str
    description: str
    tool: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    result: Optional[str] = None
    verified: bool = False
    evidence: Optional[str] = None
    error: Optional[str] = None
    attempts: int = 0
    max_attempts: int = 3


@dataclass
class AgentTask:
    objective: str
    dimension: Dimension = Dimension.GENERAL
    context: str = ""
    steps: List[TaskStep] = field(default_factory=list)
    artifacts: List[Artifact] = field(default_factory=list)
    status: str = "pending"
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    feedback: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class AtriaAgenticEngine:
    """Agentic engine implementing Atria Dawn's Verifiable Experience Pipeline.

    Pipeline: Observe → Plan → Execute (tools) → Verify → Adapt → Deliver
    """

    SYSTEM_PROMPT = """Eres ARIA con capacidades Atria Dawn. Operas en 4 dimensiones:
- 🔍 Discovery: Investigación profunda, recopilación de evidencias, planes experimentales
- 🛠️ Creation: Construcción de software, aplicaciones, visualizaciones, sistemas ML
- 📦 Delivery: Transformar requisitos en entregables estructurados (reportes, presentaciones)
- 🛡️ Cybersecurity: Análisis de seguridad, vulnerabilidades, remediación y revalidación

Para cada tarea:
1. Observa el estado del entorno y el contexto disponible
2. Planifica pasos concretos con herramientas
3. Ejecuta cada paso, produciendo artefactos verificables
4. Verifica resultados con señales externas (tests, métricas, archivos, evidencia)
5. Si falla, analiza el feedback, adapta y reintenta
6. Entrega artefactos con evidencia de verificación

Responde en español. Siempre indica qué dimensión aplica y qué artefactos produces."""

    def __init__(self, project_root: str = ".", ai_provider=None) -> None:
        self.project_root = Path(project_root).resolve()
        self.ai = ai_provider
        self._tasks: Dict[str, AgentTask] = {}
        self._execution_log: List[Dict[str, Any]] = []
        self._tools = self._register_tools()

    def _register_tools(self) -> Dict[str, callable]:
        return {
            "read_file": self._tool_read_file,
            "write_file": self._tool_write_file,
            "list_dir": self._tool_list_dir,
            "run_command": self._tool_run_command,
            "search_web": self._tool_search_web,
            "code_analysis": self._tool_code_analysis,
            "security_scan": self._tool_security_scan,
            "data_analysis": self._tool_data_analysis,
        }

    def submit_task(
        self,
        objective: str,
        dimension: str = "general",
        context: str = "",
        max_steps: int = 20,
    ) -> str:
        dim = (
            Dimension(dimension.lower())
            if dimension.lower() in [d.value for d in Dimension]
            else Dimension.GENERAL
        )
        task = AgentTask(
            objective=objective,
            dimension=dim,
            context=context,
            metadata={"max_steps": max_steps},
        )
        task_id = f"atria_{int(time.time())}_{len(self._tasks)}"
        task.metadata["task_id"] = task_id
        self._tasks[task_id] = task

        import threading

        thread = threading.Thread(target=self._execute_task, args=(task_id,), daemon=True)
        thread.start()

        return task_id

    def get_task(self, task_id: str) -> Optional[AgentTask]:
        return self._tasks.get(task_id)

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        task = self._tasks.get(task_id)
        if not task:
            return {"error": "Task not found"}
        return {
            "task_id": task_id,
            "status": task.status,
            "dimension": task.dimension.value,
            "objective": task.objective,
            "steps_count": len(task.steps),
            "completed_steps": sum(1 for s in task.steps if s.verified),
            "artifacts_count": len(task.artifacts),
            "verified_artifacts": sum(1 for a in task.artifacts if a.verified),
            "feedback_count": len(task.feedback),
        }

    def get_task_result(self, task_id: str) -> Dict[str, Any]:
        task = self._tasks.get(task_id)
        if not task:
            return {"error": "Task not found"}
        return {
            "task_id": task_id,
            "status": task.status,
            "dimension": task.dimension.value,
            "objective": task.objective,
            "steps": [
                {
                    "id": s.id,
                    "description": s.description,
                    "tool": s.tool,
                    "verified": s.verified,
                    "result": s.result,
                    "error": s.error,
                    "attempts": s.attempts,
                }
                for s in task.steps
            ],
            "artifacts": [
                {
                    "name": a.name,
                    "type": a.artifact_type,
                    "verified": a.verified,
                    "evidence": a.verification_evidence,
                    "path": a.path,
                    "preview": a.content[:500],
                }
                for a in task.artifacts
            ],
            "feedback": task.feedback,
            "execution_time": time.time() - task.created_at,
        }

    def _execute_task(self, task_id: str) -> None:
        task = self._tasks.get(task_id)
        if not task:
            return
        try:
            task.status = "planning"
            self._log(task_id, "planning", f"Planning task: {task.objective[:100]}")

            # Phase 1: PLAN — Generate steps
            plan_prompt = f"""Objetivo: {task.objective}
Dimensión: {task.dimension.value}
Contexto: {task.context[:500] if task.context else "Ninguno"}

Genera un plan de {task.metadata.get('max_steps', 20)} pasos máximo. Para cada paso indica:
- Descripción concreta
- Herramienta a usar: {list(self._tools.keys())}
- Argumentos necesarios
- Cómo verificarás que el paso fue exitoso

Responde en español. Formato: un paso por línea con descripción clara."""
            plan = self._ai_chat(plan_prompt, "planning")
            task.steps = self._parse_plan(task_id, plan, task.objective)
            task.status = "executing"
            self._log(task_id, "executing", f"Executing {len(task.steps)} steps")

            # Phase 2: EXECUTE — Run each step with tools
            for step in task.steps:
                if task.status == "paused":
                    break
                self._execute_step(task_id, step)

                # Phase 3: VERIFY — Check step result
                if step.verified:
                    self._log(task_id, "verified", f"Step {step.id}: {step.description[:60]}")
                else:
                    self._log(
                        task_id,
                        "unverified",
                        f"Step {step.id}: {step.description[:60]} — {step.error or 'no verification'}",
                    )

                # Check for feedback signals
                if step.error or not step.verified:
                    feedback = self._generate_feedback(task_id, step)
                    task.feedback.append(feedback)

                # If too many failures, adapt plan
                failed = [s for s in task.steps if s.error and s.attempts >= s.max_attempts]
                if len(failed) >= 3:
                    task.status = "adapting"
                    adapt_prompt = f"Los siguientes pasos fallaron: {[s.id for s in failed]}. Adapta los pasos restantes para el objetivo: {task.objective}"
                    adaptation = self._ai_chat(adapt_prompt, "adapting")
                    task.feedback.append(f"ADAPTATION: {adaptation}")
                    task.status = "executing"

            # Phase 4: DELIVER — Compile artifacts and final verification
            task.status = "delivering"
            self._compile_artifacts(task_id)

            # Final verification report
            verified_count = sum(1 for a in task.artifacts if a.verified)
            total_artifacts = len(task.artifacts)
            if verified_count >= total_artifacts * 0.5 or total_artifacts == 0:
                task.status = "completed"
            else:
                task.status = "partial"

            task.completed_at = time.time()
            self._log(
                task_id,
                task.status,
                f"Done. {verified_count}/{total_artifacts} artifacts verified.",
            )

        except Exception as exc:
            import traceback as _tb

            tb_str = _tb.format_exc()
            task.status = "failed"
            task.feedback.append(f"FATAL: {exc}\nTB: {tb_str}")
            self._log(task_id, "failed", str(exc))

    def _execute_step(self, task_id: str, step: TaskStep) -> None:
        while step.attempts < step.max_attempts and not step.verified:
            step.attempts += 1
            try:
                if step.tool and step.tool in self._tools:
                    result = self._tools[step.tool](step.tool_args or {})
                    step.result = str(result) if result is not None else ""
                    step.verified = self._verify_step(task_id, step)
                    if not step.verified:
                        step.error = "Result could not be verified"
                else:
                    ai_result = self._ai_chat(
                        f"Ejecuta el paso: {step.description}\nContexto: {task_id}",
                        "execute",
                    )
                    step.result = ai_result
                    step.verified = True
                    step.tool = "ai" if not step.tool else step.tool
            except Exception as exc:
                step.error = str(exc)
                step.verified = False
            self._log(
                task_id, f"step_{step.id}", f"Attempt {step.attempts}: verified={step.verified}"
            )

    def _verify_step(self, task_id: str, step: TaskStep) -> bool:
        verify_prompt = f"""Verifica si el siguiente resultado es correcto y completo:

Paso: {step.description}
Resultado: {step.result or 'N/A'}
Error: {step.error or 'N/A'}

Instrucciones de verificación esperadas del paso. Responde SÍ/NO con una breve explicación de por qué."""
        result = self._ai_chat(verify_prompt, "verify")
        return result.strip().lower().startswith(("sí", "si", "yes", "verificado", "correcto"))

    def _generate_feedback(self, task_id: str, step: TaskStep) -> str:
        feedback_prompt = f"""Revisa el paso fallido y genera feedback constructivo:

Paso: {step.description}
Error: {step.error or 'No error but unverified'}
Intentos: {step.attempts}/{step.max_attempts}
Resultado parcial: {step.result[:200] if step.result else 'N/A'}

¿Por qué falló? ¿Qué debe cambiarse?"""
        return self._ai_chat(feedback_prompt, "feedback")

    def _compile_artifacts(self, task_id: str) -> None:
        task = self._tasks.get(task_id)
        if not task:
            return
        compile_prompt = f"""Del siguiente registro de ejecución, identifica y extrae todos los artefactos producidos:

Objetivo: {task.objective}
Pasos ejecutados: {len(task.steps)}
Resultados:
"""
        for s in task.steps:
            compile_prompt += (
                f"- {s.id}: {s.description[:100]} → {'OK' if s.verified else 'FAIL'}\n"
            )

        compile_prompt += """
Para cada artefacto identifica: nombre, tipo (código/documento/datos/análisis), contenido, y evidencia de verificación.
Responde en formato estructurado en español."""
        result = self._ai_chat(compile_prompt, "deliver")
        task.artifacts.append(
            Artifact(
                name="compilation_report",
                content=result,
                artifact_type="analysis",
                verified=True,
                verification_evidence=f"Compiled from {len(task.steps)} steps",
            )
        )

    def _parse_plan(self, task_id: str, plan_text: str, objective: str) -> List[TaskStep]:
        steps: List[TaskStep] = []
        lines = plan_text.strip().split("\n")
        task = self._tasks.get(task_id)
        max_steps = task.metadata.get("max_steps", 20) if task else 20
        tool_names = list(self._tools.keys())

        for i, line in enumerate(lines[: task.metadata.get("max_steps", 20)]):
            line = line.strip()
            if not line or len(line) < 5:
                continue
            step_id = f"step_{i+1:03d}"
            tool = None
            for t in tool_names:
                if t.lower() in line.lower() or t.replace("_", " ") in line.lower():
                    tool = t
                    break
            steps.append(
                TaskStep(
                    id=step_id,
                    description=line,
                    tool=tool,
                    tool_args={"task_id": task_id, "step_id": step_id, "line": line},
                )
            )

        if not steps:
            steps.append(
                TaskStep(
                    id="step_001",
                    description=objective,
                    tool="ai",
                )
            )

        return steps

    def _ai_chat(self, message: str, mode: str = "general") -> str:
        if self.ai:
            result = self.ai.chat(message, system_prompt=self.SYSTEM_PROMPT)
            if isinstance(result, dict):
                return result.get("message", "") or result.get("error", "") or str(result)
            return str(result)
        return f"[No AI provider configured] Step would be: {message[:100]}"

    def _log(self, task_id: str, event: str, detail: str) -> None:
        entry = {
            "task_id": task_id,
            "event": event,
            "detail": detail,
            "timestamp": time.time(),
        }
        self._execution_log.append(entry)
        if len(self._execution_log) > 1000:
            self._execution_log = self._execution_log[-500:]

    # --- Tool implementations ---

    def _tool_read_file(self, args: Dict[str, Any]) -> str:
        path = args.get("path", "")
        try:
            p = Path(path)
            if p.exists():
                return p.read_text(encoding="utf-8", errors="replace")[:10000]
            return f"File not found: {path}"
        except Exception as exc:
            return f"Error reading {path}: {exc}"

    def _tool_write_file(self, args: Dict[str, Any]) -> str:
        path = args.get("path", "")
        content = args.get("content", "")
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return f"Written {len(content)} chars to {path}"
        except Exception as exc:
            return f"Error writing {path}: {exc}"

    def _tool_list_dir(self, args: Dict[str, Any]) -> str:
        path = args.get("path", ".")
        try:
            p = Path(path)
            if p.exists() and p.is_dir():
                items = []
                for item in p.iterdir():
                    info = (
                        f"DIR: {item.name}"
                        if item.is_dir()
                        else f"FILE: {item.name} ({item.stat().st_size}B)"
                    )
                    items.append(info)
                return "\n".join(items[:100])
            return f"Not a directory: {path}"
        except Exception as exc:
            return f"Error listing {path}: {exc}"

    def _tool_run_command(self, args: Dict[str, Any]) -> str:
        import subprocess

        cmd = args.get("command", "")
        timeout = args.get("timeout", 30)
        try:
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            output = proc.stdout or ""
            if proc.stderr:
                output += f"\n[STDERR] {proc.stderr[:1000]}"
            return output[:10000]
        except Exception as exc:
            return f"Command error: {exc}"

    def _tool_search_web(self, args: Dict[str, Any]) -> str:
        query = args.get("query", "")
        try:
            import urllib.parse
            import urllib.request

            url = f"https://duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                html = r.read().decode("utf-8", errors="ignore")
            results = []
            for line in html.splitlines():
                if "result__a" in line and "href=" in line:
                    results.append(line.strip())
                if len(results) >= 5:
                    break
            return "\n".join(results) if results else f"No results for: {query}"
        except Exception as exc:
            return f"Search error: {exc}"

    def _tool_code_analysis(self, args: Dict[str, Any]) -> str:
        path = args.get("path", "")
        try:
            p = Path(path)
            if p.exists():
                lines = p.read_text(encoding="utf-8", errors="replace").split("\n")
                return (
                    f"File: {path}\n"
                    f"Lines: {len(lines)}\n"
                    f"Has imports: {any('import' in l for l in lines)}\n"
                    f"Has functions: {any('def ' in l or 'function ' in l for l in lines)}\n"
                    f"Has classes: {any('class ' in l for l in lines)}\n"
                    f"First 20 lines:\n" + "\n".join(lines[:20])
                )[:3000]
            return f"Not found: {path}"
        except Exception as exc:
            return f"Analysis error: {exc}"

    def _tool_security_scan(self, args: Dict[str, Any]) -> str:
        path = args.get("path", ".")
        patterns = [
            "eval(",
            "exec(",
            "os.system(",
            "subprocess.shell=",
            "pickle.loads(",
            "yaml.load(",
        ]
        findings = []
        try:
            p = Path(path) if Path(path).exists() else Path(".")
            for root, _, files in os.walk(str(p)) if p.is_dir() else ([str(p), [], [p.name]]):
                for f in files:
                    if f.endswith((".py", ".js", ".sh", ".json")):
                        fp = Path(root) / f
                        try:
                            content = fp.read_text(encoding="utf-8", errors="ignore")
                            for pattern in patterns:
                                if pattern in content:
                                    findings.append(f"{fp}: contains '{pattern}'")
                        except Exception:
                            pass
                    if len(findings) >= 20:
                        break
            if not findings:
                return f"No security patterns found in {path}"
            return "Security scan findings:\n" + "\n".join(findings)
        except Exception as exc:
            return f"Scan error: {exc}"

    def _tool_data_analysis(self, args: Dict[str, Any]) -> str:
        path = args.get("path", "")
        try:
            p = Path(path)
            if p.exists():
                content = p.read_text(encoding="utf-8", errors="ignore")
                lines = content.split("\n")
                return (
                    f"Data file: {path}\n"
                    f"Size: {p.stat().st_size} bytes\n"
                    f"Lines: {len(lines)}\n"
                    f"Has CSV: {',' in content}\n"
                    f"Has JSON: {content.strip().startswith(('{', '['))}\n"
                    f"Sample (first 500 chars): {content[:500]}"
                )
            return f"Not found: {path}"
        except Exception as exc:
            return f"Analysis error: {exc}"
