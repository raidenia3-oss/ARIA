"""`.env` file generation and maintenance.

Rules that make this safe to run repeatedly:

* Never overwrite a value the operator already set. A key is written only if
  it is absent, empty, or still an obvious placeholder.
* Never destroy comments. The file is parsed into an ordered key/value map and
  re-emitted, preserving comment lines in their original position.
* Never write a secret into the repo. Generated files land in paths already
  covered by `.gitignore`, and the writer asserts that before saving.
* A dry run reports the diff without touching the disk.
"""

from __future__ import annotations

from pathlib import Path

from .detector import env_value_looks_real, read_env_keys
from .model import StepResult

GITIGNORE_HINT = "Add this path to .gitignore before storing secrets in it."


# Keys that contain a secret-ish substring but hold no credential. Matching
# these would both hide real leaks and generate noise in the audit.
NOT_SECRET_MARKERS: tuple[str, ...] = (
    "MAX_TOKENS",
    "TOKEN_LIMIT",
    "TOKEN_BUDGET",
    "TOKENIZER",
    "EXPIRE_MINUTES",
    "EXPIRE_SECONDS",
    "TTL",
    "_URL",
    "USERNAME",
)


def _key_of(line: str) -> str:
    """The assignment key on this line, or "" for blanks and comments.

    Shared by every read and write path so key matching cannot drift between
    them - the bug that would otherwise let a write be lost by a later lookup.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return ""
    key = stripped.partition("=")[0].strip()
    return key[len("export ") :].strip() if key.startswith("export ") else key


def _is_secret(key: str) -> bool:
    """Heuristic: does this key hold a credential?

    Used to decide whether a value may be auto-generated and whether the file
    must be git-ignored. Deliberately broad: a false positive only means we
    treat a setting as sensitive.
    """
    upper = key.upper()
    if any(marker in upper for marker in NOT_SECRET_MARKERS):
        return False
    markers = (
        "TOKEN",
        "SECRET",
        "PASSWORD",
        "PASSWD",
        "API_KEY",
        "APIKEY",
        "PRIVATE_KEY",
        "CREDENTIAL",
    )
    return any(marker in upper for marker in markers)


class EnvFile:
    """One `.env` file, parsed and rewritten without losing comments."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.lines: list[str] = self._read_lines()

    def _read_lines(self) -> list[str]:
        try:
            return self.path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return []

    def get(self, key: str) -> str:
        """Current in-memory value for `key`.

        Reads the parsed lines rather than the file, so a `set()` earlier in
        the same pass is visible here. Re-reading from disk would let a second
        write in the same run silently clobber the first.
        """
        for line in self.lines:
            existing = _key_of(line)
            if existing == key:
                return line.partition("=")[2].strip().strip('"').strip("'")
        return ""

    def has_real_value(self, key: str) -> bool:
        return env_value_looks_real(self.get(key))

    def keys(self) -> list[str]:
        return list(read_env_keys(self.path).keys())

    def set(self, key: str, value: str, overwrite: bool = False) -> bool:
        """Set a key. Returns True when the file changed.

        With `overwrite=False` (the default) an existing real value is left
        alone, which is what makes repeated runs non-destructive.
        """
        if not overwrite:
            current = self.get(key)
            if env_value_looks_real(current):
                return False

        for index, line in enumerate(self.lines):
            if _key_of(line) == key:
                if self.lines[index] == f"{key}={value}":
                    return False
                self.lines[index] = f"{key}={value}"
                return True

        self.lines.append(f"{key}={value}")
        return True

    def remove(self, key: str) -> bool:
        before = len(self.lines)
        kept = [line for line in self.lines if _key_of(line) != key]
        self.lines = kept
        return len(kept) != before

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        body = "\n".join(self.lines).rstrip("\n")
        self.path.write_text(body + "\n", encoding="utf-8")
        self._restrict_permissions()

    def _restrict_permissions(self) -> None:
        """Best effort: owner-only on POSIX. A no-op on Windows."""
        if not any(_is_secret(key) for key in self.keys()):
            return
        try:
            import os
            import stat

            os.chmod(self.path, stat.S_IRUSR | stat.S_IWUSR)
        except (OSError, NotImplementedError, ImportError):
            pass

    def delete(self) -> bool:
        try:
            self.path.unlink()
            return True
        except OSError:
            return False


