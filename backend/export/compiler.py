"""Local Manuscript Compiler & Export Engine (BLOQUE 42).

Ensambla capítulos, arcos, Character Bible y metadatos del canon en formatos
de publicación profesional: EPUB, PDF (via reportlab) y Markdown estructurado.
100% offline, sin dependencias cloud.
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        Paragraph, SimpleDocTemplate, Spacer, PageBreak, Image as RLImage
    )
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

from backend.story_memory.story_storage import StoryStorage
from backend.story_memory.canon_tracker import CanonTracker
from backend.story_memory.character_bible import CharacterBible
from backend.story_memory.chapter_planner import ChapterPlanner


@dataclass
class ExportMetadata:
    """Metadatos de la obra para exportación."""
    work_id: str
    title: str
    author: str = ""
    universe: str = ""
    description: str = ""
    language: str = "es"
    cover_image_path: Optional[str] = None
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = field(default_factory=lambda: datetime.now().timestamp())


@dataclass
class ChapterExportData:
    """Datos de un capítulo para exportación."""
    chapter_id: str
    title: str
    order: int
    beat_summary: str = ""
    scenes: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "planned"
    related_canon: List[str] = field(default_factory=list)


@dataclass
class CompiledManuscript:
    """Manuscrito compilado listo para exportación."""
    metadata: ExportMetadata
    characters: List[Dict[str, Any]] = field(default_factory=list)
    canon_events: List[Dict[str, Any]] = field(default_factory=list)
    continuity_events: List[Dict[str, Any]] = field(default_factory=list)
    chapters: List[ChapterExportData] = field(default_factory=list)


class ManuscriptCompiler:
    """Compilador local de manuscritos literarios."""

    def __init__(self, store_dir: Optional[str] = None) -> None:
        self.store_dir = store_dir or os.getenv(
            "AURA_STORY_DIR", os.path.join(os.getcwd(), "story_memory")
        )
        self.storage = StoryStorage(store_dir=self.store_dir)
        self.canon_tracker = CanonTracker()
        self.character_bible = CharacterBible()
        self.chapter_planner = ChapterPlanner()

    def compile_work(self, work_id: str) -> CompiledManuscript:
        """Compila todos los datos de una obra en un manuscrito estructurado."""
        work_meta = self.storage.get_work(work_id)
        if not work_meta:
            raise ValueError(f"Work not found: {work_id}")

        metadata = ExportMetadata(
            work_id=work_id,
            title=work_meta.get("title", ""),
            author=work_meta.get("author", ""),
            universe=work_meta.get("universe", ""),
            description=work_meta.get("description", ""),
        )

        characters = self.character_bible.list(work_id)
        canon_events = self.canon_tracker.get_canon_events(work_id)
        continuity_events = self.canon_tracker.get_continuity_events(work_id)
        raw_chapters = self.chapter_planner.list_chapters(work_id)

        chapters = []
        for ch in raw_chapters:
            chapters.append(ChapterExportData(
                chapter_id=ch.get("chapter_id", ""),
                title=ch.get("title", ""),
                order=ch.get("order", 0),
                beat_summary=ch.get("beat_summary", ""),
                scenes=ch.get("scenes", []),
                status=ch.get("status", "planned"),
                related_canon=ch.get("related_canon", []),
            ))

        chapters.sort(key=lambda c: c.order)

        return CompiledManuscript(
            metadata=metadata,
            characters=characters,
            canon_events=canon_events,
            continuity_events=continuity_events,
            chapters=chapters,
        )


class EPUBGenerator:
    """Generador de EPUB 3.0 válido (basado en ZIP + XML estándar)."""

    EPUB_VERSION = "3.0"

    def __init__(self) -> None:
        pass

    def generate(self, manuscript: CompiledManuscript, output_path: str) -> None:
        """Genera archivo EPUB completo."""
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as epub:
            self._write_mimetype(epub)
            self._write_container_xml(epub)
            self._write_opf(epub, manuscript)
            self._write_nav_xhtml(epub, manuscript)
            self._write_chapters_xhtml(epub, manuscript)
            self._write_styles_css(epub)
            if manuscript.metadata.cover_image_path:
                self._write_cover_image(epub, manuscript.metadata.cover_image_path)

    def _write_mimetype(self, epub: zipfile.ZipFile) -> None:
        epub.writestr("mimetype", "application/epub+zip")

    def _write_container_xml(self, epub: zipfile.ZipFile) -> None:
        container = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""
        epub.writestr("META-INF/container.xml", container)

    def _write_opf(self, epub: zipfile.ZipFile, manuscript: CompiledManuscript) -> None:
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        uuid = f"urn:uuid:{manuscript.metadata.work_id}"

        manifest_items = [
            '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
            '<item id="css" href="styles.css" media-type="text/css"/>',
        ]
        spine_items = ['<itemref idref="nav"/>']

        for i, ch in enumerate(manuscript.chapters):
            item_id = f"ch{i+1}"
            href = f"chapter_{i+1}.xhtml"
            manifest_items.append(
                f'<item id="{item_id}" href="{href}" media-type="application/xhtml+xml"/>'
            )
            spine_items.append(f'<itemref idref="{item_id}"/>')

        if manuscript.metadata.cover_image_path:
            manifest_items.insert(0,
                '<item id="cover" href="cover.jpg" media-type="image/jpeg" properties="cover-image"/>'
            )
            spine_items.insert(0, '<itemref idref="cover" linear="no"/>')

        opf = f"""<?xml version="1.0" encoding="UTF-8"?>
