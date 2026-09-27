"""ARIA Self-Improvement Skill -- Autonomous GitHub-driven improvement loop."""

import asyncio
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

# Phase H.5: Graceful imports — modules may not exist in all deployments
try:
    from github_admin import GitHubAdminClient, AutoCommit, AutoRelease, PRAnalyzer, IssueManager, DocGenerator
except ImportError:
    GitHubAdminClient = AutoCommit = AutoRelease = PRAnalyzer = IssueManager = DocGenerator = None

from backend.skills.registry import SkillRegistry

try:
    from api.agent_harness import harness
except ImportError:
    harness = None

try:
    from api.swarm_router import get_swarm, skill_registry
except ImportError:
    get_swarm = None
    skill_registry = None

logger = logging.getLogger(__name__)

# Phase H.5: Pi Agent skill-to-agent dispatch map
SKILL_AGENT_MAP = {
    "code-review": "CodeAnalyzer",
    "docs": "DocsWriter",
    "test": "Tester",
    "research": "ResearchAgent",
}

# Phase H.5: Custom prompt templates per skill (Pi Agent pattern)
SKILL_PROMPTS = {
    "code-review": "Review the following code changes for quality, security vulnerabilities, "
                  "performance issues, and adherence to best practices. Be thorough and specific.",
    "docs": "Generate comprehensive, well-structured documentation for the following changes. "
            "Include clear headings, code examples, and usage instructions.",
    "test": "Write and execute thorough tests for the following features. "
            "Report test coverage percentage and any failures with detailed error messages.",
    "research": "Research the given topic or URL across social media and web sources. "
                "Analyze content importance, classify topics, and extract key insights.",
}

# Phase H.5: LongMemory session tracking
_LM_SESSION_ID = None


def _get_lm_session_id() -> str:
    """Get or create a LongMemory session for this improvement cycle."""
    global _LM_SESSION_ID
    if _LM_SESSION_ID is None:
        _LM_SESSION_ID = f"auto-improve-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    return _LM_SESSION_ID


async def _store_session_memory(results: Dict[str, Any]):
    """Store improvement cycle results in LongMemory (Pi Agent session pattern)."""
    try:
        import urllib.request
        import json as _json
        lm_url = os.environ.get("LONGMEMORY_URL", "http://127.0.0.1:7331")
        payload = _json.dumps({
            "user_id": "aria",
            "text": f"Auto-improvement cycle {_get_lm_session_id()}: {results.get('actions', [])}",
            "metadata": {
                "type": "session",
                "session_id": _get_lm_session_id(),
                "cycle_timestamp": results.get("timestamp", ""),
            },
            "facet_hint": "episodic",
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{lm_url}/v1/ingest",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass  # Best-effort — LongMemory may not be running
    except Exception:
        pass


def _detect_changed_skills(commits: List[str]) -> List[str]:
    """Map changed files to skill categories for swarm dispatch."""
    changed_skills = []
    skill_keywords = {
        "code-review": [".py", ".js", ".ts", ".tsx", ".jsx"],
        "docs": [".md", "README", "docs/", "CHANGELOG"],
        "test": ["test", "spec", "tests/"],
        "research": ["research", "social", "video"],
    }
    for commit in commits:
        for skill, extensions in skill_keywords.items():
            if any(ext in commit.lower() for ext in extensions):
                if skill not in changed_skills:
                    changed_skills.append(skill)
    return changed_skills


async def _dispatch_swarm_agents(changed_skills: List[str], commit_hash: str = "") -> List[Dict]:
    """Dispatch swarm agents based on detected changed skills (Phase H.5)."""
    swarm = get_swarm()
    tasks = []
    for skill in changed_skills:
        agent_name = skill_registry.get_agent_for_skill(skill)
        if agent_name:
            prompt = SKILL_PROMPTS.get(skill, "")
            tasks.append({
                "skill": skill,
                "agent": agent_name,
                "commit": commit_hash,
                "system_prompt": prompt,
            })
    if not tasks:
        return []
    try:
        results = await swarm.execute_parallel(tasks)
        return results
    except Exception as e:
        logger.error(f"Swarm dispatch failed: {e}")
        return [{"status": "error", "error": str(e)}]


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
        if GitHubAdminClient is None:
            logger.warning("[WARN] github_admin module not available - self-improvement disabled")
            return False
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

        # NUEVO: Integrar Pi Agent harness
        agent_config = harness.get_agent_config("self-improvement")
        print(f"Agent running with skills: {[s['name'] for s in agent_config['skills']]}")
        print(f"Custom prompt loaded: {agent_config['prompt'][:50]}...")
        print(f"MCP servers available: {list(agent_config['mcp_servers'].keys())}")

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

        # Phase H.5: Dispatch swarm agents based on changed skills
        try:
            # Get recent commits to detect changed skills
            recent_commits = []
            try:
                commit_result = subprocess.run(
                    ["git", "log", "--oneline", "-5"],
                    cwd=self.repo_path, capture_output=True, text=True, timeout=5
                )
                if commit_result.returncode == 0:
                    recent_commits = commit_result.stdout.strip().split("\n")
            except Exception:
                pass

            changed_skills = _detect_changed_skills(recent_commits)
            if changed_skills:
                swarm_results = asyncio.run(_dispatch_swarm_agents(changed_skills))
                results["actions"].append({
                    "action": "swarm_dispatch",
                    "skills_detected": changed_skills,
                    "results": swarm_results,
                })
                logger.info(f"[H.5] Swarm dispatched for skills: {changed_skills}")
        except Exception as e:
            logger.warning(f"[H.5] Swarm dispatch skipped: {e}")

        # Phase H.5: Store session in LongMemory
        try:
            asyncio.run(_store_session_memory(results))
        except Exception:
            pass

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
                branch="master",
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
            error_msg = str(e) if str(e) else repr(e)
            logger.error(f"Improvement proposals failed: {error_msg}")
            return [{"error": error_msg}]

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