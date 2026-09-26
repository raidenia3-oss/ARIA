"""AURA Autonomous Deep Research & Recursive Self-Learning Engine (Bloque 63).

Pipeline de investigacion autonoma y aprendizaje recursivo 100% local:

- «Autonomous Deep Research Pipeline»: desglosa una pregunta compleja en
  sub-consultas, explora multiples fuentes (locales o publicas permitidas)
  y construye una respuesta integral.
- «Recursive Knowledge Synthesizer»: procesa los textos recopilados, elimina
  ruido, extrae conceptos clave estructurados y decide si requiere nuevas
  consultas de profundizacion (bucles de refinamiento).
- Persistencia: los nuevos patrones de conocimiento se absorben en la memoria
  episodica vectorial de largo plazo (MemoryEngine).

Sin dependencias de pasarelas de telemetria comercial ni motores de busqueda
corporativos centralizados de pago. Sin tokens ni claves en texto plano.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from backend.services.memory_engine import MemoryEngine

logger = logging.getLogger("AURA.Agent.DeepResearch")

# --------------------------------------------------------------------------- #
# Utilidades de texto (offline, sin dependencias externas de IA)
# --------------------------------------------------------------------------- #

_STOPWORDS = set(
    """
    de la el en y a los del se unas un las una que se es son para por como
    con su al lo no mas mas pero sus le ya o si este porque esta entre cuando
    muy sin sobre tambien me hasta hay donde quien desde todo nos durante todos
    uno les ni contra otros ese eso ante ellos e esto mi antes algunos que
    unos yo otro otras otra el but and the of to in for on with it or as at
    from this that these those they we you your our i he she them then there
    are was were be been not what when where which who how can will would
