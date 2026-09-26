"""Finding triage using Omniroute AI classification.

Uses the existing AURA backend omniroute integration to classify
and prioritize findings. Falls back to local rule-based triage
when no external providers are available.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from tools.security_assessment.scope import ScopePolicy
from tools.security_assessment.evidence import EvidenceCollector


@dataclass
class Finding:
    """A security finding from assessment."""
    id: str
    title: str
    severity: str
    category: str
    description: str
    evidence_ref: Optional[str] = None
    affected_target: str = ""
    recommendation: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    classified_by: str = "local_rules"
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


@dataclass
class TriageResult:
    """Results from triage classification."""
    findings: List[Finding] = field(default_factory=list)
    total_findings: int = 0
    severity_counts: Dict[str, int] = field(default_factory=dict)
    provider_used: str = "local"
    confidence_avg: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)


class FindingTriage:
    """Triage engine for security findings.

    Uses Omniroute for AI-powered classification when available,
    falls back to local pattern-based rules otherwise.
    """

    CRITICAL_PATTERNS = [
        ("SQL Injection", r"sql|injection|union.*select|';.*drop", "SQL injection pattern detected"),
        ("XSS", r"cross.?site|xss|<script|javascript:", "Cross-site scripting pattern detected"),
        ("Command Injection", r"exec|popen|system\(|eval\(|\$\(|\|.*sh", "Command injection pattern detected"),
        ("Path Traversal", r"\.\./|\.\.\\|/etc/passwd|/etc/shadow", "Path traversal pattern detected"),
        ("SSRF", r"url=|fetch.*http|file_get_contents|open.*http", "SSRF pattern detected"),
    ]

    HIGH_PATTERNS = [
        ("Hardcoded Secret", r"api[_-]?key.*=.*|password.*=.*|secret.*=", "Potential hardcoded secret"),
        ("Debug Mode", r"DEBUG\s*=\s*True|debug.*enabled", "Debug mode enabled"),
        ("Weak CORS", r"Access-Control-Allow-Origin.*\*", "Wildcard CORS policy"),
        ("Missing Auth", r"login.*not.*required|auth.*optional", "Missing authentication"),
    ]

    MEDIUM_PATTERNS = [
        ("Information Disclosure", r"version|server:|server.*header|x-powered-by", "Server version disclosure"),
        ("Missing Security Header", r"X-Frame-Options|Content-Security-Policy", "Missing security header"),
        ("Verbose Error", r"traceback|exception|error.*detail", "Verbose error messages"),
    ]

    LOW_PATTERNS = [
        ("Cookie Security", r"HttpOnly|Secure.*flag", "Cookie security flags"),
        ("Directory Listing", r"Index of|/listing", "Directory listing enabled"),
    ]

    def __init__(
        self,
        collector: Optional[EvidenceCollector] = None,
        scope_policy: Optional[ScopePolicy] = None,
    ):
        self.collector = collector or EvidenceCollector()
        self.scope_policy = scope_policy or ScopePolicy()
        self._findings: List[Finding] = []

    def classify_local(self, evidence: Dict[str, Any]) -> Finding:
        """Classify a finding using local pattern-based rules."""
        content_str = str(evidence)
        finding_id = hashlib_sha256(content_str)[:8]

        severity = "info"
        category = "unknown"
        confidence = 0.5
        recommendation = "Review manually"

        for title, pattern, desc in self.CRITICAL_PATTERNS:
            if re_search(pattern, content_str):
                severity = "critical"
                category = title
                confidence = 0.9
                recommendation = f"Immediately remediate: {desc}"
                break

        if severity == "info":
            for title, pattern, desc in self.HIGH_PATTERNS:
                if re_search(pattern, content_str):
                    severity = "high"
                    category = title
                    confidence = 0.8
                    recommendation = f"Address: {desc}"
                    break

        if severity == "info":
            for title, pattern, desc in self.MEDIUM_PATTERNS:
                if re_search(pattern, content_str):
                    severity = "medium"
                    category = title
                    confidence = 0.7
                    recommendation = f"Consider: {desc}"
                    break

        if severity == "info":
            for title, pattern, desc in self.LOW_PATTERNS:
                if re_search(pattern, content_str):
                    severity = "low"
                    category = title
                    confidence = 0.6
                    recommendation = desc
                    break

        return Finding(
            id=finding_id,
            title=category,
            severity=severity,
            category=category,
            description=content_str[:500],
            affected_target=str(evidence.get("target", evidence.get("hostname", ""))),
            recommendation=recommendation,
            classified_by="local_rules",
            confidence=confidence,
            metadata={"source": "passive_recon"},
        )

    async def classify_with_omniroute(self, evidence: Dict[str, Any]) -> Finding:
        """Classify a finding using omniroute AI provider.

        Falls back to local rules if no providers are available.
        """
        base_finding = self.classify_local(evidence)

        omniroute_url = os.getenv("OMNIROUTE_URL", "http://localhost:8080")
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                prompt = (
                    f"Classify this security finding as critical, high, medium, low, or info. "
                    f"Provide a brief title and recommendation.\n\n"
                    f"Finding: {str(evidence)[:1000]}"
                )
                response = await client.post(
                    f"{omniroute_url}/api/providers/best",  # Use best provider endpoint
                    params={"model_type": "chat"},
                    json={"message": prompt, "skill_id": "security_triage"},
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    ai_result = data.get("response", data.get("result", ""))
                    if ai_result:
                        base_finding.classified_by = "omniroute_ai"
                        base_finding.confidence = 0.85
                        lines = ai_result.strip().split("\n")
                        if lines:
                            base_finding.title = lines[0].strip()
                        if len(lines) > 1:
                            base_finding.recommendation = lines[1].strip()
                    return base_finding
        except Exception:
            pass

        return base_finding

    async def triage_evidence(self, evidence_list: List[Dict[str, Any]]) -> TriageResult:
        """Triage a list of evidence items."""
        findings = []

        for evidence in evidence_list:
            anon = self.collector.collect(evidence, source="triage_input")
            finding = await self.classify_with_omniroute(anon.anonymized_content)
            finding.evidence_ref = anon.original_hash
            findings.append(finding)
            self._findings.append(finding)

        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for f in findings:
            severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1

        confidence_avg = sum(f.confidence for f in findings) / len(findings) if findings else 0.0

        return TriageResult(
            findings=findings,
            total_findings=len(findings),
            severity_counts=severity_counts,
            provider_used="omniroute_ai" if any(f.classified_by == "omniroute_ai" for f in findings) else "local_rules",
            confidence_avg=round(confidence_avg, 2),
        )

    def triage_sync(self, evidence_list: List[Dict[str, Any]]) -> TriageResult:
        """Synchronous wrapper for triage_evidence."""
        return asyncio.run(self.triage_evidence(evidence_list))

    def get_all_findings(self) -> List[Finding]:
        """Get all findings."""
        return self._findings

    def get_findings_by_severity(self, severity: str) -> List[Finding]:
        """Filter findings by severity."""
        return [f for f in self._findings if f.severity == severity]

    def sort_by_severity(self, findings: Optional[List[Finding]] = None) -> List[Finding]:
        """Sort findings by severity (critical first)."""
        items = findings or self._findings
        return sorted(items, key=lambda f: SEVERITY_RANK.get(f.severity, 5))


import hashlib
import re as re_module


def hashlib_sha256(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode()).hexdigest()


def re_search(pattern: str, text: str):
    return re_module.search(pattern, text, re_module.IGNORECASE)
