# ARIA — Zero-Touch Setup

One command configures ARIA completely: dependencies, environment, secrets
audit, database schema, Rust crates, and end-to-end validation.

```bash
python aria_setup.py --auto-configure
```

No prompts. No manual steps. The run either finishes operational or tells you
exactly which piece is missing and how to get it.

---

## Quick Start

```bash
git clone https://github.com/raidenia3-oss/ARIA
cd ARIA

python -m venv .venv
.venv/Scripts/python.exe -m pip install --upgrade pip

.venv/Scripts/python.exe aria_setup.py --auto-configure
.venv/Scripts/python.exe aria_autonomous.py
```

On a configured machine the first run takes a few minutes (it installs
dependencies and builds Rust crates). Every run after that finishes in seconds.

---

## Commands

| Command | What it does |
|---|---|
| `python aria_setup.py --auto-configure` | Full pipeline: detect → install → configure → initialise → validate |
| `python aria_setup.py` | Same as above (no flag needed) |
| `python aria_setup.py --install-only` | Dependencies only; skips validation |
| `python aria_setup.py --validate` | Run every health check, change nothing |
| `python aria_setup.py --diagnose` | Explain current state: what ran, what's missing |
| `python aria_setup.py --reset` | Clear setup state (secrets are kept) |
| `python aria_setup.py --reset --purge-secrets` | Clear state **and** delete the env files |
| `python aria_setup.py --rollback` | Undo the most recent recorded changes |
| `python aria_setup.py --set-secret NAME VALUE` | Store one credential |
| `python aria_setup.py --list-checks` | Print the validation contract |
| `python aria_setup.py --auto-configure --dry-run` | Show what would change, write nothing |
| `python aria_setup.py --validate --json` | Machine-readable report |

Exit codes: `0` ready, `1` incomplete, `2` bad usage, `130` interrupted.

---

## Tiers

Work is grouped so a failure is never ambiguous about how much it matters.

| Tier | Contents | On failure |
|---|---|---|
| `core` | Python packages, directories, schema, `.env` files, `.gitignore` | Stops the run |
| `runtime` | Requirements files, Rust build, subsystem databases | Warns, continues |
| `optional` | Heavy native wheels, secret requests, credential audit | Warns, continues |

The default run is `core` + `runtime`. Add `--tier optional` for the large
native wheels (PySide6, aiortc, opencv) that ARIA does not need to run.

---

## Design

### Idempotent

Every step carries a **fingerprint** derived from the inputs it actually
depends on — the content hash of `requirements.txt`, the key set of a `.env`
file, the schema of the database. A step whose fingerprint is unchanged and
which previously succeeded is skipped, so a second run costs seconds.

A failure that cannot fix itself (an unavailable package pin, a source file
with broken encoding) is recorded as **permanent** and is not repeated either,
but its original warning is still shown so it never silently disappears.

### Declarative

The pipeline is a list of `(name, tier, fingerprint, action)` tuples in
`orchestrator.py:build_steps()`. `--validate`, `--diagnose` and `--rollback`
all reuse that structure, so there is one code path, not three that drift.

### Non-blocking

Only a `core` failure stops the run. Optional steps degrade to a warning with
the reason and the fix. The system is designed to come up in a degraded state
rather than not at all.

### Honest

A check that cannot run reports `SKIP` with the reason — never `OK`. A backend
that is down is a configuration state, not a broken install, and the report
says so.

### Secret-safe

- Secret **values** are never logged, printed, or written to a report. The
  audit reports presence only.
- `.env` writes never clobber a value you set; only missing keys and obvious
  placeholders (`your-api-key`, `changeme`, `<placeholder>`) are filled.
- Comments and ordering in an existing `.env` are preserved.
- The credential check **fails** the run if a tracked file contains a live
  credential, because that is already in git history and `.gitignore` cannot
  help.

---

## Architecture

```
aria_setup.py              CLI entry point
aria_autoconfig/
├── model.py               Status, Tier, StepResult, StepReport, Environment
├── journal.py             Idempotency, rollback bookkeeping, audit trail
├── detector.py            OS / toolchain / service probing (read-only)
├── installer.py           Python and Rust dependency tiers
├── configurator.py        .env creation and .gitignore hardening
├── secrets_manager.py     Secret audit, out-of-band requests, leak detection
├── initializer.py         Directory layout and SQLite schema
├── validator.py           The declared check list
├── selfheal.py            Retry classification and repair actions
├── orchestrator.py        Pipeline execution and reporting
└── report.py              Terminal and JSON output
```

State lives in two files, both inside `.aura/`:

- `setup_state.json` — per-step fingerprints, outcomes, undo records
- `setup_report.json` — the last run's full report

---

## Self-configuration

`aria_autonomous.py` calls `ensure_configured()` before its first cycle, so a
missing dependency is repaired rather than crashing the loop. A failure there
is reported and the loop retries on its next pass instead of exiting.

```python
from aria_autoconfig import ensure_configured

if not ensure_configured():
    print("degraded mode")
```

---

## What setup will not do

Deliberate limits, each of which would otherwise be an invisible surprise:

- **It does not install system toolchains.** A missing Rust, Python or Node
  install is a machine-level change; the step prints the exact command instead.
- **It does not invent secrets.** A missing credential produces a recorded
  request plus the URL to obtain it, and the run continues.
- **It does not rewrite dependency pins.** An unavailable version is reported
  with the conflicting pins listed. Auto-fixing would silently change what
  ARIA runs against.
- **It does not uninstall packages.** `--rollback` reports that a pip install
  is not automatically reversible instead of pretending it was undone.

---

## Troubleshooting

```bash
python aria_setup.py --diagnose      # what ran, what is pending, what is down
python aria_setup.py --validate      # just the checks
python aria_setup.py --reset         # force a clean rebuild
```

The report ends with the exact next action for a failed run, so you rarely
need to read further.
