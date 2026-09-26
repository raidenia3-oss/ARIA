"""AURA Security Assessment — Defensive Security Module.

A defensive security assessment toolkit inspired by bug bounty concepts
but built exclusively for authorized, in-scope testing.

Key principles:
- No active scanning against external targets
- Allowlist-based scope validation
- All evidence anonymized before storage
- Dry-run mode enabled by default
- AI-assisted triage via Omniroute (with local fallback)
- Manual approval for any active actions

Usage:
    python -m tools.security_assessment --target localhost:8000
    python -m pytest tools/security-assessment/tests/
"""

from tools.security_assessment.scope import (
    ScopePolicy,
    ScopeRule,
    default_policy,
    load_scope_from_env,
)
from tools.security_assessment.passive_recon import (
    PassiveRecon,
    PassiveReconResult,
    PassiveEvidence,
)
from tools.security_assessment.evidence import (
    EvidenceCollector,
    AnonymizedEvidence,
)
from tools.security_assessment.triage import (
    Finding,
    FindingTriage,
    TriageResult,
)
from tools.security_assessment.report import (
    ReportGenerator,
)
from tools.security_assessment.policy import (
    Action,
    PolicyEnforcer,
    EnforcementResult,
    create_default_policy,
)

__version__ = "2.1.0"
__all__ = [
    "ScopePolicy",
    "ScopeRule",
    "default_policy",
    "load_scope_from_env",
    "PassiveRecon",
    "PassiveReconResult",
    "PassiveEvidence",
    "EvidenceCollector",
    "AnonymizedEvidence",
    "Finding",
    "FindingTriage",
    "TriageResult",
    "ReportGenerator",
    "Action",
    "PolicyEnforcer",
    "EnforcementResult",
    "create_default_policy",
]
