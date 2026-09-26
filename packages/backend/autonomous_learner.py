"""Autonomous learning engine for AURA - Module 25.

Rastreo de repositorios (GitHub/Web), análisis sintáctico de patrones
avanzados, extracción de buenas prácticas y generación de módulos optimizados.
"""
from __future__ import annotations


import ast
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests as _requests


@dataclass
class ScrapedFile:
    path: str
    language: str
    content: str
    size_bytes: int = 0
    source_url: str = ""


@dataclass
class CodeInsight:
    category: str
    pattern: str
    description: str
    examples: List[str] = field(default_factory=list)
    frequency: int = 0


class RepoScraper:
    """Rastrea repositorios de código (GitHub API y webs genéricas)."""

    CODE_EXTENSIONS: Dict[str, str] = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".jsx": "javascript",
        ".tsx": "typescript",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".rb": "ruby",
    }

    GITHUB_API = "https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    GITHUB_RAW = "https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"

    def __init__(self, timeout: int = 10) -> None:
        self.timeout = timeout
        self.scraped: List[ScrapedFile] = []
        self.errors: List[str] = []

    def scrape_repo(self, repo_url: str, branch: str = "main") -> List[ScrapedFile]:
        parts = repo_url.rstrip("/").split("/")
        if len(parts) < 5:
            self.errors.append(f"Invalid repo URL: {repo_url}")
            return []
        owner, repo = parts[-2], parts[-1]
        tree = self._fetch_github_tree(owner, repo, branch)
        if tree is None:
            return []

        files: List[ScrapedFile] = []
        for item in tree.get("tree", []):
            path = item.get("path", "")
            if item.get("type") != "blob" or not self._is_code_file(path):
                continue
            content = self._fetch_github_file(owner, repo, branch, path)
            if content is not None:
                lang = self._language_for(path)
                files.append(ScrapedFile(
                    path=path,
                    language=lang,
                    content=content,
                    size_bytes=item.get("size", 0),
                    source_url=f"https://github.com/{owner}/{repo}/blob/{branch}/{path}",
                ))
        self.scraped.extend(files)
        return files

    def scrape_web_page(self, url: str) -> Optional[ScrapedFile]:
        try:
            resp = _requests.get(url, timeout=self.timeout, headers={"User-Agent": "AURA-Learner/1.0"})
            resp.raise_for_status()
            ext = self._extension_for_url(url)
            lang = self.CODE_EXTENSIONS.get(ext, "html")
            sf = ScrapedFile(
                path=url,
                language=lang,
                content=resp.text,
                size_bytes=len(resp.content),
                source_url=url,
            )
            self.scraped.append(sf)
            return sf
        except Exception as exc:
            self.errors.append(f"scrape_web_page error for {url}: {exc}")
            return None

    def summary(self) -> Dict[str, Any]:
        lang_counts: Dict[str, int] = {}
        for sf in self.scraped:
            lang_counts[sf.language] = lang_counts.get(sf.language, 0) + 1
        return {
            "total_files": len(self.scraped),
            "languages": lang_counts,
            "errors": self.errors,
            "last_scrape": datetime.utcnow().isoformat() + "Z",
        }

    def _fetch_github_tree(self, owner: str, repo: str, branch: str) -> Optional[Dict[str, Any]]:
        try:
            resp = _requests.get(
                self.GITHUB_API.format(owner=owner, repo=repo, branch=branch),
                timeout=self.timeout,
                headers={"Accept": "application/vnd.github+json", "User-Agent": "AURA-Learner/1.0"},
            )
            if resp.status_code == 404:
                resp = _requests.get(
                    self.GITHUB_API.format(owner=owner, repo=repo, branch="master"),
                    timeout=self.timeout,
                    headers={"Accept": "application/vnd.github+json", "User-Agent": "AURA-Learner/1.0"},
                )
            if resp.status_code != 200:
                self.errors.append(f"GitHub API {resp.status_code} for {owner}/{repo}")
                return None
            return resp.json()
        except Exception as exc:
            self.errors.append(f"GitHub tree fetch error: {exc}")
            return None

    def _fetch_github_file(self, owner: str, repo: str, branch: str, path: str) -> Optional[str]:
        try:
            resp = _requests.get(
                self.GITHUB_RAW.format(owner=owner, repo=repo, branch=branch, path=path),
                timeout=self.timeout,
                headers={"User-Agent": "AURA-Learner/1.0"},
            )
            if resp.status_code == 200:
                return resp.text
            self.errors.append(f"GitHub file fetch {resp.status_code} for {path}")
            return None
        except Exception as exc:
            self.errors.append(f"GitHub file fetch error for {path}: {exc}")
            return None

    def _is_code_file(self, path: str) -> bool:
        return self._extension_for_url(path) in self.CODE_EXTENSIONS

    def _extension_for_url(self, url: str) -> str:
        dot_idx = url.rfind(".")
        return url[dot_idx:].lower() if dot_idx != -1 else ""

    def _language_for(self, path: str) -> str:
        return self.CODE_EXTENSIONS.get(self._extension_for_url(path), "unknown")