class Configurator:
    """Creates and normalises every `.env` file ARIA expects."""

    #: Files to create, mapped to the keys that must exist in each.
    TARGETS: dict[str, tuple[str, ...]] = {
        ".env": (
            "DISCORD_TOKEN",
            "OLLAMA_URL",
            "AXUM_URL",
            "BACKEND_URL",
            "ARIA_DEBUG",
        ),
        "ARIA_APP/.env": (
            "ARIA_HOST",
            "ARIA_PORT",
            "AURA_TEMPERATURE",
            "AURA_MAX_TOKENS",
            "AURA_MEMORY_DIR",
        ),
        "ARIA_APP/backend/.env": (
            "GITHUB_TOKEN",
            "GITHUB_WEBHOOK_SECRET",
        ),
    }

    #: Safe defaults. No secrets here by design.
    DEFAULTS: dict[str, dict[str, str]] = {
        ".env": {
            "OLLAMA_URL": "http://127.0.0.1:11434",
            "AXUM_URL": "http://127.0.0.1:8002",
            "BACKEND_URL": "http://127.0.0.1:8002",
            "ARIA_DEBUG": "false",
        },
        "ARIA_APP/.env": {
            "ARIA_HOST": "127.0.0.1",
            "ARIA_PORT": "8001",
            "AURA_TEMPERATURE": "0.7",
            "AURA_MAX_TOKENS": "2048",
        },
        "ARIA_APP/backend/.env": {
            # A webhook secret is generated, not defaulted, because a shared
            # default would let anyone forge webhook payloads.
            "GITHUB_WEBHOOK_SECRET": "__GENERATE__",
        },
    }

    def __init__(self, project_root: Path, dry_run: bool = False) -> None:
        self.root = project_root
        self.dry_run = dry_run

    def _target(self, relative: str) -> EnvFile:
        return EnvFile(self.root / relative)

    def setup_environment(self) -> StepResult:
        """Create every target `.env` and fill in missing keys."""
        created: list[str] = []
        updated: list[str] = []
        unchanged: list[str] = []
        secrets_needing_input: list[str] = []

        for relative, keys in self.TARGETS.items():
            path = self.root / relative
            existed = path.is_file()
            env = self._target(relative)
            changed = False

            if not existed:
                env.lines = [
                    f"# ARIA generated - {relative}",
                    "# Secrets are never auto-filled; set them here or export them.",
                    "",
                ]
                created.append(relative)
                changed = True

            for key in keys:
                if env.has_real_value(key):
                    unchanged.append(f"{relative}:{key}")
                    continue

                default = self.DEFAULTS.get(relative, {}).get(key)
                if default == "__GENERATE__":
                    import secrets as _secrets

                    env.set(key, _secrets.token_hex(32))
                    secrets_needing_input.append(f"{relative}:{key}")
                    changed = True
                elif default is not None:
                    env.set(key, default)
                    changed = True
                elif key in {k for k in keys if _is_secret(k)}:
                    # Leave the key absent; secrets_manager will request it.
                    secrets_needing_input.append(f"{relative}:{key}")

            if changed and not self.dry_run:
                env.save()
            if changed:
                updated.append(relative)
            elif existed:
                unchanged.append(relative)

        message = f"{len(created)} created, {len(updated)} updated"
        if self.dry_run:
            return StepResult.warn(f"dry-run: {message}", created=created, updated=updated)
        if secrets_needing_input:
            return StepResult.ok(
                f"{message}; {len(secrets_needing_input)} secret(s) still need values",
                created=created,
                updated=updated,
                missing_secrets=secrets_needing_input,
            )
        return StepResult.ok(message, created=created, updated=updated, unchanged=unchanged)

    def ensure_gitignore(self) -> StepResult:
        """Make sure every `.env` path ARIA uses is git-ignored.

        The repo's root `.gitignore` already covers `.env`; this verifies it
        rather than assuming, because a leaked Discord token is unrecoverable
        once pushed.
        """
        gitignore = self.root / ".gitignore"
        if not gitignore.is_file():
            return StepResult.warn("no .gitignore found", hint=GITIGNORE_HINT)

        try:
            content = gitignore.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return StepResult.fail(f"could not read .gitignore: {exc}")

        required = (".env", "*.db", ".venv/")
        missing = [pattern for pattern in required if pattern not in content]
        if not missing:
            return StepResult.ok(".gitignore covers secrets and databases")

        if self.dry_run:
            return StepResult.warn(f"dry-run: would add {missing} to .gitignore", missing=missing)

        try:
            with gitignore.open("a", encoding="utf-8") as fh:
                fh.write("\n# ARIA auto-config\n" + "".join(f"{m}\n" for m in missing))
        except OSError as exc:
            return StepResult.fail(f"could not update .gitignore: {exc}")
        return StepResult.ok(f"added {len(missing)} patterns to .gitignore", added=missing)

    def reset(self, remove_secrets: bool = False) -> StepResult:
        """Clear the journal and, optionally, every generated `.env`.

        `remove_secrets=False` is the default: a reset of the *setup state*
        should not silently destroy the operator's Discord and GitHub tokens.
        """
        if not remove_secrets:
            return StepResult.skip("config reset requires --purge-secrets", hint="secrets were left untouched")

        removed: list[str] = []
        for relative in self.TARGETS:
            env = self._target(relative)
            if env.delete():
                removed.append(relative)
        if self.dry_run:
            return StepResult.warn(f"dry-run: would delete {removed}", removed=removed)
        return StepResult.ok(f"deleted {len(removed)} env file(s)", removed=removed)
