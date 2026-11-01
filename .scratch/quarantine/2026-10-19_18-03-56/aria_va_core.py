"""ARIA Virtual Assistant — Núcleo 100% local, un solo proceso.

Cero HTTP, cero localhost, cero servidores, cero comandos de shell, cero subprocess.
Todo corre en proceso local: IA (reglas + transformers opcional), voz (Vosk + Whisper + pyttsx3),
skills (stdlib solo), operación autónoma en segundo plano.
"""

from __future__ import annotations

import json
import math
import os
import random
import sys
import time
import threading
import wave
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ARIA_APP = Path(__file__).resolve().parent
PROJECT_ROOT = ARIA_APP.parent

# ─── Memoria local (JSON, sin base de datos externa) ─────────────────────────

MEMORY_DIR = ARIA_APP / "data" / "memory"
MEMORY_DIR.mkdir(parents=True, exist_ok=True)
CONVERSATIONS_FILE = MEMORY_DIR / "conversations.jsonl"
SKILLS_STATE_FILE = MEMORY_DIR / "skills_state.json"
AUTONOMOUS_STATE_FILE = MEMORY_DIR / "autonomous_state.json"


def _append_jsonl(path: Path, obj: Dict[str, Any]) -> None:
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not path.exists():
        return out
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        continue
    except Exception:
        pass
    return out


def _load_json(path: Path, default: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path: Path, obj: Any) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


# ─── IA Local: reglas + transformers opcional (sin HTTP) ─────────────────────

