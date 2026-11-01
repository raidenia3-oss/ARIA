"""Gate anti-documento-huerfano.

Una guia tecnica que nadie encuentra no documenta nada: se desactualiza y sus
afirmaciones pasan a describir algo que ya no esta en el codigo. Este gate
comprueba que docs/AGENT_GUARDS.md este enlazada desde el README y que las rutas
que cita sigan existiendo.

Las citas de linea no se comprueban: cambian con cualquier edicion y el gate
terminaria odiandose. Lo que si importa es que el archivo citado exista.
"""

from __future__ import annotations

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
GUIDE = ROOT / "docs" / "AGENT_GUARDS.md"
README = ROOT / "README.md"

# Rutas que la guia cita como "verificado en ...". Si una se renombra o se mueve,
# la guia pasa a describir codigo que ya no esta ahi.
CITED_PATHS = (
    "backend/agents/tools_registry.py",
    "backend/agents/tools",
    "backend/security_manager.py",
    "backend/agents/orchestrator.py",
    "aria_video_library/indexer.py",
    "ARIA_APP/backend/skills/registry.py",
    "ai_providers.py",
)

# Gates que la guia declara implementados. Si uno se renombra o se borra, la
# tabla de estado del documento pasa a prometer una proteccion que no existe.
DECLARED_GATES = (
    "tests/gates/test_tool_rate_limit.py",
    "tests/gates/test_gate_integrity.py",
    "tests/gates/test_ai_providers_sync.py",
)


def test_guide_exists():
    assert GUIDE.is_file(), "falta docs/AGENT_GUARDS.md"


def test_guide_is_linked_from_the_readme():
    """Sin enlace, el documento no se encuentra y deja de mantenerse."""
    assert README.is_file(), "falta README.md"
    assert "docs/AGENT_GUARDS.md" in README.read_text(encoding="utf-8"), (
        "docs/AGENT_GUARDS.md no esta enlazada desde el README: quedaria huerfana"
    )


def test_readme_link_actually_resolves():
    match = re.search(r"\]\((docs/AGENT_GUARDS\.md)\)", README.read_text(encoding="utf-8"))
    assert match, "el enlace del README a la guia no tiene la forma docs/AGENT_GUARDS.md"
    assert (ROOT / match.group(1)).is_file(), "el enlace del README apunta a un archivo inexistente"


@pytest.mark.parametrize("rel", CITED_PATHS, ids=lambda p: p)
def test_every_cited_path_still_exists(rel):
    assert (ROOT / rel).exists(), (
        f"docs/AGENT_GUARDS.md cita {rel} como verificado, pero ya no existe: "
        "el documento describe codigo que se movio"
    )


@pytest.mark.parametrize("rel", DECLARED_GATES, ids=lambda p: p)
def test_every_declared_gate_exists(rel):
    assert (ROOT / rel).is_file(), (
        f"docs/AGENT_GUARDS.md declara {rel} implementado, pero el archivo no esta"
    )


def test_guide_status_table_does_not_claim_everything_is_unimplemented():
    text = GUIDE.read_text(encoding="utf-8")
    assert "Nada de esto está implementado todavía" not in text, (
        "la guia sigue diciendo que nada esta implementado, pero el documento "
        "tiene una tabla de estado con al menos un hueco cerrado"
    )
    assert "**Implementado**" in text, "la tabla de estado debe marcar lo implementado"
