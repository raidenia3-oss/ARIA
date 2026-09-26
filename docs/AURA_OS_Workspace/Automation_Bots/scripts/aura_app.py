import os
import sys
from datetime import datetime

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from AURA_Core.brain_with_tools import AuraBrain

st.set_page_config(
    page_title="AURA - Intelligent Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "brain" not in st.session_state:
    st.session_state.brain = AuraBrain()

if "aura_session_id" not in st.session_state:
    st.session_state.aura_session_id = None

if "sidebar_provider" not in st.session_state:
    st.session_state.sidebar_provider = "Automático"

if "persona" not in st.session_state:
    st.session_state.persona = "AURA Standard"

if "pending_shell_auth" not in st.session_state:
    st.session_state.pending_shell_auth = None

brain: AuraBrain = st.session_state.brain


def ensure_session() -> int:
    if st.session_state.aura_session_id is None:
        sid = brain.create_session(title=f"Sesión Web {datetime.now().strftime('%H:%M:%S')}")
        st.session_state.aura_session_id = sid
    return st.session_state.aura_session_id


def render_provider_badge(provider: str | None) -> str:
    if not provider:
        return "🔘 Desconocido"
    mapping = {
        "ollama": "🟢 Local Ollama",
        "openrouter": "🔵 OpenRouter",
        "groq": "🟣 Groq",
        "gemini": "🟠 Gemini",
        "mistral": "🔴 Mistral",
        "cerebras": "⚪ Cerebras",
        "hf_cloud": "🤗 HF Cloud",
        "hf_space": "🧩 HF Space",
        "colab": "☁️ Colab",
        "void": "💾 VOID",
    }
    return mapping.get(provider, f"🔹 {provider}")


def risk_label(cmd: str) -> str:
    c = (cmd or "").lower().strip()
    if not c:
        return "Bajo"
    risky_prefixes = ("del ", "rm ", "rmdir", "rd ", "format", "shutdown", "reboot")
    if any(c.startswith(x) for x in risky_prefixes):
        return "Alto"
    medium = ("curl", "wget", "powershell", "python ", "py ", "pip ")
    if any(x in c for x in medium):
        return "Medio"
    return "Bajo"


with st.sidebar:
    st.header("⚙️ Panel de Control")

    session_id = ensure_session()

    persona_names = list(brain.PERSONAS.keys())
    st.session_state.persona = st.selectbox(
        "Persona",
        options=persona_names,
        index=(
            persona_names.index(st.session_state.persona)
            if st.session_state.persona in persona_names
            else 0
        ),
    )
    brain.set_persona(st.session_state.persona)

    provider_option = st.radio(
        "Modo de proveedor",
        ["Automático", "Solo Local", "Solo Nube"],
        index=(
            ["Automático", "Solo Local", "Solo Nube"].index(st.session_state.sidebar_provider)
            if st.session_state.sidebar_provider in ["Automático", "Solo Local", "Solo Nube"]
            else 0
        ),
        horizontal=True,
    )
    st.session_state.sidebar_provider = provider_option

    st.divider()

    if st.button("🆕 Nueva Sesión", use_container_width=True):
        new_sid = brain.create_session(title=f"Sesión Web {datetime.now().strftime('%H:%M:%S')}")
        st.session_state.aura_session_id = new_sid
        st.rerun()

    st.subheader("📊 Estadísticas")
    try:
        history = brain.get_history(session_id, limit=1000)
        st.metric("Mensajes en sesión actual", len(history))
        if history:
            last = history[-1]
            st.caption(
                f"Último proveedor: {render_provider_badge(last.get('provider_used') or 'N/A')}"
            )
    except Exception:
        st.metric("Mensajes en sesión actual", "–")

    st.subheader("🌐 Estado del Sistema")
    try:
        test_results = brain.router.test_all_providers()
        summary = test_results.get("summary", {})
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Disponibles", summary.get("available", 0))
        with col2:
            st.metric(
                "Sin clave / Fallidos", f"{summary.get('no_key', 0)} / {summary.get('failed', 0)}"
            )
        ollama = test_results.get("providers", {}).get("ollama", {})
        st.caption(f"Local Ollama: {'✅' if ollama.get('status') == 'ok' else '❌'}")
    except Exception:
        st.caption("No se pudo cargar el estado del sistema.")

    st.subheader("📈 Rendimiento")
    try:
        log_path = os.path.join(os.path.dirname(__file__), "AURA_Core", "logs", "performance.log")
        rows = []
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as f:
                for line in f.readlines()[-20:]:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rows.append(__import__("json").loads(line))
                    except Exception:
                        pass
        if rows:
            avg = sum(r.get("elapsed_sec", 0) for r in rows) / max(1, len(rows))
            st.metric("Tiempo medio (s)", round(avg, 3))
            st.caption(f"Últimos {len(rows)} eventos")
        else:
            st.caption("Sin logs aún.")
    except Exception:
        st.caption("No se pudo cargar rendimiento.")

    st.divider()
    st.caption("AURA Core v4 — Interfaces 2025")

st.title("🤖 AURA — Intelligent Assistant")
st.caption("Asistente avanzado con routing inteligente de modelos")

session_id = ensure_session()

try:
    chat_history = brain.get_history(session_id, limit=200) or []
except Exception:
    chat_history = []

for msg in chat_history:
    role = msg.get("role", "user")
    content = msg.get("content", "")
    provider = msg.get("provider_used")
    tool_used = msg.get("tool_used")

    with st.chat_message(role or "user"):
        st.markdown(content)
        if (role or "").lower() == "assistant" and provider:
            st.caption(f"Respondido por: {render_provider_badge(provider)}")
        if tool_used:
            st.caption(f"🛠️ Herramienta usada: `{tool_used}`")

if st.session_state.pending_shell_auth:
    pending = st.session_state.pending_shell_auth
    with st.chat_message("assistant"):
        st.warning("⚠️ AURA quiere ejecutar un comando en tu sistema.")

        cmd = pending.get("command", "")
        st.code(cmd, language="bash")

        risk = risk_label(cmd)
        if risk == "Alto":
            st.error(f" Riesgo detectado: {risk}. Revisa bien el comando antes de autorizar.")
        elif risk == "Medio":
            st.warning(f" Riesgo: {risk}. Este tipo de comando puede tocar red o scripts.")
        else:
            st.caption(f" Riesgo estimado: {risk}")

        cols = st.columns(2)
        with cols[0]:
            if st.button("✅ Autorizar", key="auth_yes"):
                st.session_state.pending_shell_auth = None
                st.rerun()
        with cols[1]:
            if st.button("❌ Denegar", key="auth_no"):
                st.session_state.pending_shell_auth = None
                st.rerun()
    st.divider()

if prompt := st.chat_input("Escribe tu mensaje a AURA..."):
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.status("Pensando...", expanded=False):
            st.write("Procesando con AURA...")

        response_placeholder = st.empty()

        try:
            tool_authorized = None
            if st.session_state.pending_shell_auth:
                tool_authorized = {"granted": True, **st.session_state.pending_shell_auth}
                st.session_state.pending_shell_auth = None

            mode = st.session_state.sidebar_provider
            force_provider = None
            if mode == "Solo Local":
                force_provider = "ollama"
            elif mode == "Solo Nube":
                for candidate in ("groq", "gemini", "openrouter"):
                    if os.environ.get(
                        "GROQ_API_KEY"
                        if candidate == "groq"
                        else "GEMINI_API_KEY" if candidate == "gemini" else "OPENROUTER_API_KEY"
                    ):
                        force_provider = candidate
                        break

            result = brain.process_input(
                session_id=session_id,
                user_prompt=prompt,
                force_provider=force_provider,
                tool_authorized=tool_authorized,
            )

            response_text = (
                result.get("response")
                or "Lo siento, no pude generar una respuesta en este momento."
            )
            provider_used = result.get("provider_used") or "desconocido"
            tool_used = result.get("tool_used")

            response_placeholder.markdown(response_text)
            st.caption(f"Respondido por: {render_provider_badge(provider_used)}")

            if tool_used:
                with st.expander("🛠️ Detalle de herramienta", expanded=False):
                    tool_output = result.get("tool_output")
                    if tool_output:
                        st.json(tool_output)
                    else:
                        st.caption(f"Herramienta: `{tool_used}`")

            if result.get("tool_pending"):
                pending_tool = result["tool_pending"]
                if pending_tool.get("tool") == "execute_shell":
                    st.session_state.pending_shell_auth = {
                        "command": pending_tool.get("args", {}).get("command", ""),
                        "risky": result.get("tool_risky", False),
                    }

        except Exception as e:
            response_placeholder.markdown(f"⚠️ Error: {e}")
            st.caption("Respondido por: ❌ Error")

    st.rerun()
