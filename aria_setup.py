#!/usr/bin/env python3
"""ARIA zero-touch setup.

One command configures the whole system:

    python aria_setup.py --auto-configure

Every flag is a subset of the full run, so there is exactly one code path:

    --auto-configure   detect, install, configure, initialise, validate
    --install-only     dependencies only (core + runtime)
    --validate         run checks, change nothing
    --diagnose         explain current state, change nothing
    --reset            clear setup state (keeps secrets unless --purge-secrets)
    --rollback         undo the most recent recorded changes
    --set-secret K V   store one credential without touching anything else

Exit codes: 0 ready, 1 incomplete, 2 bad usage, 130 interrupted.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aria_autoconfig import (  # noqa: E402
    EnvironmentDetector,
    Journal,
    Orchestrator,
    Reporter,
    SecretsManager,
    Status,
    StepReport,
    StepResult,
    Tier,
    __version__,
)
from aria_autoconfig.validator import CHECKS  # noqa: E402

EXIT_OK = 0
EXIT_INCOMPLETE = 1
EXIT_USAGE = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aria_setup",
        description="ARIA auto-configuration engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python aria_setup.py --auto-configure     full setup\n"
            "  python aria_setup.py --validate           health checks only\n"
            "  python aria_setup.py --diagnose           explain current state\n"
            "  python aria_setup.py --auto-configure --dry-run\n"
        ),
    )
    parser.add_argument("--version", action="version", version=f"aria_setup {__version__}")

    mode = parser.add_argument_group("mode")
    mode.add_argument("--auto-configure", action="store_true", help="run the full pipeline")
    mode.add_argument("--install-only", action="store_true", help="install dependencies only")
    mode.add_argument("--validate", action="store_true", help="run checks without changing anything")
    mode.add_argument("--diagnose", action="store_true", help="report current state")
    mode.add_argument("--reset", action="store_true", help="clear setup state")
    mode.add_argument("--rollback", action="store_true", help="undo recorded changes")

    options = parser.add_argument_group("options")
    options.add_argument(
        "--tier",
        action="append",
        choices=[t.value for t in Tier],
        help="restrict to a tier (repeatable; default: all)",
    )
    options.add_argument("--dry-run", action="store_true", help="show what would change, write nothing")
    options.add_argument("--quiet", "-q", action="store_true", help="only print the summary")
    options.add_argument("--json", action="store_true", help="print the report as JSON")
    options.add_argument("--purge-secrets", action="store_true", help="with --reset, also delete env files")
    options.add_argument(
        "--set-secret",
        nargs=2,
        metavar=("NAME", "VALUE"),
        action="append",
        help="store a credential (repeatable)",
    )
    options.add_argument("--list-checks", action="store_true", help="list the validation checks")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_checks:
        _list_checks()
        return EXIT_OK

    reporter = Reporter(quiet=args.quiet)
    detector = EnvironmentDetector(PROJECT_ROOT)
    env = detector.detect()
    orchestrator = Orchestrator(env, PROJECT_ROOT, reporter=reporter, dry_run=args.dry_run)

    if args.set_secret:
        return _set_secrets(args.set_secret, orchestrator, reporter)

    if args.reset:
        return _reset(args, orchestrator, reporter)
    if args.rollback:
        orchestrator.rollback()
        return EXIT_OK
    if args.diagnose:
        _emit(orchestrator.diagnose(), args.json)
        return EXIT_OK
    if args.validate:
        report = orchestrator.validate(args.tier)
        _emit(report, args.json)
        return EXIT_OK if report.get("success") else EXIT_INCOMPLETE
    if args.install_only:
        tiers = args.tier or [Tier.CORE.value, Tier.RUNTIME.value]
        report = orchestrator.run_full_setup(tiers)
        _emit(report, args.json)
        return EXIT_OK if report.get("success") else EXIT_INCOMPLETE
    if args.auto_configure:
        report = orchestrator.run_full_setup(args.tier)
        _emit(report, args.json)
        return EXIT_OK if report.get("success") else EXIT_INCOMPLETE

    # No mode flag: run the default pipeline. One command should just work.
    report = orchestrator.run_full_setup(args.tier)
    _emit(report, args.json)
    return EXIT_OK if report.get("success") else EXIT_INCOMPLETE

def _set_secrets(pairs: list[list[str]], orchestrator: Orchestrator, reporter: Reporter) -> int:
    manager = SecretsManager(PROJECT_ROOT, dry_run=orchestrator.dry_run)
    failed = 0
    for name, value in pairs:
        result = manager.inject(name, value)
        reporter.step(_as_report(name, result))
        if result.status is Status.FAILED:
            failed += 1
    return EXIT_OK if not failed else EXIT_INCOMPLETE


def _as_report(name: str, result: StepResult) -> StepReport:
    return StepReport(name, Tier.OPTIONAL, result.status, result.message, details=result.details)


def _reset(args, orchestrator: Orchestrator, reporter: Reporter) -> int:
    orchestrator.reporter.header("ARIA Reset", str(PROJECT_ROOT))
    if args.purge_secrets:
        result = orchestrator.configurator.reset(remove_secrets=True)
        reporter.step(_as_report("purge_secrets", result))
    else:
        reporter.hint("secrets are kept; add --purge-secrets to delete the env files")
    Journal(PROJECT_ROOT / ".aura" / "setup_state.json").clear()
    reporter.step(_as_report("clear_setup_state", StepResult.ok("setup state cleared")))
    reporter.write("  Next: run setup again to rebuild from scratch")
    return EXIT_OK


def _list_checks() -> None:
    print(f"{'CHECK':<20} {'TIER':<9} DESCRIPTION")
    print("-" * 72)
    for check in CHECKS:
        print(f"{check.name:<20} {check.tier.value:<9} {check.description}")


def _emit(report: dict, as_json: bool) -> None:
    """Print the machine-readable report only when explicitly requested."""
    if not as_json:
        return
    import json

    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n  Setup interrupted. Re-run to continue; completed steps are remembered.", file=sys.stderr)
        sys.exit(130)
