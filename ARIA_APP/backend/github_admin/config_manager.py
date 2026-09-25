"""ARIA Config Manager — Manage repository settings, protections, rules, and secrets."""

import logging
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class PermissionLevel(str, Enum):
    """Repository permission levels"""
    ADMIN = "admin"
    MAINTAIN = "maintain"
    WRITE = "write"
    TRIAGE = "triage"
    READ = "read"


class MergeMethod(str, Enum):
    """Allowed merge methods"""
    MERGE = "merge"
    SQUASH = "squash"
    REBASE = "rebase"


@dataclass
class BranchProtectionConfig:
    """Branch protection configuration"""
    branch: str = "main"
    required_reviews: int = 1
    dismiss_stale_reviews: bool = True
    require_code_owner_reviews: bool = False
    required_status_checks: List[str] = field(default_factory=list)
    strict_status_checks: bool = True
    enforce_admins: bool = True
    require_linear_history: bool = True
    allow_force_pushes: bool = False
    allow_deletions: bool = False
    required_conversation_resolution: bool = True


@dataclass
class RepoSettings:
    """Repository settings configuration"""
    name: str
    description: str = ""
    homepage: str = ""
    private: bool = False
    has_issues: bool = True
    has_projects: bool = True
    has_wiki: bool = False
    has_downloads: bool = True
    allow_squash_merge: bool = True
    allow_merge_commit: bool = False
    allow_rebase_merge: bool = False
    allow_auto_merge: bool = True
    delete_branch_on_merge: bool = True
    allow_update_branch: bool = True
    archived: bool = False
    template: bool = False