<package version="3.0" xmlns="http://www.idpf.org/2007/opf" unique-identifier="pub-id" prefix="rendition: http://www.idpf.org/vocab/rendition/#">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="pub-id">{uuid}</dc:identifier>
    <dc:title>{self._escape_xml(manuscript.metadata.title)}</dc:title>
    <dc:creator>{self._escape_xml(manuscript.metadata.author)}</dc:creator>
    <dc:language>{manuscript.metadata.language}</dc:language>
    <dc:description>{self._escape_xml(manuscript.metadata.description)}</dc:description>
    <dc:subject>{self._escape_xml(manuscript.metadata.universe)}</dc:subject>
    <meta property="dcterms:modified">{now}</meta>
    <meta name="cover" content="cover"/>
  </metadata>
  <manifest>
    {''.join(manifest_items)}
  </manifest>
  <spine page-progression-direction="ltr">
    {''.join(spine_items)}
  </spine>
</package>"""
        epub.writestr("OEBPS/content.opf", opf)

    def _write_nav_xhtml(self, epub: zipfile.ZipFile, manuscript: CompiledManuscript) -> None:
        nav_items = []
        for i, ch in enumerate(manuscript.chapters):
            nav_items.append(
                f'<li><a href="chapter_{i+1}.xhtml">{self._escape_xml(ch.title)}</a></li>'
            )

        nav = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
  <title>Tabla de Contenidos</title>
  <link rel="stylesheet" href="styles.css"/>
</head>
<body>
  <nav epub:type="toc" id="toc">
    <h1>Tabla de Contenidos</h1>
    <ol>
      {''.join(nav_items)}
    </ol>
  </nav>
  <nav epub:type="landmarks" hidden="">
    <h1>Landmarks</h1>
    <ol>
      <li><a epub:type="bodymatter" href="chapter_1.xhtml">Inicio de la lectura</a></li>
    </ol>
  </nav>
</body>
</html>"""
        epub.writestr("OEBPS/nav.xhtml", nav)

    def _write_chapters_xhtml(self, epub: zipfile.ZipFile, manuscript: CompiledManuscript) -> None:
        for i, ch in enumerate(manuscript.chapters):
            content_parts = [f'<h1 class="chapter-title">{self._escape_xml(ch.title)}</h1>']

            if ch.beat_summary:
                content_parts.append(f'<p class="beat-summary">{self._escape_xml(ch.beat_summary)}</p>')

            for scene in ch.scenes:
                scene_content = scene.get("content", "")
                if scene_content:
                    for para in scene_content.split("\n\n"):
                        if para.strip():
                            content_parts.append(f'<p>{self._escape_xml(para.strip())}</p>')

            xhtml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
  <title>{self._escape_xml(ch.title)}</title>
  <link rel="stylesheet" href="styles.css"/>
</head>
<body>
  <section epub:type="chapter" id="chapter-{i+1}">
    {''.join(content_parts)}
  </section>
</body>
</html>"""
            epub.writestr(f"OEBPS/chapter_{i+1}.xhtml", xhtml)

    def _write_styles_css(self, epub: zipfile.ZipFile) -> None:
        css = """@namespace epub "http://www.idpf.org/2007/ops";

body {
    font-family: Georgia, serif;
    line-height: 1.6;
    margin: 2em;
    color: #222;
}

h1.chapter-title {
    font-size: 1.8em;
    font-weight: bold;
    text-align: center;
    margin: 2em 0 1em;
    page-break-before: always;
}

p {
    margin: 0.8em 0;
    text-indent: 1.5em;
    text-align: justify;
}

