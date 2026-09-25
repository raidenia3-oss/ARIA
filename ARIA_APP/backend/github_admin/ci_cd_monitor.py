"""ARIA CI/CD Monitor — Track GitHub Actions workflows and deployments."""

import logging
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class WorkflowStatus(str, Enum):
    """Workflow run status"""
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    WAITING = "waiting"
    PENDING = "pending"


class WorkflowConclusion(str, Enum):
    """Workflow run conclusion"""
    SUCCESS = "success"
    FAILURE = "failure"
    NEUTRAL = "neutral"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
    TIMED_OUT = "timed_out"
    ACTION_REQUIRED = "action_required"


@dataclass
class WorkflowRunSummary:
    """Summary of a workflow run"""
    id: int
    name: str
    workflow_id: int
    status: str
    conclusion: Optional[str]
    branch: str
    commit_sha: str
    run_number: int
    event: str
    actor: str
    created_at: datetime
    updated_at: datetime
    run_started_at: Optional[datetime]
    duration_seconds: Optional[float]
    url: str
    jobs: List[Dict] = field(default_factory=list)


@dataclass
class DeploymentStatus:
    """Deployment status"""
    id: int
    sha: str
    ref: str
    task: str
    payload: Dict
    environment: str
    description: str
    creator: str
    created_at: datetime
    updated_at: datetime
    statuses: List[Dict]
    url: str


