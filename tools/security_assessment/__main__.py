#!/usr/bin/env python3
"""CLI entry point for AURA Security Assessment."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from tools.security_assessment import (
    PassiveRecon,
    EvidenceCollector,
    FindingTriage,
    ReportGenerator,
    PolicyEnforcer,
    Action,
    create_default_policy,
)


def main():
    parser = argparse.ArgumentParser(
        description="AURA OS Security Assessment (Defensive)",
    )
    parser.add_argument(
        "--target", "-t",
        nargs="+",
        required=True,
        help="Target(s) to assess (must be in authorized scope)",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        default=True,
        help="Dry-run mode (default: True)",
    )
    parser.add_argument(
        "--report-dir", "-o",
        default="reports/security",
        help="Output directory for reports",
    )
    parser.add_argument(
        "--evidence-only",
        action="store_true",
        help="Only collect evidence, skip triage and reporting",
    )
    parser.add_argument(
        "--scope-file", "-s",
        default=None,
        help="Scope configuration file (.env.security or .env)",
    )

    args = parser.parse_args()

    print(f"🔐 AURA Security Assessment v2.1")
    print(f"   Targets: {args.target}")
    print(f"   Dry-run: {args.dry_run}")
    print()

    scope = create_default_policy()
    enforcer = PolicyEnforcer(scope)

    print(f"📜 Policy: {enforcer.get_stats()}")
    print()

    recon = PassiveRecon(policy=scope)
    result = asyncio.run(recon.scan(args.target)) if False else recon.scan_sync(args.target)

    print(f"🔍 Passive Recon:")
    print(f"   Authorized: {result.scope_authorized}")
    print(f"   Reason: {result.scope_reason}")
    print(f"   Evidence items: {len(result.evidence)}")
    print()

    if args.evidence_only:
        print("Evidence collection complete (skip trio and reporting).")
        return

    evidence_list = [ev.anonymized_content for ev in result.evidence]
    if evidence_list or result.scope_authorized:
        if not evidence_list and result.scope_authorized and args.dry_run:
            evidence_list = [{"target": t, "status": "dry_run_no_evidence"} for t in args.target]

        collector = EvidenceCollector()
        triage = FindingTriage(collector=collector, scope_policy=scope)
        triage_result = triage.triage_sync(evidence_list)

        print(f"🧠 Triage Results:")
        print(f"   Total findings: {triage_result.total_findings}")
        print(f"   Provider: {triage_result.provider_used}")
        print(f"   Severity: {triage_result.severity_counts}")
        print()

        reporter = ReportGenerator(assessment_name="aura-security-assessment")
        paths = reporter.generate(triage_result, args.report_dir)
        print(f"📄 Reports generated:")
        print(f"   JSON: {paths['json']}")
        print(f"   Markdown: {paths['markdown']}")
    else:
        print("⚠ No evidence collected (targets may be out of scope)")
        print("   Reports will be empty")


if __name__ == "__main__":
    main()