class ConfigManager:
    """
    ARIA Config Manager
    Manages repository settings, branch protections, rules, and secrets
    """

    def __init__(self, github_client):
        self.client = github_client

    # ═══════════════════════════════════════════════════════════════════════
    # REPOSITORY SETTINGS
    # ═══════════════════════════════════════════════════════════════════════

    def get_repo_settings(self, repo_name: str) -> Optional[RepoSettings]:
        """Get current repository settings"""
        try:
            repo = self.client.get_repo(repo_name)
            if not repo:
                return None

            return RepoSettings(
                name=repo.name,
                description=repo.description or "",
                homepage=repo.homepage or "",
                private=repo.private,
                has_issues=repo.has_issues,
                has_projects=repo.has_projects,
                has_wiki=repo.has_wiki,
                has_downloads=repo.has_downloads,
                allow_squash_merge=repo.allow_squash_merge,
                allow_merge_commit=repo.allow_merge_commit,
                allow_rebase_merge=repo.allow_rebase_merge,
                allow_auto_merge=repo.allow_auto_merge,
                delete_branch_on_merge=repo.delete_branch_on_merge,
                allow_update_branch=repo.allow_update_branch,
                archived=repo.archived,
                template=repo.template_repository is not None
            )
        except Exception as e:
            logger.error(f"❌ get_repo_settings failed: {e}")
            return None

    def update_repo_settings(self, repo_name: str, settings: RepoSettings) -> bool:
        """Update repository settings"""
        try:
            repo = self.client.get_repo(repo_name)
            if not repo:
                return False

            repo.edit(
                description=settings.description,
                homepage=settings.homepage,
                private=settings.private,
                has_issues=settings.has_issues,
                has_projects=settings.has_projects,
                has_wiki=settings.has_wiki,
                has_downloads=settings.has_downloads,
                allow_squash_merge=settings.allow_squash_merge,
                allow_merge_commit=settings.allow_merge_commit,
                allow_rebase_merge=settings.allow_rebase_merge,
                allow_auto_merge=settings.allow_auto_merge,
                delete_branch_on_merge=settings.delete_branch_on_merge,
                allow_update_branch=settings.allow_update_branch,
                archived=settings.archived
            )
            logger.info(f"✅ Repo settings updated: {repo_name}")
            return True
        except Exception as e:
            logger.error(f"❌ update_repo_settings failed: {e}")
            return False

    def apply_standard_settings(self, repo_name: str, profile: str = "standard") -> bool:
        """Apply standard settings profile"""
        profiles = {
            "standard": RepoSettings(
                name="",  # Will be filled
                has_issues=True,
                has_projects=True,
                has_wiki=False,
                allow_squash_merge=True,
                allow_merge_commit=False,
                allow_rebase_merge=False,
                allow_auto_merge=True,
                delete_branch_on_merge=True,
                allow_update_branch=True,
            ),
            "open_source": RepoSettings(
                name="",
                private=False,
                has_issues=True,
                has_projects=True,
                has_wiki=True,
                has_downloads=True,
                allow_squash_merge=True,
                allow_merge_commit=True,
                allow_rebase_merge=True,
                allow_auto_merge=True,
                delete_branch_on_merge=True,
            ),
            "private_team": RepoSettings(
                name="",
                private=True,
                has_issues=True,
                has_projects=True,
                has_wiki=False,
                allow_squash_merge=True,
                allow_merge_commit=False,
                allow_rebase_merge=False,
                allow_auto_merge=True,
                delete_branch_on_merge=True,
            ),
            "archived": RepoSettings(
                name="",
                archived=True,
                has_issues=False,
                has_projects=False,
                has_wiki=False,
                allow_squash_merge=False,
                allow_merge_commit=False,
                allow_rebase_merge=False,
            ),
        }

        if profile not in profiles:
            logger.error(f"❌ Unknown profile: {profile}")
            return False

        settings = profiles[profile]
        settings.name = repo_name

        # Preserve existing description
        current = self.get_repo_settings(repo_name)
        if current:
            settings.description = current.description
            settings.homepage = current.homepage

        return self.update_repo_settings(repo_name, settings)

    # ═══════════════════════════════════════════════════════════════════════
    # BRANCH PROTECTION
    # ═══════════════════════════════════════════════════════════════════════

    def get_branch_protection(self, repo_name: str, branch: str = "main") -> Optional[BranchProtectionConfig]:
        """Get current branch protection config"""
        try:
            repo = self.client.get_repo(repo_name)
            if not repo:
                return None

            branch_obj = repo.get_branch(branch)
            try:
                protection = branch_obj.get_protection()
            except Exception:
                return None  # No protection

            config = BranchProtectionConfig(branch=branch)

            if protection.required_pull_request_reviews:
                config.required_reviews = protection.required_pull_request_reviews.required_approving_review_count
                config.dismiss_stale_reviews = protection.required_pull_request_reviews.dismiss_stale_reviews
                config.require_code_owner_reviews = protection.required_pull_request_reviews.require_code_owner_reviews

            if protection.required_status_checks:
                config.required_status_checks = protection.required_status_checks.contexts
                config.strict_status_checks = protection.required_status_checks.strict

            config.enforce_admins = protection.enforce_admins
            config.require_linear_history = protection.required_linear_history if hasattr(protection, 'required_linear_history') else True
            config.allow_force_pushes = protection.allow_force_pushes if hasattr(protection, 'allow_force_pushes') else False
            config.allow_deletions = protection.allow_deletions if hasattr(protection, 'allow_deletions') else False

            return config
        except Exception as e:
            logger.error(f"❌ get_branch_protection failed: {e}")
            return None

    def set_branch_protection(self, repo_name: str, config: BranchProtectionConfig) -> bool:
        """Set branch protection rules"""
        try:
            repo = self.client.get_repo(repo_name)
            if not repo:
                return False

            branch_obj = repo.get_branch(config.branch)

            # Build protection params
            params = {
                "enforce_admins": config.enforce_admins,
            }

            if config.required_reviews > 0:
                params["required_pull_request_reviews"] = {
                    "dismiss_stale_reviews": config.dismiss_stale_reviews,
                    "required_approving_review_count": config.required_reviews,
                    "require_code_owner_reviews": config.require_code_owner_reviews,
                }

            if config.required_status_checks:
                params["required_status_checks"] = {
                    "strict": config.strict_status_checks,
                    "contexts": config.required_status_checks,
                }

            if config.require_linear_history:
                params["required_linear_history"] = True

            if config.allow_force_pushes:
                params["allow_force_pushes"] = True

            if config.allow_deletions:
                params["allow_deletions"] = True

            branch_obj.edit_protection(**params)
            logger.info(f"✅ Branch protection set: {repo_name}/{config.branch}")
            return True
        except Exception as e:
            logger.error(f"❌ set_branch_protection failed: {e}")
            return False

    def apply_protection_profile(self, repo_name: str, branch: str = "main",
                                profile: str = "standard") -> bool:
        """Apply branch protection profile"""
        profiles = {
            "strict": BranchProtectionConfig(
                branch=branch,
                required_reviews=2,
                dismiss_stale_reviews=True,
                require_code_owner_reviews=True,
                required_status_checks=["ci", "test", "lint", "security"],
                strict_status_checks=True,
                enforce_admins=True,
                require_linear_history=True,
                allow_force_pushes=False,
                allow_deletions=False,
            ),
            "standard": BranchProtectionConfig(
                branch=branch,
                required_reviews=1,
                dismiss_stale_reviews=True,
                require_code_owner_reviews=False,
                required_status_checks=["ci", "test"],
                strict_status_checks=True,
                enforce_admins=True,
                require_linear_history=True,
            ),
            "lenient": BranchProtectionConfig(
                branch=branch,
                required_reviews=1,
                dismiss_stale_reviews=False,
                required_status_checks=["ci"],
                strict_status_checks=False,
                enforce_admins=False,
                require_linear_history=False,
            ),
            "open_source": BranchProtectionConfig(
                branch=branch,
                required_reviews=1,
                dismiss_stale_reviews=True,
                required_status_checks=["ci", "test", "lint"],
                strict_status_checks=True,
                enforce_admins=False,
                require_linear_history=False,
                allow_force_pushes=False,
            ),
        }

        if profile not in profiles:
            logger.error(f"❌ Unknown protection profile: {profile}")
            return False

        return self.set_branch_protection(repo_name, profiles[profile])

    # ═══════════════════════════════════════════════════════════════════════
    # SECRETS MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════

    def list_secrets(self, repo_name: str) -> List[Dict]:
        """List repository secrets (names only, not values)"""
        try:
            repo = self.client.get_repo(repo_name)
            if not repo:
                return []

            secrets = []
            for secret in repo.get_secrets():
                secrets.append({
                    "name": secret.name,
                    "created_at": secret.created_at.isoformat() if secret.created_at else None,
                    "updated_at": secret.updated_at.isoformat() if secret.updated_at else None,
                })
            return secrets
        except Exception as e:
            logger.error(f"❌ list_secrets failed: {e}")
            return []

    def set_secret(self, repo_name: str, name: str, value: str) -> bool:
        """Set a repository secret"""
        return self.client.set_secret(repo_name, name, value)

    def delete_secret(self, repo_name: str, name: str) -> bool:
        """Delete a repository secret"""
        return self.client.delete_secret(repo_name, name)

    def sync_secrets(self, repo_name: str, secrets: Dict[str, str],
                    delete_missing: bool = False) -> Dict:
        """Sync multiple secrets at once"""
        results = {"created": [], "updated": [], "deleted": [], "errors": []}

        existing = {s["name"]: s for s in self.list_secrets(repo_name)}

        for name, value in secrets.items():
            try:
                if name in existing:
                    self.set_secret(repo_name, name, value)
                    results["updated"].append(name)
                else:
                    self.set_secret(repo_name, name, value)
                    results["created"].append(name)
            except Exception as e:
                results["errors"].append({"name": name, "error": str(e)})

        if delete_missing:
            for name in existing:
                if name not in secrets:
                    try:
                        self.delete_secret(repo_name, name)
                        results["deleted"].append(name)
                    except Exception as e:
                        results["errors"].append({"name": name, "error": str(e)})

        return results

    # ═══════════════════════════════════════════════════════════════════════
    # COLLABORATORS & TEAMS
    # ═══════════════════════════════════════════════════════════════════════

    def list_collaborators(self, repo_name: str, permission: PermissionLevel = None) -> List[Dict]:
        """List repository collaborators"""
        try:
            repo = self.client.get_repo(repo_name)
            if not repo:
                return []

            collaborators = []
            for collab in repo.get_collaborators():
                if permission and collab.permissions != permission.value:
                    continue
                collaborators.append({
                    "login": collab.login,
                    "permissions": collab.permissions,
                    "role": collab.role_name if hasattr(collab, 'role_name') else None,
                })
            return collaborators
        except Exception as e:
            logger.error(f"❌ list_collaborators failed: {e}")
            return []

    def add_collaborator(self, repo_name: str, username: str,
                        permission: PermissionLevel = PermissionLevel.WRITE) -> bool:
        """Add collaborator to repository"""
        try:
            repo = self.client.get_repo(repo_name)
            if not repo:
                return False

            repo.add_to_collaborators(username, permission.value)
            logger.info(f"✅ Collaborator added: {username} to {repo_name} ({permission.value})")
            return True
        except Exception as e:
            logger.error(f"❌ add_collaborator failed: {e}")
            return False

    def remove_collaborator(self, repo_name: str, username: str) -> bool:
        """Remove collaborator from repository"""
        try:
            repo = self.client.get_repo(repo_name)
            if not repo:
                return False

            repo.remove_from_collaborators(username)
            logger.info(f"✅ Collaborator removed: {username} from {repo_name}")
            return True
        except Exception as e:
            logger.error(f"❌ remove_collaborator failed: {e}")
            return False

    def list_teams(self, repo_name: str) -> List[Dict]:
        """List teams with access to repository"""
        try:
            repo = self.client.get_repo(repo_name)
            if not repo:
                return []

            teams = []
            for team in repo.get_teams():
                teams.append({
                    "id": team.id,
                    "name": team.name,
                    "slug": team.slug,
                    "permission": team.permission,
                    "privacy": team.privacy,
                })
            return teams
        except Exception as e:
            logger.error(f"❌ list_teams failed: {e}")
            return []

    # ═══════════════════════════════════════════════════════════════════════
    # WEBHOOKS
    # ═══════════════════════════════════════════════════════════════════════

    def configure_webhooks(self, repo_name: str, webhook_url: str,
                          events: List[str] = None, secret: str = "") -> bool:
        """Configure webhooks for repository"""
        try:
            # Delete existing webhooks to same URL
            existing = self.client.list_webhooks(repo_name)
            for hook in existing:
                if hook["url"] == webhook_url:
                    self.client.delete_webhook(repo_name, hook["id"])

            # Create new webhook
            self.client.create_webhook(
                repo_name=repo_name,
                url=webhook_url,
                events=events or ["push", "pull_request", "issues", "release", "workflow_run"],
                secret=secret
            )
            return True
        except Exception as e:
            logger.error(f"❌ configure_webhooks failed: {e}")
            return False

    # ═══════════════════════════════════════════════════════════════════════
    # DEPLOY KEYS
    # ═══════════════════════════════════════════════════════════════════════

    def list_deploy_keys(self, repo_name: str) -> List[Dict]:
        """List deploy keys"""
        try:
            repo = self.client.get_repo(repo_name)
            if not repo:
                return []

            keys = []
            for key in repo.get_keys():
                keys.append({
                    "id": key.id,
                    "title": key.title,
                    "read_only": key.read_only,
                    "created_at": key.created_at.isoformat() if key.created_at else None,
                })
            return keys
        except Exception as e:
            logger.error(f"❌ list_deploy_keys failed: {e}")
            return []

    def add_deploy_key(self, repo_name: str, title: str, key: str, read_only: bool = True) -> bool:
        """Add deploy key"""
        try:
            repo = self.client.get_repo(repo_name)
            if not repo:
                return False

            repo.create_key(title, key, read_only)
            logger.info(f"✅ Deploy key added: {title} to {repo_name}")
            return True
        except Exception as e:
            logger.error(f"❌ add_deploy_key failed: {e}")
            return False

    # ═══════════════════════════════════════════════════════════════════════
    # TOPICS & LABELS
    # ═══════════════════════════════════════════════════════════════════════

    def set_topics(self, repo_name: str, topics: List[str]) -> bool:
        """Set repository topics"""
        try:
            repo = self.client.get_repo(repo_name)
            if not repo:
                return False

            repo.replace_topics(topics)
            logger.info(f"✅ Topics updated: {repo_name} - {topics}")
            return True
        except Exception as e:
            logger.error(f"❌ set_topics failed: {e}")
            return False

    def get_labels(self, repo_name: str) -> List[Dict]:
        """Get all labels in repository"""
        try:
            repo = self.client.get_repo(repo_name)
            if not repo:
                return []

            labels = []
            for label in repo.get_labels():
                labels.append({
                    "name": label.name,
                    "color": label.color,
                    "description": label.description,
                })
            return labels
        except Exception as e:
            logger.error(f"❌ get_labels failed: {e}")
            return []

    def create_label(self, repo_name: str, name: str, color: str,
                    description: str = "") -> bool:
        """Create a label"""
        try:
            repo = self.client.get_repo(repo_name)
            if not repo:
                return False

            repo.create_label(name, color, description)
            logger.info(f"✅ Label created: {name} in {repo_name}")
            return True
        except Exception as e:
            logger.error(f"❌ create_label failed: {e}")
            return False

    def sync_labels(self, repo_name: str, labels: List[Dict],
                   delete_missing: bool = False) -> Dict:
        """Sync labels to match desired state"""
        results = {"created": [], "updated": [], "deleted": [], "errors": []}

        existing = {l["name"]: l for l in self.get_labels(repo_name)}

        for label in labels:
            try:
                name = label["name"]
                color = label.get("color", "ededed")
                description = label.get("description", "")

                if name in existing:
                    # Update if different
                    if existing[name]["color"] != color or existing[name]["description"] != description:
                        # GitHub API doesn't have direct update, need to delete and recreate
                        repo = self.client.get_repo(repo_name)
                        repo.get_label(name).delete()
                        repo.create_label(name, color, description)
                        results["updated"].append(name)
                else:
                    self.create_label(repo_name, name, color, description)
                    results["created"].append(name)
            except Exception as e:
                results["errors"].append({"name": label.get("name"), "error": str(e)})

        if delete_missing:
            for name in existing:
                if name not in [l["name"] for l in labels]:
                    try:
                        repo = self.client.get_repo(repo_name)
                        repo.get_label(name).delete()
                        results["deleted"].append(name)
                    except Exception as e:
                        results["errors"].append({"name": name, "error": str(e)})

        return results

    # ═══════════════════════════════════════════════════════════════════════
    # MILESTONES
    # ═══════════════════════════════════════════════════════════════════════

    def create_milestone(self, repo_name: str, title: str,
                        description: str = "", due_on: str = None) -> Optional[Dict]:
        """Create a milestone"""
        return self.client.create_milestone(repo_name, title, description, due_on)

    def close_milestone(self, repo_name: str, title: str) -> bool:
        """Close a milestone"""
        try:
            repo = self.client.get_repo(repo_name)
            if not repo:
                return False

            for ms in repo.get_milestones(state="open"):
                if ms.title == title:
                    ms.edit(state="closed")
                    logger.info(f"✅ Milestone closed: {title}")
                    return True
            return False
        except Exception as e:
            logger.error(f"❌ close_milestone failed: {e}")
            return False