class InsightExtractor:
    """Análisis sintáctico de patrones avanzados y extracción de buenas prácticas."""

    def __init__(self) -> None:
        self.insights: List[CodeInsight] = []
        self._pattern_counts: Dict[str, int] = {}

    def analyze_files(self, files: List[ScrapedFile]) -> List[CodeInsight]:
        for sf in files:
            if sf.language == "python":
                self._analyze_python(sf)
        self._finalize_counts()
        return self.insights

    def _analyze_python(self, sf: ScrapedFile) -> None:
        try:
            tree = ast.parse(sf.content)
        except SyntaxError:
            self._pattern_counts["syntax_error"] = self._pattern_counts.get("syntax_error", 0) + 1
            return

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._record("functions", f"function:{node.name}", f"Función '{node.name}' definida en {sf.path}")
                if node.returns:
                    self._pattern_counts["type_hints_return"] = self._pattern_counts.get("type_hints_return", 0) + 1
                if len(node.args.args) >= 3:
                    self._pattern_counts["long_param_list"] = self._pattern_counts.get("long_param_list", 0) + 1

            if isinstance(node, ast.ClassDef):
                self._record("classes", f"class:{node.name}", f"Clase '{node.name}' definida en {sf.path}")

            if isinstance(node, ast.Try):
                self._pattern_counts["error_handling"] = self._pattern_counts.get("error_handling", 0) + 1

            if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
                self._pattern_counts["imports"] = self._pattern_counts.get("imports", 0) + 1

            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.isupper():
                        self._pattern_counts["constants"] = self._pattern_counts.get("constants", 0) + 1

    def _record(self, category: str, pattern: str, description: str) -> None:
        self._pattern_counts[f"{category}:_:{pattern}"] = self._pattern_counts.get(f"{category}:_:{pattern}", 0) + 1

    def _finalize_counts(self) -> None:
        seen: Dict[str, CodeInsight] = {}
        for key, count in self._pattern_counts.items():
            if ":_:" in key:
                category, pattern = key.split(":_:", 1)
            else:
                category, pattern = "metric", key
            if key in seen:
                seen[key].frequency = count
            else:
                seen[key] = CodeInsight(
                    category=category,
                    pattern=pattern,
                    description=f"Pattern '{pattern}' ({category})",
                    frequency=count,
                )
        self.insights = sorted(seen.values(), key=lambda i: i.frequency, reverse=True)

    def summary(self) -> Dict[str, Any]:
        return {
            "insight_count": len(self.insights),
            "top_patterns": [
                {"category": i.category, "pattern": i.pattern, "frequency": i.frequency}
                for i in self.insights[:10]
            ],
        }