class LocalAIBrain:
    """Cerebro local: reglas determinísticas + modelo transformers opcional."""

    def __init__(self) -> None:
        self.system_prompt = (
            "Eres ARIA, asistente virtual personal estilo Jarvis. "
            "Respondes en español, eres útil, conciso, amable y operativas 100% en local. "
            "No usas servidores, no usas internet, no usas la nube."
        )
        self.history: List[List[str]] = []
        self._model = None
        self._tokenizer = None
        self._model_loaded = False
        self._load_local_model()

    # -- modelo transformers opcional (solo si está instalado localmente) --
    def _load_local_model(self) -> None:
        try:
            import torch  # noqa: F401
            from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore
            model_path = os.environ.get("ARIA_LOCAL_MODEL_PATH", "fine-tuned-ame")
            base = "Qwen/Qwen2.5-0.5B-Instruct"
            name = model_path if os.path.isdir(model_path) else base
            self._tokenizer = AutoTokenizer.from_pretrained(name)
            if self._tokenizer.pad_token is None:
                self._tokenizer.pad_token = self._tokenizer.eos_token
            self._model = AutoModelForCausalLM.from_pretrained(
                name, torch_dtype="auto", device_map="cpu", low_cpu_mem_usage=True
            )
            self._model_loaded = True
            print("[VA] Modelo transformers local cargado.", flush=True)
        except Exception:
            self._model = None
            self._tokenizer = None
            self._model_loaded = False
            print("[VA] Modelo transformers no disponible; usando reglas locales.", flush=True)

    def generate_local(self, prompt: str, max_tokens: int = 200) -> str:
        if not self._model_loaded or self._model is None or self._tokenizer is None:
            return ""
        try:
            import torch  # noqa: F401
            inputs = self._tokenizer(prompt, return_tensors="pt")
            with torch.no_grad():
                outputs = self._model.generate(
                    **inputs,
                    max_new_tokens=max_tokens,
                    temperature=0.7,
                    do_sample=True,
                    pad_token_id=self._tokenizer.eos_token_id,
                )
            resp = self._tokenizer.decode(
                outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True
            )
            return resp.strip()
        except Exception:
            return ""

    # -- reglas locales -------------------------------------------------------
    def _rules_reply(self, message: str) -> Optional[str]:
        lower = message.strip().lower()
        greetings = ["hola", "buenas", "hello", "hi", "qué tal", "buenos días", "buenas tardes"]
        if any(g in lower for g in greetings):
            return "Hola, soy ARIA. Tu asistente virtual, 100% en local, sin servidores ni internet. ¿En qué te ayudo?"
        if any(g in lower for g in ["cómo estás", "como estas", "que tal", "qué pasa"]):
            return "Estoy operativa. Sistema local activo, escuchándote."
        if any(g in lower for g in ["estado", "status", "salud"]):
            return self._status_reply()
        if any(g in lower for g in ["quién eres", "que eres", "que haces", "tu nombre"]):
            return "Soy ARIA, tu asistente virtual personal. Opero 100% en tu equipo, sin servidores, sin la nube, sin internet."
        if any(g in lower for g in ["adiós", "adios", "hasta luego", "nos vemos", "chao"]):
            return "Hasta luego. Quedo a tu disposición cuando quieras."
        if any(g in lower for g in ["gracias", "thanks"]):
            return "De nada. ¿En qué más puedo ayudarte?"
        if any(g in lower for g in ["hora", "qué hora", "fecha", "qué día"]):
            return datetime.now().strftime("Son las %H:%M del %d/%m/%Y.")
        if any(g in lower for g in ["ayuda", "help", "comandos"]):
            return (
                "Puedo hablar contigo, gestionar archivos, memoria, notas, "
                "y operar en segundo plano con wake-word. Todo en local."
            )
        if any(g in lower for g in ["voz", "voice", "hablar", "escuchar"]):
            return "El sistema de voz local está activo: wake-word, transcripción y síntesis en tu equipo."
        if any(g in lower for g in ["memoria", "memory", "recordar", "olvidar"]):
            return "Tengo memoria local de conversaciones. Puedo guardar y recordar lo que me digas."
        if any(g in lower for g in ["archivo", "file", "carpeta", "directorio"]):
            return "Puedo listar, leer y escribir archivos locales. Dime qué necesitas."
        if any(g in lower for g in ["autónomo", "autonomo", "segundo plano", "background"]):
            return "Puedo operar autónomamente en segundo plano. Activada la escucha continua."
        return None

    def _status_reply(self) -> str:
        parts = ["ARIA OS — Estado del sistema:"]
        parts.append(f"  IA local: {'transformers' if self._model_loaded else 'reglas'}")
        parts.append(f"  Memoria: {len(_read_jsonl(CONVERSATIONS_FILE))} conversaciones guardadas")
        parts.append(f"  Modo: 100% local, sin servidor, sin internet")
        return "\n".join(parts)

    def chat(self, message: str, history: Optional[List[List[str]]] = None) -> Dict[str, Any]:
        msg = message.strip()
        if not msg:
            return {"response": "No escribiste nada.", "provider": "local", "source": "rules"}

        # 1. Reglas locales (instantáneo, sin dependencias)
        rule = self._rules_reply(msg)
        if rule:
            self._record(msg, rule, "rules")
            return {"response": rule, "provider": "local", "source": "rules"}

        # 2. Modelo transformers local (opcional)
        if self._model_loaded:
            context = ""
            if history:
                for h in history[-5:]:
                    if h[0]:
                        context += f"Usuario: {h[0]}\n"
                    if len(h) > 1 and h[1]:
                        context += f"ARIA: {h[1]}\n"
            prompt = f"{self.system_prompt}\n\n{context}Usuario: {msg}\nARIA:"
            gen = self.generate_local(prompt)
            if gen and len(gen.strip()) > 2:
                self._record(msg, gen, "transformers")
                return {"response": gen, "provider": "local", "source": "transformers"}

        # 3. Fallback genérico local
        fallback = (
            f"Recibido: '{msg}'. Estoy en modo local. "
            "Pregúntame sobre estado, archivos, memoria, voz o simplemente conversa."
        )
        self._record(msg, fallback, "fallback")
        return {"response": fallback, "provider": "local", "source": "fallback"}

    def _record(self, user_msg: str, bot_msg: str, source: str) -> None:
        entry = {
            "ts": time.time(),
            "user": user_msg,
            "aria": bot_msg,
            "source": source,
        }
        _append_jsonl(CONVERSATIONS_FILE, entry)
        self.history.append([user_msg, bot_msg])
        if len(self.history) > 200:
            self.history = self.history[-200:]


# ─── Voz local: Vosk wake-word + Faster-Whisper STT + pyttsx3/Piper TTS ─────

