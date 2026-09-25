"""ARIA GitHub Admin Router — FastAPI routes for all GitHub admin capabilities."""

from fastapi import APIRouter, HTTPException, Header, Request, Query, Body
from typing import Optional, List, Dict, Any
import os
import logging

from .github_client import GitHubAdminClient
from .auto_commit import AutoCommit, CommitConfig
from .auto_release import AutoRelease, ReleaseConfig
from .webhook_handler import WebhookHandler, setup_default_handlers
from .pr_analyzer import PRAnalyzer, ReviewDecision
from .issue_manager import IssueManager
from .ci_cd_monitor import CICDMonitor
from .doc_generator import DocGenerator
from .config_manager import ConfigManager, BranchProtectionConfig, RepoSettings, PermissionLevel
from .admin_dashboard import AdminDashboard

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/github", tags=["GitHub Admin"])

# ─── Initialization ───
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "dev-secret")

client = GitHubAdminClient(token=GITHUB_TOKEN) if GITHUB_TOKEN else None
auto_commit = AutoCommit(token=GITHUB_TOKEN)
auto_release = AutoRelease(github_client=client) if client else None
webhook = WebhookHandler(webhook_secret=WEBHOOK_SECRET, github_client=client) if client else None
pr_analyzer = PRAnalyzer(github_client=client) if client else None
issue_manager = IssueManager(github_client=client) if client else None
ci_cd_monitor = CICDMonitor(github_client=client) if client else None
doc_generator = DocGenerator(github_client=client) if client else None
config_manager = ConfigManager(github_client=client) if client else None
admin_dashboard = AdminDashboard(
    github_client=client,
    webhook_handler=webhook,
    pr_analyzer=pr_analyzer,
    issue_manager=issue_manager,
    ci_cd_monitor=ci_cd_monitor,
    doc_generator=doc_generator,
    config_manager=config_manager,
    auto_commit=auto_commit,
    auto_release=auto_release
) if client else None

# Setup default webhook handlers
if webhook and client:
    setup_default_handlers(webhook, client)


def _require_client():
    """Check if GitHub client is initialized."""
    if not client:
        raise HTTPException(status_code=503, detail="GitHub client not initialized. Set GITHUB_TOKEN env var.")
    return client


# ─── Repository Endpoints ───
@router.get("/repos")
async def list_repos():
    """List all repositories in the organization."""
    _require_client()
    return {"repos": client.list_repos()}


@router.post("/repos")
async def create_repo(
    name: str = Body(...),
    description: str = Body(""),
    private: bool = Body(False),
    auto_init: bool = Body(True),
    has_issues: bool = Body(True),
    has_wiki: bool = Body(False),
    has_projects: bool = Body(True)
):
    """Create a new repository."""
    _require_client()
    result = client.create_repo(name, description, private, auto_init, has_issues, has_wiki, has_projects)
    if result:
        return {"status": "created", "repo": result}
    raise HTTPException(status_code=400, detail="Failed to create repo")


@router.delete("/repos/{repo_name}")
async def delete_repo(repo_name: str):
    """Delete a repository (⚠️ DESTRUCTIVE)."""
    _require_client()
    if client.delete_repo(repo_name):
        return {"status": "deleted"}
    raise HTTPException(status_code=400, detail="Failed to delete repo")


@router.get("/repos/{repo_name}/stats")
async def get_repo_stats(repo_name: str):
    """Get repository statistics."""
    _require_client()
    stats = client.get_repo_stats(repo_name)
    if stats:
        return stats
    raise HTTPException(status_code=404, detail="Repo not found")


@router.patch("/repos/{repo_name}")
async def update_repo(repo_name: str, settings: RepoSettings):
    """Update repository settings."""
    _require_client()
    settings.name = repo_name
    if config_manager.update_repo_settings(repo_name, settings):
        return {"status": "updated"}
    raise HTTPException(status_code=400, detail="Failed to update repo")


@router.post("/repos/{repo_name}/apply-profile")
async def apply_repo_profile(repo_name: str, profile: str = Body(...)):
    """Apply standard settings profile (standard, open_source, private_team, archived)."""
    _require_client()
    if config_manager.apply_standard_settings(repo_name, profile):
        return {"status": "applied", "profile": profile}
    raise HTTPException(status_code=400, detail="Failed to apply profile")


