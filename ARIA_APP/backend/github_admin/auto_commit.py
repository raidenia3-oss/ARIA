"""ARIA Auto-Commit Engine — Monitor directories and auto-commit changes."""

import os
import subprocess
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Callable, Dict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CommitConfig:
    """Configuration for auto-commit behavior"""
    repo_path: str
    interval_minutes: int = 30
    message_template: str = "🤖 ARIA auto-commit: {timestamp}"
    files: Optional[List[str]] = None
    branch: str = "main"
    remote: str = "origin"
    author_name: str = "ARIA Bot"
    author_email: str = "aria@raidenia3-oss.dev"
    committer_name: str = "ARIA Bot"
    committer_email: str = "aria@raidenia3-oss.dev"
    pre_commit_hooks: bool = False
    push_after_commit: bool = True


class AutoCommit:
    """
    ARIA Auto-Commit Engine
    Monitors directories → auto-commits changes
    """

    def __init__(self, token: str = ""):
        self.token = token
        self.active_monitors: dict[str, threading.Thread] = {}
        self.stop_events: dict[str, threading.Event] = {}

    def _get_git_env(self, config: CommitConfig) -> dict:
        """Get environment with git author/committer info"""
        return {
            **os.environ,
            "GIT_AUTHOR_NAME": config.author_name,
            "GIT_AUTHOR_EMAIL": config.author_email,
            "GIT_COMMITTER_NAME": config.committer_name,
            "GIT_COMMITTER_EMAIL": config.committer_email,
        }

    def _run_git(self, repo_path: str, args: List[str], env: dict) -> subprocess.CompletedProcess:
        """Run git command"""
        return subprocess.run(
            ["git", "-C", repo_path] + args,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def is_git_repo(self, repo_path: str) -> bool:
        """Check if path is a git repository"""
        return os.path.exists(os.path.join(repo_path, ".git"))

    def has_changes(self, repo_path: str, config: CommitConfig) -> bool:
        """Check if there are staged or unstaged changes"""
        env = self._get_git_env(config)

        # Check unstaged changes
        result = self._run_git(repo_path, ["status", "--porcelain"], env)
        if result.stdout.strip():
            return True

        # Check staged changes
        result = self._run_git(repo_path, ["diff", "--cached", "--quiet"], env)
        return result.returncode != 0

    def get_changed_files(self, repo_path: str, config: CommitConfig) -> List[str]:
        """Get list of changed files"""
        env = self._get_git_env(config)
        result = self._run_git(repo_path, ["status", "--porcelain"], env)
        files = []
        for line in result.stdout.strip().split('\n'):
            if line:
                # Format: "XY filename" where XY are status codes
                files.append(line[3:].strip())
        return files

    def auto_commit(self, repo_path: str, message: str = "",
                   files: Optional[List[str]] = None,
                   config: Optional[CommitConfig] = None) -> bool:
        """
        Auto-commit changes in repo

        Args:
            repo_path: local repo path
            message: commit message (auto-generate if empty)
            files: specific files to commit (all if None)
            config: optional CommitConfig for advanced options
        """
        if config is None:
            config = CommitConfig(repo_path=repo_path)

        try:
            # Validate git repo
            if not self.is_git_repo(repo_path):
                logger.error(f"❌ Not a git repo: {repo_path}")
                return False

            env = self._get_git_env(config)

            # Stage files
            if files:
                for f in files:
                    result = self._run_git(repo_path, ["add", f], env)
                    if result.returncode != 0:
                        logger.error(f"❌ git add failed for {f}: {result.stderr}")
                        return False
            else:
                result = self._run_git(repo_path, ["add", "."], env)
                if result.returncode != 0:
                    logger.error(f"❌ git add failed: {result.stderr}")
                    return False

            # Check if there are changes to commit
            result = self._run_git(repo_path, ["diff", "--cached", "--quiet"], env)

            if result.returncode != 0:  # Changes exist
                # Auto-generate message if not provided
                if not message:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    message = config.message_template.format(timestamp=timestamp)

                # Run pre-commit hooks if enabled
                if config.pre_commit_hooks:
                    result = self._run_git(repo_path, ["commit", "-m", message], env)
                else:
                    result = self._run_git(repo_path, ["commit", "-m", message, "--no-verify"], env)

                if result.returncode != 0:
                    logger.error(f"❌ git commit failed: {result.stderr}")
                    return False

                # Push if enabled
                if config.push_after_commit:
                    result = self._run_git(repo_path, ["push", config.remote, config.branch], env)
                    if result.returncode != 0:
                        logger.error(f"❌ git push failed: {result.stderr}")
                        return False

                logger.info(f"✅ Auto-commit: {repo_path} → {message}")
                return True
            else:
                logger.info(f"ℹ️ No changes to commit: {repo_path}")
                return False

        except subprocess.CalledProcessError as e:
            logger.error(f"❌ auto_commit failed: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"❌ auto_commit error: {e}")
            return False

    def monitor_and_commit(self, repo_path: str, interval_minutes: int = 30,
                          message_template: str = "🤖 ARIA: {timestamp}",
                          config: Optional[CommitConfig] = None):
        """
        Monitor repo directory and auto-commit periodically
        (Run in background thread)
        """
        if config is None:
            config = CommitConfig(
                repo_path=repo_path,
                interval_minutes=interval_minutes,
                message_template=message_template
            )
        else:
            config.repo_path = repo_path
            config.interval_minutes = interval_minutes
            config.message_template = message_template

        stop_event = threading.Event()
        self.stop_events[repo_path] = stop_event

        def monitor():
            logger.info(f"✅ Monitor started: {repo_path} (interval: {interval_minutes}min)")
            while not stop_event.is_set():
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                message = message_template.format(timestamp=timestamp)
                self.auto_commit(repo_path, message, config=config)

                # Sleep in small chunks to allow quick shutdown
                for _ in range(interval_minutes * 60):
                    if stop_event.is_set():
                        break
                    time.sleep(1)

        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()
        self.active_monitors[repo_path] = thread
        return thread

    def stop_monitor(self, repo_path: str) -> bool:
        """Stop monitoring a repo"""
        if repo_path in self.stop_events:
            self.stop_events[repo_path].set()
            del self.stop_events[repo_path]

        if repo_path in self.active_monitors:
            thread = self.active_monitors[repo_path]
            thread.join(timeout=5)
            del self.active_monitors[repo_path]
            logger.info(f"✅ Monitor stopped: {repo_path}")
            return True

        return False

    def stop_all_monitors(self):
        """Stop all active monitors"""
        for repo_path in list(self.active_monitors.keys()):
            self.stop_monitor(repo_path)

    def get_status(self) -> Dict:
        """Get status of all monitors"""
        return {
            "active_monitors": list(self.active_monitors.keys()),
            "count": len(self.active_monitors)
        }


# Convenience function for simple usage
def auto_commit(repo_path: str, message: str = "", files: Optional[List[str]] = None,
               token: str = "") -> bool:
    """Simple auto-commit function"""
    ac = AutoCommit(token=token)
    return ac.auto_commit(repo_path, message, files)