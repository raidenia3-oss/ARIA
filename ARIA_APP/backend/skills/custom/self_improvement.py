"""ARIA Self-Improvement Skill -- Autonomous GitHub-driven improvement loop."""

import logging
import os
import subprocess
import json
import sys
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

# Ensure backend and project root are in path
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
for p in (BACKEND_DIR, PROJECT_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(BACKEND_DIR / ".env")
except ImportError:
    pass

from github_admin import GitHubAdminClient, AutoCommit, AutoRelease, PRAnalyzer, IssueManager, DocGenerator
from backend.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)


class ARIASelfImprovement:
    """
    ARIA Self-Improvement Engine

    Uses GitHub Admin API to autonomously improve ARIA:
    - Auto-commit changes to ARIA repo
    - Analyze PRs for quality/security
    - Triaging issues (bugs, features)
    - Auto-release versions
    - Generate documentation
    - Create improvement proposals
    """

    def __init__(self):
        self.github_token = os.getenv("GITHUB_TOKEN", "")
        self.repo_name = "ARIA"
        # Root AURA directory (contains .git)
        self.repo_path = str(Path(__file__).resolve().parent.parent.parent.parent.parent)
        self.client = None
        self.auto_commit = None
        self.auto_release = None
        self.pr_analyzer = None
        self.issue_manager = None
        self._initialized = False

    def initialize(self):
        """Initialize GitHub clients"""
        if not self.github_token:
            logger.warning("[WARN] GITHUB_TOKEN not set - self-improvement disabled")
            return False

        try:
            self.client = GitHubAdminClient(token=self.github_token, org="raidenia3-oss")
            self.auto_commit = AutoCommit(token=self.github_token)
            self.auto_release = AutoRelease(github_client=self.client)
            self.pr_analyzer = PRAnalyzer(github_client=self.client)
            self.issue_manager = IssueManager(github_client=self.client)
            self._initialized = True
            logger.info("[OK] ARIA Self-Improvement initialized")
            return True
        except Exception as e:
            logger.error(f"[ERROR] Self-improvement init failed: {e}")
            return False

    def run_improvement_cycle(self, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Run a full self-improvement cycle

        Returns:
            Dict with results of each improvement action
        """
        if not self._initialized and not self.initialize():
            return {"error": "Not initialized"}

        p = params or {}
        auto_commit = p.get("auto_commit", True)
        analyze_prs = p.get("analyze_prs", True)
        triage_issues = p.get("triage_issues", True)
        auto_release = p.get("auto_release", False)
        gen_docs = p.get("gen_docs", False)

        results = {
            "timestamp": datetime.now().isoformat(),
            "repo": self.repo_name,
            "actions": [],
            "auto_commit": auto_commit,
            "analyze_prs": analyze_prs,
            "triage_issues": triage_issues,
            "auto_release": auto_release,
            "gen_docs": gen_docs,
        }

        # 1. Auto-commit any pending changes
        if auto_commit:
            commit_result = self._auto_commit_changes()
            results["actions"].append({"action": "auto_commit", **commit_result})

        # 2. Analyze open PRs
        if analyze_prs:
            pr_results = self._analyze_open_prs()
            results["actions"].append({"action": "analyze_prs", **pr_results})
        else:
            pr_results = {"status": "skipped"}
            results["actions"].append({"action": "analyze_prs", "status": "skipped"})

        # 3. Triaging open issues
        if triage_issues:
            issue_results = self._triaging_issues()
            results["actions"].append({"action": "triaging_issues", **issue_results})
        else:
            issue_results = {"status": "skipped"}
            results["actions"].append({"action": "triaging_issues", "status": "skipped"})

        # 4. Check for auto-release opportunity
        if auto_release:
            release_result = self._check_auto_release()
            results["actions"].append({"action": "auto_release", **release_result})
        else:
            release_result = {"status": "skipped"}
            results["actions"].append({"action": "auto_release", "status": "skipped"})

        # 5. Generate/update documentation
        if gen_docs:
            docs_result = self._generate_docs()
            results["actions"].append({"action": "generate_docs", **docs_result})
        else:
            docs_result = {"status": "skipped"}
            results["actions"].append({"action": "generate_docs", "status": "skipped"})

        # 6. Create improvement proposals
        proposals = self._create_improvement_proposals()
        results["actions"].append({"action": "improvement_proposals", "proposals": proposals})

        logger.info(f"[OK] Self-improvement cycle complete: {len(results['actions'])} actions")
        return results

    def _auto_commit_changes(self) -> Dict[str, Any]:
        """Auto-commit any uncommitted changes in ARIA repo"""
        try:
            if not os.path.exists(os.path.join(self.repo_path, ".git")):
                return {"status": "skipped", "reason": "Not a git repo"}

            from github_admin.auto_commit import CommitConfig

            config = CommitConfig(
                repo_path=self.repo_path,
                branch="main",
                push_after_commit=True
            )
            committed = self.auto_commit.auto_commit(
                self.repo_path,
                "[ARIA] self-improvement: auto-commit pending changes",
                config=config
            )
            return {"status": "committed" if committed else "no_changes"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _analyze_open_prs(self) -> Dict[str, Any]:
        """Analyze all open PRs for quality and auto-approve safe ones"""
        try:
            prs = self.client.list_prs(self.repo_name, state="open")
            analyzed = 0
            approved = 0
            for pr in prs:
                analysis = self.pr_analyzer.analyze_pr(self.repo_name, pr["number"])
                if analysis:
                    analyzed += 1
                    # Auto-approve if low risk and checks pass
                    if self.pr_analyzer.auto_approve_if_safe(self.repo_name, pr["number"], max_risk="low"):
                        approved += 1
                        logger.info(f"[OK] Auto-approved PR #{pr['number']}")
            return {"status": "complete", "analyzed": analyzed, "auto_approved": approved}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _triaging_issues(self) -> Dict[str, Any]:
        """Auto-triaging open issues"""
        try:
            result = self.issue_manager.bulk_triage(
                self.repo_name,
                state="open",
                apply_labels=True,
                apply_assignee=True,
                apply_milestone=True
            )
            return {"status": "complete", **result}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _check_auto_release(self) -> Dict[str, Any]:
        """Check if we should create a new release"""
        try:
            # Get latest release
            releases = self.client.list_releases(self.repo_name)
            if not releases:
                # First release
                result = self.auto_release.auto_release(
                    self.repo_name,
                    bump_type="minor",
                    changelog="Initial automated release by ARIA self-improvement"
                )
                return {"status": "released", "release": result} if result else {"status": "failed"}

            # Check if there are enough changes for a patch release
            latest = releases[0]
            # For now, just return status - actual release logic would check commits since last release
            return {"status": "checked", "latest_version": latest["tag"]}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _generate_docs(self) -> Dict[str, Any]:
        """Generate/update documentation files"""
        try:
            from github_admin import DocGenerator
            doc_gen = DocGenerator(github_client=self.client)

            # Generate all docs
            docs = doc_gen.generate_all_docs(self.repo_name)

            # Write to repo
            write_result = doc_gen.write_docs_to_repo(self.repo_name, docs)

            return {"status": "generated", "files": list(docs.keys()), "written": write_result}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _create_improvement_proposals(self) -> List[Dict]:
        """Analyze codebase and create improvement proposals as issues"""
        proposals = []

        try:
            # Check for TODO/FIXME comments
            todos = []
            for root, dirs, files in os.walk(self.repo_path):
                # Skip hidden dirs and __pycache__
                dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
                for f in files:
                    if f.endswith(('.py', '.js', '.ts', '.tsx', '.md')):
                        path = os.path.join(root, f)
                        try:
                            with open(path, 'r', encoding='utf-8', errors='ignore') as fp:
                                content = fp.read()
                                for match in re.finditer(r'(TODO|FIXME|HACK|BUG):\s*(.+)', content):
                                    todos.append({
                                        "file": os.path.relpath(path, self.repo_path),
                                        "type": match.group(1),
                                        "message": match.group(2)[:200]
                                    })
                        except Exception:
                            pass

            # Create issues for high-priority TODOs
            for todo in todos[:5]:  # Limit to 5 per cycle
                if todo["type"] in ("FIXME", "BUG"):
                    title = f"[{todo['type']}] {todo['message'][:80]}"
                    body = f"Auto-detected in `{todo['file']}`\n\n```\n{todo['message']}\n```"
                    result = self.client.create_issue(
                        self.repo_name,
                        title=title,
                        body=body,
                        labels=["auto-detected", todo["type"].lower()],
                        assignees=[]
                    )
                    if result:
                        proposals.append({"type": "issue", "title": title, "number": result.get("number")})

            return proposals
        except Exception as e:
            logger.error(f"Improvement proposals failed: {e}")
            return [{"error": str(e)}]

    def trigger_from_webhook(self, event: str, payload: Dict) -> Dict[str, Any]:
        """Handle webhook events for reactive improvements"""
        if not self._initialized and not self.initialize():
            return {"error": "Not initialized"}

        try:
            if event == "pull_request":
                action = payload.get("action")
                if action in ("opened", "synchronize"):
                    pr_number = payload["pull_request"]["number"]
                    analysis = self.pr_analyzer.analyze_pr(self.repo_name, pr_number)
                    if analysis and analysis.risk_level == "high":
                        self.pr_analyzer.request_changes_with_reasons(
                            self.repo_name, pr_number,
                            [f"High risk detected: {analysis.risk_level}", *analysis.security_concerns[:3]]
                        )
                    return {"status": "analyzed", "pr": pr_number, "risk": analysis.risk_level if analysis else "unknown"}

            elif event == "issues":
                action = payload.get("action")
                if action == "opened":
                    issue_number = payload["issue"]["number"]
                    self.issue_manager.triage_issue(self.repo_name, issue_number)
                    return {"status": "triaged", "issue": issue_number}

            elif event == "push":
                # Trigger auto-commit check on push
                self._auto_commit_changes()
                return {"status": "checked"}

            return {"status": "ignored", "event": event}
        except Exception as e:
            return {"status": "error", "error": str(e)}


# Singleton instance
_self_improvement = None


def get_self_improvement() -> ARIASelfImprovement:
    """Get or create self-improvement singleton"""
    global _self_improvement
    if _self_improvement is None:
        _self_improvement = ARIASelfImprovement()
    return _self_improvement


def run_self_improvement_cycle(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """Run a full self-improvement cycle"""
    engine = get_self_improvement()
    return engine.run_improvement_cycle()


def get_self_improvement_status(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """Get self-improvement engine status"""
    engine = get_self_improvement()
    return {
        "initialized": engine._initialized,
        "repo": engine.repo_name,
        "repo_path": engine.repo_path,
        "github_configured": bool(engine.github_token)
    }


def trigger_self_improvement(params: Dict[str, Any]) -> Dict[str, Any]:
    """Trigger specific improvement action"""
    engine = get_self_improvement()
    if not engine._initialized and not engine.initialize():
        return {"error": "Not initialized"}

    action = params.get("action", "cycle")
    if action == "commit":
        return engine._auto_commit_changes()
    elif action == "analyze_prs":
        return engine._analyze_open_prs()
    elif action == "triaging":
        return engine._triaging_issues()
    elif action == "release":
        return engine._check_auto_release()
    elif action == "docs":
        return engine._generate_docs()
    elif action == "proposals":
        return {"proposals": engine._create_improvement_proposals()}
    else:
        return engine.run_improvement_cycle(params)


# Module entry point for skill registry
def run(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """Main entry point for self-improvement skill"""
    action = (params or {}).get("action", "status")

    engine = get_self_improvement()
    if not engine._initialized and not engine.initialize():
        return {"error": "Not initialized", "github_configured": bool(engine.github_token)}

    if action == "cycle":
        return engine.run_improvement_cycle(params)
    elif action == "status":
        return {
            "initialized": engine._initialized,
            "repo": engine.repo_name,
            "repo_path": engine.repo_path,
            "github_configured": bool(engine.github_token)
        }
    elif action in ("commit", "analyze_prs", "triaging", "release", "docs", "proposals"):
        return trigger_self_improvement(params)
    else:
        return {"error": f"Unknown action: {action}"}