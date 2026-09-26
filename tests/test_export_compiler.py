"""Tests Bloque 42 - Local Manuscript Compiler & Export Engine.

Valida:
- Compilación de manuscrito (metadatos, personajes, canon, capítulos).
- Generación EPUB válida (estructura ZIP + OPF + NAV + XHTML).
- Generación Markdown estructurado (manifest + metadata + chapters).
- Generación PDF (si reportlab disponible).
- Endpoints REST /export/formats, /export/{format}, /export/{format}/async.
"""

from __future__ import annotations

import json
import os
import tempfile
import zipfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.export.compiler import (
    ChapterExportData,
    CompiledManuscript,
    EPUBGenerator,
    ExportEngine,
    ExportMetadata,
    ManuscriptCompiler,
    MarkdownGenerator,
    PDFGenerator,
    get_export_engine,
)
from backend.story_memory.canon_tracker import CanonTracker
from backend.story_memory.chapter_planner import ChapterPlanner
from backend.story_memory.character_bible import CharacterBible
from backend.story_memory.story_storage import StoryStorage


@pytest.fixture
def temp_story_dir(tmp_path, monkeypatch):
    """Crea directorio temporal para story data."""
    story_dir = str(tmp_path / "story_memory")
    os.makedirs(story_dir, exist_ok=True)
    monkeypatch.setenv("AURA_STORY_DIR", story_dir)
    return story_dir


@pytest.fixture
def work_with_content(temp_story_dir):
    """Crea una obra con personajes, canon, continuity y capítulos."""
    storage = StoryStorage(store_dir=temp_story_dir)
    storage.create_work(
        work_id="test_export",
        title="La Espada Eterna",
        universe="Fantasía Épica",
        description="Una historia de dragones y héroes",
        author="Autor Test",
    )

    ct = CanonTracker()
    ct.add_canon_event(
        work_id="test_export",
        description="El héroe encuentra la espada en la cueva",
        timestamp=1000.0,
        scene_ref="ch1_sc1",
        source="user",
    )
    ct.add_canon_event(
        work_id="test_export",
        description="El dragón despierta y ataca la aldea",
        timestamp=2000.0,
        scene_ref="ch2_sc1",
        source="user",
    )

    ct.add_continuity_event(
        work_id="test_export",
        description="El héroe recuerda su infancia en la aldea",
        timestamp=1500.0,
        scene_ref="ch1_sc2",
        source="user",
    )

    cb = CharacterBible()
    cb.create(
        work_id="test_export",
        char_id="heroe",
        name="Aldric",
        voice="Narrativa en tercera persona, tono heroico",
        personality=["valiente", "leal", "justo"],
        objectives=["salvar el reino", "encontrar la espada"],
        conflicts=["miedo a fallar", "dragón ancestral"],
        relationships={"mentor": "guía sabio", "villano": "enemigo mortal"},
        species="humano",
        age=24,
        backstory="Huérfano criado por el herrero del pueblo",
    )

    cb.create(
        work_id="test_export",
        char_id="dragón",
        name="Pyroth",
        voice="Profundo, ancestral, habla en acertijos",
        personality=["orgulloso", "sabio", "territorial"],
        objectives=["proteger su tesoro", "dormir mil años"],
        conflicts=["héroes codiciosos", "maldición del sueño"],
        species="dragón",
        age=5000,
        backstory="Antiguo guardián de la montaña de fuego",
    )

    cp = ChapterPlanner()
    cp.create_chapter(
        work_id="test_export",
        title="El Despertar",
        order=1,
        beat_summary="El héroe descubre su destino",
        scenes=[
            {
                "scene_id": "ch1_sc1",
                "content": "Aldric caminaba por el bosque cuando vio un brillo en una cueva.",
            },
            {
                "scene_id": "ch1_sc2",
                "content": "Recordó las palabras de su mentor: 'La espada elige a su portador'.",
            },
        ],
        related_canon=["canon_1"],
    )
    cp.create_chapter(
        work_id="test_export",
        title="La Bestia Despierta",
        order=2,
        beat_summary="El dragón ataca y el héroe debe huir",
        scenes=[
            {
                "scene_id": "ch2_sc1",
                "content": "El suelo tembló. Pyroth emergió de la montaña con un rugido que heló la sangre.",
            },
        ],
        related_canon=["canon_2"],
    )
    cp.update_chapter_status(
        "test_export", cp.list_chapters("test_export")[0]["chapter_id"], "completed"
    )
    cp.update_chapter_status(
        "test_export", cp.list_chapters("test_export")[1]["chapter_id"], "in_progress"
    )

    return temp_story_dir