class CodeSynthesizer:
    """Genera módulos optimizados a partir de insights extraídos."""

    def __init__(self) -> None:
        self.synthesized: List[Dict[str, Any]] = []

    def synthesize_module(self, insights: List[CodeInsight], module_name: str = "optimized_module") -> str:
        best_practices = [i for i in insights if i.category in ("functions", "classes", "metric")]
        has_type_hints = any(i.pattern == "type_hints_return" for i in insights)
        has_error_handling = any(i.pattern == "error_handling" for i in insights)
        has_constants = any(i.pattern == "constants" for i in insights)

        lines: List[str] = [
            f'"""Modulo optimizado generado automaticamente por AURA - {module_name}."""',
            "",
            "from __future__ import annotations",
            "",
            "import logging",
            "from typing import Any, Dict, List",
            "",
            "logger = logging.getLogger(\"AURA.Optimized\")",
            "",
        ]

        if has_constants:
            lines.append("DEFAULT_TIMEOUT: int = 30")
            lines.append("MAX_RETRIES: int = 3")
            lines.append("")

        lines.append("class OptimizedProcessor:")
        lines.append('    """Procesador optimizado con patrones aprendidos."""')
        lines.append("")
        lines.append("    def __init__(self) -> None:")
        lines.append("        self.logger = logger")
        lines.append("")

        lines.append("    def process(self, payload: Dict[str, Any]) -> Dict[str, Any]:")
        if has_error_handling:
            lines.append("        try:")
            lines.append("            result = {\"processed\": True, \"data\": payload}")
            lines.append("            self.logger.info(\"Procesado correctamente\")")
            lines.append("            return result")
            lines.append("        except Exception as exc:")
            lines.append("            self.logger.error(\"Error: %s\", exc)")
            lines.append("            return {\"processed\": False, \"error\": str(exc)}")
            lines.append("")
        else:
            lines.append("        return {\"processed\": True, \"data\": payload}")
            lines.append("")

        lines.append(f"# Best practices detected: {len(best_practices)}")
        lines.append(f"# Type hints: {'yes' if has_type_hints else 'no'}, "
                      f"Error handling: {'yes' if has_error_handling else 'no'}, "
                      f"Constants: {'yes' if has_constants else 'no'}")

        code = "\n".join(lines)
        entry = {
            "module_name": module_name,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "insight_count": len(insights),
            "practices_applied": [i.category for i in best_practices],
            "source": code,
        }
        self.synthesized.append(entry)
        return code

    def history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.synthesized[-limit:]


class AutonomousLearner:
    """Orquesta el aprendizaje autónomo: scrape → extract → synthesize."""

    def __init__(self) -> None:
        self.scraper = RepoScraper()
        self.extractor = InsightExtractor()
        self.synthesizer = CodeSynthesizer()

    def learn_from_repo(self, repo_url: str, branch: str = "main", module_name: Optional[str] = None) -> Dict[str, Any]:
        files = self.scraper.scrape_repo(repo_url, branch=branch)
        if not files:
            return {
                "status": "no_files_scraped",
                "errors": self.scraper.errors,
                "scrape_summary": self.scraper.summary(),
            }
        insights = self.extractor.analyze_files(files)
        mod_name = module_name or f"learned_{repo_url.split('/')[-1]}"
        code = self.synthesizer.synthesize_module(insights, module_name=mod_name)
        return {
            "status": "completed",
            "repo_url": repo_url,
            "branch": branch,
            "files_scraped": len(files),
            "insights_count": len(insights),
            "extractor_summary": self.extractor.summary(),
            "synthesized_module": mod_name,
            "generated_code_lines": len(code.splitlines()),
            "scrape_summary": self.scraper.summary(),
        }

    def learn_from_web(self, url: str, module_name: str = "web_learned") -> Dict[str, Any]:
        sf = self.scraper.scrape_web_page(url)
        if sf is None:
            return {"status": "scrape_failed", "errors": self.scraper.errors}
        insights = self.extractor.analyze_files([sf])
        code = self.synthesizer.synthesize_module(insights, module_name=module_name)
        return {
            "status": "completed",
            "source_url": url,
            "insights_count": len(insights),
            "synthesized_module": module_name,
            "generated_code_lines": len(code.splitlines()),
        }

    def report(self) -> Dict[str, Any]:
        return {
            "scrape": self.scraper.summary(),
            "extractor": self.extractor.summary(),
            "synthesized_count": len(self.synthesizer.history()),
        }