# ─── Branch Protection Endpoints ───
@router.post("/{repo_name}/protect-branch")
async def protect_branch(
    repo_name: str,
    branch: str = Body("main"),
    required_reviews: int = Body(1),
    dismiss_stale: bool = Body(True),
    require_status_checks: bool = Body(True),
    status_contexts: List[str] = Body([]),
    enforce_admins: bool = Body(True),
    require_linear_history: bool = Body(True),
    allow_force_pushes: bool = Body(False),
    allow_deletions: bool = Body(False)
):
    """Enable branch protection rules."""
    _require_client()
    config = BranchProtectionConfig(
        branch=branch,
        required_reviews=required_reviews,
        dismiss_stale_reviews=dismiss_stale,
        required_status_checks=status_contexts if require_status_checks else [],
        strict_status_checks=True,
        enforce_admins=enforce_admins,
        require_linear_history=require_linear_history,
        allow_force_pushes=allow_force_pushes,
        allow_deletions=allow_deletions
    )
    if config_manager.set_branch_protection(repo_name, config):
        return {"status": "protected", "branch": branch}
    raise HTTPException(status_code=400, detail="Failed to enable branch protection")


@router.post("/{repo_name}/protection-profile")
async def apply_protection_profile(repo_name: str, branch: str = Body("main"), profile: str = Body("standard")):
    """Apply branch protection profile (strict, standard, lenient, open_source)."""
    _require_client()
    if config_manager.apply_protection_profile(repo_name, branch, profile):
        return {"status": "applied", "branch": branch, "profile": profile}
    raise HTTPException(status_code=400, detail="Failed to apply protection profile")


@router.get("/{repo_name}/protection")
async def get_branch_protection(repo_name: str, branch: str = "main"):
    """Get current branch protection config."""
    _require_client()
    config = config_manager.get_branch_protection(repo_name, branch)
    if config:
        return config.__dict__
    raise HTTPException(status_code=404, detail="No branch protection configured")


# ─── Auto-Commit Endpoints ───
@router.post("/auto-commit")
async def trigger_auto_commit(
    repo_path: str = Body(...),
    message: str = Body(""),
    files: Optional[List[str]] = Body(None),
    branch: str = Body("main"),
    push_after_commit: bool = Body(True)
):
    """Manually trigger auto-commit."""
    config = CommitConfig(
        repo_path=repo_path,
        branch=branch,
        push_after_commit=push_after_commit
    )
    if auto_commit.auto_commit(repo_path, message, files, config):
        return {"status": "committed"}
    raise HTTPException(status_code=400, detail="Auto-commit failed")


@router.post("/monitor")
async def start_monitor(
    repo_path: str = Body(...),
    interval_minutes: int = Body(30),
    message_template: str = Body("🤖 ARIA: {timestamp}"),
    branch: str = Body("main"),
    push_after_commit: bool = Body(True)
):
    """Start monitoring repo for changes."""
    config = CommitConfig(
        repo_path=repo_path,
        interval_minutes=interval_minutes,
        message_template=message_template,
        branch=branch,
        push_after_commit=push_after_commit
    )
    thread = auto_commit.monitor_and_commit(repo_path, interval_minutes, message_template, config)
    return {"status": "monitoring", "interval": f"{interval_minutes}min"}


@router.post("/monitor/stop")
async def stop_monitor(repo_path: str = Body(...)):
    """Stop monitoring a repo."""
    if auto_commit.stop_monitor(repo_path):
        return {"status": "stopped"}
    raise HTTPException(status_code=404, detail="Monitor not found")


@router.get("/monitor/status")
async def get_monitor_status():
    """Get status of all active monitors."""
    return auto_commit.get_status()


# ─── Auto-Release Endpoints ───
@router.post("/auto-release/{repo_name}")
async def trigger_auto_release(
    repo_name: str,
    bump_type: str = Body("patch"),
    changelog: str = Body(""),
    draft: bool = Body(False),
    prerelease: bool = Body(False),
    target_branch: str = Body("main"),
    assets: Optional[List[str]] = Body(None),
    generate_changelog: bool = Body(True)
):
    """Auto-create release with version bump."""
    _require_client()
    config = ReleaseConfig(
        repo_name=repo_name,
        bump_type=bump_type,
        changelog=changelog,
        draft=draft,
        prerelease=prerelease,
        target_branch=target_branch,
        assets=assets,
        generate_changelog=generate_changelog
    )
    result = auto_release.auto_release(repo_name, bump_type, changelog, config)
    if result:
        return {"status": "released", "release": result}
    raise HTTPException(status_code=400, detail="Auto-release failed")


