"""ARIA GitHub Admin Module — Complete GitHub Integration for DevOps Automation."""

from .github_client import GitHubAdminClient
from .auto_commit import AutoCommit
from .auto_release import AutoRelease
from .webhook_handler import WebhookHandler
from .pr_analyzer import PRAnalyzer
from .issue_manager import IssueManager
from .ci_cd_monitor import CICDMonitor
from .doc_generator import DocGenerator
from .config_manager import ConfigManager
from .admin_dashboard import AdminDashboard
from .router import router

__all__ = [
    "GitHubAdminClient",
    "AutoCommit",
    "AutoRelease",
    "WebhookHandler",
    "PRAnalyzer",
    "IssueManager",
    "CICDMonitor",
    "DocGenerator",
    "ConfigManager",
    "AdminDashboard",
    "router",
]

__version__ = "1.0.0"