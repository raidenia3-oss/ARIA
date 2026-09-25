"""ARIA GitHub Admin Client — Core API wrapper using PyGithub."""

from github import Github, GithubException
from github.Repository import Repository
from github.Organization import Organization
from github.NamedUser import NamedUser
from github.AuthenticatedUser import AuthenticatedUser
from github.PullRequest import PullRequest
from github.Issue import Issue
from github.GitRelease import GitRelease as Release
from github.Workflow import Workflow
from github.WorkflowRun import WorkflowRun
import subprocess
import os
import base64
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class GitHubAdminClient:
    """
    ARIA GitHub Admin Client
    Handles auth, org/repo management, API calls
    Works with both Organizations and Users
    """

    def __init__(self, token: str, org: str = "raidenia3-oss"):
        self.token = token
        self.org = org
        self.client = Github(token)
        self.org_obj: Optional[Organization] = None
        self.user_obj: Optional[NamedUser] = None
        self.auth_user: Optional[AuthenticatedUser] = None
        self._is_org = False
        self._init_owner()

    def _init_owner(self):
        """Initialize organization or user reference"""
        # First try as organization
        try:
            self.org_obj = self.client.get_organization(self.org)
            self._is_org = True
            logger.info(f"✅ GitHub org initialized: {self.org}")
        except GithubException:
            pass

        # Fallback: try as user
        try:
            self.user_obj = self.client.get_user(self.org)
            self._is_org = False
            logger.info(f"✅ GitHub user initialized: {self.org}")
        except GithubException as e:
            logger.error(f"❌ Owner init failed: {e}")

        # Get authenticated user for repo creation (works for both org and user)
        try:
            self.auth_user = self.client.get_user()
            logger.info(f"✅ Authenticated user: {self.auth_user.login}")
        except GithubException as e:
            logger.error(f"❌ Auth user init failed: {e}")

    @property
    def owner(self):
        """Get the owner (org or user) for repo operations"""
        return self.org_obj if self._is_org else self.user_obj

    @property
    def creator(self):
        """Get the entity that can create repos (org or authenticated user)"""
        if self._is_org and self.org_obj:
            return self.org_obj
        return self.auth_user

    # ═══════════════════════════════════════════════════════════════════════
    # REPOSITORY MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════

    def list_repos(self) -> List[Dict]:
        """List all repos in org/user"""
        try:
            repos = []
            for repo in self.owner.get_repos():
                repos.append({
                    "name": repo.name,
                    "description": repo.description,
                    "url": repo.html_url,
                    "stars": repo.stargazers_count,
                    "forks": repo.forks_count,
                    "language": repo.language,
                    "is_private": repo.private,
                    "is_archived": repo.archived,
                    "is_fork": repo.fork,
                    "default_branch": repo.default_branch,
                    "size_kb": repo.size,
                    "created_at": repo.created_at.isoformat() if repo.created_at else None,
                    "updated_at": repo.updated_at.isoformat() if repo.updated_at else None,
                    "pushed_at": repo.pushed_at.isoformat() if repo.pushed_at else None,
                })
            return repos
        except GithubException as e:
            logger.error(f"❌ list_repos failed: {e}")
            return []

    def create_repo(self, name: str, description: str = "",
                   private: bool = False, auto_init: bool = True,
                   has_issues: bool = True, has_wiki: bool = False,
                   has_projects: bool = True) -> Optional[Dict]:
        """Create new repository"""
        try:
            creator = self.creator
            if not creator:
                logger.error("❌ No creator available (no org or auth user)")
                return None
            repo = creator.create_repo(
                name=name,
                description=description,
                private=private,
                auto_init=auto_init,
                has_issues=has_issues,
                has_wiki=has_wiki,
                has_projects=has_projects
            )
            logger.info(f"✅ Repo created: {name}")
            return {
                "name": repo.name,
                "url": repo.html_url,
                "clone_url": repo.clone_url,
                "ssh_url": repo.ssh_url,
                "default_branch": repo.default_branch
            }
        except GithubException as e:
            logger.error(f"❌ create_repo failed: {e}")
            return None

    def delete_repo(self, repo_name: str) -> bool:
        """Delete repository (⚠️ DESTRUCTIVE)"""
        try:
            repo = self.owner.get_repo(repo_name)
            repo.delete()
            logger.warning(f"⚠️ Repo deleted: {repo_name}")
            return True
        except GithubException as e:
            logger.error(f"❌ delete_repo failed: {e}")
            return False

    def get_repo(self, repo_name: str) -> Optional[Repository]:
        """Get repo object"""
        try:
            return self.owner.get_repo(repo_name)
        except GithubException as e:
            logger.error(f"❌ get_repo failed: {e}")
            return None

    def update_repo(self, repo_name: str, **kwargs) -> bool:
        """Update repository settings"""
        try:
            repo = self.get_repo(repo_name)
            if not repo:
                return False
            repo.edit(**kwargs)
            logger.info(f"✅ Repo updated: {repo_name}")
            return True
        except GithubException as e:
            logger.error(f"❌ update_repo failed: {e}")
            return False

    # ═══════════════════════════════════════════════════════════════════════
    # BRANCH PROTECTION & CONFIG
    # ═══════════════════════════════════════════════════════════════════════

    def enable_branch_protection(self, repo_name: str, branch: str = "main",
                                required_reviews: int = 1,
                                dismiss_stale: bool = True,
                                require_status_checks: bool = True,
                                status_contexts: List[str] = None,
                                enforce_admins: bool = True,
                                require_linear_history: bool = True,
                                allow_force_pushes: bool = False,
                                allow_deletions: bool = False) -> bool:
        """Enable branch protection rules"""
        try:
            repo = self.get_repo(repo_name)
            if not repo:
                return False

            branch_obj = repo.get_branch(branch)

            protection = {
                "required_status_checks": {
                    "strict": True,
                    "contexts": status_contexts or []
                } if require_status_checks else None,
                "enforce_admins": enforce_admins,
                "required_pull_request_reviews": {
                    "dismiss_stale_reviews": dismiss_stale,
                    "required_approving_review_count": required_reviews,
                    "require_code_owner_reviews": False
                } if required_reviews > 0 else None,
                "restrictions": None,
                "required_linear_history": require_linear_history,
                "allow_force_pushes": allow_force_pushes,
                "allow_deletions": allow_deletions,
            }

            branch_obj.edit_protection(**{k: v for k, v in protection.items() if v is not None})
            logger.info(f"✅ Branch protection enabled: {repo_name}/{branch}")
            return True
        except GithubException as e:
            logger.error(f"❌ enable_branch_protection failed: {e}")
            return False

    def disable_branch_protection(self, repo_name: str, branch: str = "main") -> bool:
        """Disable branch protection"""
        try:
            repo = self.get_repo(repo_name)
            if not repo:
                return False
            repo.get_branch(branch).remove_protection()
            logger.info(f"✅ Branch protection disabled: {repo_name}/{branch}")
            return True
        except GithubException as e:
            logger.error(f"❌ disable_branch_protection failed: {e}")
            return False

    def set_secret(self, repo_name: str, secret_name: str, secret_value: str) -> bool:
        """Set GitHub secret (for CI/CD) - uses PyGithub encryption"""
        try:
            repo = self.get_repo(repo_name)
            if not repo:
                return False

            public_key = repo.get_public_key()
            encrypted = self._encrypt_secret(public_key.key, secret_value)

            repo.create_secret(secret_name, encrypted, public_key.key_id)
            logger.info(f"✅ Secret set: {repo_name}/{secret_name}")
            return True
        except GithubException as e:
            logger.error(f"❌ set_secret failed: {e}")
            return False

    def _encrypt_secret(self, public_key: str, secret_value: str) -> str:
        """Encrypt secret using libnacl (PyGithub handles this)"""
        from nacl import encoding, public
        public_key_obj = public.PublicKey(public_key.encode("utf-8"), encoding.Base64Encoder())
        sealed_box = public.SealedBox(public_key_obj)
        encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
        return base64.b64encode(encrypted).decode("utf-8")

    def delete_secret(self, repo_name: str, secret_name: str) -> bool:
        """Delete a secret"""
        try:
            repo = self.get_repo(repo_name)
            if not repo:
                return False
            repo.delete_secret(secret_name)
            logger.info(f"✅ Secret deleted: {repo_name}/{secret_name}")
            return True
        except GithubException as e:
            logger.error(f"❌ delete_secret failed: {e}")
            return False

    # ═══════════════════════════════════════════════════════════════════════
    # PR MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════

    def list_prs(self, repo_name: str, state: str = "open",
                sort: str = "updated", direction: str = "desc") -> List[Dict]:
        """List PRs"""
        try:
            repo = self.get_repo(repo_name)
            if not repo:
                return []

            prs = []
            for pr in repo.get_pulls(state=state, sort=sort, direction=direction):
                prs.append({
                    "number": pr.number,
                    "title": pr.title,
                    "author": pr.user.login,
                    "status": pr.state,
                    "url": pr.html_url,
                    "created_at": pr.created_at.isoformat() if pr.created_at else None,
                    "updated_at": pr.updated_at.isoformat() if pr.updated_at else None,
                    "closed_at": pr.closed_at.isoformat() if pr.closed_at else None,
                    "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
                    "base_branch": pr.base.ref,
                    "head_branch": pr.head.ref,
                    "is_draft": pr.draft,
                    "mergeable": pr.mergeable,
                    "review_comments": pr.review_comments,
                    "commits": pr.commits,
                    "additions": pr.additions,
                    "deletions": pr.deletions,
                    "changed_files": pr.changed_files,
                })
            return prs
        except GithubException as e:
            logger.error(f"❌ list_prs failed: {e}")
            return []

    def get_pr(self, repo_name: str, pr_number: int) -> Optional[PullRequest]:
        """Get PR object"""
        try:
            repo = self.get_repo(repo_name)
            if not repo:
                return None
            return repo.get_pull(pr_number)
        except GithubException as e:
            logger.error(f"❌ get_pr failed: {e}")
            return None

    def merge_pr(self, repo_name: str, pr_number: int,
                commit_title: str = "", commit_message: str = "",
                merge_method: str = "squash") -> bool:
        """Auto-merge PR (merge_method: merge, squash, rebase)"""
        try:
            repo = self.get_repo(repo_name)
            if not repo:
                return False

            pr = repo.get_pull(pr_number)
            if pr.mergeable or pr.mergeable_state == "clean":
                pr.merge(
                    commit_title=commit_title or pr.title,
                    commit_message=commit_message or f"Merge PR #{pr_number}: {pr.title}",
                    merge_method=merge_method
                )
                logger.info(f"✅ PR merged: {repo_name}#{pr_number}")
                return True
            else:
                logger.warning(f"⚠️ PR not mergeable: {repo_name}#{pr_number} - state: {pr.mergeable_state}")
                return False
        except GithubException as e:
            logger.error(f"❌ merge_pr failed: {e}")
            return False

    def close_pr(self, repo_name: str, pr_number: int) -> bool:
        """Close PR without merging"""
        try:
            pr = self.get_pr(repo_name, pr_number)
            if not pr:
                return False
            pr.edit(state="closed")
            logger.info(f"✅ PR closed: {repo_name}#{pr_number}")
            return True
        except GithubException as e:
            logger.error(f"❌ close_pr failed: {e}")
            return False

    def get_pr_reviews(self, repo_name: str, pr_number: int) -> List[Dict]:
        """Get PR reviews"""
        try:
            pr = self.get_pr(repo_name, pr_number)
            if not pr:
                return []

            reviews = []
            for review in pr.get_reviews():
                reviews.append({
                    "id": review.id,
                    "user": review.user.login,
                    "state": review.state,
                    "body": review.body,
                    "submitted_at": review.submitted_at.isoformat() if review.submitted_at else None,
                })
            return reviews
        except GithubException as e:
            logger.error(f"❌ get_pr_reviews failed: {e}")
            return []

    def get_pr_checks(self, repo_name: str, pr_number: int) -> List[Dict]:
        """Get PR status checks"""
        try:
            pr = self.get_pr(repo_name, pr_number)
            if not pr:
                return []

            checks = []
            for check in pr.get_check_runs():
                checks.append({
                    "name": check.name,
                    "status": check.status,
                    "conclusion": check.conclusion,
                    "started_at": check.started_at.isoformat() if check.started_at else None,
                    "completed_at": check.completed_at.isoformat() if check.completed_at else None,
                    "url": check.html_url,
                })
            return checks
        except GithubException as e:
            logger.error(f"❌ get_pr_checks failed: {e}")
            return []

    # ═══════════════════════════════════════════════════════════════════════
    # ISSUE MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════

    def list_issues(self, repo_name: str, state: str = "open",
                   labels: List[str] = None, sort: str = "updated") -> List[Dict]:
        """List issues"""
        try:
            repo = self.get_repo(repo_name)
            if not repo:
                return []

            issues = []
            kwargs = {"state": state, "sort": sort}
            if labels:
                kwargs["labels"] = labels
            for issue in repo.get_issues(**kwargs):
                issues.append({
                    "number": issue.number,
                    "title": issue.title,
                    "author": issue.user.login,
                    "status": issue.state,
                    "labels": [l.name for l in issue.labels],
                    "url": issue.html_url,
                    "created_at": issue.created_at.isoformat() if issue.created_at else None,
                    "updated_at": issue.updated_at.isoformat() if issue.updated_at else None,
                    "closed_at": issue.closed_at.isoformat() if issue.closed_at else None,
                    "assignees": [a.login for a in issue.assignees],
                    "milestone": issue.milestone.title if issue.milestone else None,
                    "comments": issue.comments,
                })
            return issues
        except GithubException as e:
            logger.error(f"❌ list_issues failed: {e}")
            return []

    def create_issue(self, repo_name: str, title: str, body: str = "",
                    labels: List[str] = None, assignees: List[str] = None,
                    milestone: str = None) -> Optional[Dict]:
        """Create issue"""
        try:
            repo = self.get_repo(repo_name)
            if not repo:
                return None

            issue = repo.create_issue(
                title=title,
                body=body,
                labels=labels or [],
                assignees=assignees or [],
                milestone=repo.get_milestone_by_title(milestone) if milestone else None
            )
            logger.info(f"✅ Issue created: {repo_name}#{issue.number}")
            return {
                "number": issue.number,
                "title": issue.title,
                "url": issue.html_url
            }
        except GithubException as e:
            logger.error(f"❌ create_issue failed: {e}")
            return None

    def update_issue(self, repo_name: str, issue_number: int, **kwargs) -> bool:
        """Update issue"""
        try:
            repo = self.get_repo(repo_name)
            if not repo:
                return False
            issue = repo.get_issue(issue_number)
            issue.edit(**kwargs)
            logger.info(f"✅ Issue updated: {repo_name}#{issue_number}")
            return True
        except GithubException as e:
            logger.error(f"❌ update_issue failed: {e}")
            return False

    def close_issue(self, repo_name: str, issue_number: int) -> bool:
        """Close issue"""
        try:
            repo = self.get_repo(repo_name)
            if not repo:
                return False
            issue = repo.get_issue(issue_number)
            issue.edit(state="closed")
            logger.info(f"✅ Issue closed: {repo_name}#{issue_number}")
            return True
        except GithubException as e:
            logger.error(f"❌ close_issue failed: {e}")
            return False

    def add_labels(self, repo_name: str, issue_number: int, labels: List[str]) -> bool:
        """Add labels to issue"""
        try:
            repo = self.get_repo(repo_name)
            if not repo:
                return False
            issue = repo.get_issue(issue_number)
            issue.add_to_labels(*labels)
            logger.info(f"✅ Labels added: {repo_name}#{issue_number} - {labels}")
            return True
        except GithubException as e:
            logger.error(f"❌ add_labels failed: {e}")
            return False

    def remove_label(self, repo_name: str, issue_number: int, label: str) -> bool:
        """Remove label from issue"""
        try:
            repo = self.get_repo(repo_name)
            if not repo:
                return False
            issue = repo.get_issue(issue_number)
            issue.remove_from_labels(label)
            logger.info(f"✅ Label removed: {repo_name}#{issue_number} - {label}")
            return True
        except GithubException as e:
            logger.error(f"❌ remove_label failed: {e}")
            return False

    # ═══════════════════════════════════════════════════════════════════════
    # RELEASE MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════

    def create_release(self, repo_name: str, tag: str, title: str,
                      body: str = "", draft: bool = False,
                      prerelease: bool = False, target_commitish: str = "main",
                      assets: List[str] = None) -> Optional[Dict]:
        """Create release with optional assets"""
        try:
            repo = self.get_repo(repo_name)
            if not repo:
                return None

            release = repo.create_git_release(
                tag=tag,
                name=title,
                message=body,
                draft=draft,
                prerelease=prerelease,
                target_commitish=target_commitish
            )

            # Upload assets if provided
            if assets:
                for asset_path in assets:
                    if os.path.exists(asset_path):
                        release.upload_asset(asset_path)
                        logger.info(f"✅ Asset uploaded: {asset_path}")

            logger.info(f"✅ Release created: {repo_name}/{tag}")
            return {
                "tag": release.tag_name,
                "title": release.title,
                "url": release.html_url,
                "draft": release.draft,
                "prerelease": release.prerelease,
                "published_at": release.published_at.isoformat() if release.published_at else None,
                "assets": [a.name for a in release.get_assets()]
            }
        except GithubException as e:
            logger.error(f"❌ create_release failed: {e}")
            return None

    def list_releases(self, repo_name: str) -> List[Dict]:
        """List releases"""
        try:
            repo = self.get_repo(repo_name)
            if not repo:
                return []

            releases = []
            for release in repo.get_releases():
                releases.append({
                    "tag": release.tag_name,
                    "title": release.title,
                    "body": release.body,
                    "draft": release.draft,
                    "prerelease": release.prerelease,
                    "published_at": release.published_at.isoformat() if release.published_at else None,
                    "url": release.html_url,
                    "assets": [{"name": a.name, "size": a.size, "url": a.browser_download_url} for a in release.get_assets()]
                })
            return releases
        except GithubException as e:
            logger.error(f"❌ list_releases failed: {e}")
            return []

    def get_latest_release(self, repo_name: str) -> Optional[Dict]:
        """Get latest release"""
        releases = self.list_releases(repo_name)
        return releases[0] if releases else None

    def delete_release(self, repo_name: str, tag: str) -> bool:
        """Delete release"""
        try:
            repo = self.get_repo(repo_name)
            if not repo:
                return False
            release = repo.get_release(tag)
            release.delete_release()
            logger.info(f"✅ Release deleted: {repo_name}/{tag}")
            return True
        except GithubException as e:
            logger.error(f"❌ delete_release failed: {e}")
            return False

    # ═══════════════════════════════════════════════════════════════════════
    # CI/CD - WORKFLOWS & RUNS
    # ═══════════════════════════════════════════════════════════════════════

    def list_workflows(self, repo_name: str) -> List[Dict]:
        """List GitHub Actions workflows"""
        try:
            repo = self.get_repo(repo_name)
            if not repo:
                return []

            workflows = []
            for wf in repo.get_workflows():
                workflows.append({
                    "id": wf.id,
                    "name": wf.name,
                    "path": wf.path,
                    "state": wf.state,
                    "created_at": wf.created_at.isoformat() if wf.created_at else None,
                    "updated_at": wf.updated_at.isoformat() if wf.updated_at else None,
                    "url": wf.html_url,
                    "badge_url": wf.badge_url,
                })
            return workflows
        except GithubException as e:
            logger.error(f"❌ list_workflows failed: {e}")
            return []

    def trigger_workflow(self, repo_name: str, workflow_id: str,
                        branch: str = "main", inputs: Dict = None) -> bool:
        """Trigger workflow dispatch"""
        try:
            repo = self.get_repo(repo_name)
            if not repo:
                return False
            workflow = repo.get_workflow(workflow_id)
            workflow.create_dispatch(branch, inputs or {})
            logger.info(f"✅ Workflow triggered: {repo_name}/{workflow_id}")
            return True
        except GithubException as e:
            logger.error(f"❌ trigger_workflow failed: {e}")
            return False

    def get_workflow_runs(self, repo_name: str, workflow_id: str = None,
                         limit: int = 20) -> List[Dict]:
        """Get workflow runs"""
        try:
            repo = self.get_repo(repo_name)
            if not repo:
                return []

            runs = []
            if workflow_id:
                workflow = repo.get_workflow(workflow_id)
                run_iter = workflow.get_runs()
            else:
                run_iter = repo.get_workflow_runs()

            for i, run in enumerate(run_iter):
                if i >= limit:
                    break
                runs.append({
                    "id": run.id,
                    "name": run.name,
                    "status": run.status,
                    "conclusion": run.conclusion,
                    "branch": run.head_branch,
                    "commit_sha": run.head_sha,
                    "created_at": run.created_at.isoformat() if run.created_at else None,
                    "updated_at": run.updated_at.isoformat() if run.updated_at else None,
                    "run_number": run.run_number,
                    "url": run.html_url,
                })
            return runs
        except GithubException as e:
            logger.error(f"❌ get_workflow_runs failed: {e}")
            return []

    # ═══════════════════════════════════════════════════════════════════════
    # STATS & MONITORING
    # ═══════════════════════════════════════════════════════════════════════

    def get_repo_stats(self, repo_name: str) -> Optional[Dict]:
        """Get repo statistics"""
        try:
            repo = self.get_repo(repo_name)
            if not repo:
                return None

            return {
                "name": repo.name,
                "full_name": repo.full_name,
                "description": repo.description,
                "stars": repo.stargazers_count,
                "forks": repo.forks_count,
                "watchers": repo.watchers_count,
                "open_issues": repo.open_issues_count,
                "language": repo.language,
                "default_branch": repo.default_branch,
                "size_kb": repo.size,
                "license": repo.license.name if repo.license else None,
                "topics": repo.get_topics(),
                "last_push": repo.pushed_at.isoformat() if repo.pushed_at else None,
                "created_at": repo.created_at.isoformat() if repo.created_at else None,
                "commits": repo.get_commits().totalCount,
                "contributors": repo.get_contributors().totalCount,
                "network_count": repo.network_count,
                "subscribers_count": repo.subscribers_count,
            }
        except GithubException as e:
            logger.error(f"❌ get_repo_stats failed: {e}")
            return None

    def get_contributors(self, repo_name: str, limit: int = 20) -> List[Dict]:
        """Get repo contributors"""
        try:
            repo = self.get_repo(repo_name)
            if not repo:
                return []

            contributors = []
            for i, contrib in enumerate(repo.get_contributors()):
                if i >= limit:
                    break
                contributors.append({
                    "login": contrib.login,
                    "contributions": contrib.contributions,
                    "avatar_url": contrib.avatar_url,
                    "url": contrib.html_url,
                })
            return contributors
        except GithubException as e:
            logger.error(f"❌ get_contributors failed: {e}")
            return []

    def get_languages(self, repo_name: str) -> Dict[str, int]:
        """Get language breakdown"""
        try:
            repo = self.get_repo(repo_name)
            if not repo:
                return {}
            return repo.get_languages()
        except GithubException as e:
            logger.error(f"❌ get_languages failed: {e}")
            return {}

    def get_traffic_stats(self, repo_name: str) -> Optional[Dict]:
        """Get traffic stats (views/clones) - requires admin"""
        try:
            repo = self.get_repo(repo_name)
            if not repo:
                return None

            views = repo.get_views_traffic()
            clones = repo.get_clones_traffic()

            return {
                "views": {
                    "count": views.count,
                    "uniques": views.uniques,
                    "views": [{"timestamp": v.timestamp.isoformat(), "count": v.count, "uniques": v.uniques} for v in views.views]
                },
                "clones": {
                    "count": clones.count,
                    "uniques": clones.uniques,
                    "clones": [{"timestamp": c.timestamp.isoformat(), "count": c.count, "uniques": c.uniques} for c in clones.clones]
                }
            }
        except GithubException as e:
            logger.error(f"❌ get_traffic_stats failed: {e}")
            return None

    # ═══════════════════════════════════════════════════════════════════════
    # MILESTONES & PROJECTS
    # ═══════════════════════════════════════════════════════════════════════

    def list_milestones(self, repo_name: str, state: str = "open") -> List[Dict]:
        """List milestones"""
        try:
            repo = self.get_repo(repo_name)
            if not repo:
                return []

            milestones = []
            for ms in repo.get_milestones(state=state):
                milestones.append({
                    "number": ms.number,
                    "title": ms.title,
                    "description": ms.description,
                    "state": ms.state,
                    "due_on": ms.due_on.isoformat() if ms.due_on else None,
                    "open_issues": ms.open_issues,
                    "closed_issues": ms.closed_issues,
                    "url": ms.html_url,
                })
            return milestones
        except GithubException as e:
            logger.error(f"❌ list_milestones failed: {e}")
            return []

    def create_milestone(self, repo_name: str, title: str, description: str = "",
                        due_on: str = None) -> Optional[Dict]:
        """Create milestone"""
        try:
            repo = self.get_repo(repo_name)
            if not repo:
                return None

            due = datetime.fromisoformat(due_on) if due_on else None
            ms = repo.create_milestone(title, description=description, due_on=due)
            logger.info(f"✅ Milestone created: {repo_name}/{title}")
            return {
                "number": ms.number,
                "title": ms.title,
                "url": ms.html_url
            }
        except GithubException as e:
            logger.error(f"❌ create_milestone failed: {e}")
            return None

    # ═══════════════════════════════════════════════════════════════════════
    # WEBHOOKS
    # ═══════════════════════════════════════════════════════════════════════

    def list_webhooks(self, repo_name: str) -> List[Dict]:
        """List webhooks for repo"""
        try:
            repo = self.get_repo(repo_name)
            if not repo:
                return []

            hooks = []
            for hook in repo.get_hooks():
                hooks.append({
                    "id": hook.id,
                    "url": hook.config.get("url", ""),
                    "events": hook.events,
                    "active": hook.active,
                    "last_response": hook.last_response,
                    "updated_at": hook.updated_at.isoformat() if hook.updated_at else None,
                })
            return hooks
        except GithubException as e:
            logger.error(f"❌ list_webhooks failed: {e}")
            return []

    def create_webhook(self, repo_name: str, url: str, events: List[str] = None,
                      secret: str = "", active: bool = True) -> Optional[Dict]:
        """Create webhook"""
        try:
            repo = self.get_repo(repo_name)
            if not repo:
                return None

            hook = repo.create_hook(
                name="web",
                config={
                    "url": url,
                    "content_type": "json",
                    "secret": secret,
                    "insecure_ssl": "0"
                },
                events=events or ["push", "pull_request", "issues", "release"],
                active=active
            )
            logger.info(f"✅ Webhook created: {repo_name} -> {url}")
            return {
                "id": hook.id,
                "url": hook.config.get("url"),
                "events": hook.events
            }
        except GithubException as e:
            logger.error(f"❌ create_webhook failed: {e}")
            return None

    def delete_webhook(self, repo_name: str, hook_id: int) -> bool:
        """Delete webhook"""
        try:
            repo = self.get_repo(repo_name)
            if not repo:
                return False
            hook = repo.get_hook(hook_id)
            hook.delete()
            logger.info(f"✅ Webhook deleted: {repo_name}/{hook_id}")
            return True
        except GithubException as e:
            logger.error(f"❌ delete_webhook failed: {e}")
            return False