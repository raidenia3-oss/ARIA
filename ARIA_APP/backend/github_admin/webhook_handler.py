"""ARIA GitHub Webhook Handler — Listen and respond to GitHub events."""

import hashlib
import hmac
import json
import logging
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class GitHubEvent(str, Enum):
    """GitHub webhook event types"""
    PUSH = "push"
    PULL_REQUEST = "pull_request"
    PULL_REQUEST_REVIEW = "pull_request_review"
    ISSUES = "issues"
    ISSUE_COMMENT = "issue_comment"
    RELEASE = "release"
    WORKFLOW_RUN = "workflow_run"
    WORKFLOW_JOB = "workflow_job"
    REPOSITORY = "repository"
    STAR = "star"
    FORK = "fork"
    WATCH = "watch"
    MEMBER = "member"
    TEAM = "team"
    DEPLOYMENT = "deployment"
    DEPLOYMENT_STATUS = "deployment_status"
    CHECK_RUN = "check_run"
    CHECK_SUITE = "check_suite"
    CODE_SCANNING_ALERT = "code_scanning_alert"
    SECRET_SCANNING_ALERT = "secret_scanning_alert"
    DEPENDABOT_ALERT = "dependabot_alert"


@dataclass
class WebhookEvent:
    """Parsed webhook event"""
    event_type: str
    payload: Dict[str, Any]
    delivery_id: str
    timestamp: datetime
    signature_verified: bool


