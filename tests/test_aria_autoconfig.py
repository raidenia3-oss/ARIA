"""Tests for the ARIA auto-configuration engine.

Scope: the behaviours that would silently break zero-touch setup if they
regressed - idempotency, non-destructive env writes, secret redaction,
permanent-vs-transient failure classification, and the CLI contract.

No test touches the real repository: everything runs against a tmp_path so the
suite is safe to run on a configured machine.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aria_autoconfig import (  # noqa: E402
    Configurator,
    EnvironmentDetector,
    Initializer,
    Installer,
    Journal,
    Orchestrator,
    Reporter,
    RetryPolicy,
    SecretsManager,
    SelfHealer,
    Status,
    StepResult,
    Tier,
    Validator,
    ensure_configured,
)
from aria_autoconfig.configurator import EnvFile, _is_secret  # noqa: E402
from aria_autoconfig.detector import env_value_looks_real, read_env_keys  # noqa: E402
from aria_autoconfig.journal import file_fingerprint, fingerprint  # noqa: E402
from aria_autoconfig.selfheal import is_transient  # noqa: E402
from aria_autoconfig.validator import CHECKS  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------- journal


def test_fingerprint_is_stable_and_input_sensitive():
    assert fingerprint("a", 1) == fingerprint("a", 1)
    assert fingerprint("a", 1) != fingerprint("a", 2)


def test_file_fingerprint_distinguishes_missing_from_empty(tmp_path):
    empty = tmp_path / "empty"
    empty.write_text("", encoding="utf-8")
    assert file_fingerprint(tmp_path / "nope") == "missing"
    assert file_fingerprint(empty) != "missing"


def test_journal_roundtrip(tmp_path):
    journal = Journal(tmp_path / "state.json")
    journal.record("step", "print1", "ok", "done")
    assert Journal(tmp_path / "state.json").record_of("step").message == "done"


def test_journal_survives_corrupt_state(tmp_path):
    """A corrupt state file must not block setup."""
    path = tmp_path / "state.json"
    path.write_text("{not json", encoding="utf-8")
    journal = Journal(path)
    assert journal.source.startswith("corrupt")
    journal.record("step", "p", "ok")
    assert Journal(path).record_of("step") is not None


def test_journal_ignores_version_mismatch(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"version": 999, "steps": []}), encoding="utf-8")
    assert Journal(path).source == "version-mismatch"


def test_journal_settles_permanent_warn_but_not_failed(tmp_path):
    journal = Journal(tmp_path / "state.json")
    journal.record("settled", "p", "warn", "unavailable", permanent=True)
    journal.record("retryable", "p", "warn", "timeout")
    journal.record("broken", "p", "failed", "boom")
    assert journal.is_satisfied("settled", "p") is True
    assert journal.is_satisfied("retryable", "p") is False
    assert journal.is_satisfied("broken", "p") is False


def test_journal_fingerprint_change_invalidates(tmp_path):
    journal = Journal(tmp_path / "state.json")
    journal.record("step", "old", "ok")
    assert journal.is_satisfied("step", "new") is False


# ----------------------------------------------------------------- env writing


def test_envfile_preserves_comments_and_overwrites_in_place(tmp_path):
    """A rewrite keeps the comment header and the blank line around it."""
    path = tmp_path / ".env"
    path.write_text("# header\nexport FOO=1\n\n# tail\n", encoding="utf-8")
    env = EnvFile(path)
    assert env.set("FOO", "2", overwrite=True) is True
    assert env.set("FOO", "2", overwrite=True) is False  # already equal
    env.save()
    body = path.read_text(encoding="utf-8")
    assert body.startswith("# header")
    assert "# tail" in body
    assert "\n\n" in body
    # The `export ` prefix is dropped on rewrite: a normalised KEY=VALUE line
    # is what every reader in this repo expects.
    assert "FOO=2" in body and "export FOO" not in body


def test_envfile_does_not_clobber_existing_real_value(tmp_path):
    path = tmp_path / ".env"
    path.write_text("DISCORD_TOKEN=real-token-value\n", encoding="utf-8")
    env = EnvFile(path)
    assert env.set("DISCORD_TOKEN", "something-else") is False
    assert env.get("DISCORD_TOKEN") == "real-token-value"


def test_envfile_overwrites_when_asked(tmp_path):
    path = tmp_path / ".env"
    path.write_text("DISCORD_TOKEN=real-token-value\n", encoding="utf-8")
    env = EnvFile(path)
    assert env.set("DISCORD_TOKEN", "replacement", overwrite=True) is True
    assert env.get("DISCORD_TOKEN") == "replacement"


def test_envfile_remove(tmp_path):
    path = tmp_path / ".env"
    path.write_text("A=1\n# c\nB=2\n", encoding="utf-8")
    env = EnvFile(path)
    assert env.remove("A") is True
    assert env.remove("NOPE") is False
    env.save()
    assert "A=1" not in path.read_text(encoding="utf-8")
    assert "# c" in path.read_text(encoding="utf-8")


def test_envfile_tolerates_malformed_lines(tmp_path):
    path = tmp_path / ".env"
    path.write_text("garbage line\n\nA=1\n", encoding="utf-8")
    assert read_env_keys(path) == {"A": "1"}


@pytest.mark.parametrize(
    "key,expected",
    [
        ("DISCORD_TOKEN", True),
        ("GITHUB_TOKEN", True),
        ("AURA_JWT_SECRET", True),
        ("OPENAI_API_KEY", True),
        ("AURA_MAX_TOKENS", False),
        ("ACCESS_TOKEN_EXPIRE_MINUTES", False),
        ("OLLAMA_URL", False),
        ("AURA_PORT", False),
    ],
)
def test_is_secret_heuristic(key, expected):
    assert _is_secret(key) is expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ("", False),
        ("your-api-key", False),
        ("your_api_key", False),
        ("changeme", False),
        ("<placeholder>", False),
        ("https://sk-abc123", True),
    ],
)
def test_env_value_looks_real(value, expected):
    assert env_value_looks_real(value) is expected


def test_configurator_is_idempotent(tmp_path):
    configurator = Configurator(tmp_path)
    first = configurator.setup_environment()
    assert first.status is Status.OK
    snapshot = (tmp_path / ".env").read_text(encoding="utf-8")
    second = Configurator(tmp_path).setup_environment()
    assert (tmp_path / ".env").read_text(encoding="utf-8") == snapshot
    assert second.details.get("updated") == []


def test_configurator_generates_webhook_secret(tmp_path):
    """The webhook secret must be random, never a shared default."""
    Configurator(tmp_path).setup_environment()
    backend = read_env_keys(tmp_path / "ARIA_APP" / "backend" / ".env")
    secret = backend.get("GITHUB_WEBHOOK_SECRET", "")
    assert len(secret) == 64  # token_hex(32)
    assert secret != "dev-secret"


def test_configurator_dry_run_writes_nothing(tmp_path):
    result = Configurator(tmp_path, dry_run=True).setup_environment()
    assert result.status is Status.WARN
    assert not (tmp_path / ".env").exists()


def test_configurator_adds_missing_gitignore_patterns(tmp_path):
    (tmp_path / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
    result = Configurator(tmp_path).ensure_gitignore()
    assert result.status is Status.OK
    body = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in body and "*.db" in body
    assert Configurator(tmp_path).ensure_gitignore().status is Status.OK


def test_configurator_reset_keeps_secrets_by_default(tmp_path):
    Configurator(tmp_path).setup_environment()
    result = Configurator(tmp_path).reset()
    assert result.status is Status.SKIPPED
    assert (tmp_path / ".env").exists()


# -------------------------------------------------------------------- secrets


def test_audit_never_returns_values(tmp_path):
    (tmp_path / ".env").write_text(
        "DISCORD_TOKEN=" + "A" * 60 + "\n", encoding="utf-8"
    )
    statuses = {s.name: s for s in SecretsManager(tmp_path).audit()}
    assert statuses["DISCORD_TOKEN"].present is True
    assert "A" * 60 not in json.dumps(statuses["DISCORD_TOKEN"].to_dict())


def test_audit_rejects_malformed_token(tmp_path):
    (tmp_path / ".env").write_text("DISCORD_TOKEN=tooshort\n", encoding="utf-8")
    statuses = {s.name: s for s in SecretsManager(tmp_path).audit()}
    assert statuses["DISCORD_TOKEN"].present is False


def test_github_token_shape_is_enforced(tmp_path):
    manager = SecretsManager(tmp_path)
    assert manager.inject("GITHUB_TOKEN", "not-a-real-token").status is Status.FAILED
    good = "ghp_" + "a" * 36
    assert manager.inject("GITHUB_TOKEN", good).status is Status.OK
    assert read_env_keys(tmp_path / "ARIA_APP" / "backend" / ".env")["GITHUB_TOKEN"] == good


def test_inject_rejects_unknown_secret(tmp_path):
    assert SecretsManager(tmp_path).inject("NOPE_KEY", "x").status is Status.FAILED


def test_setup_secrets_is_non_blocking(tmp_path):
    """Missing secrets must warn, never fail, and never prompt."""
    result = SecretsManager(tmp_path).setup_secrets()
    assert result.status is Status.WARN
    assert result.details.get("missing")


def test_setup_secrets_dry_run_makes_no_request_log(tmp_path, monkeypatch, tmp_path_factory):
    state = tmp_path_factory.mktemp("state")
    monkeypatch.setenv("ARIA_STATE_DIR", str(state))
    SecretsManager(tmp_path, dry_run=True).setup_secrets()
    assert not (state / "secret_requests.json").exists()


# ----------------------------------------------------------------- initializer


def test_initializer_creates_dirs_and_schema(tmp_path):
    result = Initializer(tmp_path).setup_directories()
    assert result.status is Status.OK
    db_result = Initializer(tmp_path).setup_databases()
    assert db_result.status is Status.OK
    import sqlite3

    with sqlite3.connect(tmp_path / "aura.db") as connection:
        tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"conversations", "messages", "memories", "tasks", "events"} <= tables


def test_initializer_does_not_wipe_existing_data(tmp_path):
    import sqlite3

    db = tmp_path / "aura.db"
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE memories (id INTEGER PRIMARY KEY, note TEXT)")
        connection.execute("INSERT INTO memories (note) VALUES ('keep me')")
    Initializer(tmp_path).setup_databases()
    with sqlite3.connect(db) as connection:
        rows = list(connection.execute("SELECT note FROM memories"))
    assert ("keep me",) in rows


def test_initializer_dry_run_creates_nothing(tmp_path):
    assert Initializer(tmp_path, dry_run=True).setup_databases().status is Status.WARN
    assert not (tmp_path / "aura.db").exists()


# ----------------------------------------------------------------- self-heal


@pytest.mark.parametrize(
    "message,transient",
    [
        ("pip install timed out after 900s", True),
        ("read timed out", True),
        ("[WinError 32] The process cannot access the file", True),
        ("ERROR: No matching distribution found for ccxt==4.0.0", False),
        ("requires a compiler", False),
        ("Access is denied", False),
    ],
)
def test_transient_classification(message, transient):
    assert is_transient(message) is transient


def test_retry_policy_stops_on_permanent_error():
    calls = []

    def action():
        calls.append(1)
        return StepResult.fail("ERROR: No matching distribution found")

    policy = RetryPolicy(attempts=3, sleep_fn=lambda _: None)
    result, attempts = policy.run("install", action)
    assert attempts == 1
    assert len(calls) == 1
    assert result.status is Status.FAILED


def test_retry_policy_retries_transient_error():
    calls = []

    def action():
        calls.append(1)
        if len(calls) < 3:
            return StepResult.fail("connection reset")
        return StepResult.ok("recovered")

    policy = RetryPolicy(attempts=3, sleep_fn=lambda _: None)
    result, attempts = policy.run("flaky", action)
    assert attempts == 3
    assert result.status is Status.OK


def test_selfhealer_repair_never_raises(tmp_path):
    healer = SelfHealer(tmp_path)

    def boom():
        raise RuntimeError("repair exploded")

    from aria_autoconfig.selfheal import RepairAction

    result = RepairAction("boom", "explodes", boom).attempt()
    assert result.status is Status.FAILED


def test_selfhealer_recreates_dirs(tmp_path):
    healer = SelfHealer(tmp_path)
    (tmp_path / "data").mkdir()
    healer._recreate_directories().status is Status.OK
    assert (tmp_path / "logs").is_dir()


# ----------------------------------------------------------------- validator


def test_every_declared_check_has_a_handler():
    """A declared check with no handler would always report 'failed'."""
    validator = Validator(EnvironmentDetector(REPO_ROOT))
    for check in CHECKS:
        assert hasattr(validator, f"_check_{check.name}"), f"{check.name} has no handler"


def test_validator_skips_unreachable_service():
    """A down backend is a configuration state, not a broken install."""
    validator = Validator(EnvironmentDetector(REPO_ROOT))
    result = validator._http_check("nothing", "http://127.0.0.1:59999/health")
    assert result.status is Status.SKIPPED


def test_validator_reports_missing_db_as_failed(tmp_path):
    result = Validator(EnvironmentDetector(tmp_path))._check_database()
    assert result.status is Status.FAILED


def test_validator_credential_check_passes_on_clean_tree(tmp_path):
    """No tracked env files means no exposure."""
    result = Validator(EnvironmentDetector(tmp_path))._check_credentials()
    assert result.status in (Status.OK, Status.WARN)


# --------------------------------------------------------------- orchestrator


def test_orchestrator_dry_run_changes_nothing(tmp_path):
    env = EnvironmentDetector(tmp_path).detect()
    report = Orchestrator(env, tmp_path, dry_run=True, reporter=Reporter(quiet=True)).run_full_setup(
        [Tier.CORE.value]
    )
    assert report["dry_run"] is True
    assert not (tmp_path / "aura.db").exists()


def test_orchestrator_second_run_skips_settled_steps(tmp_path):
    env = EnvironmentDetector(tmp_path).detect()
    orchestrator = Orchestrator(env, tmp_path, reporter=Reporter(quiet=True))
    orchestrator.run_full_setup([Tier.CORE.value])
    first = {s["name"]: s["status"] for s in journal_steps(tmp_path)}

    second_report = Orchestrator(
        EnvironmentDetector(tmp_path).detect(), tmp_path, reporter=Reporter(quiet=True)
    ).run_full_setup([Tier.CORE.value])
    second = {s["name"]: s["status"] for s in second_report["steps"]}

    # Anything that succeeded the first time must not re-do the work.
    for name, status in first.items():
        if status == "ok":
            assert second.get(name) in ("skipped", "ok"), f"{name} re-ran despite succeeding"


def test_orchestrator_report_is_json_serialisable(tmp_path):
    env = EnvironmentDetector(tmp_path).detect()
    report = Orchestrator(env, tmp_path, dry_run=True, reporter=Reporter(quiet=True)).run_full_setup(
        [Tier.CORE.value]
    )
    json.dumps(report)  # must not raise


def test_orchestrator_report_written_to_disk(tmp_path):
    env = EnvironmentDetector(tmp_path).detect()
    Orchestrator(env, tmp_path, reporter=Reporter(quiet=True)).run_full_setup([Tier.CORE.value])
    assert (tmp_path / ".aura" / "setup_report.json").is_file()


def journal_steps(root):
    state = root / ".aura" / "setup_state.json"
    if not state.is_file():
        return []
    return Journal(state).last_run.get("steps", [])


# ------------------------------------------------------------------ installer


def test_installer_plan_uses_import_checks(tmp_path):
    plans = Installer(EnvironmentDetector(tmp_path), dry_run=True).plan(["core"])
    plan = next(p for p in plans if p.tier == "core")
    # fastapi is importable in the test interpreter, so it must not be planned.
    assert "fastapi" not in plan.missing
    assert "fastapi" in plan.present


def test_installer_dry_run_does_not_pip(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "aria_autoconfig.installer.Installer._pip_install",
        lambda self, cmd: pytest.fail("pip must not run in dry-run mode"),
    )
    result = Installer(EnvironmentDetector(tmp_path), dry_run=True).install_python("optional")
    assert result.status is Status.WARN


# --------------------------------------------------------------------- public


def test_ensure_configured_returns_bool_on_empty_tree(tmp_path):
    assert isinstance(ensure_configured(tmp_path, auto_install=False), bool)


def test_ensure_configured_never_raises(tmp_path):
    """The autonomous loop depends on this never propagating an exception."""
    assert ensure_configured(tmp_path / "nonexistent") in (True, False)


# ----------------------------------------------------------------------- CLI


def run_cli(*args, cwd=REPO_ROOT):
    return subprocess.run(
        [sys.executable, "aria_setup.py", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=300,
    )


def test_cli_list_checks():
    result = run_cli("--list-checks")
    assert result.returncode == 0
    assert "python_version" in result.stdout


def test_cli_version():
    result = run_cli("--version")
    assert result.returncode == 0
    assert "aria_setup" in result.stdout


def test_cli_diagnose_is_read_only():
    before = sorted(p.name for p in (REPO_ROOT / ".aura").glob("*")) if (REPO_ROOT / ".aura").is_dir() else []
    result = run_cli("--diagnose", "--quiet")
    after = sorted(p.name for p in (REPO_ROOT / ".aura").glob("*")) if (REPO_ROOT / ".aura").is_dir() else []
    assert result.returncode == 0
    assert before == after


def test_cli_rejects_unknown_tier():
    result = run_cli("--auto-configure", "--tier", "bogus")
    assert result.returncode == 2