# -- ManuscriptCompiler tests -------------------------------------------------


def test_compiler_compiles_complete_manuscript(work_with_content):
    compiler = ManuscriptCompiler(store_dir=work_with_content)
    manuscript = compiler.compile_work("test_export")

    assert isinstance(manuscript, CompiledManuscript)
    assert manuscript.metadata.work_id == "test_export"
    assert manuscript.metadata.title == "La Espada Eterna"
    assert manuscript.metadata.author == "Autor Test"
    assert manuscript.metadata.universe == "Fantasía Épica"

    assert len(manuscript.characters) == 2
    char_names = {c["name"] for c in manuscript.characters}
    assert "Aldric" in char_names
    assert "Pyroth" in char_names

    assert len(manuscript.canon_events) == 2
    assert len(manuscript.continuity_events) == 1

    assert len(manuscript.chapters) == 2
    assert manuscript.chapters[0].order == 1
    assert manuscript.chapters[0].title == "El Despertar"
    assert manuscript.chapters[1].order == 2
    assert manuscript.chapters[1].title == "La Bestia Despierta"


def test_compiler_raises_on_missing_work(work_with_content):
    compiler = ManuscriptCompiler(store_dir=work_with_content)
    with pytest.raises(ValueError, match="Work not found"):
        compiler.compile_work("nonexistent")


# -- EPUBGenerator tests ------------------------------------------------------


def test_epub_generator_creates_valid_structure(work_with_content, tmp_path):
    compiler = ManuscriptCompiler(store_dir=work_with_content)
    manuscript = compiler.compile_work("test_export")

    gen = EPUBGenerator()
    output_path = str(tmp_path / "test.epub")
    gen.generate(manuscript, output_path)

    assert os.path.exists(output_path)

    # Verificar estructura ZIP
    with zipfile.ZipFile(output_path, "r") as epub:
        names = epub.namelist()
        assert "mimetype" in names
        assert "META-INF/container.xml" in names
        assert "OEBPS/content.opf" in names
        assert "OEBPS/nav.xhtml" in names
        assert "OEBPS/styles.css" in names
        assert "OEBPS/chapter_1.xhtml" in names
        assert "OEBPS/chapter_2.xhtml" in names

        # Verificar mimetype
        mimetype = epub.read("mimetype").decode("utf-8")
        assert mimetype == "application/epub+zip"

        # Verificar OPF tiene metadata correcta
        opf = epub.read("OEBPS/content.opf").decode("utf-8")
        assert "La Espada Eterna" in opf
        assert "Autor Test" in opf
        assert "Fantasía Épica" in opf

        # Verificar NAV tiene capítulos
        nav = epub.read("OEBPS/nav.xhtml").decode("utf-8")
        assert "El Despertar" in nav
        assert "La Bestia Despierta" in nav


def test_epub_chapter_content_includes_scenes(work_with_content, tmp_path):
    compiler = ManuscriptCompiler(store_dir=work_with_content)
    manuscript = compiler.compile_work("test_export")

    gen = EPUBGenerator()
    output_path = str(tmp_path / "test.epub")
    gen.generate(manuscript, output_path)

    with zipfile.ZipFile(output_path, "r") as epub:
        ch1 = epub.read("OEBPS/chapter_1.xhtml").decode("utf-8")
        assert "Aldric caminaba por el bosque" in ch1
        assert "Recordó las palabras de su mentor" in ch1


# -- MarkdownGenerator tests --------------------------------------------------