class WebhookHandler:
    """
    ARIA GitHub Webhook Handler
    Listens for: push, pull_request, issues, release, etc.
    """

    def __init__(self, webhook_secret: str, github_client):
        self.webhook_secret = webhook_secret.encode('utf-8') if isinstance(webhook_secret, str) else webhook_secret
        self.client = github_client
        self.handlers: Dict[str, List[Callable]] = {}
        self.global_handlers: List[Callable] = []

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verify webhook came from GitHub using HMAC SHA256"""
        if not signature or not signature.startswith("sha256="):
            return False

        expected = "sha256=" + hmac.new(
            self.webhook_secret,
            payload,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(signature, expected)

    def register_handler(self, event: str, handler: Callable):
        """Register event handler for specific event type"""
        if event not in self.handlers:
            self.handlers[event] = []
        self.handlers[event].append(handler)
        logger.info(f"✅ Handler registered: {event}")

    def register_global_handler(self, handler: Callable):
        """Register handler that receives ALL events"""
        self.global_handlers.append(handler)
        logger.info(f"✅ Global handler registered")

    def unregister_handler(self, event: str, handler: Callable):
        """Unregister a specific handler"""
        if event in self.handlers and handler in self.handlers[event]:
            self.handlers[event].remove(handler)
            logger.info(f"✅ Handler unregistered: {event}")

    def handle_event(self, event: str, payload: Dict[str, Any],
                    delivery_id: str = "", signature: str = "",
                    raw_payload: bytes = b"") -> Dict[str, Any]:
        """
        Handle incoming webhook event

        Returns dict with results from all handlers
        """
        verified = True
        if signature and raw_payload:
            verified = self.verify_signature(raw_payload, signature)

        webhook_event = WebhookEvent(
            event_type=event,
            payload=payload,
            delivery_id=delivery_id,
            timestamp=datetime.now(),
            signature_verified=verified
        )

        results = {
            "event": event,
            "delivery_id": delivery_id,
            "verified": verified,
            "handlers_executed": 0,
            "handler_results": [],
            "errors": []
        }

        if not verified:
            logger.warning(f"⚠️ Webhook signature verification failed for {event}")
            results["errors"].append("Signature verification failed")

        # Execute global handlers first
        for handler in self.global_handlers:
            try:
                result = handler(webhook_event)
                results["handler_results"].append({"handler": handler.__name__, "result": result})
                results["handlers_executed"] += 1
            except Exception as e:
                logger.error(f"❌ Global handler error: {e}")
                results["errors"].append(f"Global handler {handler.__name__}: {str(e)}")

        # Execute event-specific handlers
        if event in self.handlers:
            for handler in self.handlers[event]:
                try:
                    result = handler(webhook_event)
                    results["handler_results"].append({"handler": handler.__name__, "result": result})
                    results["handlers_executed"] += 1
                except Exception as e:
                    logger.error(f"❌ Handler error for {event}: {e}")
                    results["errors"].append(f"Handler {handler.__name__}: {str(e)}")
        else:
            logger.warning(f"⚠️ No handler for event: {event}")

        logger.info(f"✅ Event handled: {event} ({results['handlers_executed']} handlers)")
        return results

    def process_webhook(self, event: str, payload: Dict[str, Any],
                       delivery_id: str = "", signature: str = "",
                       raw_payload: bytes = b"") -> Dict[str, Any]:
        """
        Process webhook with full payload handling
        (Convenience method for FastAPI integration)
        """
        return self.handle_event(event, payload, delivery_id, signature, raw_payload)


# ═══════════════════════════════════════════════════════════════════════
# BUILT-IN HANDLERS
# ═══════════════════════════════════════════════════════════════════════

def create_push_handler(github_client) -> Callable:
    """Create a push event handler"""

    def handler(event: WebhookEvent):
        payload = event.payload
        repo = payload["repository"]["name"]
        branch = payload["ref"].split("/")[-1]
        commits = payload.get("commits", [])
        pusher = payload.get("pusher", {}).get("name", "unknown")

        logger.info(f"📤 Push: {repo}/{branch} by {pusher} ({len(commits)} commits)")

        # Log each commit
        for commit in commits:
            logger.info(f"   - {commit['id'][:7]}: {commit['message'][:80]} by {commit['author']['name']}")

        return {
            "action": "logged",
            "repo": repo,
            "branch": branch,
            "commits_count": len(commits)
        }

    return handler


def create_pr_handler(github_client) -> Callable:
    """Create a pull request event handler"""

    def handler(event: WebhookEvent):
        payload = event.payload
        action = payload["action"]  # opened, synchronize, closed, merged, reopened, review_requested
        pr = payload["pull_request"]
        repo = payload["repository"]["name"]

        logger.info(f"📋 PR {action}: {repo}#{pr['number']} - {pr['title']}")

        # Auto-merge if configured and all checks pass
        if action == "closed" and pr.get("merged"):
            logger.info(f"✅ PR merged: {repo}#{pr['number']}")

        return {
            "action": "logged",
            "repo": repo,
            "pr_number": pr['number'],
            "pr_action": action,
            "merged": pr.get("merged", False)
        }

    return handler


def create_issue_handler(github_client) -> Callable:
    """Create an issues event handler"""

    def handler(event: WebhookEvent):
        payload = event.payload
        action = payload["action"]  # opened, closed, reopened, edited, labeled, unlabeled
        issue = payload["issue"]
        repo = payload["repository"]["name"]

        logger.info(f"🐛 Issue {action}: {repo}#{issue['number']} - {issue['title']}")

        return {
            "action": "logged",
            "repo": repo,
            "issue_number": issue['number'],
            "issue_action": action
        }

    return handler


def create_release_handler(github_client) -> Callable:
    """Create a release event handler"""

    def handler(event: WebhookEvent):
        payload = event.payload
        action = payload["action"]  # published, created, edited, deleted, prereleased, released
        release = payload["release"]
        repo = payload["repository"]["name"]

        logger.info(f"🎁 Release {action}: {repo}/{release['tag_name']}")

        return {
            "action": "logged",
            "repo": repo,
            "release_tag": release['tag_name'],
            "release_action": action
        }

    return handler


def create_workflow_handler(github_client) -> Callable:
    """Create a workflow run event handler"""

    def handler(event: WebhookEvent):
        payload = event.payload
        action = payload["action"]  # completed, requested, in_progress
        run = payload["workflow_run"]
        repo = payload["repository"]["name"]

        logger.info(f"⚙️ Workflow {action}: {repo}/{run['name']} #{run['run_number']} - {run['conclusion'] or run['status']}")

        # Notify on failure
        if action == "completed" and run["conclusion"] == "failure":
            logger.warning(f"⚠️ Workflow failed: {repo}/{run['name']}")

        return {
            "action": "logged",
            "repo": repo,
            "workflow": run['name'],
            "run_number": run['run_number'],
            "conclusion": run.get('conclusion'),
            "status": run.get('status')
        }

    return handler


def create_auto_label_handler(github_client, label_rules: Dict[str, List[str]]) -> Callable:
    """
    Create an auto-label handler based on file patterns

    label_rules = {
        "frontend": ["*.tsx", "*.ts", "*.css", "*.html"],
        "backend": ["*.py", "*.rs", "*.go"],
        "docs": ["*.md", "*.rst", "docs/*"],
        "config": ["*.yaml", "*.yml", "*.toml", "*.json"],
    }
    """

    def handler(event: WebhookEvent):
        payload = event.payload
        if event.event_type != "pull_request":
            return

        pr = payload["pull_request"]
        repo_name = payload["repository"]["name"]
        pr_number = pr["number"]

        # Get changed files
        # Note: This requires an additional API call to get PR files
        # For now, we'll use the title/body for basic labeling
        title = pr["title"].lower()
        body = (pr.get("body") or "").lower()

        labels_to_add = []
        for label, patterns in label_rules.items():
            for pattern in patterns:
                # Simple pattern matching
                if pattern.replace("*", "") in title or pattern.replace("*", "") in body:
                    labels_to_add.append(label)
                    break

        if labels_to_add:
            github_client.add_labels(repo_name, pr_number, labels_to_add)
            logger.info(f"🏷️ Auto-labeled PR {repo_name}#{pr_number}: {labels_to_add}")

        return {"labels_added": labels_to_add}

    return handler


def create_auto_assign_handler(github_client, assignees: List[str]) -> Callable:
    """Create auto-assign handler for new issues/PRs"""

    def handler(event: WebhookEvent):
        payload = event.payload
        action = payload["action"]

        if event.event_type == "issues" and action == "opened":
            issue = payload["issue"]
            repo_name = payload["repository"]["name"]
            issue_number = issue["number"]

            # Round-robin assignment
            import random
            assignee = random.choice(assignees)
            github_client.update_issue(repo_name, issue_number, assignees=[assignee])
            logger.info(f"👤 Auto-assigned issue {repo_name}#{issue_number} to {assignee}")

        elif event.event_type == "pull_request" and action == "opened":
            pr = payload["pull_request"]
            repo_name = payload["repository"]["name"]
            pr_number = pr["number"]

            import random
            assignee = random.choice(assignees)
            # Note: PR assignment requires different API
            logger.info(f"👤 Would assign PR {repo_name}#{pr_number} to {assignee}")

    return handler


# ═══════════════════════════════════════════════════════════════════════
# DEFAULT HANDLER SETUP
# ═══════════════════════════════════════════════════════════════════════

def setup_default_handlers(webhook_handler: WebhookHandler, github_client):
    """Set up default handlers for common events"""
    webhook_handler.register_handler("push", create_push_handler(github_client))
    webhook_handler.register_handler("pull_request", create_pr_handler(github_client))
    webhook_handler.register_handler("issues", create_issue_handler(github_client))
    webhook_handler.register_handler("release", create_release_handler(github_client))
    webhook_handler.register_handler("workflow_run", create_workflow_handler(github_client))

    # Global logger
    def log_all(event: WebhookEvent):
        logger.debug(f"📥 Webhook: {event.event_type} (verified: {event.signature_verified})")

    webhook_handler.register_global_handler(log_all)