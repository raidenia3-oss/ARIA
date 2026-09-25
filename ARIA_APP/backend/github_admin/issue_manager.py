"""ARIA Issue Manager — Triaging, labeling, and managing GitHub issues."""

import logging
import re
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class IssuePriority(str, Enum):
    """Issue priority levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IssueType(str, Enum):
    """Issue type classification"""
    BUG = "bug"
    FEATURE = "feature"
    ENHANCEMENT = "enhancement"
    DOCUMENTATION = "documentation"
    QUESTION = "question"
    SECURITY = "security"
    PERFORMANCE = "performance"
    REFACTOR = "refactor"
    DEPENDENCY = "dependency"
    OTHER = "other"


@dataclass
class IssueAnalysis:
    """Result of issue analysis"""
    number: int
    repo_name: str
    title: str
    author: str
    type: IssueType
    priority: IssuePriority
    labels: List[str]
    suggested_labels: List[str]
    assignee_suggestion: Optional[str]
    milestone_suggestion: Optional[str]
    estimated_effort: str  # xs, s, m, l, xl
    related_issues: List[int]
    is_duplicate: bool
    duplicate_of: Optional[int]
    auto_close_reason: Optional[str]


@dataclass
class TriageRule:
    """Rule for automatic triaging"""
    name: str
    patterns: List[str]  # Regex patterns in title/body
    labels: List[str]
    priority: IssuePriority
    type: IssueType
    assignee: Optional[str] = None
    milestone: Optional[str] = None


class IssueManager:
    """
    ARIA Issue Manager
    Triaging, labeling, assignment, and automation
    """

    DEFAULT_RULES = [
        TriageRule(
            name="bug-report",
            patterns=[r"bug", r"error", r"crash", r"fail", r"broken", r"not working", r"issue"],
            labels=["bug", "needs-triage"],
            priority=IssuePriority.HIGH,
            type=IssueType.BUG
        ),
        TriageRule(
            name="security",
            patterns=[r"security", r"vulnerab", r"exploit", r"xss", r"csrf", r"injection", r"auth"],
            labels=["security", "urgent"],
            priority=IssuePriority.CRITICAL,
            type=IssueType.SECURITY
        ),
        TriageRule(
            name="performance",
            patterns=[r"slow", r"performance", r"lag", r"timeout", r"memory leak", r"cpu"],
            labels=["performance", "needs-investigation"],
            priority=IssuePriority.MEDIUM,
            type=IssueType.PERFORMANCE
        ),
        TriageRule(
            name="feature-request",
            patterns=[r"feature", r"request", r"add", r"implement", r"support", r"would be nice"],
            labels=["enhancement", "needs-triage"],
            priority=IssuePriority.LOW,
            type=IssueType.FEATURE
        ),
        TriageRule(
            name="documentation",
            patterns=[r"doc", r"readme", r"comment", r"example", r"tutorial", r"guide"],
            labels=["documentation", "good-first-issue"],
            priority=IssuePriority.LOW,
            type=IssueType.DOCUMENTATION
        ),
        TriageRule(
            name="dependency",
            patterns=[r"dependen", r"upgrade", r"update", r"version", r"deprecat"],
            labels=["dependencies", "maintenance"],
            priority=IssuePriority.MEDIUM,
            type=IssueType.DEPENDENCY
        ),
    ]

    def __init__(self, github_client):
        self.client = github_client
        self.rules: List[TriageRule] = self.DEFAULT_RULES.copy()
        self.assignees: List[str] = []
        self.auto_close_days: int = 90  # Auto-close stale issues after 90 days
        self.auto_close_labels: List[str] = ["stale", "wontfix", "duplicate"]

    def add_rule(self, rule: TriageRule):
        """Add a custom triage rule"""
        self.rules.append(rule)
        logger.info(f"✅ Triage rule added: {rule.name}")

    def remove_rule(self, name: str) -> bool:
        """Remove a triage rule by name"""
        for i, rule in enumerate(self.rules):
            if rule.name == name:
                self.rules.pop(i)
                logger.info(f"✅ Triage rule removed: {name}")
                return True
        return False

    def set_assignees(self, assignees: List[str]):
        """Set available assignees for round-robin assignment"""
        self.assignees = assignees

    def analyze_issue(self, repo_name: str, issue_number: int) -> Optional[IssueAnalysis]:
        """Analyze an issue and suggest labels, priority, etc."""
        try:
            issues = self.client.list_issues(repo_name, state="all")
            issue = next((i for i in issues if i["number"] == issue_number), None)
            if not issue:
                return None

            title = issue["title"].lower()
            body = ""  # Would need another API call to get body

            # Apply triage rules
            matched_rules = []
            for rule in self.rules:
                for pattern in rule.patterns:
                    if re.search(pattern, title, re.IGNORECASE) or re.search(pattern, body, re.IGNORECASE):
                        matched_rules.append(rule)
                        break

            # Determine best match (highest priority)
            if matched_rules:
                best_rule = max(matched_rules, key=lambda r: list(IssuePriority).index(r.priority))
                suggested_labels = best_rule.labels.copy()
                suggested_type = best_rule.type
                suggested_priority = best_rule.priority
                suggested_assignee = best_rule.assignee
                suggested_milestone = best_rule.milestone
            else:
                suggested_labels = ["needs-triage"]
                suggested_type = IssueType.OTHER
                suggested_priority = IssuePriority.MEDIUM
                suggested_assignee = None
                suggested_milestone = None

            # Check for duplicates (simple title similarity)
            is_duplicate, duplicate_of = self._check_duplicate(repo_name, issue_number, issue["title"])

            # Estimate effort based on labels and description
            effort = self._estimate_effort(suggested_labels, title)

            # Check if should auto-close
            auto_close_reason = self._check_auto_close(issue)

            return IssueAnalysis(
                number=issue_number,
                repo_name=repo_name,
                title=issue["title"],
                author=issue["author"],
                type=suggested_type,
                priority=suggested_priority,
                labels=issue["labels"],
                suggested_labels=suggested_labels,
                assignee_suggestion=suggested_assignee,
                milestone_suggestion=suggested_milestone,
                estimated_effort=effort,
                related_issues=[],
                is_duplicate=is_duplicate,
                duplicate_of=duplicate_of,
                auto_close_reason=auto_close_reason
            )
        except Exception as e:
            logger.error(f"❌ analyze_issue failed: {e}")
            return None

    def _check_duplicate(self, repo_name: str, issue_number: int, title: str) -> tuple:
        """Check for duplicate issues (simple implementation)"""
        # In practice, would use more sophisticated similarity matching
        issues = self.client.list_issues(repo_name, state="open")
        for issue in issues:
            if issue["number"] != issue_number:
                # Simple word overlap check
                title_words = set(title.lower().split())
                other_words = set(issue["title"].lower().split())
                overlap = len(title_words & other_words) / max(len(title_words), len(other_words))
                if overlap > 0.7:
                    return True, issue["number"]
        return False, None

    def _estimate_effort(self, labels: List[str], title: str) -> str:
        """Estimate effort size"""
        effort_keywords = {
            "xs": ["typo", "fix typo", "small", "minor"],
            "s": ["bug", "fix", "update", "add"],
            "m": ["feature", "implement", "refactor", "improve"],
            "l": ["refactor", "rewrite", "architecture", "migration"],
            "xl": ["rewrite", "rearchitecture", "major", "overhaul"]
        }

        for size, keywords in effort_keywords.items():
            for kw in keywords:
                if kw in title.lower():
                    return size

        # Default based on labels
        if "good-first-issue" in labels:
            return "xs"
        if "bug" in labels:
            return "s"
        if "feature" in labels or "enhancement" in labels:
            return "m"
        return "m"

    def _check_auto_close(self, issue: Dict) -> Optional[str]:
        """Check if issue should be auto-closed"""
        # Check for stale
        if issue["updated_at"]:
            try:
                updated = datetime.fromisoformat(issue["updated_at"].replace('Z', '+00:00'))
                if datetime.now(updated.tzinfo) - updated > timedelta(days=self.auto_close_days):
                    # Check if has activity
                    if issue["comments"] == 0:
                        return "stale_no_activity"
            except Exception:
                pass

        # Check for wontfix/duplicate labels
        for label in issue["labels"]:
            if label in self.auto_close_labels:
                return f"labeled_{label}"

        return None

    def triage_issue(self, repo_name: str, issue_number: int,
                    apply_labels: bool = True,
                    apply_assignee: bool = True,
                    apply_milestone: bool = True) -> bool:
        """Auto-triage an issue based on rules"""
        try:
            analysis = self.analyze_issue(repo_name, issue_number)
            if not analysis:
                return False

            success = True

            # Apply suggested labels
            if apply_labels and analysis.suggested_labels:
                new_labels = [l for l in analysis.suggested_labels if l not in analysis.labels]
                if new_labels:
                    self.client.add_labels(repo_name, issue_number, new_labels)
                    logger.info(f"🏷️ Added labels to {repo_name}#{issue_number}: {new_labels}")

            # Apply assignee
            if apply_assignee and analysis.assignee_suggestion:
                self.client.update_issue(repo_name, issue_number, assignees=[analysis.assignee_suggestion])
                logger.info(f"👤 Assigned {repo_name}#{issue_number} to {analysis.assignee_suggestion}")

            # Apply milestone
            if apply_milestone and analysis.milestone_suggestion:
                self.client.update_issue(repo_name, issue_number, milestone=analysis.milestone_suggestion)
                logger.info(f"🎯 Milestone set for {repo_name}#{issue_number}: {analysis.milestone_suggestion}")

            # Handle duplicates
            if analysis.is_duplicate and analysis.duplicate_of:
                self.client.update_issue(repo_name, issue_number, state="closed")
                self.client.add_labels(repo_name, issue_number, ["duplicate"])
                # Add comment about duplicate
                logger.warning(f"⚠️ Closed duplicate issue {repo_name}#{issue_number} (duplicate of #{analysis.duplicate_of})")

            # Handle auto-close
            if analysis.auto_close_reason:
                self.client.update_issue(repo_name, issue_number, state="closed")
                self.client.add_labels(repo_name, issue_number, ["stale", "auto-closed"])
                logger.info(f"🔒 Auto-closed {repo_name}#{issue_number}: {analysis.auto_close_reason}")

            return success
        except Exception as e:
            logger.error(f"❌ triage_issue failed: {e}")
            return False

    def bulk_triage(self, repo_name: str, state: str = "open",
                   apply_labels: bool = True,
                   apply_assignee: bool = True,
                   apply_milestone: bool = True) -> Dict:
        """Triage all issues in a repo"""
        issues = self.client.list_issues(repo_name, state=state)
        results = {
            "total": len(issues),
            "triaged": 0,
            "failed": 0,
            "duplicates_found": 0,
            "auto_closed": 0,
            "errors": []
        }

        for issue in issues:
            try:
                analysis = self.analyze_issue(repo_name, issue["number"])
                if not analysis:
                    results["failed"] += 1
                    continue

                if self.triage_issue(repo_name, issue["number"],
                                    apply_labels, apply_assignee, apply_milestone):
                    results["triaged"] += 1
                    if analysis.is_duplicate:
                        results["duplicates_found"] += 1
                    if analysis.auto_close_reason:
                        results["auto_closed"] += 1
                else:
                    results["failed"] += 1
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(f"Issue #{issue['number']}: {str(e)}")

        logger.info(f"✅ Bulk triage complete: {results['triaged']}/{results['total']} triaged")
        return results

    def get_issue_stats(self, repo_name: str, days: int = 30) -> Dict:
        """Get issue statistics"""
        try:
            issues = self.client.list_issues(repo_name, state="all")
            now = datetime.now()

            stats = {
                "total": len(issues),
                "open": 0,
                "closed": 0,
                "by_type": defaultdict(int),
                "by_priority": defaultdict(int),
                "by_label": defaultdict(int),
                "by_assignee": defaultdict(int),
                "avg_time_to_close": None,
                "recent_activity": 0,
            }

            close_times = []
            cutoff = now - timedelta(days=days)

            for issue in issues:
                if issue["status"] == "open":
                    stats["open"] += 1
                else:
                    stats["closed"] += 1

                # Count labels
                for label in issue["labels"]:
                    stats["by_label"][label] += 1

                # Count assignees
                for assignee in issue["assignees"]:
                    stats["by_assignee"][assignee] += 1

                # Recent activity
                try:
                    updated = datetime.fromisoformat(issue["updated_at"].replace('Z', '+00:00'))
                    if updated > cutoff:
                        stats["recent_activity"] += 1
                except Exception:
                    pass

            # Calculate avg time to close
            if close_times:
                stats["avg_time_to_close"] = sum(close_times) / len(close_times)

            return dict(stats)
        except Exception as e:
            logger.error(f"❌ get_issue_stats failed: {e}")
            return {}

    def create_issue_from_template(self, repo_name: str, template_name: str,
                                  variables: Dict[str, str]) -> Optional[Dict]:
        """Create issue from a template"""
        templates = {
            "bug_report": {
                "title": "Bug: {summary}",
                "body": """## Description
{description}

## Steps to Reproduce
{steps}

## Expected Behavior
{expected}

## Actual Behavior
{actual}

## Environment
- OS: {os}
- Version: {version}
- Browser: {browser}

## Additional Context
{context}
""",
                "labels": ["bug", "needs-triage"]
            },
            "feature_request": {
                "title": "Feature: {summary}",
                "body": """## Problem
{problem}

## Proposed Solution
{solution}

## Alternatives Considered
{alternatives}

## Additional Context
{context}
""",
                "labels": ["enhancement", "needs-triage"]
            }
        }

        if template_name not in templates:
            logger.error(f"❌ Template not found: {template_name}")
            return None

        template = templates[template_name]
        title = template["title"].format(**variables)
        body = template["body"].format(**variables)

        return self.client.create_issue(
            repo_name=repo_name,
            title=title,
            body=body,
            labels=template["labels"]
        )