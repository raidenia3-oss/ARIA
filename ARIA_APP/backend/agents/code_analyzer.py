# -*- coding: utf-8 -*-
"""ARIA OS - CodeAnalyzer Agent.

Analyzes pull requests, code quality, refactoring opportunities,
and provides recommendations for improvement.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from agents.base import Agent

logger = logging.getLogger("ARIA.Agents.CodeAnalyzer")


class CodeAnalyzerAgent(Agent):
    """Analyzes code quality, PRs, and refactoring opportunities."""

    def __init__(self):
        super().__init__(
            name="CodeAnalyzer",
            role="Analyzes code quality, PRs, refactoring opportunities",
        )

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a PR or code snippet."""
        pr_number = task.get("pr_number")
        repo = task.get("repo", "raidenia3-oss/ARIA")
        code = task.get("code", "")
        files = task.get("files", [])

        # If we have actual code, run lightweight analysis
        issues = []
        recommendations = []
        complexity = "low"
        approved = True

        if code:
            # Basic heuristic analysis
            lines = code.split("\n")
            loc = len(lines)

            # Check for long functions (>50 lines)
            if loc > 50:
                issues.append({
                    "severity": "B",
                    "message": f"File has {loc} lines — consider splitting into modules",
                })
                recommendations.append("Split into smaller modules")
                approved = False

            # Check for TODO/FIXME
            todos = [l for l in lines if "TODO" in l or "FIXME" in l]
            if todos:
                issues.append({
                    "severity": "C",
                    "message": f"{len(todos)} TODO/FIXME comments found",
                })

            # Check for bare except
            bare_excepts = [l for l in lines if "except:" in l and "except Exception" not in l]
            if bare_excepts:
                issues.append({
                    "severity": "A",
                    "message": f"{len(bare_excepts)} bare except clauses — catch specific exceptions",
                })
                recommendations.append("Catch specific exception types")
                approved = False

            complexity = "high" if loc > 200 else "medium" if loc > 50 else "low"

        if pr_number:
            recommendations.append(f"Review PR #{pr_number} in {repo}")

        return {
            "pr": pr_number,
            "repo": repo,
            "complexity": complexity,
            "issues": len(issues),
            "issue_details": issues,
            "recommendations": recommendations,
            "approved": approved,
            "files_analyzed": len(files),
        }