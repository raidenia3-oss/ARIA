"""ARIA Skill Registry — discovery, execution and basic Tool RAG."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class SkillMeta:
    name: str
    module: str
    category: str
    description: str = ""
    enabled: bool = True


_SKILL_NAMES = [
    "status",
    "time",
    "ping",
    "scan",
    "whois",
    "weather",
    "open",
    "volume",
    "screenshot",
    "memory",
    "lock",
    "apps",
    "search",
    "list",
    "write",
    "read",
    "social-research",
    "video-analyze",
]


def _load_all() -> Dict[str, Dict[str, Any]]:
    from backend.skills.files.list import run as _f
    from backend.skills.files.read import run as _f
    from backend.skills.files.write import run as _f
    from backend.skills.system.apps import run as _f
    from backend.skills.system.lock import run as _f
    from backend.skills.system.memory import run as _f
    from backend.skills.system.open import run as _f
    from backend.skills.system.ping import run as _f
    from backend.skills.system.scan import run as _f
    from backend.skills.system.screenshot import run as _f
    from backend.skills.system.status import run as _f
    from backend.skills.system.time import run as _f
    from backend.skills.system.volume import run as _f
    from backend.skills.system.whois import run as _f
    from backend.skills.web.search import run as _f
    from backend.skills.web.weather import run as _f

    return {}


def _try_import_social_research():
    try:
        from backend.social_research.analyzer import VideoAnalyzer
        from backend.social_research.classifier import ContentClassifier
        from backend.social_research.collector import SocialCollector
        from backend.social_research.memory_bridge import MemoryBridge
        from backend.social_research.transcriber import WhisperTranscriber

        return True
    except Exception:
        return False


_social_available = _try_import_social_research()


class SkillRegistry:
    def __init__(self, skills_dir: Optional[str] = None) -> None:
        self.skills_dir = Path(skills_dir) if skills_dir else None
        self._skills: Dict[str, SkillMeta] = {}
        self._modules: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        self._skills.clear()
        self._modules.clear()
        from backend.skills.files import list as _list
        from backend.skills.files import read, write
        from backend.skills.system import (
            apps,
            lock,
            memory,
            open,
            ping,
            scan,
            screenshot,
            status,
            time,
            volume,
            whois,
        )
        from backend.skills.web import search, weather
        try:
            from backend.skills.system import control as _control_module
        except Exception:
            _control_module = None
        try:
            from backend.skills.system import explorer as _explorer_module
        except Exception:
            _explorer_module = None
        try:
            from backend.skills.system import code_exec as _code_exec_module
        except Exception:
            _code_exec_module = None
        try:
            from backend.skills.web import automation as _automation_module
        except Exception:
            _automation_module = None

        try:
            from backend.skills.custom import self_improvement as _self_improvement_module
        except Exception:
            _self_improvement_module = None

        try:
            from backend.aria_brain import AriaBrain

            _brain_loaded = True
        except Exception:
            _brain_loaded = False
        try:
            from backend.connectors import (
                discord_connector,
                github_connector,
                google_apis_connector,
                huggingface_connector,
                notion_connector,
                slack_connector,
                stable_diffusion_connector,
                stripe_connector,
                supabase_connector,
                twitter_api_connector,
            )

            _connectors_loaded = True
        except Exception:
            _connectors_loaded = False

        registrations = [
            ("status", status, "system", "Estado del sistema (CPU/RAM/disco)"),
            ("time", time, "system", "Hora y fecha actuales"),
            ("ping", ping, "system", "Ping a un host"),
            ("scan", scan, "system", "Escanear puertos abiertos"),
            ("whois", whois, "system", "Búsqueda de información de dominio"),
            ("open", open, "system", "Abrir aplicaciones"),
            ("volume", volume, "system", "Control de volumen del sistema"),
            ("screenshot", screenshot, "system", "Capturar pantalla"),
            ("memory", memory, "system", "Buscar en memoria"),
            ("lock", lock, "system", "Bloquear pantalla"),
            ("apps", apps, "system", "Listar procesos/aplicaciones"),
            ("search", search, "web", "Búsqueda web"),
            ("weather", weather, "web", "Información del clima"),
            ("list", _list, "files", "Listar archivos"),
            ("write", write, "files", "Escribir archivo"),
            ("read", read, "files", "Leer archivo"),
            ("control", _control_module, "system", "Control del PC (mouse/keyboard)"),
            ("explorer", _explorer_module, "system", "Explorador de archivos"),
            ("code_exec", _code_exec_module, "system", "Ejecución de código"),
            ("automation", _automation_module, "web", "Automatización de navegador"),
            ("social-research", None, "research", "Investigación en redes sociales (shorts/reels)"),
            ("video-analyze", None, "research", "Análisis de video inteligente"),
            ("think", None, "brain", "Motor cerebro ARIA - razonamiento y decisión"),
            ("memory-query", None, "brain", "Consulta de memoria y aprendizaje"),
            ("connectors", None, "integration", "Conectores a APIs externas (Notion, Slack, etc.)"),
            ("self-improvement", _self_improvement_module, "improvement", "Auto-mejora mediante GitHub (commits, PRs, issues, releases)"),
        ]
        for name, module, category, description in registrations:
            self._skills[name] = SkillMeta(
                name=name,
                module=module.__name__ if module else "social_research",
                category=category,
                description=description,
            )
            if module:
                self._modules[name] = module

    def list(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": name,
                "full_name": f"{m.category}.{name}",
                "category": m.category,
                "description": m.description,
                "enabled": m.enabled,
            }
            for name, m in self._skills.items()
        ]

    def has(self, name: str) -> bool:
        return name in self._skills

    def run(self, name: str, params: Dict[str, Any]) -> Any:
        if name not in self._skills:
            raise ValueError(f"Skill no encontrada: {name}")
        module = self._modules.get(name)
        if not module:
            return self._run_research_skill(name, params)
        fn = getattr(module, "run", None)
        if not callable(fn):
            return {"status": "error", "skill": name, "error": "missing run()"}
        try:
            result = fn(params)
            return {"status": "ok", "skill": name, "result": result}
        except Exception as e:
            return {"status": "error", "skill": name, "error": str(e)}

    def _run_research_skill(self, name: str, params: Dict[str, Any]) -> Any:
        if name == "social-research":
            return self._run_social_research(params)
        if name == "video-analyze":
            return self._run_video_analyze(params)
        return {"status": "error", "skill": name, "error": "skill no implementado"}

    def _run_social_research(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from backend.social_research.analyzer import VideoAnalyzer
            from backend.social_research.classifier import ContentClassifier
            from backend.social_research.collector import SocialCollector, VideoMetadata
            from backend.social_research.memory_bridge import MemoryBridge
            from backend.social_research.routes import router as social_router
            from backend.social_research.transcriber import WhisperTranscriber

            collector = SocialCollector()
            transcriber = WhisperTranscriber(model_size="base")
            analyzer = VideoAnalyzer()
            classifier = ContentClassifier()
            memory = MemoryBridge()
            url = params.get("url", "")
            topic = params.get("topic", "")
            if url and collector.is_supported(url):
                meta = collector.collect(url)
                transcription = transcriber.transcribe(meta.audio_path) if meta.audio_path else None
                frames = collector.extract_frames(meta.video_path or "", fps=0.15, max_frames=10)
                frame_paths = [f["path"] for f in frames]
                visual = analyzer.analyze_visual(frame_paths[0]) if frame_paths else None
                analysis = analyzer.analyze_video(
                    video_path=meta.video_path or "",
                    transcription_text=transcription.full_text if transcription else "",
                    visual_samples=frame_paths,
                )
                topics = [t.topic for t in analysis.topics]
                importance = classifier.classify_importance(
                    transcription_text=transcription.full_text if transcription else "",
                    visual_desc=visual.description if visual else "",
                    topics=topics,
                )
                tags = classifier.tag_content(
                    transcription.full_text if transcription else "", topics
                )
                return {
                    "status": "ok",
                    "url": url,
                    "title": meta.title,
                    "platform": meta.platform,
                    "transcription": transcription.full_text[:1000] if transcription else "",
                    "topics": topics,
                    "summary": analysis.summary,
                    "importance": {
                        "score": importance.score,
                        "level": importance.level,
                        "reasons": importance.reasons,
                    },
                    "tags": tags,
                    "visual_description": visual.description if visual else "",
                    "auto_save": importance.score >= 0.4,
                }
            elif topic:
                from backend.skills.web.search import run as search_skill

                results = []
                for q in [topic, f"{topic} tutorial", f"{topic} guía"]:
                    try:
                        r = search_skill({"query": q})
                        results.append(str(r)[:500])
                    except Exception as e:
                        results.append(f"Error: {e}")
                return {
                    "status": "ok",
                    "topic": topic,
                    "research_results": results,
                    "mode": "web_search",
                }
            return {"status": "error", "error": "URL no soportada o topic no proporcionado"}
        except Exception as e:
            return {"status": "error", "skill": "social-research", "error": str(e)}

    def _run_video_analyze(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from backend.video_analyzer.pipeline import VideoAnalysisPipeline

            pipeline = VideoAnalysisPipeline()
            url = params.get("url", "")
            if not url:
                return {"status": "error", "error": "url requerido"}
            result = pipeline.process_url(
                url, save_if_important=params.get("save_if_important", True)
            )
            return {
                "status": "ok",
                "url": result.url,
                "platform": result.platform,
                "title": result.title,
                "summary": result.summary,
                "importance": result.importance,
                "saved": result.saved,
                "processing_time": result.processing_time,
            }
        except Exception as e:
            return {"status": "error", "skill": "video-analyze", "error": str(e)}

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        query_tokens = set(query.lower().split())
        scored: List[tuple[float, Dict[str, Any]]] = []
        for name, item in zip(self._skills.keys(), self.list()):
            text = f"{item['name']} {item['description']} {item['category']}".lower()
            score = sum(1 for token in query_tokens if token in text)
            scored.append((score, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:top_k]]