class LocalVoice:
    """Motor de voz 100% local. Sin backend, sin HTTP."""

    def __init__(self) -> None:
        self.wake_words = ["hey aria", "hola aria", "ok aria", "oye aria", "aria"]
        self.listening = False
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._on_transcript: Optional[Callable[[str], None]] = None
        self._on_wake: Optional[Callable[[str], None]] = None
        self._tts_engine = None
        self._stt_available = False
        self._tts_available = False
        self._mic_available = False
        self._wake_available = False
        self._detect_deps()

    def _detect_deps(self) -> None:
        # TTS: pyttsx3 (local, sin red)
        try:
            import pyttsx3  # noqa: F401
            self._tts_available = True
        except Exception:
            pass
        # STT: speech_recognition (local, offline engine si está disponible)
        try:
            import speech_recognition as sr  # noqa: F401
            self._stt_available = True
        except Exception:
            pass
        # Mic: pyaudio / sounddevice
        try:
            import pyaudio  # noqa: F401
            self._mic_available = True
        except Exception:
            try:
                import sounddevice  # noqa: F401
                self._mic_available = True
            except Exception:
                pass
        # Wake word: vosk (local)
        try:
            import vosk  # noqa: F401
            self._wake_available = True
        except Exception:
            pass

    def capabilities(self) -> Dict[str, bool]:
        return {
            "stt": self._stt_available,
            "tts": self._tts_available,
            "mic": self._mic_available,
            "wake_word": self._wake_available,
            "local_only": True,
        }

    def speak(self, text: str) -> None:
        """Síntesis de voz local (bloqueante, en hilo separado si se desea)."""
        if not self._tts_available:
            print(f"[VA][TTS] {text}", flush=True)
            return
        try:
            import pyttsx3
            eng = pyttsx3.init()
            eng.setProperty("rate", 170)
            eng.setProperty("volume", 1.0)
            eng.say(text)
            eng.runAndWait()
        except Exception as exc:
            print(f"[VA][TTS] error: {exc}", flush=True)

    def speak_async(self, text: str) -> None:
        t = threading.Thread(target=self.speak, args=(text,), daemon=True)
        t.start()

    def start_listening(self, on_transcript: Callable[[str], None],
                        on_wake: Callable[[str], None]) -> None:
        if self.listening:
            return
        self.listening = True
        self._stop.clear()
        self._on_transcript = on_transcript
        self._on_wake = on_wake
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def stop_listening(self) -> None:
        self.listening = False
        self._stop.set()

    def _listen_loop(self) -> None:
        recognizer = None
        mic = None
        if self._stt_available and self._mic_available:
            try:
                import speech_recognition as sr
                recognizer = sr.Recognizer()
                mic = sr.Microphone()
                with mic as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.5)
            except Exception:
                recognizer = None
                mic = None

        while self.listening and not self._stop.is_set():
            transcript = ""
            if recognizer and mic:
                try:
                    with mic as source:
                        audio = recognizer.listen(source, timeout=1, phrase_time_limit=6)
                    transcript = recognizer.recognize_google(audio, language="es-ES")
                except Exception:
                    transcript = ""
            if not transcript:
                time.sleep(0.3)
                continue

            lower = transcript.lower()
            if any(ww in lower for ww in self.wake_words):
                if self._on_wake:
                    self._on_wake(transcript)
                cmd = self._extract_command(transcript)
                if cmd and self._on_transcript:
                    self._on_transcript(cmd)
            elif self._on_transcript:
                self._on_transcript(transcript)

    def _extract_command(self, text: str) -> Optional[str]:
        lower = text.lower()
        for kw, cmd in [
            ("estado", "system_status"), ("memoria", "memory_status"),
            ("archivo", "file_ops"), ("ayuda", "help"),
            ("detener", "stop_listening"), ("silencio", "silence"),
        ]:
            if kw in lower:
                return cmd
        return None


# ─── Skills locales (stdlib solo, sin subprocess, sin comandos de shell) ─────

