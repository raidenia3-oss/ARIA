"""Report generation for AURA Security Assessment.

Generates reproducible reports in JSON and Markdown formats.
All evidence is referenced via hash (not raw data) for traceability.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from tools.security_assessment.triage import Finding, TriageResult, SEVERITY_RANK


SEVERITY_LABELS = {
    "critical": "🔴 CRITICAL",
    "high": "🟠 HIGH",
    "medium": "🟡 MEDIUM",
    "low": "🟢 LOW",
    "info": "🔵 INFO",
}


SEVERITY_COLORS = {
    "critical": "red",
    "high": "orange",
    "medium": "yellow",
    "low": "green",
    "info": "blue",
}


class ReportGenerator:
    """Generates security assessment reports.

    Produces deterministic, reproducible reports that reference
    anonymized evidence hashes rather than raw data.
    """

    def __init__(self, assessment_name: str = "security-assessment"):
        self.assessment_name = assessment_name
        self.timestamp = datetime.utcnow().isoformat()

    def generate_json(self, triage: TriageResult, output_path: Optional[str] = None) -> str:
        """Generate a JSON report."""
        report = {
            "metadata": {
                "name": self.assessment_name,
                "timestamp": self.timestamp,
                "total_findings": triage.total_findings,
                "provider_used": triage.provider_used,
                "confidence_avg": triage.confidence_avg,
            },
            "severity_counts": triage.severity_counts,
            "findings": [f.to_dict() for f in sorted(triage.findings, key=lambda f: SEVERITY_RANK.get(f.severity, 5))],
        }

        json_str = json_dumps(report)
        if output_path:
            Path(output_path).write_text(json_str, encoding="utf-8")
            print(f"[+] JSON report: {output_path}")
        return json_str

    def generate_markdown(self, triage: TriageResult, output_path: Optional[str] = None) -> str:
        """Generate a Markdown report."""
        lines = []
        lines.append(f"# Security Assessment Report")
        lines.append("")
        lines.append(f"**Assessment**: {self.assessment_name}")
        lines.append(f"**Generated**: {self.timestamp}")
        lines.append(f"**Triage Provider**: {triage.provider_used}")
        lines.append(f"**Avg Confidence**: {triage.confidence_avg}")
        lines.append("")
        lines.append("## Summary")
        lines.append("")
        lines.append("| Severity | Count |")
        lines.append("|----------|-------|")
        for sev in ["critical", "high", "medium", "low", "info"]:
            count = triage.severity_counts.get(sev, 0)
            label = SEVERITY_LABELS.get(sev, sev)
            lines.append(f"| {label} | {count} |")
        lines.append(f"| **Total** | **{triage.total_findings}** |")
        lines.append("")

        lines.append("## Findings")
        lines.append("")
        sorted_findings = sorted(triage.findings, key=lambda f: SEVERITY_RANK.get(f.severity, 5))

        if not sorted_findings:
            lines.append("No findings detected. ✅")
        else:
            for finding in sorted_findings:
                label = SEVERITY_LABELS.get(finding.severity, finding.severity.upper())
                lines.append(f"### {label}: {finding.title}")
                lines.append("")
                lines.append(f"- **ID**: `{finding.id}`")
                lines.append(f"- **Category**: {finding.category}")
                lines.append(f"- **Confidence**: {finding.confidence}")
                lines.append(f"- **Classified by**: {finding.classified_by}")
                lines.append(f"- **Target**: {finding.affected_target or 'N/A'}")
                lines.append(f"- **Evidence Ref**: `{finding.evidence_ref or 'N/A'}`")
                lines.append("")
                lines.append(f"**Description**:")
                lines.append(f"```")
                lines.append(f"{finding.description[:500]}")
                lines.append(f"```")
                lines.append("")
                lines.append(f"**Recommendation**: {finding.recommendation}")
                lines.append("")

        lines.append("## Methodology")
        lines.append("")
        lines.append("This report was generated using AURA Security Assessment v2.1.")
        lines.append("All evidence was anonymized before analysis. See evidence hashes in finding records.")
        lines.append("")
        lines.append("## Reproduction")
        lines.append("")
        lines.append("```bash")
        lines.append(f"cd tools/security-assessment")
        lines.append(f"python -m __main__ --target localhost:8000")
        lines.append("```")
        lines.append("")

        md_str = "\n".join(lines)
        if output_path:
            Path(output_path).write_text(md_str, encoding="utf-8")
            print(f"[+] Markdown report: {output_path}")
        return md_str

    def generate(self, triage: TriageResult, output_dir: str = ".") -> Dict[str, str]:
        """Generate both JSON and Markdown reports."""
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        json_path = out_dir / f"{self.assessment_name}_{timestamp_str}.json"
        md_path = out_dir / f"{self.assessment_name}_{timestamp_str}.md"

        self.generate_json(triage, str(json_path))
        self.generate_markdown(triage, str(md_path))

        return {
            "json": str(json_path),
            "markdown": str(md_path),
        }


def json_dumps(data) -> str:
    """Safe JSON serialization."""
    import json
    return json.dumps(data, indent=2, default=str, sort_keys=False)