def test_markdown_generator_creates_structure(work_with_content, tmp_path):
    compiler = ManuscriptCompiler(store_dir=work_with_content)
    manuscript = compiler.compile_work("test_export")

    gen = MarkdownGenerator()
    output_dir = str(tmp_path / "markdown_export")
    gen.generate(manuscript, output_dir)

    out = Path(output_dir)
    assert (out / "manifest.json").exists()
    assert (out / "metadata.yaml").exists()
    assert (out / "canon.md").exists()
    assert (out / "characters" / "heroe.md").exists()
    assert (out / "characters" / "dragón.md").exists()
    assert (out / "chapters").exists()

    # Verificar manifest
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["title"] == "La Espada Eterna"
    assert manifest["chapters_count"] == 2
    assert manifest["characters_count"] == 2

    # Verificar metadata.yaml
    metadata = (out / "metadata.yaml").read_text(encoding="utf-8")
    assert 'title: "La Espada Eterna"' in metadata
    assert 'author: "Autor Test"' in metadata

    # Verificar canon.md
    canon = (out / "canon.md").read_text(encoding="utf-8")
    assert "El héroe encuentra la espada" in canon
    assert "El dragón despierta" in canon
    assert "Eventos de Continuidad" in canon
    assert "recuerda su infancia" in canon

    # Verificar capítulos
    ch_files = list((out / "chapters").glob("*.md"))
    assert len(ch_files) == 2


def test_markdown_chapter_contains_scenes(work_with_content, tmp_path):
    compiler = ManuscriptCompiler(store_dir=work_with_content)
    manuscript = compiler.compile_work("test_export")

    gen = MarkdownGenerator()
    output_dir = str(tmp_path / "markdown_export")
    gen.generate(manuscript, output_dir)

    out = Path(output_dir)
    ch1_files = list((out / "chapters").glob("chapter_001_*.md"))
    assert len(ch1_files) == 1
    content = ch1_files[0].read_text(encoding="utf-8")
    assert "Capítulo 1: El Despertar" in content
    assert "Aldric caminaba por el bosque" in content
    assert "Recordó las palabras" in content


# -- ExportEngine tests -------------------------------------------------------


def test_export_engine_epub(work_with_content, tmp_path):
    engine = ExportEngine(store_dir=work_with_content)
    output_path = str(tmp_path / "export.epub")
    result = engine.compile_and_export("test_export", "epub", output_path)

    assert result["status"] == "ok"
    assert result["format"] == "epub"
    assert os.path.exists(output_path)

    # Verificar que es ZIP válido
    with zipfile.ZipFile(output_path, "r") as z:
        assert "OEBPS/content.opf" in z.namelist()


def test_export_engine_markdown(work_with_content, tmp_path):
    engine = ExportEngine(store_dir=work_with_content)
    output_path = str(tmp_path / "markdown_out")
    result = engine.compile_and_export("test_export", "markdown", output_path)

    assert result["status"] == "ok"
    assert result["format"] == "markdown"
    assert os.path.exists(output_path)
    assert (Path(output_path) / "manifest.json").exists()


def test_export_engine_supported_formats(work_with_content):
    engine = ExportEngine(store_dir=work_with_content)
    formats = engine.get_supported_formats()
    assert "epub" in formats
    assert "markdown" in formats


def test_export_engine_invalid_format(work_with_content, tmp_path):
    engine = ExportEngine(store_dir=work_with_content)
    with pytest.raises(ValueError, match="Unsupported format"):
        engine.compile_and_export("test_export", "invalid", str(tmp_path / "x"))


# -- PDFGenerator tests (conditional) -----------------------------------------


def test_pdf_generator_if_available(work_with_content, tmp_path):
    try:
        gen = PDFGenerator()
    except RuntimeError:
        pytest.skip("reportlab not installed")

    compiler = ManuscriptCompiler(store_dir=work_with_content)
    manuscript = compiler.compile_work("test_export")

    output_path = str(tmp_path / "test.pdf")
    gen.generate(manuscript, output_path)

    assert os.path.exists(output_path)
    assert os.path.getsize(output_path) > 0


# -- REST API tests -----------------------------------------------------------