@router.post("/auto-release/prerelease/{repo_name}")
async def create_prerelease(repo_name: str, base_version: str = Body(...), label: str = Body("beta")):
    """Create a prerelease version."""
    _require_client()
    result = auto_release.create_prerelease(repo_name, base_version, label)
    if result:
        return {"status": "prereleased", "release": result}
    raise HTTPException(status_code=400, detail="Prerelease failed")


@router.post("/auto-release/promote/{repo_name}")
async def promote_prerelease(repo_name: str, prerelease_tag: str = Body(...), bump_type: str = Body("patch")):
    """Promote a prerelease to stable."""
    _require_client()
    result = auto_release.promote_prerelease(repo_name, prerelease_tag, bump_type)
    if result:
        return {"status": "promoted", "release": result}
    raise HTTPException(status_code=400, detail="Promotion failed")


@router.get("/releases/{repo_name}")
async def list_releases(repo_name: str, include_drafts: bool = False, include_prereleases: bool = False):
    """List releases."""
    _require_client()
    releases = auto_release.list_releases(repo_name, include_drafts, include_prereleases)
    return {"releases": releases}


@router.get("/releases/{repo_name}/latest")
async def get_latest_release(repo_name: str):
    """Get latest release."""
    _require_client()
    release = client.get_latest_release(repo_name)
    if release:
        return release
    raise HTTPException(status_code=404, detail="No releases found")


# ─── PR Management Endpoints ───
@router.get("/{repo_name}/prs")
async def list_prs(repo_name: str, state: str = "open", sort: str = "updated", direction: str = "desc"):
    """List pull requests."""
    _require_client()
    return {"prs": client.list_prs(repo_name, state, sort, direction)}


@router.get("/{repo_name}/prs/{pr_number}")
async def get_pr(repo_name: str, pr_number: int):
    """Get PR details."""
    _require_client()
    pr = client.get_pr(repo_name, pr_number)
    if pr:
        return {"number": pr.number, "title": pr.title, "author": pr.user.login}
    raise HTTPException(status_code=404, detail="PR not found")


@router.post("/{repo_name}/prs/{pr_number}/merge")
async def merge_pr(
    repo_name: str,
    pr_number: int,
    commit_title: str = Body(""),
    commit_message: str = Body(""),
    merge_method: str = Body("squash")
):
    """Auto-merge PR."""
    _require_client()
    if client.merge_pr(repo_name, pr_number, commit_title, commit_message, merge_method):
        return {"status": "merged"}
    raise HTTPException(status_code=400, detail="Merge failed")


@router.post("/{repo_name}/prs/{pr_number}/close")
async def close_pr(repo_name: str, pr_number: int):
    """Close PR without merging."""
    _require_client()
    if client.close_pr(repo_name, pr_number):
        return {"status": "closed"}
    raise HTTPException(status_code=400, detail="Close failed")


@router.post("/{repo_name}/prs/{pr_number}/analyze")
async def analyze_pr(repo_name: str, pr_number: int):
    """Analyze PR for quality, security, and best practices."""
    _require_client()
    analysis = pr_analyzer.analyze_pr(repo_name, pr_number)
    if analysis:
        return analysis.__dict__
    raise HTTPException(status_code=404, detail="PR not found or analysis failed")


