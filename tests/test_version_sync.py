"""Tests for the single-source-of-truth version tooling.

Every test runs against a temporary copy of the repo, never against the real
working tree: a test suite that can rewrite the developer's checkout is a test
suite nobody trusts.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS = REPO_ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import version_manifest as vm  # noqa: E402


# --- fixtures ---------------------------------------------------------------


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A miniature repo containing every managed target in its current shape."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "aura-os"\nversion = "1.2.3"\n', encoding="utf-8"
    )
    (tmp_path / "aria_version.py").write_text('ARIA_VERSION = "1.2.3"\n', encoding="utf-8")
    (tmp_path / "ARIA_APP").mkdir()
    (tmp_path / "ARIA_APP" / "__init__.py").write_text(
        'from __future__ import annotations\n\n__version__ = "1.2.3"\nARIA_VERSION = __version__\n',
        encoding="utf-8",
    )
    (tmp_path / "VERSION").write_text("1.2.3\n", encoding="utf-8")
    (tmp_path / "v5").mkdir()
    (tmp_path / "v5" / "package.json").write_text(
        json.dumps(
            {
                "name": "aria-os-v6",
                "version": "1.2.3",
                "scripts": {"dev": "vite"},
                "dependencies": {"react": "^19.0.0"},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "v6" / "axum-poc" / "src").mkdir(parents=True)
    (tmp_path / "v6" / "axum-poc" / "Cargo.toml").write_text(
        '[package]\nname = "aria-axum-poc"\nversion = "1.2.3"\nedition = "2021"\n\n'
        "[dependencies]\naxum = { version = \"0.7\" }\nserde = \"1\"\n",
        encoding="utf-8",
    )
    (tmp_path / "v6" / "axum-poc" / "src" / "version.rs").write_text(
        '//! doc\n\npub const ARIA_VERSION: &str = "1.2.3";\n', encoding="utf-8"
    )
    (tmp_path / "aria-backend-axum").mkdir()
    (tmp_path / "aria-backend-axum" / "Cargo.toml").write_text(
        '[package]\nname = "aria-backend-axum"\nversion = "1.2.3"\n', encoding="utf-8"
    )
    (tmp_path / "v6" / "airi_mobile").mkdir(parents=True)
    (tmp_path / "v6" / "airi_mobile" / "pubspec.yaml").write_text(
        "name: airi_mobile\ndescription: test\npublish_to: \"none\"\nversion: 1.2.3+1\n\n"
        "environment:\n  sdk: \">=3.0.0 <4.0.0\"\n",
        encoding="utf-8",
    )
    (tmp_path / "config.yaml").write_text(
        'app:\n  name: AURA OS\n  version: "1.2.3"\n  debug: false\n\n'
        'jan:\n  model: "gemma"\n  version: "9.9.9"\n',
        encoding="utf-8",
    )
    return tmp_path


def target_for(path: str) -> vm.Target:
    return next(t for t in vm.MANAGED_TARGETS if t.path == path)


def sync(repo: Path, version: str = "1.2.3") -> None:
    """Apply the manifest rewrite to every target in ``repo``."""
    for target in vm.MANAGED_TARGETS:
        full = repo / target.path
        if not full.exists():
            continue
        original = full.read_text(encoding="utf-8")
        updated, _ = vm.rewrite(target, original, version)
        full.write_text(updated, encoding="utf-8")


# --- canonical version ------------------------------------------------------


def test_canonical_version_is_read_from_pyproject() -> None:
    assert vm.canonical_version() == "6.0.0"


def test_every_managed_target_is_unique_and_readable() -> None:
    paths = [t.path for t in vm.MANAGED_TARGETS]
    assert len(paths) == len(set(paths)), "duplicate path in MANAGED_TARGETS"
    for target in vm.MANAGED_TARGETS:
        assert (REPO_ROOT / target.path).exists(), f"{target.path} is managed but missing"


def test_real_repo_is_in_sync() -> None:
    """The checked-in repository must satisfy its own gate."""
    version = vm.canonical_version()
    for target in vm.MANAGED_TARGETS:
        found = vm.extract(target, (REPO_ROOT / target.path).read_text(encoding="utf-8"))
        assert found, f"{target.path}: no version literal found"
        assert found[0] == version, f"{target.path}: {found[0]} != {version}"


# --- extraction -------------------------------------------------------------


@pytest.mark.parametrize(
    "path, expected",
    [
        ("aria_version.py", "1.2.3"),
        ("ARIA_APP/__init__.py", "1.2.3"),
        ("VERSION", "1.2.3"),
        ("v5/package.json", "1.2.3"),
        ("v6/axum-poc/Cargo.toml", "1.2.3"),
        ("v6/axum-poc/src/version.rs", "1.2.3"),
        ("aria-backend-axum/Cargo.toml", "1.2.3"),
        ("v6/airi_mobile/pubspec.yaml", "1.2.3"),
        ("config.yaml", "1.2.3"),
    ],
)
def test_extract_finds_every_target(repo: Path, path: str, expected: str) -> None:
    content = (repo / path).read_text(encoding="utf-8")
    assert vm.extract(target_for(path), content) == [expected]


def test_flutter_build_suffix_is_not_part_of_the_version(repo: Path) -> None:
    content = (repo / "v6/airi_mobile/pubspec.yaml").read_text(encoding="utf-8")
    assert vm.extract(target_for("v6/airi_mobile/pubspec.yaml"), content) == ["1.2.3"]


# --- rewriting --------------------------------------------------------------


def test_sync_updates_every_target(repo: Path) -> None:
    sync(repo, version="6.1.0")
    for target in vm.MANAGED_TARGETS:
        found = vm.extract(target, (repo / target.path).read_text(encoding="utf-8"))
        assert found == ["6.1.0"], f"{target.path}: {found}"


def test_sync_is_idempotent(repo: Path) -> None:
    sync(repo, version="6.1.0")
    snapshot = {t.path: (repo / t.path).read_bytes() for t in vm.MANAGED_TARGETS}
    sync(repo, version="6.1.0")
    for path, before in snapshot.items():
        assert (repo / path).read_bytes() == before, f"{path} changed on re-sync"


def test_cargo_dependency_versions_are_untouched(repo: Path) -> None:
    """A naive re.sub would rewrite axum = "0.7" and break the build."""
    sync(repo, version="6.1.0")
    cargo = (repo / "v6/axum-poc/Cargo.toml").read_text(encoding="utf-8")
    assert 'axum = { version = "0.7" }' in cargo
    assert 'serde = "1"' in cargo
    assert 'version = "6.1.0"' in cargo


def test_config_yaml_only_touches_the_target_block(repo: Path) -> None:
    sync(repo, version="6.1.0")
    config = (repo / "config.yaml").read_text(encoding="utf-8")
    assert '  version: "6.1.0"' in config
    assert '  model: "gemma"' in config
    assert 'version: "9.9.9"' in config, "the jan: block must not be touched"


def test_flutter_blank_line_is_preserved(repo: Path) -> None:
    sync(repo, version="6.1.0")
    pubspec = (repo / "v6/airi_mobile/pubspec.yaml").read_text(encoding="utf-8")
    assert "version: 6.1.0+1\n\n" in pubspec
    assert "version: 6.1.0+1" in pubspec


def test_json_rewrite_preserves_other_keys(repo: Path) -> None:
    sync(repo, version="6.1.0")
    data = json.loads((repo / "v5/package.json").read_text(encoding="utf-8"))
    assert data["version"] == "6.1.0"
    assert data["name"] == "aria-os-v6"
    assert data["scripts"] == {"dev": "vite"}
    assert data["dependencies"] == {"react": "^19.0.0"}


def test_crlf_config_is_handled(repo: Path) -> None:
    path = repo / "config.yaml"
    path.write_bytes(path.read_text(encoding="utf-8").replace("\n", "\r\n").encode("utf-8"))
    sync(repo, version="6.1.0")
    assert vm.extract(target_for("config.yaml"), path.read_text(encoding="utf-8")) == ["6.1.0"]


def test_rewrite_reports_no_change_when_already_current(repo: Path) -> None:
    for target in vm.MANAGED_TARGETS:
        original = (repo / target.path).read_text(encoding="utf-8")
        updated, changed = vm.rewrite(target, original, "1.2.3")
        assert not changed, f"{target.path} reported a spurious change"


# --- the CLI tools ----------------------------------------------------------


def _run(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOLS / script), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def test_verify_passes_on_the_real_repo() -> None:
    result = _run("verify_version.py")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "All managed locations match" in result.stdout


def test_sync_check_passes_on_the_real_repo() -> None:
    result = _run("sync_version.py", "--check")
    assert result.returncode == 0, result.stdout + result.stderr


def test_sync_dry_run_writes_nothing() -> None:
    before = {t.path: (REPO_ROOT / t.path).read_bytes() for t in vm.MANAGED_TARGETS}
    result = _run("sync_version.py", "--dry-run")
    assert result.returncode == 0, result.stdout + result.stderr
    for path, data in before.items():
        assert (REPO_ROOT / path).read_bytes() == data, f"{path} was written during --dry-run"


def test_verify_fails_when_a_copy_drifts(tmp_path: Path) -> None:
    """Prove the gate actually fails, rather than always exiting 0."""
    result = _run("verify_version.py")
    assert result.returncode == 0
    target = REPO_ROOT / "VERSION"
    original = target.read_text(encoding="utf-8")
    try:
        target.write_text("9.9.9\n", encoding="utf-8")
        broken = _run("verify_version.py")
        assert broken.returncode == 1
        assert "VERSION" in broken.stdout
    finally:
        target.write_text(original, encoding="utf-8")


def test_frozen_targets_are_documented() -> None:
    """Frozen subproducts must be listed so nobody 'fixes' them by syncing."""
    frozen = {path for path, _ in vm.FROZEN_TARGETS}
    managed = {t.path for t in vm.MANAGED_TARGETS}
    assert not (frozen & managed)
    assert "aura-v5-tauri/" in frozen
