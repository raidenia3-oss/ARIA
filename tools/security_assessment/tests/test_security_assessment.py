"""Tests for AURA Security Assessment module."""

from __future__ import annotations

import pytest
from pathlib import Path

from tools.security_assessment.scope import (
    ScopePolicy,
    default_policy,
    ScopeRule,
)
from tools.security_assessment.evidence import EvidenceCollector
from tools.security_assessment.triage import FindingTriage, Finding
from tools.security_assessment.policy import PolicyEnforcer, Action
from tools.security_assessment.report import ReportGenerator
from tools.security_assessment.passive_recon import PassiveRecon


class TestScopePolicy:
    def test_default_policy_allows_localhost(self):
        policy = default_policy()
        assert policy.is_authorized("http://localhost:8000")
        assert policy.is_authorized("http://127.0.0.1:8000")

    def test_blocks_external_targets(self):
        policy = default_policy()
        assert not policy.is_authorized("https://hackerone.com/test")
        assert not policy.is_authorized("http://example.com/api")

    def test_add_target(self):
        policy = ScopePolicy()
        policy.add_target("localhost", "domain", "testing")
        assert policy.is_authorized("http://localhost:8000")

    def test_dry_run_by_default(self):
        policy = default_policy()
        assert policy.dry_run is True

    def test_is_external_blocks_hackerone(self):
        policy = default_policy()
        assert policy.is_external("https://hackerone.com/test")
        assert policy.is_external("https://api.hackerone.com")

    def test_is_external_allows_localhost(self):
        policy = default_policy()
        assert not policy.is_external("http://localhost:8000")
        assert not policy.is_external("http://127.0.0.1:8000")

    def test_validate_request_blocks_external(self):
        policy = default_policy()
        allowed, reason = policy.validate_request("https://hackerone.com", "GET")
        assert not allowed
        assert "blocked" in reason

    def test_validate_request_allows_local_with_dry_run(self):
        policy = default_policy()
        allowed, reason = policy.validate_request("http://localhost:8000", "GET")
        assert allowed
        assert "DRY RUN" in reason


class TestEvidenceCollector:
    def test_redacts_credentials(self):
        collector = EvidenceCollector()
        evidence = {"password": "secret123", "api_key": "key123", "data": "normal"}
        record = collector.collect(evidence, "test")
        assert record.anonymized_content["password"] == "[REDACTED]"
        assert record.anonymized_content["api_key"] == "[REDACTED]"
        assert record.anonymized_content["data"] == "normal"

    def test_hashes_ip_addresses(self):
        collector = EvidenceCollector()
        evidence = {"ip": "192.168.1.100", "note": "connection from 10.0.0.1"}
        record = collector.collect(evidence, "test")
        assert "192.168.1.100" not in json_dumps(record.anonymized_content)
        assert "ip-" in record.anonymized_content["ip"]

    def test_redacts_emails(self):
        collector = EvidenceCollector()
        evidence = {"contact": "user@example.com"}
        record = collector.collect(evidence, "test")
        assert "user@example.com" not in str(record.anonymized_content)
        assert "[EMAIL_REDACTED]" in record.anonymized_content["contact"]

    def test_collect_generates_hash(self):
        collector = EvidenceCollector()
        evidence = {"test": "data", "value": 42}
        record = collector.collect(evidence, "test")
        assert len(record.original_hash) == 16
        assert record.timestamp is not None

    def test_get_all_and_clear(self):
        collector = EvidenceCollector()
        collector.collect({"a": 1}, "test")
        collector.collect({"b": 2}, "test")
        assert len(collector.get_all()) == 2
        collector.clear()
        assert len(collector.get_all()) == 0