def _rest_setup(temp_story_dir, monkeypatch):
    from backend.story_memory.canon_tracker import CanonTracker
    from backend.story_memory.chapter_planner import ChapterPlanner
    from backend.story_memory.character_bible import CharacterBible
    from backend.story_memory.story_storage import StoryStorage
    from backend.story_routes import router

    # Create test work data
    storage = StoryStorage(store_dir=temp_story_dir)
    storage.create_work(
        work_id="test_export",
        title="Test Export",
        universe="Test",
        description="Test",
        author="Test",
    )
    ct = CanonTracker()
    ct.add_canon_event(work_id="test_export", description="Event 1")
    cb = CharacterBible()
    cb.create(work_id="test_export", char_id="char1", name="Char 1")
    cp = ChapterPlanner()
    cp.create_chapter(
        work_id="test_export",
        title="Chapter 1",
        order=1,
        scenes=[{"scene_id": "s1", "content": "Content"}],
    )

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    return client


def test_rest_export_formats(temp_story_dir, monkeypatch):
    monkeypatch.setenv("AURA_STORY_DIR", temp_story_dir)
    client = _rest_setup(temp_story_dir, monkeypatch)

    r = client.get("/api/story/test_export/export/formats")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "epub" in body["formats"]
    assert "markdown" in body["formats"]


def test_rest_export_epub(temp_story_dir, monkeypatch):
    monkeypatch.setenv("AURA_STORY_DIR", temp_story_dir)
    client = _rest_setup(temp_story_dir, monkeypatch)

    r = client.post("/api/story/test_export/export/epub", json={})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/epub+zip"
    assert "attachment" in r.headers["content-disposition"]
    assert len(r.content) > 0


def test_rest_export_markdown(temp_story_dir, monkeypatch):
    monkeypatch.setenv("AURA_STORY_DIR", temp_story_dir)
    client = _rest_setup(temp_story_dir, monkeypatch)

    r = client.post("/api/story/test_export/export/markdown", json={})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    assert len(r.content) > 0

    # Verificar que el ZIP contiene manifest.json
    import io

    with zipfile.ZipFile(io.BytesIO(r.content), "r") as z:
        assert "manifest.json" in z.namelist()


def test_rest_export_custom_filename(temp_story_dir, monkeypatch):
    monkeypatch.setenv("AURA_STORY_DIR", temp_story_dir)
    client = _rest_setup(temp_story_dir, monkeypatch)

    r = client.post("/api/story/test_export/export/epub", json={"output_filename": "mi_libro.epub"})
    assert r.status_code == 200
    assert "mi_libro.epub" in r.headers["content-disposition"]


def test_rest_export_work_not_found(temp_story_dir, monkeypatch):
    monkeypatch.setenv("AURA_STORY_DIR", temp_story_dir)
    client = _rest_setup(temp_story_dir, monkeypatch)

    r = client.post("/api/story/ghost/export/epub", json={})
    assert r.status_code == 404


def test_rest_export_invalid_format(temp_story_dir, monkeypatch):
    monkeypatch.setenv("AURA_STORY_DIR", temp_story_dir)
    client = _rest_setup(temp_story_dir, monkeypatch)

    r = client.post("/api/story/test_export/export/invalid", json={})
    assert r.status_code == 400


def test_rest_export_async_epub(temp_story_dir, monkeypatch):
    monkeypatch.setenv("AURA_STORY_DIR", temp_story_dir)
    client = _rest_setup(temp_story_dir, monkeypatch)

    r = client.post("/api/story/test_export/export/epub/async", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "accepted"
    assert "job_id" in body

    job_id = body["job_id"]

    # Poll hasta completado
    import time

    for _ in range(20):
        time.sleep(0.2)
        r2 = client.get(f"/api/story/test_export/export/jobs/{job_id}")
        if r2.status_code == 200:
            job = r2.json()["job"]
            if job["status"] == "completed":
                break

    r2 = client.get(f"/api/story/test_export/export/jobs/{job_id}")
    assert r2.status_code == 200
    job = r2.json()["job"]
    assert job["status"] == "completed"
    assert "path" in job

    # Descargar
    r3 = client.get(f"/api/story/test_export/export/jobs/{job_id}/download")
    assert r3.status_code == 200
    assert len(r3.content) > 0


def test_rest_export_async_job_not_found(temp_story_dir, monkeypatch):
    monkeypatch.setenv("AURA_STORY_DIR", temp_story_dir)
    client = _rest_setup(temp_story_dir, monkeypatch)

    r = client.get("/api/story/test_export/export/jobs/nonexistent")
    assert r.status_code == 404
