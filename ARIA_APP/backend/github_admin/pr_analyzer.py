"""ARIA PR Analyzer — Analyze, review, and manage pull requests."""

import logging
import re
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ReviewDecision(str, Enum):
    """PR review decision"""
    APPROVE = "APPROVE"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    COMMENT = "COMMENT"


@dataclass
class PRAnalysis:
    """Result of PR analysis"""
    pr_number: int
    repo_name: str
    title: str
    author: str
    files_changed: int
    additions: int
    deletions: int
    is_draft: bool
    mergeable: bool
    mergeable_state: str
    checks_passing: bool
    review_status: str
    risk_level: str  # low, medium, high
    suggestions: List[str]
    security_concerns: List[str]
    performance_concerns: List[str]
    style_issues: List[str]


class PRAnalyzer:
    """
    ARIA PR Analyzer
    Analyzes PRs for quality, security, and best practices
    """

    def __init__(self, github_client):
        self.client = github_client

    def analyze_pr(self, repo_name: str, pr_number: int) -> Optional[PRAnalysis]:
        """Perform comprehensive PR analysis"""
        try:
            pr = self.client.get_pr(repo_name, pr_number)
            if not pr:
                return None

            # Get PR details
            files = list(pr.get_files())
            reviews = self.client.get_pr_reviews(repo_name, pr_number)
            checks = self.client.get_pr_checks(repo_name, pr_number)

            # Analyze
            risk_level = self._assess_risk(pr, files)
            suggestions = self._generate_suggestions(pr, files)
            security_concerns = self._check_security(pr, files)
            performance_concerns = self._check_performance(pr, files)
            style_issues = self._check_style(pr, files)

            # Check review status
            review_states = [r["state"] for r in reviews]
            if "CHANGES_REQUESTED" in review_states:
                review_status = "changes_requested"
            elif "APPROVED" in review_states:
                review_status = "approved"
            elif reviews:
                review_status = "reviewed"
            else:
                review_status = "pending"

            # Check checks
            checks_passing = all(c.get("conclusion") == "success" for c in checks) if checks else False

            return PRAnalysis(
                pr_number=pr_number,
                repo_name=repo_name,
                title=pr.title,
                author=pr.user.login,
                files_changed=pr.changed_files,
                additions=pr.additions,
                deletions=pr.deletions,
                is_draft=pr.draft,
                mergeable=pr.mergeable,
                mergeable_state=pr.mergeable_state,
                checks_passing=checks_passing,
                review_status=review_status,
                risk_level=risk_level,
                suggestions=suggestions,
                security_concerns=security_concerns,
                performance_concerns=performance_concerns,
                style_issues=style_issues
            )
        except Exception as e:
            logger.error(f"❌ analyze_pr failed: {e}")
            return None

    def _assess_risk(self, pr, files) -> str:
        """Assess risk level of PR"""
        risk_score = 0

        # Large PR = higher risk
        if pr.additions + pr.deletions > 500:
            risk_score += 3
        elif pr.additions + pr.deletions > 200:
            risk_score += 2
        elif pr.additions + pr.deletions > 50:
            risk_score += 1

        # Many files = higher risk
        if pr.changed_files > 20:
            risk_score += 2
        elif pr.changed_files > 10:
            risk_score += 1

        # Check for sensitive files
        sensitive_patterns = [
            r"\.env", r"config", r"secret", r"password", r"token",
            r"key", r"credential", r"certificate", r"\.pem", r"\.key"
        ]
        for f in files:
            for pattern in sensitive_patterns:
                if re.search(pattern, f.filename, re.IGNORECASE):
                    risk_score += 2
                    break

        # No tests = higher risk
        has_tests = any("test" in f.filename.lower() for f in files)
        if not has_tests and (pr.additions + pr.deletions > 50):
            risk_score += 1

        if risk_score >= 5:
            return "high"
        elif risk_score >= 2:
            return "medium"
        return "low"

    def _generate_suggestions(self, pr, files) -> List[str]:
        """Generate improvement suggestions"""
        suggestions = []

        # Size suggestions
        if pr.additions + pr.deletions > 500:
            suggestions.append("Consider breaking this PR into smaller, focused changes")
        elif pr.additions + pr.deletions > 200:
            suggestions.append("Large PR - consider splitting if possible")

        # Test suggestions
        has_tests = any("test" in f.filename.lower() for f in files)
        if not has_tests and (pr.additions + pr.deletions > 50):
            suggestions.append("Add tests for new functionality")

        # Description suggestions
        if not pr.body or len(pr.body) < 50:
            suggestions.append("Add a detailed PR description explaining the changes")

        # Commit message suggestions
        commits = list(pr.get_commits())
        if len(commits) > 10:
            suggestions.append("Consider squashing commits for cleaner history")

        # Branch naming
        if not re.match(r"^(feature|fix|hotfix|refactor|docs|test|chore)/", pr.head.ref):
            suggestions.append("Consider using conventional branch naming (feature/, fix/, etc.)")

        return suggestions

    def _check_security(self, pr, files) -> List[str]:
        """Check for security concerns"""
        concerns = []

        security_patterns = {
            "Hardcoded secrets": r"(password|secret|token|api_key|apikey|access_key)\s*=\s*[\"'][^\"']+[\"']",
            "SQL injection risk": r"(execute|query)\s*\(\s*[\"'].*\{.*\}.*[\"']",
            "XSS risk": r"dangerouslySetInnerHTML|innerHTML\s*=",
            "Insecure random": r"Math\.random\(\)",
            "Weak crypto": r"(md5|sha1)\s*\(",
        }

        for f in files:
            if f.patch:
                for concern, pattern in security_patterns.items():
                    if re.search(pattern, f.patch, re.IGNORECASE):
                        concerns.append(f"{concern} in {f.filename}")

        return concerns

    def _check_performance(self, pr, files) -> List[str]:
        """Check for performance concerns"""
        concerns = []

        perf_patterns = {
            "N+1 query risk": r"\.query\(\)|\.filter\(\)|\.all\(\)",  # In loops
            "Large data loading": r"\.load\(\)|\.fetchall\(\)",
            "Sync I/O in async": r"time\.sleep\(|requests\.(get|post)",
            "Missing pagination": r"\.limit\(\d{3,}\)",
        }

        for f in files:
            if f.patch:
                for concern, pattern in perf_patterns.items():
                    if re.search(pattern, f.patch, re.IGNORECASE):
                        concerns.append(f"{concern} in {f.filename}")

        return concerns

    def _check_style(self, pr, files) -> List[str]:
        """Check for style issues"""
        issues = []

        for f in files:
            if f.patch:
                lines = f.patch.split('\n')
                for i, line in enumerate(lines):
                    if line.startswith('+') and len(line) > 120:
                        issues.append(f"Line too long (>120 chars) in {f.filename}:{i}")
                    if line.startswith('+') and re.search(r'console\.log|print\(|debugger', line):
                        issues.append(f"Debug statement in {f.filename}:{i}")

        return issues[:10]  # Limit to 10

    def post_review(self, repo_name: str, pr_number: int,
                   decision: ReviewDecision, body: str = "",
                   comments: List[Dict] = None) -> bool:
        """Post a review on the PR"""
        try:
            pr = self.client.get_pr(repo_name, pr_number)
            if not pr:
                return False

            # PyGithub review creation
            pr.create_review(
                body=body,
                event=decision.value,
                comments=comments or []
            )
            logger.info(f"✅ Review posted: {repo_name}#{pr_number} - {decision.value}")
            return True
        except Exception as e:
            logger.error(f"❌ post_review failed: {e}")
            return False

    def add_line_comment(self, repo_name: str, pr_number: int,
                        file_path: str, line: int, body: str) -> bool:
        """Add a line-specific comment"""
        try:
            pr = self.client.get_pr(repo_name, pr_number)
            if not pr:
                return False

            # Get commit to comment on
            commits = list(pr.get_commits())
            if not commits:
                return False

            pr.create_comment(body)  # General comment for now
            # For line comments, need: pr.create_review_comment(body, commits[-1], file_path, line)
            logger.info(f"✅ Comment added: {repo_name}#{pr_number} - {file_path}:{line}")
            return True
        except Exception as e:
            logger.error(f"❌ add_line_comment failed: {e}")
            return False

    def auto_approve_if_safe(self, repo_name: str, pr_number: int,
                            max_risk: str = "low") -> bool:
        """Auto-approve PR if risk is low and checks pass"""
        analysis = self.analyze_pr(repo_name, pr_number)
        if not analysis:
            return False

        risk_order = {"low": 0, "medium": 1, "high": 2}
        if risk_order.get(analysis.risk_level, 2) <= risk_order.get(max_risk, 0):
            if analysis.checks_passing and analysis.mergeable:
                body = f"✅ Auto-approved by ARIA\n\nRisk: {analysis.risk_level}\nChecks: {'✅' if analysis.checks_passing else '❌'}"
                return self.post_review(repo_name, pr_number, ReviewDecision.APPROVE, body)

        return False

    def request_changes_with_reasons(self, repo_name: str, pr_number: int,
                                    reasons: List[str]) -> bool:
        """Request changes with specific reasons"""
        body = "❌ Changes requested by ARIA:\n\n" + "\n".join(f"- {r}" for r in reasons)
        return self.post_review(repo_name, pr_number, ReviewDecision.REQUEST_CHANGES, body)

    def get_pr_summary(self, repo_name: str, pr_number: int) -> Optional[Dict]:
        """Get a summary of PR for display"""
        analysis = self.analyze_pr(repo_name, pr_number)
        if not analysis:
            return None

        return {
            "pr_number": analysis.pr_number,
            "title": analysis.title,
            "author": analysis.author,
            "stats": {
                "files": analysis.files_changed,
                "additions": analysis.additions,
                "deletions": analysis.deletions,
            },
            "status": {
                "draft": analysis.is_draft,
                "mergeable": analysis.mergeable,
                "mergeable_state": analysis.mergeable_state,
                "checks_passing": analysis.checks_passing,
                "review_status": analysis.review_status,
            },
            "risk": analysis.risk_level,
            "suggestions": analysis.suggestions,
            "concerns": {
                "security": analysis.security_concerns,
                "performance": analysis.performance_concerns,
                "style": analysis.style_issues,
            }
        }