class TestFindingTriage:
    def test_local_classification_critical(self):
        triage = FindingTriage()
        finding = triage.classify_local({"error": "SQL injection UNION SELECT"})
        assert finding.severity == "critical"
        assert finding.category == "SQL Injection"

    def test_local_classification_high(self):
        triage = FindingTriage()
        finding = triage.classify_local({"note": "DEBUG=True found in config"})
        assert finding.severity == "high"
        assert finding.category == "Debug Mode"

    def test_local_classification_medium(self):
        triage = FindingTriage()
        finding = triage.classify_local({"header": "Server: Apache/2.4.1"})
        assert finding.severity == "medium"
        assert finding.category == "Information Disclosure"

    def test_local_classification_low(self):
        triage = FindingTriage()
        finding = triage.classify_local({"note": "Cookie missing Secure flag"})
        assert finding.severity == "low"
        assert finding.category == "Cookie Security"

    def test_local_classification_info(self):
        triage = FindingTriage()
        finding = triage.classify_local({"data": "normal content"})
        assert finding.severity == "info"
        assert finding.confidence > 0

    def test_triage_sync(self):
        triage = FindingTriage()
        evidence = [
            {"error": "SQL injection detected"},
            {"note": "DEBUG=True"},
        ]
        result = triage.triage_sync(evidence)
        assert result.total_findings == 2
        assert result.severity_counts["critical"] >= 1
        assert result.severity_counts["high"] >= 1


class TestPolicyEnforcer:
    def test_blocks_exploit_action(self):
        enforcer = PolicyEnforcer(default_policy())
        result = enforcer.validate(Action.EXPLOIT, "http://localhost:8000")
        assert not result.allowed
        assert "never" in result.reason.lower()

    def test_blocks_external_target(self):
        enforcer = PolicyEnforcer(default_policy())
        result = enforcer.validate(Action.RECON, "https://hackerone.com")
        assert not result.allowed
        assert "blocked" in result.reason.lower()

    def test_allows_local_dry_run(self):
        enforcer = PolicyEnforcer(default_policy())
        result = enforcer.validate(Action.RECON, "http://localhost:8000")
        assert result.allowed
        assert "DRY RUN" in result.reason

    def test_rate_limiting(self):
        policy = ScopePolicy(max_requests_per_minute=2, dry_run=False)
        enforcer = PolicyEnforcer(policy)
        for _ in range(2):
            result = enforcer.validate(Action.HEADERS, "http://localhost:8000")
            assert result.allowed
        result = enforcer.validate(Action.HEADERS, "http://localhost:8000")
        assert not result.allowed
        assert "rate" in result.reason.lower()

    def test_dry_run_allows_scan_with_warning(self):
        enforcer = PolicyEnforcer(default_policy())
        result = enforcer.validate(Action.SCAN, "http://localhost:8000")
        assert result.allowed
        assert "DRY RUN" in result.reason

    def test_audit_log(self):
        enforcer = PolicyEnforcer(default_policy())
        enforcer.validate(Action.RECON, "http://localhost:8000")
        enforcer.validate(Action.EXPLOIT, "http://localhost:8000")
        log = enforcer.get_audit_log()
        assert len(log) == 2
        assert any(not entry["allowed"] for entry in log)


class TestReportGenerator:
    def test_generate_json(self):
        from tools.security_assessment.triage import TriageResult, Finding
        generator = ReportGenerator("test-assessment")
        triage = TriageResult(
            findings=[
                Finding(
                    id="abc123",
                    title="Test Finding",
                    severity="high",
                    category="test",
                    description="Test description",
                    recommendation="Fix it",
                    confidence=0.8,
                )
            ],
            total_findings=1,
            severity_counts={"critical": 0, "high": 1, "medium": 0, "low": 0, "info": 0},
            provider_used="local_rules",
            confidence_avg=0.8,
        )
        result = generator.generate_json(triage)
        assert "test-assessment" in result or "Test Finding" in result

    def test_generate_markdown(self):
        from tools.security_assessment.triage import TriageResult, Finding
        generator = ReportGenerator("test-assessment")
        triage = TriageResult(
            findings=[],
            total_findings=0,
            severity_counts={"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0},
            provider_used="local_rules",
            confidence_avg=0.0,
        )
        result = generator.generate_markdown(triage)
        assert "Security Assessment Report" in result
        assert "No findings" in result

    def test_generate_both(self, tmp_path):
        from tools.security_assessment.triage import TriageResult
        generator = ReportGenerator("test-assessment")
        triage = TriageResult(
            findings=[],
            total_findings=0,
            severity_counts={"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0},
            provider_used="local_rules",
            confidence_avg=0.0,
        )
        paths = generator.generate(triage, str(tmp_path))
        assert "json" in paths
        assert "markdown" in paths
        assert Path(paths["json"]).exists()
        assert Path(paths["markdown"]).exists()


def json_dumps(data) -> str:
    import json
    return json.dumps(data, default=str, sort_keys=True)
