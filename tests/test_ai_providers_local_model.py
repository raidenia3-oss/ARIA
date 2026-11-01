"""Gates for the local-model selection and Ollama request flags in ai_providers.py.

Two failure modes are pinned here.

1. Picking the wrong model: /api/tags mixes text and vision models into one list,
   and a naive models[0] fallback lands on granite3.2-vision:2b because "g" sorts
   before "s".

2. Forgetting the request flags. spark2_5 architectures reason by default; without
   think=false every reply arrives wrapped in <think> and takes far longer.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROVIDER_COPIES = (
    ROOT / "ai_providers.py",
    ROOT / "ARIA_APP" / "ai_providers.py",
    ROOT / "aura-v5-tauri" / "ARIA_APP" / "ai_providers.py",
    ROOT / "aura-v5-tauri-webgpu" / "ARIA_APP" / "ai_providers.py",
)

EXPECTED_MODEL = "spark25-ab"


def _load(path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(f"providers_{abs(hash(str(path)))}", path)
    assert spec and spec.loader, f"cannot import {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ap = _load(PROVIDER_COPIES[0])


def test_default_local_model_is_the_measured_best():
    # Measured on this machine: spark25-ab 7/7 (2943 MB resident), dolphin3:8b
    # 6/7 (5325 MB), spark25-q4 4/7 because it refuses the uncensored probes.
    assert ap.DEFAULT_OLLAMA_MODEL == EXPECTED_MODEL


@pytest.mark.parametrize("path", PROVIDER_COPIES, ids=lambda p: str(p.relative_to(ROOT)))
def test_every_provider_copy_agrees_on_the_default(path):
    module = _load(path)
    assert module.DEFAULT_OLLAMA_MODEL == ap.DEFAULT_OLLAMA_MODEL
    source = path.read_text(encoding="utf-8")
    assert 'os.environ.get("LOCAL_LFM_MODEL", "dolphin-2_6-phi-2' not in source
    assert "active = models[0]" not in source


@pytest.mark.parametrize(
    "models,expected",
    [
        (["granite3.2-vision:2b", "spark25-ab"], "spark25-ab"),
        (["spark25-ab", "granite3.2-vision:2b"], "spark25-ab"),
        (["granite3.2-vision:2b"], "granite3.2-vision:2b"),
        (["llava:latest", "minicpm-v:8b", "qwen2.5:3b"], "qwen2.5:3b"),
        (["qwen2.5vl:7b", "moondream:latest", "spark25-ab"], "spark25-ab"),
        (["phi4-mini", "llava-phi3:3b"], "phi4-mini"),
    ],
)
def test_text_model_fallback_never_lands_on_a_vision_model(models, expected):
    assert ap._pick_text_model(models) == expected


def test_fallback_still_returns_something_when_only_vision_is_installed():
    assert ap._pick_text_model(["granite3.2-vision:2b"]) == "granite3.2-vision:2b"


# The real /api/tags order on this machine, captured live: spark25-ab,
# spark25-q4, nomic-embed-text, dolphin3:8b, granite3.2-vision:2b.
REAL_TAG_ORDER = [
    "spark25-ab:latest",
    "spark25-q4:latest",
    "nomic-embed-text:latest",
    "dolphin3:8b",
    "granite3.2-vision:2b",
]


def test_embedding_model_is_never_picked_as_the_chat_model():
    """nomic-embed-text sorts between spark25-ab and dolphin3:8b in /api/tags."""
    assert ap._pick_text_model(REAL_TAG_ORDER) == "spark25-ab:latest"
    assert ap._pick_text_model(["nomic-embed-text:latest", "qwen2.5:3b"]) == "qwen2.5:3b"


@pytest.mark.parametrize(
    "name",
    ["nomic-embed-text:latest", "mxbai-embed-large", "bge-m3", "e5-base-v2", "gte-small", "all-MiniLM-L6-v2"],
)
def test_embedding_markers_are_recognised(name):
    assert ap._pick_text_model([name, "qwen2.5:3b"]) == "qwen2.5:3b"


def test_censored_build_loses_to_the_abliterated_one_when_the_default_is_missing():
    """spark25-q4 refused all three uncensored probes; it must not win a fallback."""
    without_default = [m for m in REAL_TAG_ORDER if m != "spark25-ab:latest"]
    assert ap._pick_text_model(without_default) == "dolphin3:8b"


def test_only_censored_and_embeddings_installed_still_returns_a_text_model():
    chosen = ap._pick_text_model(["spark25-q4:latest", "nomic-embed-text:latest"])
    assert chosen == "spark25-q4:latest", "sin alternativa hay que devolver algo, no romperse"


def test_dolphin3_still_usable_as_the_uncensored_fallback():
    assert ap._pick_text_model(["spark25-q4:latest", "dolphin3:8b"]) == "dolphin3:8b"


def test_manager_reports_the_active_local_model():
    manager = ap.AIProviderManager()
    assert manager.providers["ollama"]["model"] == EXPECTED_MODEL


def test_vision_markers_do_not_match_ordinary_text_model_names():
    for name in ("spark25-ab", "dolphin3:8b", "qwen2.5:3b-instruct", "llama3.2:3b", "mistral:7b"):
        assert ap._pick_text_model([name]) == name


def test_chosen_model_is_not_mistaken_for_a_vision_model():
    lowered = EXPECTED_MODEL.lower()
    assert not any(m in lowered for m in ap.VISION_MODEL_MARKERS)


def test_flags_disable_thinking_and_release_ram_by_default(monkeypatch):
    monkeypatch.delenv("OLLAMA_THINK", raising=False)
    monkeypatch.delenv("OLLAMA_KEEP_ALIVE", raising=False)
    flags = ap._ollama_request_flags()
    assert flags["think"] is False
    assert flags["keep_alive"] == 0


def test_thinking_can_be_turned_back_on(monkeypatch):
    for value in ("1", "true", "yes"):
        monkeypatch.setenv("OLLAMA_THINK", value)
        assert ap._ollama_request_flags()["think"] is True
    for value in ("0", "false", "no", ""):
        monkeypatch.setenv("OLLAMA_THINK", value)
        assert ap._ollama_request_flags()["think"] is False


def test_keep_alive_can_be_warmed_and_bad_values_are_ignored(monkeypatch):
    monkeypatch.setenv("OLLAMA_KEEP_ALIVE", "300")
    assert ap._ollama_request_flags()["keep_alive"] == 300
    monkeypatch.setenv("OLLAMA_KEEP_ALIVE", "-1")
    assert "keep_alive" not in ap._ollama_request_flags()
    monkeypatch.setenv("OLLAMA_KEEP_ALIVE", "")
    assert "keep_alive" not in ap._ollama_request_flags()
    monkeypatch.setenv("OLLAMA_KEEP_ALIVE", "not-a-number")
    assert "keep_alive" not in ap._ollama_request_flags()


def test_flags_are_json_serialisable(monkeypatch):
    monkeypatch.delenv("OLLAMA_THINK", raising=False)
    monkeypatch.delenv("OLLAMA_KEEP_ALIVE", raising=False)
    assert json.loads(json.dumps(ap._ollama_request_flags()))["think"] is False


@pytest.mark.parametrize("path", PROVIDER_COPIES, ids=lambda p: str(p.relative_to(ROOT)))
def test_both_ollama_call_sites_send_the_flags(path):
    source = path.read_text(encoding="utf-8")
    assert "_ollama_request_flags()" in source
    # chat_stream_ollama and _chat_ollama each build their own body.
    assert source.count('**_ollama_request_flags()') == 2


@pytest.mark.parametrize("path", PROVIDER_COPIES, ids=lambda p: str(p.relative_to(ROOT)))
def test_install_hint_names_the_model_actually_used(path):
    source = path.read_text(encoding="utf-8")
    hint = 'Instalá Ollama con `hf download'
    assert hint in source
    assert EXPECTED_MODEL in source
    # stale advice: the GGUF has to be imported with ollama create, so a
    # "ollama pull" hint would send users to a tag that does not exist.
    assert "ollama pull dolphin3:8b" not in source
    assert "ollama create %s" % EXPECTED_MODEL in source