p.beat-summary {
    font-style: italic;
    color: #555;
    text-indent: 0;
    margin: 1em 2em;
}

    section[epub|type="chapter"] {
        page-break-before: always;
    }
    """
        epub.writestr("OEBPS/styles.css", css)

    @staticmethod
    def _escape_xml(text: str) -> str:
        return (
            text.replace("&", "&")
            .replace("<", "<")
            .replace(">", ">")
            .replace('"', '"')
            .replace("'", "'")
        )

    def _write_cover_image(self, epub: zipfile.ZipFile, cover_path: str) -> None:
        try:
            with open(cover_path, "rb") as f:
                epub.writestr("OEBPS/cover.jpg", f.read())
        except Exception:
            pass


class MarkdownGenerator:
    """Generador de paquete Markdown estructurado con front-matter YAML."""

    def generate(self, manuscript: CompiledManuscript, output_dir: str) -> None:
        """Genera estructura de directorios con archivos Markdown."""
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        self._write_manifest(manuscript, out_path)
        self._write_metadata(manuscript, out_path)
        self._write_characters(manuscript, out_path)
        self._write_canon(manuscript, out_path)
        self._write_chapters(manuscript, out_path)

    def _write_manifest(self, manuscript: CompiledManuscript, out_path: Path) -> None:
        manifest = {
            "work_id": manuscript.metadata.work_id,
            "title": manuscript.metadata.title,
            "author": manuscript.metadata.author,
            "universe": manuscript.metadata.universe,
            "language": manuscript.metadata.language,
            "exported_at": datetime.now().isoformat(),
            "chapters_count": len(manuscript.chapters),
            "characters_count": len(manuscript.characters),
            "canon_events_count": len(manuscript.canon_events),
            "structure": {
                "metadata": "metadata.yaml",
                "characters": "characters/",
                "canon": "canon.yaml",
                "chapters": "chapters/",
            }
        }
        (out_path / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _write_metadata(self, manuscript: CompiledManuscript, out_path: Path) -> None:
        yaml_lines = [
            f"title: \"{manuscript.metadata.title}\"",
            f"author: \"{manuscript.metadata.author}\"",
            f"universe: \"{manuscript.metadata.universe}\"",
            f"language: \"{manuscript.metadata.language}\"",
            f"description: \"{manuscript.metadata.description}\"",
            f"work_id: \"{manuscript.metadata.work_id}\"",
            f"created_at: {manuscript.metadata.created_at}",
            f"updated_at: {manuscript.metadata.updated_at}",
        ]
        (out_path / "metadata.yaml").write_text("\n".join(yaml_lines), encoding="utf-8")

    def _write_characters(self, manuscript: CompiledManuscript, out_path: Path) -> None:
        chars_dir = out_path / "characters"
        chars_dir.mkdir(exist_ok=True)
        for char in manuscript.characters:
            char_id = char.get("char_id", "unknown")
            lines = [
                f"# {char.get('name', char_id)}",
                "",
                f"**ID:** {char_id}",
            ]
            if char.get("aliases"):
                lines.append(f"**Alias:** {', '.join(char['aliases'])}")
            if char.get("species"):
                lines.append(f"**Especie:** {char['species']}")
            if char.get("age"):
                lines.append(f"**Edad:** {char['age']}")
            if char.get("voice"):
                lines.append(f"**Voz:** {char['voice']}")
            if char.get("personality"):
                lines.append(f"**Personalidad:** {', '.join(char['personality'])}")
            if char.get("objectives"):
                lines.append(f"**Objetivos:** {', '.join(char['objectives'])}")
            if char.get("conflicts"):
                lines.append(f"**Conflictos:** {', '.join(char['conflicts'])}")
            if char.get("relationships"):
                lines.append("**Relaciones:**")
                for k, v in char["relationships"].items():
                    lines.append(f"- {k}: {v}")
            if char.get("backstory"):
                lines.append(f"**Historia:** {char['backstory']}")

            (chars_dir / f"{char_id}.md").write_text("\n".join(lines), encoding="utf-8")

    def _write_canon(self, manuscript: CompiledManuscript, out_path: Path) -> None:
        lines = ["# Eventos Canónicos", ""]
        for ev in manuscript.canon_events:
            ts = datetime.fromtimestamp(ev.get("timestamp", 0)).strftime("%Y-%m-%d %H:%M")
            lines.append(f"## {ts} — {ev.get('description', '')}")
            if ev.get("scene_ref"):
                lines.append(f"*Escena:* {ev['scene_ref']}")
            lines.append("")

        lines.append("## Eventos de Continuidad")
        for ev in manuscript.continuity_events:
            ts = datetime.fromtimestamp(ev.get("timestamp", 0)).strftime("%Y-%m-%d %H:%M")
            lines.append(f"### {ts} — {ev.get('description', '')}")
            if ev.get("scene_ref"):
                lines.append(f"*Escena:* {ev['scene_ref']}")
            lines.append("")

        (out_path / "canon.md").write_text("\n".join(lines), encoding="utf-8")

    def _write_chapters(self, manuscript: CompiledManuscript, out_path: Path) -> None:
        ch_dir = out_path / "chapters"
        ch_dir.mkdir(exist_ok=True)
        for ch in manuscript.chapters:
            lines = [
                f"# Capítulo {ch.order}: {ch.title}",
                "",
                f"**Status:** {ch.status}",
                f"**ID:** {ch.chapter_id}",
            ]
            if ch.beat_summary:
                lines.append(f"**Resumen:** {ch.beat_summary}")
            if ch.related_canon:
                lines.append(f"**Canon relacionado:** {', '.join(ch.related_canon)}")
            lines.append("")

            for scene in ch.scenes:
                content = scene.get("content", "")
                if content:
                    lines.append(f"## Escena {scene.get('scene_id', '?')}")
                    lines.append("")
                    lines.append(content)
                    lines.append("")

            (ch_dir / f"chapter_{ch.order:03d}_{ch.chapter_id}.md").write_text(
                "\n".join(lines), encoding="utf-8"
            )


class PDFGenerator:
    """Generador de PDF limpio usando reportlab (si está disponible)."""

    def __init__(self) -> None:
        if not REPORTLAB_AVAILABLE:
            raise RuntimeError("reportlab no está instalado. pip install reportlab")

    def generate(self, manuscript: CompiledManuscript, output_path: str) -> None:
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            leftMargin=25*72/25.4,
            rightMargin=25*72/25.4,
            topMargin=25*72/25.4,
            bottomMargin=25*72/25.4,
        )
        styles = getSampleStyleSheet()
        style_title = ParagraphStyle(
            'CustomTitle', parent=styles['Title'], fontSize=24, spaceAfter=30,
            alignment=1,
        )
        style_h1 = ParagraphStyle(
            'CustomH1', parent=styles['Heading1'], fontSize=18, spaceBefore=24, spaceAfter=12,
        )
        style_body = ParagraphStyle(
            'CustomBody', parent=styles['Normal'], fontSize=11, leading=16,
            firstLineIndent=36, alignment=4,
        )
        style_meta = ParagraphStyle(
            'Meta', parent=styles['Normal'], fontSize=10, textColor='#666', spaceAfter=6,
        )

        story = []

        story.append(Paragraph(manuscript.metadata.title, style_title))
        if manuscript.metadata.author:
            story.append(Paragraph(f"por {manuscript.metadata.author}", style_meta))
        if manuscript.metadata.universe:
            story.append(Paragraph(f"Universo: {manuscript.metadata.universe}", style_meta))
        story.append(Spacer(1, 24))

        for ch in manuscript.chapters:
            story.append(Paragraph(ch.title, style_h1))
            if ch.beat_summary:
                story.append(Paragraph(f"<i>{ch.beat_summary}</i>", style_meta))
            story.append(Spacer(1, 12))

            for scene in ch.scenes:
                content = scene.get("content", "")
                if content:
                    for para in content.split("\n\n"):
                        if para.strip():
                            story.append(Paragraph(para.strip(), style_body))
            story.append(PageBreak())

        doc.build(story)


class ExportEngine:
    """Motor principal de exportación: compila y genera artefactos."""

    def __init__(self, store_dir: Optional[str] = None) -> None:
        self.compiler = ManuscriptCompiler(store_dir=store_dir)
        self.epub_gen = EPUBGenerator()
        self.md_gen = MarkdownGenerator()
        self.pdf_gen = PDFGenerator() if REPORTLAB_AVAILABLE else None

    def compile_and_export(
        self,
        work_id: str,
        format: str,
        output_path: str,
    ) -> Dict[str, Any]:
        """Compila la obra y exporta al formato solicitado."""
        manuscript = self.compiler.compile_work(work_id)

        if format == "epub":
            self.epub_gen.generate(manuscript, output_path)
            return {"status": "ok", "format": "epub", "path": output_path}
        elif format == "markdown":
            self.md_gen.generate(manuscript, output_path)
            return {"status": "ok", "format": "markdown", "path": output_path}
        elif format == "pdf":
            if not self.pdf_gen:
                raise RuntimeError("PDF generation requires reportlab (pip install reportlab)")
            self.pdf_gen.generate(manuscript, output_path)
            return {"status": "ok", "format": "pdf", "path": output_path}
        else:
            raise ValueError(f"Unsupported format: {format}")

    def get_supported_formats(self) -> List[str]:
        formats = ["epub", "markdown"]
        if REPORTLAB_AVAILABLE:
            formats.append("pdf")
        return formats


def get_export_engine(store_dir: Optional[str] = None) -> ExportEngine:
    return ExportEngine(store_dir=store_dir)