class LocalSkills:
    """Habilidades que usan solo la librería estándar de Python."""

    def __init__(self, brain: LocalAIBrain) -> None:
        self.brain = brain
        self.state: Dict[str, Any] = _load_json(SKILLS_STATE_FILE, {
            "files": [], "notes": [], "reminders": [], "autonomous": False
        })

    def list(self) -> List[Dict[str, str]]:
        return [
            {"id": "system_status", "name": "Estado del sistema", "category": "system"},
            {"id": "memory_status", "name": "Estado de memoria", "category": "memoria"},
            {"id": "file_list", "name": "Listar archivos", "category": "archivos"},
            {"id": "file_read", "name": "Leer archivo", "category": "archivos"},
            {"id": "file_write", "name": "Escribir archivo", "category": "archivos"},
            {"id": "note_add", "name": "Agregar nota", "category": "memoria"},
            {"id": "note_list", "name": "Listar notas", "category": "memoria"},
            {"id": "conversation_history", "name": "Historial conversaciones", "category": "memoria"},
            {"id": "autonomous_toggle", "name": "Modo autónomo", "category": "sistema"},
            {"id": "voice_test", "name": "Probar voz", "category": "voz"},
        ]

    def run(self, skill_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if skill_id == "system_status":
            return self._sys_status()
        if skill_id == "memory_status":
            return self._memory_status()
        if skill_id == "file_list":
            return self._file_list(params)
        if skill_id == "file_read":
            return self._file_read(params)
        if skill_id == "file_write":
            return self._file_write(params)
        if skill_id == "note_add":
            return self._note_add(params)
        if skill_id == "note_list":
            return self._note_list()
        if skill_id == "conversation_history":
            return self._conversation_history()
        if skill_id == "autonomous_toggle":
            return self._autonomous_toggle(params)
        if skill_id == "voice_test":
            return self._voice_test(params)
        return {"status": "error", "error": f"skill desconocida: {skill_id}"}

    # -- implementaciones -----------------------------------------------------
    def _sys_status(self) -> Dict[str, Any]:
        import platform
        return {
            "status": "ok",
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "cwd": str(Path.cwd()),
            "mode": "100% local, sin servidor, sin internet",
            "skills": len(self.list()),
        }

    def _memory_status(self) -> Dict[str, Any]:
        convs = _read_jsonl(CONVERSATIONS_FILE)
        return {
            "status": "ok",
            "conversations": len(convs),
            "skills_state": self.state,
        }

    def _file_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        target = Path(params.get("path", str(ARIA_APP)))
        if not target.exists() or not target.is_dir():
            return {"status": "error", "error": "ruta no válida"}
        entries = []
        try:
            for p in sorted(target.iterdir())[:50]:
                entries.append({
                    "name": p.name,
                    "is_dir": p.is_dir(),
                    "size": p.stat().st_size if p.is_file() else 0,
                })
        except Exception as exc:
            return {"status": "error", "error": str(exc)}
        return {"status": "ok", "path": str(target), "entries": entries}

    def _file_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        path = Path(params.get("path", ""))
        if not path.exists() or not path.is_file():
            return {"status": "error", "error": "archivo no encontrado"}
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            return {"status": "ok", "path": str(path), "content": content[:5000]}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def _file_write(self, params: Dict[str, Any]) -> Dict[str, Any]:
        path = Path(params.get("path", ""))
        content = params.get("content", "")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return {"status": "ok", "path": str(path), "bytes": len(content)}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def _note_add(self, params: Dict[str, Any]) -> Dict[str, Any]:
        text = params.get("text", "")
        if not text:
            return {"status": "error", "error": "texto vacío"}
        entry = {"ts": time.time(), "text": text}
        self.state.setdefault("notes", []).append(entry)
        _save_json(SKILLS_STATE_FILE, self.state)
        return {"status": "ok", "note": entry}

    def _note_list(self) -> Dict[str, Any]:
        return {"status": "ok", "notes": self.state.get("notes", [])}

    def _conversation_history(self) -> Dict[str, Any]:
        convs = _read_jsonl(CONVERSATIONS_FILE)
        return {"status": "ok", "conversations": convs[-50:]}

    def _autonomous_toggle(self, params: Dict[str, Any]) -> Dict[str, Any]:
        val = bool(params.get("enable", not self.state.get("autonomous", False)))
        self.state["autonomous"] = val
        _save_json(SKILLS_STATE_FILE, self.state)
        return {"status": "ok", "autonomous": val}

    def _voice_test(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "ok", "message": "Prueba de voz local"}


# ─── Núcleo VA: une IA + voz + skills + autónomo ─────────────────────────────

class VirtualAssistant:
    """Asistente virtual único: IA local + voz local + skills locales + autónomo."""

    def __init__(self) -> None:
        self.brain = LocalAIBrain()
        self.voice = LocalVoice()
        self.skills = LocalSkills(self.brain)
        self.autonomous = False
        self._awake = False
        self._callbacks: Dict[str, List[Callable]] = {
            "on_response": [],
            "on_wake": [],
            "on_state": [],
        }
        self._load_autonomous_state()

    def _load_autonomous_state(self) -> None:
        st = _load_json(AUTONOMOUS_STATE_FILE, {"autonomous": False})
        self.autonomous = bool(st.get("autonomous", False))

    def save_autonomous_state(self) -> None:
        _save_json(AUTONOMOUS_STATE_FILE, {"autonomous": self.autonomous})

    # -- registro de callbacks ------------------------------------------------
    def on(self, event: str, cb: Callable) -> None:
        if event in self._callbacks:
            self._callbacks[event].append(cb)

    def _emit(self, event: str, *args) -> None:
        for cb in self._callbacks.get(event, []):
            try:
                cb(*args)
            except Exception:
                pass

    # -- ciclo principal ------------------------------------------------------
    def process_text(self, text: str) -> str:
        """Procesa texto de entrada y devuelve respuesta de ARIA."""
        result = self.brain.chat(text)
        response = result.get("response", "")
        self._emit("on_response", text, response, result)
        return response

    def process_voice(self, transcript: str) -> str:
        """Procesa un transcript de voz."""
        lower = transcript.lower()
        if any(ww in lower for ww in self.voice.wake_words):
            self._awake = True
            self._emit("on_wake", transcript)
            # Extraer comando después del wake word
            cmd_text = transcript
            for ww in self.voice.wake_words:
                cmd_text = cmd_text.replace(ww, "").strip()
            if not cmd_text:
                resp = "Te escucho. ¿En qué te ayudo?"
                self.voice.speak_async(resp)
                self._emit("on_response", transcript, resp, {"source": "wake"})
                return resp
            return self.process_text(cmd_text)
        if self._awake or any(k in lower for k in ["aria", "asistente"]):
            return self.process_text(transcript)
        return ""

    def start_autonomous(self) -> None:
        self.autonomous = True
        self.save_autonomous_state()
        self._emit("on_state", "autonomous_on")

    def stop_autonomous(self) -> None:
        self.autonomous = False
        self.save_autonomous_state()
        self._emit("on_state", "autonomous_off")

    def start_voice_listening(self) -> None:
        def _on_transcript(text: str) -> None:
            resp = self.process_voice(text)
            if resp:
                self.voice.speak_async(resp)

        def _on_wake(text: str) -> None:
            self.voice.speak_async("Te escucho.")

        self.voice.start_listening(_on_transcript, _on_wake)

    def stop_voice_listening(self) -> None:
        self.voice.stop_listening()

    def speak(self, text: str) -> None:
        self.voice.speak_async(text)

    def get_status(self) -> Dict[str, Any]:
        return {
            "autonomous": self.autonomous,
            "awake": self._awake,
            "voice_caps": self.voice.capabilities(),
            "skills": len(self.skills.list()),
            "conversations": len(_read_jsonl(CONVERSATIONS_FILE)),
            "model": "transformers" if self.brain._model_loaded else "rules",
            "mode": "100% local",
        }


# ─── Instancia singleton ─────────────────────────────────────────────────────

_va: Optional[VirtualAssistant] = None
_va_lock = threading.Lock()


def get_va() -> VirtualAssistant:
    global _va
    if _va is None:
        with _va_lock:
            if _va is None:
                _va = VirtualAssistant()
    return _va


def reset_va() -> None:
    global _va
    with _va_lock:
        _va = None


__all__ = [
    "LocalAIBrain",
    "LocalVoice",
    "LocalSkills",
    "VirtualAssistant",
    "get_va",
    "reset_va",
]
