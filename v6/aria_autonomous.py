#!/usr/bin/env python3
"""
ARIA Autonomous Controller v6.0
Analyzes git log every 5 minutes, auto-commits improvements, creates GitHub issues.
"""

import os
import sys
import json
import time
import logging
import subprocess
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("aria-autonomous")

REPO_ROOT = Path(os.getenv("ARIA_REPO_ROOT", "C:/Users/User/Downloads/AURA"))
BRANCH = os.getenv("ARIA_BRANCH", "feature/v6.0-axum-migration")
INTERVAL = int(os.getenv("ARIA_AUTONOMOUS_INTERVAL", "300"))
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "owner/repo")


def discord_notify(content: str, username: str = "ARIA Autonomous") -> bool:
    if not DISCORD_WEBHOOK:
        return False
    payload = json.dumps({"content": content, "username": username}).encode()
    req = urllib.request.Request(
        DISCORD_WEBHOOK,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 204
    except Exception as e:
        log.warning(f"Discord webhook failed: {e}")
        return False


def run_cmd(cmd: List[str], cwd: Path = REPO_ROOT) -> tuple[int, str, str]:
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=60)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)


def get_git_log(since_minutes: int = 10) -> List[Dict[str, str]]:
    since = (datetime.now() - timedelta(minutes=since_minutes)).strftime("%Y-%m-%d %H:%M:%S")
    code, out, err = run_cmd(["git", "log", f"--since={since}", "--pretty=format:%H|%an|%s", "--no-merges"])
    if code != 0:
        log.warning(f"git log failed: {err}")
        return []

    commits = []
    for line in out.splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3:
            commits.append({"hash": parts[0], "author": parts[1], "message": parts[2]})
    return commits


def analyze_commits(commits: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    improvements = []
    patterns = {
        "fix": ["fix", "bug", "error", "crash", "fail", "issue"],
        "perf": ["perf", "optimize", "speed", "fast", "memory", "cpu"],
        "refactor": ["refactor", "cleanup", "reorganize", "restructure"],
        "feat": ["feat", "feature", "add", "implement", "support"],
        "docs": ["doc", "readme", "comment", "typo"],
        "test": ["test", "spec", "coverage"],
        "security": ["security", "vuln", "cve", "auth", "token", "secret"]
    }

    for commit in commits:
        msg = commit["message"].lower()
        for cat, keywords in patterns.items():
            if any(k in msg for k in keywords):
                improvements.append({
                    "commit": commit["hash"][:8],
                    "category": cat,
                    "message": commit["message"],
                    "author": commit["author"]
                })
                break
    return improvements


def auto_commit_improvements(improvements: List[Dict[str, Any]]) -> bool:
    if not improvements:
        return False

    code, out, err = run_cmd(["git", "status", "--porcelain"])
    if code != 0 or not out.strip():
        log.debug("No changes to commit")
        return False

    code, out, err = run_cmd(["git", "diff", "--name-only"])
    changed_files = out.splitlines() if out else []

    commit_msg = "auto: improvements detected\n\n"
    for imp in improvements:
        commit_msg += f"- [{imp['category']}] {imp['message']} ({imp['commit']})\n"

    run_cmd(["git", "add", "-A"])
    code, out, err = run_cmd(["git", "commit", "-m", commit_msg.strip()])
    if code == 0:
        log.info(f"Auto-committed {len(improvements)} improvements")
        run_cmd(["git", "push", "origin", BRANCH])
        return True
    return False


def create_github_issue(title: str, body: str, labels: List[str] = None) -> Optional[int]:
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return None

    url = f"https://api.github.com/repos/{GITHUB_REPO}/issues"
    data = json.dumps({"title": title, "body": body, "labels": labels or []}).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "ARIA-Autonomous"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 201:
                result = json.loads(resp.read().decode())
                return result.get("number")
    except urllib.error.HTTPError as e:
        log.warning(f"GitHub issue creation failed: {e.code} {e.read().decode()}")
    except Exception as e:
        log.warning(f"GitHub issue creation error: {e}")
    return None


def detect_problems() -> List[Dict[str, Any]]:
    problems = []

    code, out, err = run_cmd(["git", "status", "--porcelain"])
    if code == 0 and out.strip():
        untracked = [l for l in out.splitlines() if l.startswith("??")]
        if len(untracked) > 20:
            problems.append({
                "type": "untracked_files",
                "severity": "medium",
                "detail": f"{len(untracked)} untracked files",
                "files": [f[3:] for f in untracked[:10]]
            })

    code, out, err = run_cmd(["git", "log", "--oneline", "-20"])
    if code == 0:
        recent = out.splitlines()
        fix_count = sum(1 for c in recent if any(k in c.lower() for k in ["fix", "bug", "error", "crash"]))
        if fix_count > 5:
            problems.append({
                "type": "high_fix_rate",
                "severity": "high",
                "detail": f"{fix_count}/20 recent commits are fixes",
                "commits": recent[:10]
            })

    return problems


def main_loop() -> None:
    log.info("ARIA Autonomous Controller started")
    log.info(f"Repo: {REPO_ROOT}")
    log.info(f"Branch: {BRANCH}")
    log.info(f"Interval: {INTERVAL}s")

    discord_notify(f"🤖 **ARIA Autonomous Online**\nRepo: `{REPO_ROOT}`\nBranch: `{BRANCH}`\nInterval: {INTERVAL}s")

    while True:
        try:
            log.info("Running autonomous cycle...")

            commits = get_git_log(since_minutes=10)
            if commits:
                log.info(f"Found {len(commits)} recent commits")
                improvements = analyze_commits(commits)
                if improvements:
                    log.info(f"Detected {len(improvements)} improvements")
                    if auto_commit_improvements(improvements):
                        discord_notify(
                            f"✅ **Auto-commit**\n"
                            f"Committed {len(improvements)} improvements to `{BRANCH}`\n"
                            + "\n".join(f"- [{i['category']}] {i['message']}" for i in improvements[:5])
                        )

            problems = detect_problems()
            for prob in problems:
                issue_num = create_github_issue(
                    title=f"[Auto] {prob['type'].replace('_', ' ').title()}",
                    body=f"**Severity:** {prob['severity']}\n**Detail:** {prob['detail']}\n\n"
                         f"Detected by ARIA Autonomous Controller at {datetime.now().isoformat()}",
                    labels=["auto-detected", prob['severity'], prob['type']]
                )
                if issue_num:
                    log.info(f"Created GitHub issue #{issue_num}: {prob['type']}")
                    discord_notify(
                        f"🐛 **Issue Created #{issue_num}**\n"
                        f"Type: `{prob['type']}`\nSeverity: `{prob['severity']}`\n{prob['detail']}"
                    )

            time.sleep(INTERVAL)

        except KeyboardInterrupt:
            log.info("Shutdown requested")
            discord_notify("🔴 **ARIA Autonomous Offline**")
            break
        except Exception as e:
            log.error(f"Autonomous cycle error: {e}")
            discord_notify(f"⚠️ **ARIA Autonomous Error**\n```{e}```")
            time.sleep(30)


def run_with_retry() -> None:
    while True:
        try:
            main_loop()
        except Exception as e:
            log.critical(f"Fatal error, restarting in 5s: {e}")
            discord_notify(f"💥 **ARIA Autonomous Crashed**\n```{e}```\nRestarting in 5s...")
            time.sleep(5)


if __name__ == "__main__":
    run_with_retry()