class CICDMonitor:
    """
    ARIA CI/CD Monitor
    Tracks GitHub Actions workflows, runs, and deployments
    """

    def __init__(self, github_client):
        self.client = github_client

    def get_workflow_health(self, repo_name: str, limit: int = 20) -> Dict:
        """Get overall workflow health for a repo"""
        try:
            runs = self.client.get_workflow_runs(repo_name, limit=limit)

            if not runs:
                return {"status": "no_data", "runs": []}

            # Analyze recent runs
            total = len(runs)
            successful = sum(1 for r in runs if r.get("conclusion") == "success")
            failed = sum(1 for r in runs if r.get("conclusion") == "failure")
            in_progress = sum(1 for r in runs if r.get("status") == "in_progress")

            success_rate = (successful / total * 100) if total > 0 else 0

            # Get unique workflows
            workflows = set(r["name"] for r in runs)
            workflow_stats = {}
            for wf_name in workflows:
                wf_runs = [r for r in runs if r["name"] == wf_name]
                wf_success = sum(1 for r in wf_runs if r.get("conclusion") == "success")
                wf_total = len(wf_runs)
                workflow_stats[wf_name] = {
                    "total": wf_total,
                    "success": wf_success,
                    "failed": wf_total - wf_success,
                    "success_rate": (wf_success / wf_total * 100) if wf_total > 0 else 0,
                    "last_run": wf_runs[0] if wf_runs else None
                }

            # Determine overall health
            if success_rate >= 90:
                health = "healthy"
            elif success_rate >= 70:
                health = "degraded"
            else:
                health = "critical"

            return {
                "status": health,
                "success_rate": round(success_rate, 1),
                "total_runs": total,
                "successful": successful,
                "failed": failed,
                "in_progress": in_progress,
                "workflows": workflow_stats,
                "runs": runs[:10]  # Recent 10
            }
        except Exception as e:
            logger.error(f"❌ get_workflow_health failed: {e}")
            return {"status": "error", "error": str(e)}

    def get_workflow_details(self, repo_name: str, workflow_name: str,
                           limit: int = 10) -> Optional[Dict]:
        """Get detailed info for a specific workflow"""
        try:
            workflows = self.client.list_workflows(repo_name)
            workflow = next((w for w in workflows if w["name"] == workflow_name), None)
            if not workflow:
                return None

            runs = self.client.get_workflow_runs(repo_name, workflow["id"], limit=limit)

            # Get job details for recent runs
            for run in runs[:5]:
                run["jobs"] = self._get_job_details(repo_name, run["id"])

            return {
                "workflow": workflow,
                "runs": runs,
                "stats": self._calculate_workflow_stats(runs)
            }
        except Exception as e:
            logger.error(f"❌ get_workflow_details failed: {e}")
            return None

    def _get_job_details(self, repo_name: str, run_id: int) -> List[Dict]:
        """Get job details for a workflow run (requires additional API call)"""
        # This would require a direct API call since PyGithub doesn't have direct support
        # For now, return empty list
        return []

    def _calculate_workflow_stats(self, runs: List[Dict]) -> Dict:
        """Calculate statistics for workflow runs"""
        if not runs:
            return {}

        total = len(runs)
        successful = sum(1 for r in runs if r.get("conclusion") == "success")
        failed = sum(1 for r in runs if r.get("conclusion") == "failure")

        # Average duration
        durations = []
        for r in runs:
            if r.get("run_started_at") and r.get("updated_at"):
                try:
                    start = datetime.fromisoformat(r["run_started_at"].replace('Z', '+00:00'))
                    end = datetime.fromisoformat(r["updated_at"].replace('Z', '+00:00'))
                    durations.append((end - start).total_seconds())
                except Exception:
                    pass

        avg_duration = sum(durations) / len(durations) if durations else 0

        return {
            "total_runs": total,
            "success_rate": round(successful / total * 100, 1) if total > 0 else 0,
            "avg_duration_seconds": round(avg_duration, 1),
            "avg_duration_minutes": round(avg_duration / 60, 1),
            "last_success": next((r for r in runs if r.get("conclusion") == "success"), None),
            "last_failure": next((r for r in runs if r.get("conclusion") == "failure"), None),
        }

    def get_failing_workflows(self, repo_name: str, limit: int = 50) -> List[Dict]:
        """Get list of currently failing workflow runs"""
        try:
            runs = self.client.get_workflow_runs(repo_name, limit=limit)
            failing = [r for r in runs if r.get("conclusion") == "failure"]
            return failing
        except Exception as e:
            logger.error(f"❌ get_failing_workflows failed: {e}")
            return []

    def get_recent_deployments(self, repo_name: str, limit: int = 20) -> List[Dict]:
        """Get recent deployments"""
        try:
            repo = self.client.get_repo(repo_name)
            if not repo:
                return []

            deployments = []
            for dep in repo.get_deployments()[:limit]:
                statuses = []
                for status in dep.get_statuses():
                    statuses.append({
                        "state": status.state,
                        "description": status.description,
                        "environment_url": status.environment_url,
                        "created_at": status.created_at.isoformat() if status.created_at else None,
                    })

                deployments.append({
                    "id": dep.id,
                    "sha": dep.sha,
                    "ref": dep.ref,
                    "task": dep.task,
                    "environment": dep.environment,
                    "description": dep.description,
                    "creator": dep.creator.login if dep.creator else None,
                    "created_at": dep.created_at.isoformat() if dep.created_at else None,
                    "statuses": statuses,
                    "url": dep.url,
                })

            return deployments
        except Exception as e:
            logger.error(f"❌ get_recent_deployments failed: {e}")
            return []

    def get_deployment_status(self, repo_name: str, environment: str = None) -> Dict:
        """Get current deployment status for environments"""
        try:
            deployments = self.get_recent_deployments(repo_name, limit=50)

            env_status = {}
            for dep in deployments:
                env = dep["environment"]
                if environment and env != environment:
                    continue

                if env not in env_status:
                    # Get latest status for this environment
                    latest_status = dep["statuses"][0] if dep["statuses"] else {"state": "unknown"}
                    env_status[env] = {
                        "current_sha": dep["sha"],
                        "status": latest_status["state"],
                        "last_deployment": dep["created_at"],
                        "url": dep.get("statuses", [{}])[0].get("environment_url") if dep["statuses"] else None,
                    }

            return env_status
        except Exception as e:
            logger.error(f"❌ get_deployment_status failed: {e}")
            return {}

    def trigger_workflow(self, repo_name: str, workflow_name: str,
                        branch: str = "main", inputs: Dict = None) -> bool:
        """Manually trigger a workflow dispatch"""
        try:
            workflows = self.client.list_workflows(repo_name)
            workflow = next((w for w in workflows if w["name"] == workflow_name), None)
            if not workflow:
                logger.error(f"❌ Workflow not found: {workflow_name}")
                return False

            return self.client.trigger_workflow(repo_name, workflow["id"], branch, inputs or {})
        except Exception as e:
            logger.error(f"❌ trigger_workflow failed: {e}")
            return False

    def cancel_workflow_run(self, repo_name: str, run_id: int) -> bool:
        """Cancel a running workflow"""
        try:
            repo = self.client.get_repo(repo_name)
            if not repo:
                return False

            run = repo.get_workflow_run(run_id)
            run.cancel()
            logger.info(f"✅ Workflow run cancelled: {repo_name}#{run_id}")
            return True
        except Exception as e:
            logger.error(f"❌ cancel_workflow_run failed: {e}")
            return False

    def rerun_failed_workflow(self, repo_name: str, run_id: int) -> bool:
        """Re-run a failed workflow"""
        try:
            repo = self.client.get_repo(repo_name)
            if not repo:
                return False

            run = repo.get_workflow_run(run_id)
            if run.conclusion != "failure":
                logger.warning(f"⚠️ Can only rerun failed workflows: {run_id}")
                return False

            run.rerun()
            logger.info(f"✅ Workflow re-run triggered: {repo_name}#{run_id}")
            return True
        except Exception as e:
            logger.error(f"❌ rerun_failed_workflow failed: {e}")
            return False

    def get_workflow_trends(self, repo_name: str, days: int = 30) -> Dict:
        """Get workflow trends over time"""
        try:
            runs = self.client.get_workflow_runs(repo_name, limit=200)
            cutoff = datetime.now() - timedelta(days=days)

            daily_stats = defaultdict(lambda: {"total": 0, "success": 0, "failed": 0})

            for run in runs:
                try:
                    created = datetime.fromisoformat(run["created_at"].replace('Z', '+00:00'))
                    if created < cutoff:
                        continue

                    day_key = created.strftime("%Y-%m-%d")
                    daily_stats[day_key]["total"] += 1

                    if run.get("conclusion") == "success":
                        daily_stats[day_key]["success"] += 1
                    elif run.get("conclusion") == "failure":
                        daily_stats[day_key]["failed"] += 1
                except Exception:
                    pass

            # Convert to list sorted by date
            trend = [
                {"date": day, **stats}
                for day, stats in sorted(daily_stats.items())
            ]

            return {
                "period_days": days,
                "daily_trend": trend,
                "summary": {
                    "total_runs": sum(d["total"] for d in daily_stats.values()),
                    "total_success": sum(d["success"] for d in daily_stats.values()),
                    "total_failed": sum(d["failed"] for d in daily_stats.values()),
                }
            }
        except Exception as e:
            logger.error(f"❌ get_workflow_trends failed: {e}")
            return {"daily_trend": [], "summary": {}}

    def check_required_checks(self, repo_name: str, pr_number: int) -> Dict:
        """Check if all required status checks pass for a PR"""
        try:
            checks = self.client.get_pr_checks(repo_name, pr_number)
            repo = self.client.get_repo(repo_name)
            branch = repo.get_branch("main")  # Get default branch protection

            # Get required contexts from branch protection
            required_contexts = []
            try:
                protection = branch.get_protection()
                if protection.required_status_checks:
                    required_contexts = protection.required_status_checks.contexts
            except Exception:
                pass

            # Check each required context
            check_results = {}
            all_passing = True

            for context in required_contexts:
                matching = [c for c in checks if c["name"] == context]
                if matching:
                    check_results[context] = matching[0]
                    if matching[0].get("conclusion") != "success":
                        all_passing = False
                else:
                    check_results[context] = {"status": "missing", "conclusion": None}
                    all_passing = False

            return {
                "all_passing": all_passing,
                "required_contexts": required_contexts,
                "checks": check_results,
                "total_checks": len(checks),
                "passing_checks": sum(1 for c in checks if c.get("conclusion") == "success"),
            }
        except Exception as e:
            logger.error(f"❌ check_required_checks failed: {e}")
            return {"all_passing": False, "error": str(e)}

    def get_queue_status(self, repo_name: str) -> Dict:
        """Get workflow queue status (in-progress + queued)"""
        try:
            runs = self.client.get_workflow_runs(repo_name, limit=50)

            queued = [r for r in runs if r.get("status") in ("queued", "waiting", "pending")]
            in_progress = [r for r in runs if r.get("status") == "in_progress"]

            return {
                "queued_count": len(queued),
                "in_progress_count": len(in_progress),
                "queued": queued[:10],
                "in_progress": in_progress[:10],
                "estimated_wait": len(queued) * 5  # Rough estimate in minutes
            }
        except Exception as e:
            logger.error(f"❌ get_queue_status failed: {e}")
            return {"queued_count": 0, "in_progress_count": 0}