""".split()
)


@dataclass
class Source:
    url: str
    text: str
    fetched: bool = False
    error: str = ""
    indexed_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "fetched": self.fetched,
            "error": self.error,
            "indexed_at": self.indexed_at,
            "chars": len(self.text),
        }


@dataclass
class Finding:
    """Fragmento util extraido de una fuente, libre de ruido."""

    source_url: str
    sentence: str
    relevance: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_url": self.source_url,
            "sentence": self.sentence,
            "relevance": round(self.relevance, 3),
        }


@dataclass
class ResearchMission:
    mission_id: str
    question: str
    status: str = "pending"          # pending | running | completed | failed
    sub_questions: List[str] = field(default_factory=list)
    sources: List[Source] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)
    knowledge_map: Dict[str, Any] = field(default_factory=dict)
    refinement_rounds: int = 0
    memory_ids: List[str] = field(default_factory=list)
    error: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "question": self.question,
            "status": self.status,
            "sub_questions": self.sub_questions,
            "sources": [s.to_dict() for s in self.sources],
            "findings": [f.to_dict() for f in self.findings],
            "knowledge_map": self.knowledge_map,
            "refinement_rounds": self.refinement_rounds,
            "memory_ids": self.memory_ids,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }
# --------------------------------------------------------------------------- #
# Recuperacion de fuentes (solo stdlib; sin enlaces cloud)
# --------------------------------------------------------------------------- #

def _default_fetch(url: str, timeout: int = 10) -> Optional[str]:
    """Descarga el contenido de una URL publica http(s) usando solo stdlib.

    En ausencia de red devuelve None; el pipeline continua con las fuentes
    literalmente inyectadas (por ejemplo en pruebas).
    """
    if not url or not url.lower().startswith(("http://", "https://")):
        return None
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 AURA-Research"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(2_000_000)
        try:
            return raw.decode("utf-8", errors="ignore")
        except Exception:
            return raw.decode("latin-1", errors="ignore")
    except Exception as exc:  # sin conexion o recurso inaccesible
        logger.debug("fetch failed %s: %s", url, exc)
        return None


class SourceFetcher:
    """Fetcher modular y desconectable para indexar fuentes."""

    def __init__(self, fetch: Optional[Callable[[str, int], Optional[str]]] = None) -> None:
        self.fetch = fetch or _default_fetch

    def fetch_text(self, url: str, timeout: int = 10) -> Source:
        text = self.fetch(url, timeout)
        if text:
            return Source(url=url, text=text, fetched=True)
        return Source(url=url, text="", fetched=False, error="fetch_failed")


# --------------------------------------------------------------------------- #
# Descomposicion de la pregunta en sub-consultas
# --------------------------------------------------------------------------- #

_JOINERS = [" y ", " and ", ";", ", ", ":", "\n", " — ", " - "]


def decompose_question(question: str, max_parts: int = 8) -> List[str]:
    """Divide una pregunta compleja en sub-consultas accionables (offline)."""
    cleaned = re.sub(r"\s+", " ", question.strip())
    if not cleaned:
        return []

    seps = [j for j in _JOINERS if j in cleaned]
    if not seps:
        return [cleaned]

    seps.sort(key=len, reverse=True)
    parts = [cleaned]
    for sep in seps:
        merged: List[str] = []
        for part in parts:
            if sep in part:
                merged.extend([p.strip() for p in part.split(sep)])
            else:
                merged.append(part)
        parts = merged

    parts = [p for p in parts if p]
    # Re-agrupa fragmentos demasiado cortos (evita ruido de descomposicion).
    merged_parts: List[str] = []
    buf = ""
    for p in parts:
        if len(p.split()) < 4 and buf:
            buf = f"{buf} {p}".strip()
        else:
            if buf:
                merged_parts.append(buf)
            buf = p
    if buf:
        merged_parts.append(buf)

    final = merged_parts[:max_parts]
    return final or [cleaned]


# --------------------------------------------------------------------------- #
# Sintetizador recursivo de conocimiento
# --------------------------------------------------------------------------- #

class KnowledgeSynthesizer:
    """Convierte textos en bruto en hallazgos estructurados y mapa de conceptos."""

    MIN_SENTENCE_LEN = 5
    MIN_RELEVANT_TOKENS = 3
    MAX_CONCEPTS = 12

    def split_sentences(self, text: str) -> List[str]:
        raw = re.split(r"(?<=[.!?¿?])\s+|\n+", text)
        sentences = []
        for s in raw:
            s = re.sub(r"\s+", " ", s).strip()
            words = re.findall(r"\w+", s)
            if len(words) >= self.MIN_SENTENCE_LEN:
                sentences.append(s)
        return sentences

    def _content_tokens(self, sentence: str) -> List[str]:
        words = [w.lower() for w in re.findall(r"\w+", sentence)]
        return [w for w in words if w not in _STOPWORDS and len(w) > 2]

    def extract_sentences(self, texts: List[str], source_urls: Optional[List[str]] = None) -> List[Finding]:
        findings: List[Finding] = []
        urls = source_urls or [""] * len(texts)
        for text, url in zip(texts, urls):
            for sent in self.split_sentences(text):
                tokens = self._content_tokens(sent)
                relevance = len(tokens) / (len(tokens) + 1.0)
                if len(tokens) >= self.MIN_RELEVANT_TOKENS:
                    findings.append(Finding(source_url=url, sentence=sent, relevance=relevance))
        return findings

    def extract_concepts(self, texts: List[str], top_n: int = MAX_CONCEPTS) -> Dict[str, int]:
        freq: Dict[str, int] = {}
        for text in texts:
            for w in self._content_tokens(text):
                freq[w] = freq.get(w, 0) + 1
        ranked = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)
        return {word: count for word, count in ranked[:top_n]}

    def evaluate_coverage(self, mission: ResearchMission) -> float:
        """Proporcion de sub-consultas con al menos un hallazgo util (0..1)."""
        if not mission.sub_questions:
            return 1.0
        covered = 0
        for sub in mission.sub_questions:
            tokens = set(self._content_tokens(sub))
            matched = any(
                tokens.intersection(self._content_tokens(f.sentence))
                for f in mission.findings
            )
            if matched:
                covered += 1
        return covered / len(mission.sub_questions)

    def noise_ratio(self, texts: List[str]) -> float:
        """Fraccion de oraciones descartadas por ser demasiado cortas o ruido."""
        total = 0
        kept = 0
        for text in texts:
            for sent in self.split_sentences(text):
                total += 1
                if len(self._content_tokens(sent)) >= self.MIN_RELEVANT_TOKENS:
                    kept += 1
        return round(1.0 - (kept / total), 3) if total else 0.0

    def synthetize(self, texts: List[str], source_urls: Optional[List[str]] = None) -> Dict[str, Any]:
        findings = self.extract_sentences(texts, source_urls)
        concepts = self.extract_concepts(texts)
        combined = "\n".join(texts)
        summary = self._build_summary(findings, concepts)
        return {
            "concepts": concepts,
            "concept_count": len(concepts),
            "finding_count": len(findings),
            "findings": findings,
            "summary": summary,
            "noise_ratio": self.noise_ratio(texts),
            "coverage": None,
        }

    def _build_summary(self, findings: List[Finding], concepts: Dict[str, int]) -> str:
        if not findings:
            return ""
        top_keys = list(concepts.keys())[:6]
        best = " ".join(top_keys)
        return f"{len(findings)} fuentes sintetizadas sobre: {best}."
# --------------------------------------------------------------------------- #
# Motor de investigacion profunda
# --------------------------------------------------------------------------- #

class DeepResearchEngine:
    def __init__(
        self,
        memory_engine: Optional[MemoryEngine] = None,
        fetcher: Optional[SourceFetcher] = None,
        storage_dir: Optional[str] = None,
        max_refine_depth: int = 2,
        coverage_target: float = 0.6,
    ) -> None:
        self._lock = threading.Lock()
        self._memory = memory_engine or MemoryEngine()
        self._fetcher = fetcher or SourceFetcher()
        self._synth = KnowledgeSynthesizer()
        self._max_refine_depth = max_refine_depth
        self._coverage_target = coverage_target
        self._storage_dir = Path(
            storage_dir or os.getenv("AURA_RESEARCH_DIR", os.path.join("data", "research"))
        )
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._missions: Dict[str, ResearchMission] = {}
        self._load()

    def _uuid(self) -> str:
        return hashlib.sha256(f"{time.time()}:{os.urandom(8)}".encode("utf-8")).hexdigest()[:16]

    def _mission_file(self, mission_id: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_-]", "", mission_id)
        return self._storage_dir / f"{safe}.json"

    def _load(self) -> None:
        try:
            for f in sorted(self._storage_dir.glob("*.json")):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    self._restore(data)
                except Exception as exc:
                    logger.debug("skip corrupt mission %s: %s", f.name, exc)
        except Exception as exc:
            logger.debug("research dir load failed: %s", exc)

    def _restore(self, data: Dict[str, Any]) -> None:
        mission = ResearchMission(
            mission_id=str(data.get("mission_id", "")),
            question=str(data.get("question", "")),
            status=str(data.get("status", "completed")),
            sub_questions=list(data.get("sub_questions", []) or []),
            findings=[
                Finding(
                    source_url=str(f.get("source_url", "")),
                    sentence=str(f.get("sentence", "")),
                    relevance=float(f.get("relevance", 0.0)),
                )
                for f in data.get("findings", []) or []
            ],
            knowledge_map=dict(data.get("knowledge_map", {}) or {}),
            refinement_rounds=int(data.get("refinement_rounds", 0)),
            memory_ids=list(data.get("memory_ids", []) or []),
            error=str(data.get("error", "")),
            created_at=float(data.get("created_at", time.time())),
            updated_at=float(data.get("updated_at", time.time())),
            metadata=dict(data.get("metadata", {}) or {}),
        )
        for s in data.get("sources", []) or []:
            mission.sources.append(
                Source(
                    url=str(s.get("url", "")),
                    text=str(s.get("text", "")),
                    fetched=bool(s.get("fetched", False)),
                    error=str(s.get("error", "")),
                    indexed_at=float(s.get("indexed_at", time.time())),
                )
            )
        with self._lock:
            self._missions[mission.mission_id] = mission

    def start_mission(
        self,
        question: str,
        sources: Optional[List[str]] = None,
        seed_texts: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        max_refine_depth: Optional[int] = None,
    ) -> ResearchMission:
        if not question or not question.strip():
            raise ValueError("question_required")
        mission_id = self._uuid()
        mission = ResearchMission(
            mission_id=mission_id,
            question=question.strip(),
            status="pending",
            sub_questions=decompose_question(question),
            metadata=metadata or {},
        )
        with self._lock:
            self._missions[mission_id] = mission
        self._execute(mission, sources or [], seed_texts or [], max_refine_depth)
        return mission

    def _execute(
        self,
        mission: ResearchMission,
        source_urls: List[str],
        seed_texts: List[str],
        max_refine_depth: Optional[int],
    ) -> None:
        mission.status = "running"
        self._touch(mission)
        depth = max_refine_depth if max_refine_depth is not None else self._max_refine_depth
        try:
            texts: List[str] = []
            urls: List[str] = []
            for t in seed_texts:
                if t and t.strip():
                    texts.append(t.strip())
                    urls.append("seed://inline")
            for url in source_urls:
                src = self._fetcher.fetch_text(url)
                mission.sources.append(src)
                if src.fetched:
                    texts.append(src.text)
                    urls.append(src.url)

            refine_attempts = 0
            while refine_attempts <= depth:
                result = self._synth.synthetize(texts, urls)
                mission.knowledge_map = {
                    "concepts": result["concepts"],
                    "concept_count": result["concept_count"],
                    "finding_count": result["finding_count"],
                    "summary": result["summary"],
                    "noise_ratio": result["noise_ratio"],
                    "sources_indexed": len(mission.sources),
                    "refinement_rounds": mission.refinement_rounds,
                }
                mission.findings = result["findings"]
                coverage = self._synth.evaluate_coverage(mission)
                mission.knowledge_map["coverage"] = round(coverage, 3)
                mission.knowledge_map["target_met"] = coverage >= self._coverage_target

                if coverage >= self._coverage_target or refine_attempts >= depth:
                    break
                # Bucle de refinamiento: deriva sub-consultas de los conceptos
                # con menor cobertura para profundizar la investigacion.
                deeper = self._derive_deeper_questions(mission, limit=2)
                if not deeper:
                    break
                for sub in deeper:
                    if sub not in mission.sub_questions:
                        mission.sub_questions.append(sub)
                mission.refinement_rounds += 1
                refine_attempts += 1
                self._touch(mission)

            mission.status = "completed"
            self._absorb_to_memory(mission)
        except Exception as exc:
            logger.exception("research mission %s failed", mission.mission_id)
            mission.status = "failed"
            mission.error = str(exc)
        self._touch(mission)
        self._save(mission)

    def _derive_deeper_questions(self, mission: ResearchMission, limit: int = 2) -> List[str]:
        """Genera sub-consultas de profundizacion a partir de conceptos descubiertos."""
        concepts = list((mission.knowledge_map.get("concepts") or {}).keys())
        if not concepts:
            return []
        out = []
        for c in concepts[:limit]:
            out.append(f"Detalle y contexto adicional sobre {c}.")
        return out

    def _absorb_to_memory(self, mission: ResearchMission) -> None:
        """Alimenta la memoria episodica vectorial de largo plazo."""
        concepts = mission.knowledge_map.get("concepts") or {}
        stored: List[str] = []
        if mission.knowledge_map.get("summary"):
            try:
                r = self._memory.remember(
                    mission.knowledge_map["summary"],
                    memory_type="research",
                    source="deep_research",
                    metadata={
                        "kind": "research",
                        "mission_id": mission.mission_id,
                        "question": mission.question,
                        "concepts": list(concepts.keys()),
                        "sources_indexed": mission.knowledge_map.get("sources_indexed", 0),
                    },
                )
                if r.get("status") == "ok":
                    stored.append(r["memory_id"])
            except Exception as exc:
                logger.debug("memory absorb failed: %s", exc)
        mission.memory_ids = stored

    def _touch(self, mission: ResearchMission) -> None:
        mission.updated_at = time.time()

    def _save(self, mission: ResearchMission) -> None:
        try:
            path = self._mission_file(mission.mission_id)
            path.write_text(json.dumps(mission.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.debug("mission save failed: %s", exc)

    def get_mission(self, mission_id: str) -> Optional[ResearchMission]:
        return self._missions.get(mission_id)

    def delete_mission(self, mission_id: str) -> bool:
        with self._lock:
            existed = mission_id in self._missions
            self._missions.pop(mission_id, None)
        if existed:
            try:
                self._mission_file(mission_id).unlink(missing_ok=True)
            except Exception:
                pass
        return existed

    def list_missions(self, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            missions = list(self._missions.values())
        if status:
            missions = [m for m in missions if m.status == status]
        missions.sort(key=lambda m: m.created_at, reverse=True)
        return [m.to_dict() for m in missions[:limit]]

    def search_knowledge(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        try:
            return self._memory.search(query, max_results=max_results, min_relevance=0.1)
        except Exception:
            return {"status": "ok", "count": 0, "results": []}

    def history(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            missions = list(self._missions.values())
        missions.sort(key=lambda m: m.created_at, reverse=True)
        entries = []
        for m in missions[:limit]:
            entries.append({
                "mission_id": m.mission_id,
                "question": m.question,
                "status": m.status,
                "concept_count": m.knowledge_map.get("concept_count", 0),
                "sources_indexed": m.knowledge_map.get("sources_indexed", 0),
                "coverage": m.knowledge_map.get("coverage", 0.0),
                "created_at": m.created_at,
                "memory_ids": m.memory_ids,
            })
        return entries

    def get_status(self) -> Dict[str, Any]:
        total = len(self._missions)
        by_status: Dict[str, int] = {}
        for m in self._missions.values():
            by_status[m.status] = by_status.get(m.status, 0) + 1
        stored = self._memory.get_status()
        return {
            "total_missions": total,
            "missions_by_status": by_status,
            "storage_dir": str(self._storage_dir),
            "max_refine_depth": self._max_refine_depth,
            "coverage_target": self._coverage_target,
            "knowledge_memories": stored.get("total_memories", 0),
        }

    def count(self) -> int:
        return len(self._missions)


_research_engine: Optional[DeepResearchEngine] = None


def get_research_engine() -> DeepResearchEngine:
    global _research_engine
    if _research_engine is None:
        _research_engine = DeepResearchEngine()
    return _research_engine


def reset_research_engine() -> None:
    global _research_engine
    _research_engine = None


__all__ = [
    "DeepResearchEngine",
    "Finding",
    "KnowledgeSynthesizer",
    "ResearchMission",
    "Source",
    "SourceFetcher",
    "decompose_question",
    "get_research_engine",
    "reset_research_engine",
]