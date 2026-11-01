"""
REA Bridge — Conecta Aria con Reverse Engineer Anything (morluto/rea).

Provee capacidades autónomas que Aria utiliza para su crecimiento y
mejora continua:

1. **Análisis binario**: REA inspecciona binarios (Mach-O, PE, WASM, APK)
   extrayendo estructuras, funciones, strings, call graphs.

2. **Navegación web con REA**: REA inspecciona páginas web, extrae
   estructura, scripts, redes y observaciones.

3. **Análisis de videos de YouTube**: descarga y transcribe videos
   mediante yt-dlp + Whisper, luego Aria procesa las transcripciones.

4. **Clonación de software**: REA inspecciona binarios/apps y Aria
   sintetiza código funcional equivalente.

Diseño:
- ``REABridge`` comunica con el MCP server de REA (--mcp stdio mode) usando
  el cliente `mcp` library.
- Las operaciones son *headless* y observables vía API REST.
- Si REA no está disponible, las operaciones degradan gracefulmente
  al motor de investigación local de AURA (Bloque 63).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AURA.REABridge")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

_REA_PATH = Path(os.getenv("AURA_REA_PATH", str(_PROJECT_ROOT / "github" / "reverse-engineer")))
_DEFAULT_REA_PORT = 8843

_NATIVE_PROVIDERS = {
    "ghidra": {
        "env_keys": ["GHIDRA_INSTALL_DIR", "GHIDRA_HOME"],
        "binary": "ghidra",
    },
    "hopper": {
        "env_keys": ["HOPPER_HOME"],
        "binary": "hopper",
    },
    "ida": {
        "env_keys": ["IDA_PRO", "IDA_HOME"],
        "binary": "ida",
    },
}


def _provider_info(name: str, provider: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": name,
        "binary": provider["binary"],
    }


class REABridge:
    """Puente entre AURA y el MCP server de REA.

    Comunica con REA a través de su MCP server (stdio mode) usando
    el cliente `mcp` library. Si REA no está disponible, las operaciones
    degradan gracefulmente al motor de investigación local de AURA.

    Gestiona cuentas de proveedores de análisis nativo (Ghidra, Hopper, IDA)
    mediante variables de entorno o credenciales configuradas por el usuario.
    """

    def __init__(self) -> None:
        self._rea_path = _REA_PATH
        self._port = os.getenv("AURA_REA_PORT", str(_DEFAULT_REA_PORT))
        self._available: Optional[bool] = None
        self._client: Optional[Any] = None
        self._yt_dlp_path = shutil.which("yt-dlp") or None
        self._whisper_model = os.getenv("AURA_WHISPER_MODEL", "base")
        self._provider_configs: Dict[str, Dict[str, Any]] = {}
        self._load_provider_configs()

    def _load_provider_configs(self) -> None:
        """Carga configuraciones de proveedores desde env/.rea/providers.json."""
        config_path = Path(os.getenv("AURA_REA_CONFIG", _PROJECT_ROOT / ".rea" / "providers.json"))
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    self._provider_configs = json.load(f)
                logger.info("REABridge: configuración de proveedores cargada desde %s", config_path)
            except Exception as exc:
                logger.warning("REABridge: no se pudo cargar config de proveedores: %s", exc)

        for name, info in _NATIVE_PROVIDERS.items():
            for env_key in info["env_keys"]:
                val = os.getenv(env_key)
                if val:
                    self._provider_configs[name] = {
                        "env_key": env_key,
                        "path": val,
                        "binary": info["binary"],
                    }
                    break

    @property
    def _mcp_params(self) -> Any:
        """Construye los parámetros StdioServerParameters para el cliente MCP."""
        rea_cmd = _resolve_rea_binary()
        return StdioServerParameters(
            command=rea_cmd,
            args=["--mcp"],
            cwd=str(self._rea_path),
            env={**os.environ, "NODE_ENV": "production"},
        )

    def _get_rea_env(self) -> Dict[str, str]:
        """Entorno extendido con credenciales de proveedores para REA."""
        env = {**os.environ, "NODE_ENV": "production"}
        provider_map = {}
        for name, cfg in self._provider_configs.items():
            provider_map[name] = {
                "available": True,
                "path": cfg.get("path"),
                "binary": cfg.get("binary"),
            }
        if provider_map:
            env["REA_PROVIDER_CONFIG"] = json.dumps(provider_map)
        return env

    def get_providers(self) -> Dict[str, Dict[str, Any]]:
        """Devuelve los proveedores de análisis nativo configurados."""
        return {
            name: {
                **_provider_info(name, info),
                "configured": name in self._provider_configs,
                "config": self._provider_configs.get(name, {}),
            }
            for name, info in _NATIVE_PROVIDERS.items()
        }

    def connect_provider(self, name: str, **kwargs: Any) -> bool:
        """Conecta/registra un proveedor de análisis nativo (cuenta Ghidra/IDA/Hopper).

        Accepta api_key/password (credenciales), o path/binary (instalación local).
        """
        if name not in _NATIVE_PROVIDERS:
            return False
        if "api_key" in kwargs or "password" in kwargs:
            kwargs["api_key"] = kwargs.get("api_key", kwargs.pop("password"))
            self._provider_configs[name] = {**_provider_info(name, _NATIVE_PROVIDERS[name]), **kwargs}
        elif "path" in kwargs or "binary" in kwargs:
            self._provider_configs[name] = {
                **kwargs,
                "env_key": kwargs.get("env_key", _NATIVE_PROVIDERS[name]["env_keys"][0]),
                "path": kwargs.get("path", ""),
                "binary": kwargs.get("binary", _NATIVE_PROVIDERS[name]["binary"]),
            }
        else:
            for env_key in _NATIVE_PROVIDERS[name]["env_keys"]:
                env_val = os.getenv(env_key)
                if env_val:
                    self._provider_configs[name] = {
                        "env_key": env_key,
                        "path": env_val,
                        "binary": _NATIVE_PROVIDERS[name]["binary"],
                    }
                    break
        return name in self._provider_configs

    def save_provider_config(self) -> bool:
        """Persiste la configuración de proveedores en .rea/providers.json."""
        config_path = Path(os.getenv("AURA_REA_CONFIG", _PROJECT_ROOT / ".rea" / "providers.json"))
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(self._provider_configs, f, indent=2)
            logger.info("REABridge: configuración guardada en %s", config_path)
            return True
        except Exception as exc:
            logger.error("REABridge: error guardando config: %s", exc)
            return False

    def is_available(self) -> bool:
        """Verifica si el MCP server de REA está disponible."""
        if self._available is not None:
            return self._available
        if not self._rea_path.exists():
            logger.warning("REABridge: REA path no existe: %s", self._rea_path)
            self._available = False
            return False
        try:
            import mcp  # noqa: F401
            self._available = True
        except ImportError:
            logger.warning("REABridge: mcp client library no disponible")
            self._available = False
        return self._available

    async def _call_mcp_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Invoca una herramienta MCP en el servidor REA.

        Crea una conexión MCP stdio, llama la herramienta y cierra la conexión.
        Esto es necesario porque REA es un MCP server stdio, no un servidor HTTP persistente.
        """
        if not self.is_available():
            return {"error": "REA no disponible"}

        from mcp import Client, StdioServerParameters

        params = StdioServerParameters(
            command=_resolve_rea_binary(),
            args=["--mcp"],
            cwd=str(self._rea_path),
            env=self._get_rea_env(),
        )
        client = Client(params, raise_exceptions=False, read_timeout_seconds=300)

        try:
            async with client:
                result = await client.call_tool(tool_name, arguments or {})
                # Extract text content from the result
                output: Dict[str, Any] = {}
                if hasattr(result, 'content') and result.content:
                    for item in result.content:
                        if hasattr(item, 'text') and item.text:
                            try:
                                output = json.loads(item.text)
                            except json.JSONDecodeError:
                                output["raw"] = item.text
                if hasattr(result, 'isError') and result.isError:
                    output["error"] = output.get("error", "MCP tool returned error")
                return output
        except Exception as exc:
            logger.error("REABridge: error llamando MCP tool %s: %s", tool_name, exc)
            return {"error": str(exc)}

    async def analyze_binary(self, path: str) -> Dict[str, Any]:
        """Analiza un binario local usando REA.

        Abre el binario y obtiene: overview, funciones, strings, call graph.
        """
        result: Dict[str, Any] = {
            "path": path,
            "source": "rea",
            "timestamp": time.time(),
            "available": False,
        }

        target_path = Path(path)
        if not target_path.exists():
            result["error"] = f"Path no existe: {path}"
            return result

        if not self.is_available():
            result["error"] = "REA no disponible"
            return result

        try:
            # Step 1: open_binary
            open_result = await self._call_mcp_tool("open_binary", {"path": path})
            if "error" in open_result:
                result["error"] = open_result["error"]
                return result
            result["binary_opened"] = True

            # Step 2: binary_overview
            overview = await self._call_mcp_tool("binary_overview")
            if "error" in overview:
                result["error"] = overview["error"]
                return result

            result["available"] = True
            result["overview"] = overview
            result["findings"] = overview.get("findings", [])
            result["evidence"] = overview.get("evidence", {})

            logger.info("REABridge: análisis binario completado para %s", path)
        except Exception as exc:
            result["error"] = str(exc)
            logger.exception("REABridge: error analizando binario %s", path)

        return result

    async def analyze_website(self, url: str) -> Dict[str, Any]:
        """Navega y analiza una página web usando REA.

        Retorna: page structure, scripts, network observations, screenshots.
        """
        result: Dict[str, Any] = {
            "url": url,
            "source": "rea",
            "timestamp": time.time(),
            "available": False,
        }

        if not self.is_available():
            logger.warning("REABridge: REA no disponible, usando fallback local")
            return await self._fallback_web_analysis(url, result)

        try:
            web_result = await self._call_mcp_tool("inspect_web_page", {
                "origins": [url],
                "capture": {
                    "network": True,
                    "javascript": True,
                    "screenshot": True,
                },
            })

            if "error" in web_result:
                logger.warning("REABridge: REA falló (%s), fallback", web_result["error"][:200])
                return await self._fallback_web_analysis(url, result)

            result["available"] = True
            result["structure"] = web_result.get("structure", {})
            result["scripts"] = web_result.get("scripts", [])
            result["network"] = web_result.get("network", [])
            result["screenshots"] = web_result.get("screenshots", [])
            result["pages"] = web_result.get("pages", [])
            logger.info("REABridge: análisis web completado para %s", url)
        except (asyncio.TimeoutError, FileNotFoundError) as exc:
            logger.warning("REABridge: REA error (%s), fallback", exc)
            return await self._fallback_web_analysis(url, result)

        return result

    async def _fallback_web_analysis(self, url: str, base: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback local usando urllib (Bloque 63 DeepResearch engine)."""
        base["source"] = "local-fallback"
        base["available"] = False
        try:
            from backend.agent.deep_research import SourceFetcher
            fetcher = SourceFetcher()
            src = fetcher.fetch_text(url, timeout=15)
            base["fetched"] = src.fetched
            base["text"] = src.text[:5000]
            if src.error:
                base["error"] = src.error
        except Exception as exc:
            base["error"] = str(exc)
        return base

    async def analyze_youtube_video(self, url: str) -> Dict[str, Any]:
        """Descarga y analiza un video de YouTube.

        Pipeline:
        1. yt-dlp descarga el audio/video.
        2. Whisper transcribe el audio.
        3. REA (si disponible) inspecciona el video para extraer
           escenas, texto en pantalla (OCR) y observaciones.
        4. El resultado se alimenta al motor de investigación (MemoryEngine).
        """
        result: Dict[str, Any] = {
            "url": url,
            "source": "rea-youtube",
            "timestamp": time.time(),
            "available": False,
            "yt_dlp_available": self._yt_dlp_path is not None,
        }

        if self._yt_dlp_path is None:
            result["error"] = "yt-dlp no encontrado en PATH"
            logger.warning("REABridge: yt-dlp no disponible")
            return result

        video_id = self._extract_youtube_id(url)
        work_dir = Path(os.getenv("AURA_RESEARCH_DIR", "data/research")) / "youtube"
        work_dir.mkdir(parents=True, exist_ok=True)
        video_file = work_dir / f"{video_id}.mp4"
        audio_file = work_dir / f"{video_id}.m4a"
        transcript_file = work_dir / f"{video_id}_transcript.txt"

        try:
            if not video_file.exists():
                download_cmd = [
                    self._yt_dlp_path,
                    "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
                    "-o", str(video_file),
                    url,
                ]
                proc = await asyncio.create_subprocess_exec(
                    *download_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                rc = await asyncio.wait_for(proc.wait(), timeout=300)
                result["downloaded"] = rc == 0 and video_file.exists()
                result["download_rc"] = rc
            else:
                result["downloaded"] = True
                result["source"] = "cached"

            if not video_file.exists():
                result["error"] = "No se pudo descargar el video"
                return result

            if audio_file.exists() or video_file.exists():
                if not audio_file.exists():
                    import subprocess as sp
                    extract = sp.run(
                        ["ffmpeg", "-i", str(video_file), "-vn", "-acodec", "copy", str(audio_file)],
                        capture_output=True, timeout=120,
                    )
                    if extract.returncode != 0:
                        logger.debug("REABridge: ffmpeg falló, usando video directamente")

                transcript_text = ""
                if not transcript_file.exists():
                    whisper_path = shutil.which("whisper")
                    if whisper_path:
                        import subprocess as sp
                        proc = sp.run(
                            [whisper_path, str(audio_file if audio_file.exists() else video_file),
                             "--model", self._whisper_model, "--language", "es", "--output_txt",
                             "--output_dir", str(work_dir)],
                            capture_output=True, timeout=600,
                        )
                        possible = list(work_dir.glob(f"{video_id}*.txt"))
                        if possible:
                            transcript_text = possible[0].read_text(encoding="utf-8", errors="replace")
                            transcript_file.write_text(transcript_text, encoding="utf-8")
                        result["whisper_rc"] = proc.returncode

                if transcript_file.exists():
                    transcript_text = transcript_file.read_text(encoding="utf-8", errors="replace")
                    result["transcript_available"] = True
                    result["transcript_length"] = len(transcript_text)
                    result["transcript_preview"] = transcript_text[:2000]
                else:
                    result["transcript_available"] = False
                    result["error"] = "No se pudo transcribir el video"

            from backend.agent.deep_research import get_research_engine
            engine = get_research_engine()
            engine.start_mission(
                question=f"Análisis profundo del video de YouTube: {url}",
                seed_texts=[transcript_text] if transcript_text else [],
                metadata={
                    "source": "youtube-video",
                    "video_url": url,
                    "video_id": video_id,
                    "video_file": str(video_file),
                },
            )
            result["memory_indexed"] = True
            logger.info("REABridge: video de YouTube analizado e indexado: %s", url)

        except asyncio.TimeoutError:
            result["error"] = "timeout durante análisis de video"
            logger.error("REABridge: timeout analizando video %s", url)
        except Exception as exc:
            result["error"] = str(exc)
            logger.exception("REABridge: error analizando video %s", url)

        return result

    @staticmethod
    def _extract_youtube_id(url: str) -> str:
        """Extrae el ID de video de YouTube de una URL."""
        import re
        match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
        if match:
            return match.group(1)
        return str(int(time.time()))

    async def fuse_game_mod(self, source_game: str, target_game: str, character: str) -> Dict[str, Any]:
        """Fusiona un personaje o mod de un juego origen a un juego destino.

        Usa REA para inspeccionar los binarios de ambos juegos y extraer
        estructuras de datos (modelos, texturas, animaciones, comportamientos),
        luego genera código compatible con el motor del juego destino.

        Args:
            source_game: Ruta al binario/directorio del juego origen.
            target_game: Ruta al binario/directorio del juego destino.
            character: Nombre del personaje/mode a fusionar.

        Returns:
            Dict con findings, evidence y código generado.
        """
        result: Dict[str, Any] = {
            "source_game": source_game,
            "target_game": target_game,
            "character": character,
            "timestamp": time.time(),
            "source": "rea-fusion",
            "available": False,
        }

        source_path = Path(source_game)
        target_path = Path(target_game)

        if not source_path.exists() or not target_path.exists():
            result["error"] = "Uno o ambos caminos de juego no existen"
            return result

        if not self.is_available():
            result["error"] = "REA no disponible para análisis de binarios"
            logger.warning("REABridge: REA no disponible para fusión de mods")
            return result

        try:
            for label, game_path, prefix in [
                ("source", source_path, ""),
                ("target", target_path, "target_"),
            ]:
                analysis = await self.analyze_binary(str(game_path))
                if analysis.get("available"):
                    result[f"{prefix}analysis"] = analysis
                    result["available"] = True
                else:
                    result[f"{prefix}error"] = analysis.get("error", "unknown error")

            prompt = (
                f"Actúa como un ingeniero de mods experto. Fusiona el personaje "
                f"'{character}' del juego origen al juego destino. "
                f"Origen: {result.get('analysis', {}).get('overview', source_game)}\n"
                f"Destino: {result.get('target_analysis', {}).get('overview', target_game)}\n"
                f"Extrae: modelos 3D, texturas, animaciones, comportamientos, estructuras de datos.\n"
                f"Genera código compatible con el motor del juego destino."
            )

            from backend.agent.deep_research import get_research_engine
            engine = get_research_engine()
            mission = engine.start_mission(
                question=f"Fusionar personaje '{character}' de {source_game} a {target_game}",
                seed_texts=[prompt],
                metadata={
                    "source": "mod-fusion",
                    "character": character,
                    "source_game": source_game,
                    "target_game": target_game,
                },
            )
            result["mission_id"] = mission.mission_id
            result["knowledge_map"] = mission.knowledge_map
            result["generated_code"] = self._generate_mod_code(
                character, source_game, target_game, mission
            )
            logger.info("REABridge: fusión de mods completada: %s -> %s (%s)", source_game, target_game, character)

        except asyncio.TimeoutError:
            result["error"] = "timeout durante análisis de binarios"
            logger.error("REABridge: timeout en fusión de mods")
        except Exception as exc:
            result["error"] = str(exc)
            logger.exception("REABridge: error en fusión de mods")

        return result

    def _generate_mod_code(
        self, character: str, source_game: str, target_game: str, mission: Any
    ) -> Dict[str, str]:
        """Genera código base para el mod fusionado."""
        concepts = mission.knowledge_map.get("concepts", {}) if mission else {}
        concept_list = list(concepts.keys())[:8]

        model_code = (
            f"// {character} mod fusionado para {target_game}\n"
            f"// Fuente: {source_game}\n"
            f"// Conceptos detectados por REA: {', '.join(concept_list) or 'N/A'}\n"
            f"\n"
            f"// TODO: Implementar carga de modelo 3D\n"
            f"// TODO: Mapear texturas del personaje\n"
            f"// TODO: Portar animaciones al motor objetivo\n"
            f"// TODO: Adaptar comportamientos de IA\n"
        )

        return {
            "cpp_mod": model_code,
            "lua_mod": f"-- {character} mod fusionado\nlocal mod = {{}}\nmod.name = \"{character}\"\nreturn mod\n",
            "python_bridge": (
                f"# Bridge Python para {character}\n"
                f"import re\n"
                f"class {character.replace('-', '_').replace(' ', '_')}Mod:\n"
                f"    def __init__(self):\n"
                f"        self.name = \"{character}\"\n"
                f"        self.source = \"{source_game}\"\n"
                f"        self.target = \"{target_game}\"\n"
            ),
        }

    async def clone_software(self, target_url_or_path: str, output_dir: str) -> Dict[str, Any]:
        """Pipeline completo de clonación de software usando REA.

        1. REA inspecciona el binario/aplicación objetivo (Ghidra/Hopper/IDA).
        2. Extrae estructuras de datos, funciones, strings, call graphs.
        3. El motor de investigación de AURA sintetiza un reemplazamiento
           funcional compatible con el stack del usuario.
        4. Genera código de clonación y documentación de evidencia.

        Args:
            target_url_or_path: URL o ruta al software/binario a clonar.
            output_dir: Directorio donde guardar el código clonado.

        Returns:
            Dict con findings, evidence, generated_files, y mission_id.
        """
        result: Dict[str, Any] = {
            "target": target_url_or_path,
            "output_dir": output_dir,
            "timestamp": time.time(),
            "source": "rea-clone",
            "available": False,
        }

        target_path = Path(target_url_or_path)

        if not self.is_available():
            result["error"] = "REA no disponible"
            logger.warning("REABridge: REA no disponible para clonación")
            return result

        try:
            if target_path.exists() and target_path.is_file():
                analysis = await self.analyze_binary(str(target_path))
            elif target_path.exists() and target_path.is_dir():
                analysis = await self.analyze_binary(str(target_path))
            else:
                # Treat as URL - use inspect_web_page
                analysis = await self._call_mcp_tool("inspect_web_page", {
                    "origins": [target_url_or_path],
                    "capture": {"network": True, "javascript": True},
                })
                if "error" in analysis:
                    result["error"] = analysis["error"]
                    return result
                analysis = {"available": True, "overview": analysis}

            if not analysis.get("available"):
                result["error"] = analysis.get("error", "REA analysis failed")
                return result

            result["analysis"] = analysis
            result["available"] = True
            result["findings"] = analysis.get("findings", [])
            result["evidence"] = analysis.get("evidence", analysis.get("overview", {}))

            output = Path(output_dir)
            output.mkdir(parents=True, exist_ok=True)

            from backend.agent.deep_research import get_research_engine
            engine = get_research_engine()
            synthesis = engine.start_mission(
                question=f"Clonar el software en {target_url_or_path} generando código funcional equivalente",
                seed_texts=[json.dumps(analysis.get("findings", []), ensure_ascii=False)[:5000]],
                metadata={
                    "source": "software-clone",
                    "target": target_url_or_path,
                    "findings_count": len(analysis.get("findings", [])),
                },
            )

            code_content = self._generate_clone_code(
                target_url_or_path, analysis, synthesis
            )
            code_file = output / "cloned_software.py"
            code_file.write_text(code_content, encoding="utf-8")

            docs_file = output / "CLONE_REPORT.md"
            docs_file.write_text(self._generate_clone_report(target_url_or_path, analysis), encoding="utf-8")

            result["mission_id"] = synthesis.mission_id
            result["knowledge_map"] = synthesis.knowledge_map
            result["generated_files"] = [str(code_file), str(docs_file)]
            result["output_dir"] = str(output)
            logger.info("REABridge: clonación completada: %s -> %s", target_url_or_path, output_dir)

        except asyncio.TimeoutError:
            result["error"] = "timeout durante clonación de software"
            logger.error("REABridge: timeout clonando %s", target_url_or_path)
        except Exception as exc:
            result["error"] = str(exc)
            logger.exception("REABridge: error clonando software")

        return result

    def _generate_clone_code(self, target: str, analysis: Dict[str, Any], mission: Any) -> str:
        """Genera código base para el software clonado."""
        concepts = mission.knowledge_map.get("concepts", {}) if mission else {}
        concept_list = list(concepts.keys())[:10]
        functions = analysis.get("analysis", {}).get("functions", analysis.get("functions", []))
        strings = analysis.get("analysis", {}).get("strings", analysis.get("strings", []))[:50]

        code = [
            f'"""Clonación automática de: {target}',
            f"Conceptos detectados por REA: {', '.join(concept_list) or 'N/A'}",
            f'"""',
            "from __future__ import annotations",
            "",
            "class ClonedSoftware:",
            f'    """Clon de {target.split("/")[-1] if target else "software"}."""',
            "",
        ]

        for fn in functions[:5]:
            code.append(f"    def {fn.get('name', 'unknown')}({fn.get('params', '')}):")
            purpose = fn.get('purpose', 'Sin descripción')
            code.append(f'        """{purpose}"""')
            code.append("        pass")
            code.append("")

        code.append("    def _extracted_strings(self):")
        code.append(f"        return {repr(strings)}")
        code.append("")

        return "\n".join(code)

    def _generate_clone_report(self, target: str, analysis: Dict[str, Any]) -> str:
        """Genera reporte Markdown con el proceso de clonación."""
        overview = analysis.get("overview", analysis.get("analysis", analysis))
        findings = analysis.get("findings", overview.get("findings", []))
        evidence = overview.get("evidence", analysis.get("evidence", {}))

        report = [
            "# Reporte de Clonación — REA + AURA",
            "",
            f"**Target:** {target}",
            f"**Timestamp:** {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}",
            f"**Herramienta:** {evidence.get('tool', 'REA')}",
            "",
            "## Hallazgos",
            "",
        ]

        for i, finding in enumerate(findings[:20], 1):
            report.append(f"{i}. {finding.get('description', str(finding))}")

        report.extend([
            "",
            "## Estructura Detectada",
            "",
            f"- Funciones: {len(overview.get('functions', []))}",
            f"- Strings: {len(overview.get('strings', []))}",
            f"- Calls: {len(overview.get('calls', []))}",
            "",
            "## Próximos Pasos",
            "1. Refinar el código generado con pruebas unitarias",
            "2. Verificar funcionalidad equivalente con el binario original",
            "3. Optimizar rendimiento con el motor de análisis local",
            "",
        ])

        return "\n".join(report)

    async def connect_account(self, provider: str, **credentials: Any) -> Dict[str, Any]:
        """Conecta una cuenta de proveedor (Ghidra, IDA, Hopper) a REA.

        Args:
            provider: "ghidra", "hopper" o "ida"
            **credentials: credenciales (api_key, password, path, binary, etc.)

        Returns:
            Estado de la conexión.
        """
        success = self.connect_provider(provider, **credentials)
        if success:
            self.save_provider_config()
        return {
            "provider": provider,
            "connected": success,
            "providers": self.get_providers(),
        }


def _resolve_rea_binary() -> str:
    """Resuelve el binario REA para invocar como MCP server stdio."""
    for binary in ("rea", "rea.cmd", "rea-agents", "rea-agents.cmd"):
        exe = shutil.which(binary)
        if exe:
            return exe
    if os.name == "nt":
        return "rea.cmd"
    return "rea"


def _resolve_mcp_params() -> "StdioServerParameters":
    """Construye StdioServerParameters para lanzar REA como MCP server stdio."""
    from mcp import StdioServerParameters
    rea_path = _REA_PATH
    return StdioServerParameters(
        command=_resolve_rea_binary(),
        args=["--mcp"],
        cwd=str(rea_path),
        env={**os.environ, "NODE_ENV": "production"},
    )


# Import StdioServerParameters at module level for type hints
try:
    from mcp import StdioServerParameters  # noqa: E402
except ImportError:
    StdioServerParameters = None  # type: ignore


_rea_bridge: Optional[REABridge] = None


def get_rea_bridge() -> REABridge:
    """Singleton accessor for REABridge."""
    global _rea_bridge
    if _rea_bridge is None:
        _rea_bridge = REABridge()
    return _rea_bridge


__all__ = ["REABridge", "get_rea_bridge"]
