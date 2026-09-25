"""ARIA Admin Dashboard — Unified API endpoints for GitHub administration UI."""

import logging
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DashboardStats:
    """Overall dashboard statistics"""
    org: str
    total_repos: int
    total_stars: int
    total_forks: int
    total_open_issues: int
    total_open_prs: int
    active_workflows: int
    failed_workflows: int
    recent_commits: int
    recent_releases: int


class AdminDashboard:
    """
    ARIA Admin Dashboard
    Provides aggregated data for admin UI
    """

    def __init__(self, github_client, webhook_handler=None, pr_analyzer=None,
                 issue_manager=None, ci_cd_monitor=None, doc_generator=None,
                 config_manager=None, auto_commit=None, auto_release=None):
        self.client = github_client
        self.webhook = webhook_handler
        self.pr_analyzer = pr_analyzer
        self.issue_manager = issue_manager
        self.ci_cd = ci_cd_monitor
        self.doc_gen = doc_generator
        self.config = config_manager
        self.auto_commit = auto_commit
        self.auto_release = auto_release

    def get_org_overview(self) -> Dict[str, Any]:
        """Get organization overview"""
        try:
            repos = self.client.list_repos()

            stats = DashboardStats(
                org=self.client.org,
                total_repos=len(repos),
                total_stars=sum(r["stars"] for r in repos),
                total_forks=sum(r["forks"] for r in repos),
                total_open_issues=sum(r.get("open_issues", 0) for r in repos),
                total_open_prs=0,  # Would need to sum from each repo
                active_workflows=0,
                failed_workflows=0,
                recent_commits=0,
                recent_releases=0
            )

            # Get PR counts
            for repo in repos[:20]:  # Sample first 20 to avoid rate limits
                prs = self.client.list_prs(repo["name"], state="open")
                stats.total_open_prs += len(prs)

            # Get workflow health
            for repo in repos[:10]:
                health = self.ci_cd.get_workflow_health(repo["name"], limit=5) if self.ci_cd else {}
                if health.get("status") != "error":
                    stats.active_workflows += health.get("in_progress", 0)
                    stats.failed_workflows += health.get("failed", 0)

            return {
                "org": stats.org,
                "repo_count": stats.total_repos,
                "stars": stats.total_stars,
                "forks": stats.total_forks,
                "open_issues": stats.total_open_issues,
                "open_prs": stats.total_open_prs,
                "active_workflows": stats.active_workflows,
                "failed_workflows": stats.failed_workflows,
                "repos": repos
            }
        except Exception as e:
            logger.error(f"❌ get_org_overview failed: {e}")
            return {"error": str(e)}

    def get_repo_dashboard(self, repo_name: str) -> Dict[str, Any]:
        """Get detailed repository dashboard"""
        try:
            stats = self.client.get_repo_stats(repo_name)
            prs = self.client.list_prs(repo_name, state="open")
            issues = self.client.list_issues(repo_name, state="open")
            releases = self.client.list_releases(repo_name)
            workflows = self.client.list_workflows(repo_name)
            health = self.ci_cd.get_workflow_health(repo_name) if self.ci_cd else {}
            deployments = self.ci_cd.get_recent_deployments(repo_name) if self.ci_cd else []

            # PR analysis
            pr_analysis = []
            for pr in prs[:10]:
                if self.pr_analyzer:
                    analysis = self.pr_analyzer.get_pr_summary(repo_name, pr["number"])
                    if analysis:
                        pr_analysis.append(analysis)

            # Issue analysis
            issue_analysis = []
            for issue in issues[:10]:
                if self.issue_manager:
                    analysis = self.issue_manager.analyze_issue(repo_name, issue["number"])
                    if analysis:
                        issue_analysis.append({
                            "number": analysis.number,
                            "title": analysis.title,
                            "type": analysis.type.value,
                            "priority": analysis.priority.value,
                            "suggested_labels": analysis.suggested_labels,
                        })

            return {
                "repo": stats,
                "prs": {
                    "open": len(prs),
                    "total": stats.get("commits", 0) if stats else 0,
                    "analysis": pr_analysis,
                    "recent": prs[:5]
                },
                "issues": {
                    "open": len(issues),
                    "analysis": issue_analysis,
                    "recent": issues[:5]
                },
                "releases": {
                    "latest": releases[0] if releases else None,
                    "count": len(releases),
                    "recent": releases[:5]
                },
                "workflows": {
                    "health": health,
                    "count": len(workflows),
                    "recent_runs": health.get("runs", [])
                },
                "deployments": deployments[:5],
                "contributors": self.client.get_contributors(repo_name, limit=10),
                "languages": self.client.get_languages(repo_name),
            }
        except Exception as e:
            logger.error(f"❌ get_repo_dashboard failed: {e}")
            return {"error": str(e)}

    def get_workflow_dashboard(self, repo_name: str = None) -> Dict[str, Any]:
        """Get CI/CD workflow dashboard"""
        try:
            if repo_name:
                return self.ci_cd.get_workflow_health(repo_name) if self.ci_cd else {}

            # Aggregate across all repos
            repos = self.client.list_repos()
            all_health = {}
            total_failing = []

            for repo in repos[:20]:
                health = self.ci_cd.get_workflow_health(repo["name"], limit=10) if self.ci_cd else {}
                if health.get("status") != "error":
                    all_health[repo["name"]] = health
                    failing = self.ci_cd.get_failing_workflows(repo["name"], limit=5) if self.ci_cd else []
                    total_failing.extend([{**f, "repo": repo["name"]} for f in failing])

            return {
                "repos": all_health,
                "total_failing": len(total_failing),
                "failing_details": total_failing[:20],
            }
        except Exception as e:
            logger.error(f"❌ get_workflow_dashboard failed: {e}")
            return {"error": str(e)}

    def get_security_dashboard(self, repo_name: str = None) -> Dict[str, Any]:
        """Get security overview"""
        try:
            if repo_name:
                repo = self.client.get_repo(repo_name)
                if not repo:
                    return {}

                # Get security advisories (requires GitHub API)
                # For now, return basic info
                return {
                    "repo": repo_name,
                    "has_security_policy": False,  # Would check for SECURITY.md
                    "branch_protection": self.config.get_branch_protection(repo_name) is not None if self.config else False,
                    "secrets_count": len(self.config.list_secrets(repo_name)) if self.config else 0,
                }

            # Org-wide security
            repos = self.client.list_repos()
            security_issues = []

            for repo in repos[:30]:
                if repo.get("open_issues", 0) > 0:
                    issues = self.client.list_issues(repo["name"], state="open", labels=["security"])
                    if issues:
                        security_issues.extend([{**i, "repo": repo["name"]} for i in issues])

            return {
                "total_security_issues": len(security_issues),
                "security_issues": security_issues[:20],
                "repos_without_protection": [],  # Would check each repo
            }
        except Exception as e:
            logger.error(f"❌ get_security_dashboard failed: {e}")
            return {"error": str(e)}

    def get_activity_feed(self, repo_name: str = None, limit: int = 50) -> List[Dict]:
        """Get recent activity feed"""
        activities = []

        try:
            repos = [repo_name] if repo_name else [r["name"] for r in self.client.list_repos()[:10]]

            for repo in repos:
                # Recent commits
                repo_obj = self.client.get_repo(repo)
                if repo_obj:
                    commits = list(repo_obj.get_commits())[:5]
                    for commit in commits:
                        activities.append({
                            "type": "commit",
                            "repo": repo,
                            "message": commit.commit.message.split('\n')[0],
                            "author": commit.commit.author.name,
                            "sha": commit.sha[:7],
                            "date": commit.commit.author.date.isoformat() if commit.commit.author.date else None,
                            "url": commit.html_url,
                        })

                # Recent PRs
                prs = self.client.list_prs(repo, state="all")[:5]
                for pr in prs:
                    activities.append({
                        "type": "pr",
                        "repo": repo,
                        "number": pr["number"],
                        "title": pr["title"],
                        "author": pr["author"],
                        "status": pr["status"],
                        "date": pr["updated_at"],
                        "url": pr["url"],
                    })

                # Recent releases
                releases = self.client.list_releases(repo)[:3]
                for rel in releases:
                    activities.append({
                        "type": "release",
                        "repo": repo,
                        "tag": rel["tag"],
                        "title": rel["title"],
                        "date": rel["published_at"],
                        "url": rel["url"],
                    })

                # Recent issues
                issues = self.client.list_issues(repo, state="all")[:3]
                for issue in issues:
                    activities.append({
                        "type": "issue",
                        "repo": repo,
                        "number": issue["number"],
                        "title": issue["title"],
                        "author": issue["author"],
                        "status": issue["status"],
                        "date": issue["updated_at"],
                        "url": issue["url"],
                    })

            # Sort by date
            activities.sort(key=lambda x: x.get("date", ""), reverse=True)
            return activities[:limit]

        except Exception as e:
            logger.error(f"❌ get_activity_feed failed: {e}")
            return []

    def get_contributor_stats(self, repo_name: str = None) -> Dict[str, Any]:
        """Get contributor statistics"""
        try:
            if repo_name:
                contributors = self.client.get_contributors(repo_name)
                return {
                    "repo": repo_name,
                    "contributors": contributors,
                    "total": len(contributors),
                }

            # Org-wide
            repos = self.client.list_repos()[:20]
            all_contributors = {}

            for repo in repos:
                contribs = self.client.get_contributors(repo["name"], limit=100)
                for c in contribs:
                    login = c["login"]
                    if login not in all_contributors:
                        all_contributors[login] = {
                            "login": login,
                            "avatar_url": c["avatar_url"],
                            "total_contributions": 0,
                            "repos": []
                        }
                    all_contributors[login]["total_contributions"] += c["contributions"]
                    all_contributors[login]["repos"].append(repo["name"])

            # Sort by contributions
            sorted_contribs = sorted(
                all_contributors.values(),
                key=lambda x: x["total_contributions"],
                reverse=True
            )

            return {
                "total_contributors": len(sorted_contribs),
                "top_contributors": sorted_contribs[:20],
            }
        except Exception as e:
            logger.error(f"❌ get_contributor_stats failed: {e}")
            return {"error": str(e)}

    def get_automation_status(self) -> Dict[str, Any]:
        """Get automation engine status"""
        status = {}

        if self.auto_commit:
            status["auto_commit"] = self.auto_commit.get_status()

        if self.auto_release:
            # Auto-release doesn't have a status method, but we could add one
            status["auto_release"] = {"enabled": True}

        if self.webhook:
            status["webhooks"] = {
                "registered_handlers": sum(len(h) for h in self.webhook.handlers.values()),
                "global_handlers": len(self.webhook.global_handlers),
            }

        return status

    def search_across_org(self, query: str, search_type: str = "all") -> Dict[str, Any]:
        """Search across organization repos"""
        results = {"repos": [], "code": [], "issues": [], "prs": []}

        try:
            repos = self.client.list_repos()

            for repo in repos[:20]:
                repo_name = repo["name"]

                if search_type in ("all", "repos"):
                    if query.lower() in repo_name.lower() or query.lower() in (repo.get("description") or "").lower():
                        results["repos"].append(repo)

                if search_type in ("all", "issues"):
                    issues = self.client.list_issues(repo_name, state="all")
                    for issue in issues:
                        if query.lower() in issue["title"].lower():
                            results["issues"].append({**issue, "repo": repo_name})

                if search_type in ("all", "prs"):
                    prs = self.client.list_prs(repo_name, state="all")
                    for pr in prs:
                        if query.lower() in pr["title"].lower():
                            results["prs"].append({**pr, "repo": repo_name})

            return results
        except Exception as e:
            logger.error(f"❌ search_across_org failed: {e}")
            return {"error": str(e)}

    def bulk_operations(self, operation: str, repo_names: List[str],
                       params: Dict = None) -> Dict[str, Any]:
        """Perform bulk operations across multiple repos"""
        results = {"success": [], "failed": []}

        for repo_name in repo_names:
            try:
                if operation == "enable_protection":
                    profile = params.get("profile", "standard")
                    branch = params.get("branch", "main")
                    if self.config and self.config.apply_protection_profile(repo_name, branch, profile):
                        results["success"].append(repo_name)
                    else:
                        results["failed"].append({"repo": repo_name, "error": "Protection failed"})

                elif operation == "update_settings":
                    profile = params.get("profile", "standard")
                    if self.config and self.config.apply_standard_settings(repo_name, profile):
                        results["success"].append(repo_name)
                    else:
                        results["failed"].append({"repo": repo_name, "error": "Settings failed"})

                elif operation == "create_webhook":
                    url = params.get("url")
                    if url and self.config and self.config.configure_webhooks(repo_name, url):
                        results["success"].append(repo_name)
                    else:
                        results["failed"].append({"repo": repo_name, "error": "Webhook failed"})

                elif operation == "sync_labels":
                    labels = params.get("labels", [])
                    if self.config and self.config.sync_labels(repo_name, labels):
                        results["success"].append(repo_name)
                    else:
                        results["failed"].append({"repo": repo_name, "error": "Labels failed"})

                elif operation == "triage_issues":
                    if self.issue_manager:
                        self.issue_manager.bulk_triage(repo_name)
                        results["success"].append(repo_name)
                    else:
                        results["failed"].append({"repo": repo_name, "error": "Issue manager not available"})

                else:
                    results["failed"].append({"repo": repo_name, "error": f"Unknown operation: {operation}"})

            except Exception as e:
                results["failed"].append({"repo": repo_name, "error": str(e)})

        return results