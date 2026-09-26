"""
AURA Chat — Hugging Face Space
Asistente IA generalista con memoria conversacional, routing multi-modelo y evolución.
"""

import os
import json
import logging
import time
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from datetime import datetime

import gradio as gr

from src.model_router import ModelRouter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("AURA.Space")

SYSTEM_PROMPT = (
    "Eres AURA, un asistente de IA avanzado, autónomo y versátil. "
    "Puedes conversar, escribir código, resolver problemas matemáticos, "
    "analizar información, ser creativo y adaptarte al usuario. "
    "Responde en el mismo idioma en que te hablen. "
    "Sé conciso pero completo. Si no sabes algo, dilo honestamente. "
    "Tu objetivo es ser útil, preciso y agradable."
)

MAX_HISTORY = 10
INTERACTIONS_FILE = "data/interactions.jsonl"
PREFERENCES_FILE = "data/preferences.json"

PRIMARY_MODEL = os.getenv("HF_MODEL", "openbmb/MiniCPM5-1B")
HF_TOKEN = os.getenv("HF_TOKEN", "")

router = ModelRouter(
    primary_model=PRIMARY_MODEL,
    hf_token=HF_TOKEN,
)

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)


def load_preferences() -> Dict:
    path = Path(PREFERENCES_FILE)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_preferences(prefs: Dict) -> None:
    try:
        Path(PREFERENCES_FILE).write_text(
            json.dumps(prefs, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError as exc:
        logger.warning("Could not save preferences: %s", exc)


def log_interaction(prompt: str, response: str, model: str, domain: str, latency: float) -> None:
    try:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "prompt": prompt,
            "response_length": len(response),
            "model": model,
            "domain": domain,
            "latency_s": round(latency, 2),
        }
        with open(INTERACTIONS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as exc:
        logger.warning("Could not log interaction: %s", exc)


def get_interaction_stats() -> Dict:
    path = Path(INTERACTIONS_FILE)
    if not path.exists():
        return {"total": 0, "domains": {}, "models": {}}

    stats = {"total": 0, "domains": {}, "models": {}}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                stats["total"] += 1
                domain = entry.get("domain", "unknown")
                stats["domains"][domain] = stats["domains"].get(domain, 0) + 1
                model = entry.get("model", "unknown")
                stats["models"][model] = stats["models"].get(model, 0) + 1
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    return stats


def chat_fn(
    message: str,
    history: List[Tuple[str, str]],
    system_prompt: str,
    temperature: float,
    max_tokens: int,
) -> Tuple[str, List[Tuple[str, str]]]:
    if not message or not message.strip():
        return "Por favor escribe un mensaje.", history

    messages = []
    for user_msg, bot_msg in history:
        messages.append({"role": "user", "content": user_msg})
        if bot_msg:
            messages.append({"role": "assistant", "content": bot_msg})

    sp = system_prompt if system_prompt and system_prompt.strip() else SYSTEM_PROMPT

    start = time.time()
    try:
        result = router.query(
            prompt=message,
            system_prompt=sp,
            max_tokens=int(max_tokens),
            temperature=float(temperature),
            history=messages,
        )
        latency = time.time() - start

        if result["error"]:
            response = (
                "⚠️ Lo siento, el modelo no está disponible en este momento. "
                "Esto puede ocurrir si el Space se quedó sin créditos de API. "
                "Por favor intenta de nuevo más tarde.\n\n"
                f"Detalle técnico: {result['error']}"
            )
        else:
            response = result["response"]

        log_interaction(
            prompt=message,
            response=response,
            model=result.get("model_used", "unknown"),
            domain=result.get("domain", "unknown"),
            latency=latency,
        )
        return response, history

    except Exception as e:
        logger.error("Chat error: %s", e, exc_info=True)
        return (
            "❌ Ocurrió un error inesperado. Por favor intenta de nuevo.\n\n"
            f"Error: {str(e)}",
            history,
        )


def clear_chat() -> Tuple[List[Tuple[str, str]], str]:
    router.cache.clear()
    return [], ""


def get_status() -> str:
    health = router.health_check()
    stats = get_interaction_stats()

    lines = [
        "## 📊 Estado del Sistema\n",
        f"**Modelo primario:** {health['primary_model']}",
        f"**Estado:** {'✅ Online' if health['primary_online'] else '⚠️ Degradado'}",
        f"**Cache:** {health['cache_size']} respuestas cacheadas",
        "",
        "### 📈 Estadísticas de uso",
        f"**Total interacciones:** {stats['total']}",
    ]

    if stats.get("domains"):
        lines.append("\n**Por dominio:**")
        for domain, count in sorted(stats["domains"].items(), key=lambda x: -x[1]):
            lines.append(f"- {domain}: {count}")

    if stats.get("models"):
        lines.append("\n**Por modelo:**")
        for model, count in sorted(stats["models"].items(), key=lambda x: -x[1]):
            lines.append(f"- {model}: {count}")

    return "\n".join(lines)


CSS = """
.gradio-container { max-width: 900px !important; margin: auto; }
.chatbot { min-height: 400px; }
footer { display: none !important; }
"""

with gr.Blocks(
    title="AURA Chat",
    theme=gr.themes.Soft(primary_hue="blue", neutral_hue="slate"),
    css=CSS,
) as demo:
    gr.Markdown(
        """
        # 🤖 AURA — Asistente IA Autónomo

        **AURA** es un asistente de IA versátil que puede conversar, escribir código,
        resolver problemas y adaptarse a tus necesidades.

        *Powered by Hugging Face Inference API*
        """
    )

    chatbot = gr.Chatbot(
        label="Conversación",
        height=450,
        bubble_full_width=False,
        show_copy_button=True,
    )

    msg = gr.Textbox(
        label="Tu mensaje",
        placeholder="Escribe tu mensaje aquí...",
        lines=2,
        max_lines=6,
    )

    with gr.Row():
        clear_btn = gr.Button("🗑️ Clear Chat", variant="secondary", scale=1)
        status_btn = gr.Button("📊 Estado", variant="secondary", scale=1)
        submit_btn = gr.Button("🚀 Enviar", variant="primary", scale=2)

    with gr.Accordion("⚙️ Configuración avanzada", open=False):
        system_prompt_input = gr.Textbox(
            label="System Prompt",
            value=SYSTEM_PROMPT,
            lines=3,
            max_lines=6,
        )
        with gr.Row():
            temperature_slider = gr.Slider(
                minimum=0.1, maximum=1.5, value=0.7, step=0.1, label="Temperatura"
            )
            max_tokens_slider = gr.Slider(
                minimum=64, maximum=2048, value=512, step=64, label="Máx. tokens"
            )

    status_output = gr.Markdown(visible=False)

    msg.submit(
        fn=chat_fn,
        inputs=[msg, chatbot, system_prompt_input, temperature_slider, max_tokens_slider],
        outputs=[msg, chatbot],
    ).then(
        fn=lambda: "",
        inputs=[],
        outputs=msg,
        queue=False,
    )

    submit_btn.click(
        fn=chat_fn,
        inputs=[msg, chatbot, system_prompt_input, temperature_slider, max_tokens_slider],
        outputs=[msg, chatbot],
    ).then(
        fn=lambda: "",
        inputs=[],
        outputs=msg,
        queue=False,
    )

    clear_btn.click(
        fn=clear_chat,
        inputs=[],
        outputs=[chatbot, msg],
    )

    def show_status():
        return gr.update(visible=True), get_status()

    status_btn.click(
        fn=show_status,
        inputs=[],
        outputs=[status_output],
    )

    gr.Markdown(
        """
        ---
        **AURA v4.0** · [GitHub](https://github.com/raidenia3-oss/AURA-server.01) ·
        Hecho con ❤️ y Hugging Face
        """
    )

if __name__ == "__main__":
    port = int(os.getenv("PORT", 7860))
    demo.launch(server_name="0.0.0.0", server_port=port, share=False)