@router.post("/{repo_name}/prs/{pr_number}/review")
async def review_pr(
    repo_name: str,
    pr_number: int,
    decision: str = Body(...),
    body: str = Body(""),
    comments: Optional[List[Dict]] = Body(None)
):
    """Post a review on the PR."""
    _require_client()
    try:
        review_decision = ReviewDecision(decision.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid decision. Use: APPROVE, REQUEST_CHANGES, COMMENT")
    
    if pr_analyzer.post_review(repo_name, pr_number, review_decision, body, comments):
        return {"status": "reviewed", "decision": decision}
    raise HTTPException(status_code=400, detail="Review failed")


@router.post("/{repo_name}/prs/{pr_number}/auto-approve")
async def auto_approve_pr(repo_name: str, pr_number: int, max_risk: str = Body("low")):
    """Auto-approve PR if risk is low and checks pass."""
    _require_client()
    if pr_analyzer.auto_approve_if_safe(repo_name, pr_number, max_risk):
        return {"status": "approved"}
    raise HTTPException(status_code=400, detail="Auto-approval conditions not met")


# ─── Issue Management Endpoints ───
@router.get("/{repo_name}/issues")
async def list_issues(repo_name: str, state: str = "open", labels: Optional[List[str]] = Query(None), sort: str = "updated"):
    """List issues."""
    _require_client()
    return {"issues": client.list_issues(repo_name, state, labels, sort)}


@router.post("/{repo_name}/issues")
async def create_issue(
    repo_name: str,
    title: str = Body(...),
    body: str = Body(""),
    labels: Optional[List[str]] = Body(None),
    assignees: Optional[List[str]] = Body(None),
    milestone: Optional[str] = Body(None)
):
    """Create an issue."""
    _require_client()
    result = client.create_issue(repo_name, title, body, labels, assignees, milestone)
    if result:
        return {"status": "created", "issue": result}
    raise HTTPException(status_code=400, detail="Failed to create issue")


@router.patch("/{repo_name}/issues/{issue_number}")
async def update_issue(repo_name: str, issue_number: int, **kwargs):
    """Update an issue."""
    _require_client()
    if client.update_issue(repo_name, issue_number, **kwargs):
        return {"status": "updated"}
    raise HTTPException(status_code=400, detail="Failed to update issue")


@router.post("/{repo_name}/issues/{issue_number}/close")
async def close_issue(repo_name: str, issue_number: int):
    """Close an issue."""
    _require_client()
    if client.close_issue(repo_name, issue_number):
        return {"status": "closed"}
    raise HTTPException(status_code=400, detail="Failed to close issue")


@router.post("/{repo_name}/issues/{issue_number}/labels")
async def add_labels(repo_name: str, issue_number: int, labels: List[str] = Body(...)):
    """Add labels to issue."""
    _require_client()
    if client.add_labels(repo_name, issue_number, labels):
        return {"status": "labels_added"}
    raise HTTPException(status_code=400, detail="Failed to add labels")


@router.delete("/{repo_name}/issues/{issue_number}/labels/{label}")
async def remove_label(repo_name: str, issue_number: int, label: str):
    """Remove label from issue."""
    _require_client()
    if client.remove_label(repo_name, issue_number, label):
        return {"status": "label_removed"}
    raise HTTPException(status_code=400, detail="Failed to remove label")


@router.post("/{repo_name}/issues/{issue_number}/analyze")
async def analyze_issue(repo_name: str, issue_number: int):
    """Analyze issue and suggest labels, priority, etc."""
    _require_client()
    analysis = issue_manager.analyze_issue(repo_name, issue_number)
    if analysis:
        return analysis.__dict__
    raise HTTPException(status_code=404, detail="Issue not found or analysis failed")


@router.post("/{repo_name}/issues/{issue_number}/triage")
async def triage_issue(
    repo_name: str,
    issue_number: int,
    apply_labels: bool = Body(True),
    apply_assignee: bool = Body(True),
    apply_milestone: bool = Body(True)
):
    """Auto-triage an issue based on rules."""
    _require_client()
    if issue_manager.triage_issue(repo_name, issue_number, apply_labels, apply_assignee, apply_milestone):
        return {"status": "triaged"}
    raise HTTPException(status_code=400, detail="Triage failed")


@router.post("/{repo_name}/issues/bulk-triage")
async def bulk_triage(repo_name: str, state: str = Body("open"), apply_labels: bool = Body(True), apply_assignee: bool = Body(True), apply_milestone: bool = Body(True)):
    """Triage all issues in a repo."""
    _require_client()
    results = issue_manager.bulk_triage(repo_name, state, apply_labels, apply_assignee, apply_milestone)
    return results


@router.post("/{repo_name}/issues/from-template")
async def create_issue_from_template(repo_name: str, template_name: str = Body(...), variables: Dict[str, str] = Body(...)):
    """Create issue from template (bug_report, feature_request)."""
    _require_client()
    result = issue_manager.create_issue_from_template(repo_name, template_name, variables)
    if result:
        return {"status": "created", "issue": result}
    raise HTTPException(status_code=400, detail="Failed to create issue from template")


@router.get("/{repo_name}/issues/stats")
async def get_issue_stats(repo_name: str, days: int = 30):
    """Get issue statistics."""
    _require_client()
    return issue_manager.get_issue_stats(repo_name, days)


# ─── CI/CD Endpoints ───
@router.get("/{repo_name}/workflows")
async def list_workflows(repo_name: str):
    """List GitHub Actions workflows."""
    _require_client()
    return {"workflows": client.list_workflows(repo_name)}


@router.get("/{repo_name}/workflows/health")
async def get_workflow_health(repo_name: str, limit: int = 20):
    """Get overall workflow health."""
    _require_client()
    return ci_cd_monitor.get_workflow_health(repo_name, limit)


@router.get("/{repo_name}/workflows/{workflow_name}")
async def get_workflow_details(repo_name: str, workflow_name: str, limit: int = 10):
    """Get detailed info for a specific workflow."""
    _require_client()
    details = ci_cd_monitor.get_workflow_details(repo_name, workflow_name, limit)
    if details:
        return details
    raise HTTPException(status_code=404, detail="Workflow not found")


@router.post("/{repo_name}/workflows/{workflow_name}/trigger")
async def trigger_workflow(repo_name: str, workflow_name: str, branch: str = Body("main"), inputs: Optional[Dict] = Body(None)):
    """Manually trigger a workflow dispatch."""
    _require_client()
    if ci_cd_monitor.trigger_workflow(repo_name, workflow_name, branch, inputs):
        return {"status": "triggered"}
    raise HTTPException(status_code=400, detail="Failed to trigger workflow")


@router.post("/{repo_name}/workflows/runs/{run_id}/cancel")
async def cancel_workflow_run(repo_name: str, run_id: int):
    """Cancel a running workflow."""
    _require_client()
    if ci_cd_monitor.cancel_workflow_run(repo_name, run_id):
        return {"status": "cancelled"}
    raise HTTPException(status_code=400, detail="Failed to cancel workflow")


@router.post("/{repo_name}/workflows/runs/{run_id}/rerun")
async def rerun_failed_workflow(repo_name: str, run_id: int):
    """Re-run a failed workflow."""
    _require_client()
    if ci_cd_monitor.rerun_failed_workflow(repo_name, run_id):
        return {"status": "rerun_triggered"}
    raise HTTPException(status_code=400, detail="Failed to rerun workflow")


@router.get("/{repo_name}/deployments")
async def get_deployments(repo_name: str, limit: int = 20):
    """Get recent deployments."""
    _require_client()
    return {"deployments": ci_cd_monitor.get_recent_deployments(repo_name, limit)}


@router.get("/{repo_name}/deployments/status")
async def get_deployment_status(repo_name: str, environment: Optional[str] = None):
    """Get current deployment status."""
    _require_client()
    return ci_cd_monitor.get_deployment_status(repo_name, environment)


@router.get("/{repo_name}/workflows/trends")
async def get_workflow_trends(repo_name: str, days: int = 30):
    """Get workflow trends over time."""
    _require_client()
    return ci_cd_monitor.get_workflow_trends(repo_name, days)


@router.get("/{repo_name}/workflows/queue")
async def get_queue_status(repo_name: str):
    """Get workflow queue status."""
    _require_client()
    return ci_cd_monitor.get_queue_status(repo_name)


@router.get("/{repo_name}/prs/{pr_number}/checks")
async def check_required_checks(repo_name: str, pr_number: int):
    """Check if all required status checks pass for a PR."""
    _require_client()
    return ci_cd_monitor.check_required_checks(repo_name, pr_number)


# ─── Documentation Endpoints ───
@router.get("/{repo_name}/docs/readme")
async def generate_readme(repo_name: str, template: str = "default"):
    """Generate README.md content."""
    _require_client()
    return {"content": doc_generator.generate_readme(repo_name, template)}


@router.get("/{repo_name}/docs/changelog")
async def generate_changelog(repo_name: str, from_tag: Optional[str] = None, to_tag: Optional[str] = None):
    """Generate CHANGELOG.md from releases."""
    _require_client()
    return {"content": doc_generator.generate_changelog(repo_name, from_tag, to_tag)}


@router.get("/{repo_name}/docs/contributing")
async def generate_contributing(repo_name: str):
    """Generate CONTRIBUTING.md."""
    _require_client()
    return {"content": doc_generator.generate_contributing(repo_name)}


@router.get("/{repo_name}/docs/security")
async def generate_security_policy(repo_name: str):
    """Generate SECURITY.md."""
    _require_client()
    return {"content": doc_generator.generate_security_policy(repo_name)}


@router.get("/{repo_name}/docs/code-of-conduct")
async def generate_code_of_conduct(repo_name: str):
    """Generate CODE_OF_CONDUCT.md."""
    _require_client()
    return {"content": doc_generator.generate_code_of_conduct(repo_name)}


@router.get("/{repo_name}/docs/all")
async def generate_all_docs(repo_name: str):
    """Generate all standard documentation files."""
    _require_client()
    return doc_generator.generate_all_docs(repo_name)


# ─── Config Management Endpoints ───
@router.get("/{repo_name}/config/settings")
async def get_repo_settings(repo_name: str):
    """Get repository settings."""
    _require_client()
    settings = config_manager.get_repo_settings(repo_name)
    if settings:
        return settings.__dict__
    raise HTTPException(status_code=404, detail="Repo not found")


@router.patch("/{repo_name}/config/settings")
async def update_repo_settings(repo_name: str, settings: RepoSettings):
    """Update repository settings."""
    _require_client()
    settings.name = repo_name
    if config_manager.update_repo_settings(repo_name, settings):
        return {"status": "updated"}
    raise HTTPException(status_code=400, detail="Failed to update settings")


@router.get("/{repo_name}/config/secrets")
async def list_secrets(repo_name: str):
    """List repository secrets (names only)."""
    _require_client()
    return {"secrets": config_manager.list_secrets(repo_name)}


@router.post("/{repo_name}/config/secrets")
async def set_secret(repo_name: str, name: str = Body(...), value: str = Body(...)):
    """Set a repository secret."""
    _require_client()
    if config_manager.set_secret(repo_name, name, value):
        return {"status": "set"}
    raise HTTPException(status_code=400, detail="Failed to set secret")


@router.delete("/{repo_name}/config/secrets/{name}")
async def delete_secret(repo_name: str, name: str):
    """Delete a repository secret."""
    _require_client()
    if config_manager.delete_secret(repo_name, name):
        return {"status": "deleted"}
    raise HTTPException(status_code=400, detail="Failed to delete secret")


@router.post("/{repo_name}/config/secrets/sync")
async def sync_secrets(repo_name: str, secrets: Dict[str, str] = Body(...), delete_missing: bool = Body(False)):
    """Sync multiple secrets at once."""
    _require_client()
    return config_manager.sync_secrets(repo_name, secrets, delete_missing)


@router.get("/{repo_name}/config/collaborators")
async def list_collaborators(repo_name: str, permission: Optional[str] = None):
    """List repository collaborators."""
    _require_client()
    perm = PermissionLevel(permission) if permission else None
    return {"collaborators": config_manager.list_collaborators(repo_name, perm)}


@router.post("/{repo_name}/config/collaborators")
async def add_collaborator(repo_name: str, username: str = Body(...), permission: str = Body("write")):
    """Add collaborator to repository."""
    _require_client()
    if config_manager.add_collaborator(repo_name, username, PermissionLevel(permission)):
        return {"status": "added"}
    raise HTTPException(status_code=400, detail="Failed to add collaborator")


@router.delete("/{repo_name}/config/collaborators/{username}")
async def remove_collaborator(repo_name: str, username: str):
    """Remove collaborator from repository."""
    _require_client()
    if config_manager.remove_collaborator(repo_name, username):
        return {"status": "removed"}
    raise HTTPException(status_code=400, detail="Failed to remove collaborator")


@router.get("/{repo_name}/config/teams")
async def list_teams(repo_name: str):
    """List teams with access to repository."""
    _require_client()
    return {"teams": config_manager.list_teams(repo_name)}


@router.post("/{repo_name}/config/webhooks")
async def configure_webhooks(repo_name: str, webhook_url: str = Body(...), events: Optional[List[str]] = Body(None), secret: str = Body("")):
    """Configure webhooks for repository."""
    _require_client()
    if config_manager.configure_webhooks(repo_name, webhook_url, events, secret):
        return {"status": "configured"}
    raise HTTPException(status_code=400, detail="Failed to configure webhooks")


@router.get("/{repo_name}/config/topics")
async def get_topics(repo_name: str):
    """Get repository topics."""
    _require_client()
    repo = client.get_repo(repo_name)
    if repo:
        return {"topics": repo.get_topics()}
    raise HTTPException(status_code=404, detail="Repo not found")


@router.post("/{repo_name}/config/topics")
async def set_topics(repo_name: str, topics: List[str] = Body(...)):
    """Set repository topics."""
    _require_client()
    if config_manager.set_topics(repo_name, topics):
        return {"status": "updated"}
    raise HTTPException(status_code=400, detail="Failed to update topics")


@router.get("/{repo_name}/config/labels")
async def get_labels(repo_name: str):
    """Get all labels in repository."""
    _require_client()
    return {"labels": config_manager.get_labels(repo_name)}


@router.post("/{repo_name}/config/labels")
async def create_label(repo_name: str, name: str = Body(...), color: str = Body("ededed"), description: str = Body("")):
    """Create a label."""
    _require_client()
    if config_manager.create_label(repo_name, name, color, description):
        return {"status": "created"}
    raise HTTPException(status_code=400, detail="Failed to create label")


@router.post("/{repo_name}/config/labels/sync")
async def sync_labels(repo_name: str, labels: List[Dict] = Body(...), delete_missing: bool = Body(False)):
    """Sync labels to match desired state."""
    _require_client()
    return config_manager.sync_labels(repo_name, labels, delete_missing)


@router.post("/{repo_name}/config/milestones")
async def create_milestone(repo_name: str, title: str = Body(...), description: str = Body(""), due_on: Optional[str] = Body(None)):
    """Create a milestone."""
    _require_client()
    result = config_manager.create_milestone(repo_name, title, description, due_on)
    if result:
        return {"status": "created", "milestone": result}
    raise HTTPException(status_code=400, detail="Failed to create milestone")


@router.post("/{repo_name}/config/milestones/{title}/close")
async def close_milestone(repo_name: str, title: str):
    """Close a milestone."""
    _require_client()
    if config_manager.close_milestone(repo_name, title):
        return {"status": "closed"}
    raise HTTPException(status_code=400, detail="Failed to close milestone")


# ─── Webhook Endpoint ───
@router.post("/webhook")
async def github_webhook(
    request: Request,
    x_github_event: Optional[str] = Header(None),
    x_hub_signature_256: Optional[str] = Header(None),
    x_github_delivery: Optional[str] = Header(None)
):
    """
    GitHub webhook receiver.
    POST /api/github/webhook
    """
    if not webhook:
        raise HTTPException(status_code=503, detail="Webhook handler not initialized")
    
    try:
        raw_body = await request.body()
        payload = await request.json()
        
        result = webhook.process_webhook(
            event=x_github_event or "unknown",
            payload=payload,
            delivery_id=x_github_delivery or "",
            signature=x_hub_signature_256 or "",
            raw_payload=raw_body
        )
        return result
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ─── Admin Dashboard Endpoints ───
@router.get("/dashboard")
async def admin_dashboard_overview():
    """Get organization overview."""
    _require_client()
    return admin_dashboard.get_org_overview()


@router.get("/dashboard/{repo_name}")
async def repo_dashboard(repo_name: str):
    """Get detailed repository dashboard."""
    _require_client()
    return admin_dashboard.get_repo_dashboard(repo_name)


@router.get("/dashboard/workflows")
async def workflow_dashboard(repo_name: Optional[str] = None):
    """Get CI/CD workflow dashboard."""
    _require_client()
    return admin_dashboard.get_workflow_dashboard(repo_name)


@router.get("/dashboard/security")
async def security_dashboard(repo_name: Optional[str] = None):
    """Get security overview."""
    _require_client()
    return admin_dashboard.get_security_dashboard(repo_name)


@router.get("/dashboard/activity")
async def activity_feed(repo_name: Optional[str] = None, limit: int = 50):
    """Get recent activity feed."""
    _require_client()
    return {"activities": admin_dashboard.get_activity_feed(repo_name, limit)}


@router.get("/dashboard/contributors")
async def contributor_stats(repo_name: Optional[str] = None):
    """Get contributor statistics."""
    _require_client()
    return admin_dashboard.get_contributor_stats(repo_name)


@router.get("/dashboard/automation")
async def automation_status():
    """Get automation engine status."""
    _require_client()
    return admin_dashboard.get_automation_status()


@router.get("/dashboard/search")
async def search_org(query: str, search_type: str = "all"):
    """Search across organization repos."""
    _require_client()
    return admin_dashboard.search_across_org(query, search_type)


@router.post("/dashboard/bulk")
async def bulk_operations(
    operation: str = Body(...),
    repo_names: List[str] = Body(...),
    params: Optional[Dict] = Body(None)
):
    """Perform bulk operations across multiple repos."""
    _require_client()
    return admin_dashboard.bulk_operations(operation, repo_names, params or {})