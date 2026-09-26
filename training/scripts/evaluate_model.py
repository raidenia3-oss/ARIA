"""
Evaluador de modelo AURA: base vs fine-tuneado (LoRA).

Carga el modelo base y el fine-tuneado (con LoRA), ejecuta 30 preguntas de
test predefinidas, y compara respuestas usando un modelo externo (Gemini/Groq)
como juez. Guarda resultados en training/output/evaluation_report.json.

Uso:
    python training/scripts/evaluate_model.py
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("evaluate_model")

ROOT = Path(__file__).resolve().parents[2]
LORA_PATH = ROOT / "fine-tuned-ame" / "aura_finetuned_lora"
BASE_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"

# Cargar variables de entorno (.env.ai) para disponibilidad de API keys.
try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env.ai")
    load_dotenv(ROOT / "ame_backend" / ".env.local")
except Exception:
    pass

# 30 preguntas de test (diversas complejidades)
TEST_QUESTIONS: List[Dict[str, str]] = [
    # LOW (10)
    {"complexity": "low", "prompt": "¿Qué hora es?"},
    {"complexity": "low", "prompt": "Hola, ¿cómo estás?"},
    {"complexity": "low", "prompt": "¿Qué puedes hacer?"},
    {"complexity": "low", "prompt": "Abre el navegador"},
    {"complexity": "low", "prompt": "Lista los archivos del directorio actual"},
    {"complexity": "low", "prompt": "¿Cuál es tu nombre?"},
    {"complexity": "low", "prompt": "Repite la palabra 'hola'"},
    {"complexity": "low", "prompt": "¿Qué día es hoy?"},
    {"complexity": "low", "prompt": "Di algo motivador"},
    {"complexity": "low", "prompt": "¿Estás funcionando?"},
    # MEDIUM (10)
    {
        "complexity": "medium",
        "prompt": "Explica brevemente qué es un modelo de lenguaje",
    },
    {
        "complexity": "medium",
        "prompt": "¿Cuál es la capital de Francia y su población?",
    },
    {
        "complexity": "medium",
        "prompt": "Resume el concepto de aprendizaje por refuerzo",
    },
    {
        "complexity": "medium",
        "prompt": "¿Cómo funciona una red neuronal convolucional?",
    },
    {"complexity": "medium", "prompt": "Dame 3 consejos para mejorar la productividad"},
    {
        "complexity": "medium",
        "prompt": "¿Qué diferencias hay entre Python y JavaScript?",
    },
    {"complexity": "medium", "prompt": "Explica qué es la computación en la nube"},
    {
        "complexity": "medium",
        "prompt": "¿Cómo se entrena un modelo de clasificación de texto?",
    },
    {
        "complexity": "medium",
        "prompt": "Describe el ciclo de vida del desarrollo de software",
    },
    {"complexity": "medium", "prompt": "¿Qué es el overfitting y cómo evitarlo?"},
    # HIGH (10)
    {
        "complexity": "high",
        "prompt": "Analiza en profundidad la arquitectura de un sistema distribuido de microservicios y propón mejoras",
    },
    {
        "complexity": "high",
        "prompt": "Diseña una estrategia de optimización de rendimiento para una base de datos PostgreSQL con millones de registros",
    },
    {
        "complexity": "high",
        "prompt": "Investiga y compara en detalle los frameworks de machine learning más usados en producción en 2025",
    },
    {
        "complexity": "high",
        "prompt": "Planifica una arquitectura de seguridad de red para una empresa con múltiples sucursales y acceso remoto",
    },
    {
        "complexity": "high",
        "prompt": "Implementa un algoritmo de recomendación colaborativa explicando cada paso del razonamiento",
    },
    {
        "complexity": "high",
        "prompt": "Diseña un sistema de caché distribuido para una API de alta concurrencia",
    },
    {
        "complexity": "high",
        "prompt": "Explica cómo implementar autenticación OAuth2 con refresh tokens en FastAPI",
    },
    {
        "complexity": "high",
        "prompt": "Propón una arquitectura de datos para un sistema de recomendación en tiempo real",
    },
    {
        "complexity": "high",
        "prompt": "Analiza las ventajas y desventajas de microservicios vs monolitos en producción",
    },
    {
        "complexity": "high",
        "prompt": "Diseña un pipeline de CI/CD con pruebas automatizadas y despliegue canario",
    },
]


def load_model(model_name: str) -> Optional[Dict[str, Any]]:
    """Carga un modelo causal con su tokenizer."""
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch

        logger.info("Cargando tokenizer: %s", model_name)
        tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        logger.info("Cargando modelo: %s (CPU)", model_name)
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            trust_remote_code=True,
            torch_dtype=torch.float32,
            device_map="cpu",
            low_cpu_mem_usage=True,
        )
        model.eval()
        return {"model": model, "tokenizer": tokenizer}
    except Exception as exc:
        logger.warning("No se pudo cargar modelo %s: %s", model_name, exc)
        return None


def infer(engine: Dict[str, Any], prompt: str) -> Dict[str, Any]:
    """Ejecuta inferencia y devuelve texto, latencia y tokens."""
    import torch

    model = engine["model"]
    tokenizer = engine["tokenizer"]

    messages = [{"role": "user", "content": prompt}]
    try:
        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
    except Exception:
        text = f"User: {prompt}\nAssistant:"

    start = time.time()
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=256)
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=128,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
            pad_token_id=tokenizer.pad_token_id,
        )
    latency = (time.time() - start) * 1000

    response = tokenizer.decode(
        outputs[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True
    )
    tokens = len(outputs[0]) - inputs["input_ids"].shape[1]
    return {"text": response.strip(), "latency_ms": round(latency, 2), "tokens": tokens}


def judge_with_ai(prompt: str, base_resp: str, ft_resp: str) -> Dict[str, Any]:
    """Usa AIEngine (Gemini/Groq) como juez, o fallback heurístico si no hay API keys."""
    # Detectar si hay API keys disponibles para el juez externo.
    _has_external_key = any(
        os.getenv(k)
        for k in ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "HF_TOKEN")
    )
    if not _has_external_key:
        # Fallback heurístico directamente (sin intentar llamadas de red).
        base_len = len(base_resp)
        ft_len = len(ft_resp)
        base_score = min(100, base_len // 5)
        ft_score = min(100, ft_len // 5)
        winner = (
            "ft"
            if ft_score > base_score
            else ("base" if base_score > ft_score else "tie")
        )
        return {
            "base_score": base_score,
            "ft_score": ft_score,
            "winner": winner,
            "reason": "heuristic",
        }

    try:
        # Timeouts cortos para que el juez no bloquee en proveedores no disponibles.
        os.environ.setdefault("GEMINI_TIMEOUT", "3")
        os.environ.setdefault("GROQ_TIMEOUT", "3")
        os.environ.setdefault("OPENROUTER_TIMEOUT", "3")
        os.environ.setdefault("DEEPSEEK_TIMEOUT", "3")
        os.environ.setdefault("NVIDIA_TIMEOUT", "3")
        os.environ.setdefault("MISTRAL_TIMEOUT", "3")
        os.environ.setdefault("HF_TIMEOUT", "3")
        os.environ.setdefault("LM_STUDIO_TIMEOUT", "3")
        os.environ.setdefault("LOCAL_LFM_TIMEOUT", "3")

        sys.path.insert(0, str(ROOT))
        from ame_backend.src.services.ai_engine import AIEngine

        engine = AIEngine()
        judge_prompt = (
            f"Eres un juez de calidad de respuestas de IA. Compara dos respuestas "
            f"a la misma pregunta y puntúa cada una de 0 a 100.\n\n"
            f"Pregunta: {prompt}\n\n"
            f"Respuesta A (modelo base):\n{base_resp}\n\n"
            f"Respuesta B (modelo fine-tuneado):\n{ft_resp}\n\n"
            f'Responde SOLO con JSON: {{"base_score": 0-100, "ft_score": 0-100, '
            f'"winner": "base"|"ft"|"tie", "reason": "breve"}}'
        )
        result = engine.chat(prompt=judge_prompt)
        text = result.get("text", "")
        # Extraer JSON del texto
        import re

        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            data = json.loads(m.group(0))
            return {
                "base_score": int(data.get("base_score", 50)),
                "ft_score": int(data.get("ft_score", 50)),
                "winner": data.get("winner", "tie"),
                "reason": data.get("reason", ""),
            }
    except Exception as exc:
        logger.warning("Juez AI falló: %s", exc)
    # Fallback: puntuación heurística por longitud
    base_len = len(base_resp)
    ft_len = len(ft_resp)
    base_score = min(100, base_len // 5)
    ft_score = min(100, ft_len // 5)
    winner = (
        "ft" if ft_score > base_score else ("base" if base_score > ft_score else "tie")
    )
    return {
        "base_score": base_score,
        "ft_score": ft_score,
        "winner": winner,
        "reason": "heuristic",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluador de modelo AURA: base vs fine-tuneado."
    )
    parser.add_argument(
        "--questions", type=int, default=30, help="Número de preguntas de test"
    )
    parser.add_argument(
        "--output",
        default="training/output/evaluation_report.json",
        help="Ruta del reporte",
    )
    args = parser.parse_args()

    questions = TEST_QUESTIONS[: args.questions]

    # Cargar modelos
    base_engine = load_model(BASE_MODEL)
    ft_model_name = str(LORA_PATH) if LORA_PATH.exists() else BASE_MODEL
    ft_engine = load_model(ft_model_name)

    if base_engine is None:
        logger.error("No se pudo cargar el modelo base. Abortando.")
        return 1

    results: List[Dict[str, Any]] = []
    base_latencies: List[float] = []
    ft_latencies: List[float] = []
    base_tokens: List[int] = []
    ft_tokens: List[int] = []
    ft_wins = 0
    base_wins = 0
    ties = 0

    for i, q in enumerate(questions, 1):
        prompt = q["prompt"]
        logger.info("[%d/%d] Evaluando: %s", i, len(questions), prompt[:60])

        base_res = infer(base_engine, prompt)
        base_latencies.append(base_res["latency_ms"])
        base_tokens.append(base_res["tokens"])

        ft_res = None
        if ft_engine is not None:
            ft_res = infer(ft_engine, prompt)
            ft_latencies.append(ft_res["latency_ms"])
            ft_tokens.append(ft_res["tokens"])

        # Juez
        judge = judge_with_ai(
            prompt, base_res["text"], ft_res["text"] if ft_res else ""
        )
        if judge["winner"] == "ft":
            ft_wins += 1
        elif judge["winner"] == "base":
            base_wins += 1
        else:
            ties += 1

        results.append(
            {
                "prompt": prompt,
                "complexity": q["complexity"],
                "base": {
                    "text": base_res["text"][:200],
                    "latency_ms": base_res["latency_ms"],
                    "tokens": base_res["tokens"],
                    "score": judge["base_score"],
                },
                "fine_tuned": {
                    "text": ft_res["text"][:200] if ft_res else "N/A",
                    "latency_ms": ft_res["latency_ms"] if ft_res else 0,
                    "tokens": ft_res["tokens"] if ft_res else 0,
                    "score": judge["ft_score"],
                },
                "winner": judge["winner"],
                "reason": judge["reason"],
            }
        )

    total = len(questions)
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_questions": total,
        "model_base": BASE_MODEL,
        "model_fine_tuned": ft_model_name,
        "metrics": {
            "base_avg_latency_ms": (
                round(sum(base_latencies) / len(base_latencies), 2)
                if base_latencies
                else 0
            ),
            "ft_avg_latency_ms": (
                round(sum(ft_latencies) / len(ft_latencies), 2) if ft_latencies else 0
            ),
            "base_avg_tokens": (
                round(sum(base_tokens) / len(base_tokens), 2) if base_tokens else 0
            ),
            "ft_avg_tokens": (
                round(sum(ft_tokens) / len(ft_tokens), 2) if ft_tokens else 0
            ),
            "base_avg_score": (
                round(sum(r["base"]["score"] for r in results) / total, 2)
                if total
                else 0
            ),
            "ft_avg_score": (
                round(sum(r["fine_tuned"]["score"] for r in results) / total, 2)
                if total
                else 0
            ),
            "win_rate_ft": round(ft_wins / total, 4) if total else 0,
            "win_rate_base": round(base_wins / total, 4) if total else 0,
            "ties": ties,
        },
        "results": results,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info("Reporte guardado en %s", out_path)
    logger.info(
        "Métricas: base_lat=%.1fms ft_lat=%.1fms | base_score=%.1f ft_score=%.1f | "
        "win_rate_ft=%.1f%% (wins=%d, ties=%d)",
        report["metrics"]["base_avg_latency_ms"],
        report["metrics"]["ft_avg_latency_ms"],
        report["metrics"]["base_avg_score"],
        report["metrics"]["ft_avg_score"],
        report["metrics"]["win_rate_ft"] * 100,
        ft_wins,
        ties,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
