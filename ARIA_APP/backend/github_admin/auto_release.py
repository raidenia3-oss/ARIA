"""ARIA Auto-Release Engine — Auto-versioning and release generation."""

import re
import logging
from typing import Optional, Dict, List
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ReleaseConfig:
    """Configuration for auto-release behavior"""
    repo_name: str
    bump_type: str = "patch"  # major, minor, patch
    changelog: str = ""
    draft: bool = False
    prerelease: bool = False
    target_branch: str = "main"
    assets: List[str] = None
    generate_changelog: bool = True
    changelog_template: str = "## {version} ({date})\n\n{changelog}\n\n---\n"


class AutoRelease:
    """
    ARIA Auto-Release Engine
    Auto-versioning + release generation
    """

    VERSION_PATTERN = re.compile(r"v?(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9.]+))?")

    def __init__(self, github_client):
        self.client = github_client

    def get_current_version(self, repo_name: str) -> str:
        """Get latest version from releases"""
        releases = self.client.list_releases(repo_name)
        if releases:
            # Get the most recent non-draft, non-prerelease release
            for release in releases:
                if not release.get("draft") and not release.get("prerelease"):
                    return release["tag"]
            # Fallback to first release
            return releases[0]["tag"]
        return "0.0.0"

    def parse_version(self, version: str) -> tuple:
        """Parse version string into (major, minor, patch, prerelease)"""
        match = self.VERSION_PATTERN.match(version)
        if not match:
            return (0, 0, 0, None)

        major = int(match.group(1))
        minor = int(match.group(2))
        patch = int(match.group(3))
        prerelease = match.group(4)
        return (major, minor, patch, prerelease)

    def bump_version(self, current: str, bump_type: str = "patch") -> str:
        """
        Bump version number
        bump_type: major|minor|patch
        """
        try:
            major, minor, patch, prerelease = self.parse_version(current)

            # If there's a prerelease, just remove it for stable release
            if prerelease and bump_type in ("major", "minor", "patch"):
                prerelease = None

            if bump_type == "major":
                major += 1
                minor = 0
                patch = 0
            elif bump_type == "minor":
                minor += 1
                patch = 0
            elif bump_type == "patch":
                patch += 1
            else:
                logger.warning(f"⚠️ Unknown bump_type: {bump_type}, defaulting to patch")
                patch += 1

            return f"{major}.{minor}.{patch}"
        except Exception as e:
            logger.error(f"❌ bump_version failed: {e}")
            return current

    def generate_changelog(self, repo_name: str, from_version: str, to_version: str,
                          template: str = None) -> str:
        """Generate changelog from commits between versions"""
        try:
            repo = self.client.get_repo(repo_name)
            if not repo:
                return ""

            # Get commits between tags
            commits = list(repo.get_commits())
            # Note: In practice you'd want to filter by date or tag range

            # Simple commit-based changelog
            changelog_parts = []
            for commit in commits[:50]:  # Limit to 50 most recent
                msg = commit.commit.message.split('\n')[0]  # First line only
                author = commit.commit.author.name
                sha = commit.sha[:7]
                changelog_parts.append(f"- {msg} (@{author}, {sha})")

            changelog = "\n".join(changelog_parts)

            if template:
                return template.format(
                    version=to_version,
                    date=datetime.now().strftime("%Y-%m-%d"),
                    changelog=changelog
                )

            return f"## {to_version} ({datetime.now().strftime('%Y-%m-%d')})\n\n{changelog}\n\n---\n"
        except Exception as e:
            logger.error(f"❌ generate_changelog failed: {e}")
            return ""

    def auto_release(self, repo_name: str, bump_type: str = "patch",
                    changelog: str = "", config: Optional[ReleaseConfig] = None) -> Optional[Dict]:
        """
        Auto-create release with bumped version

        Args:
            repo_name: repository name
            bump_type: major|minor|patch
            changelog: manual changelog (overrides auto-generation)
            config: ReleaseConfig for advanced options
        """
        try:
            if config is None:
                config = ReleaseConfig(repo_name=repo_name, bump_type=bump_type, changelog=changelog)

            current = self.get_current_version(repo_name)
            new_version = self.bump_version(current, config.bump_type)

            # Generate changelog if not provided and enabled
            body = config.changelog
            if not body and config.generate_changelog:
                body = self.generate_changelog(repo_name, current, new_version, config.changelog_template)
            elif not body:
                body = f"Automated release by ARIA Bot\n\n**Date**: {datetime.now().isoformat()}"

            title = f"Release {new_version}"

            release = self.client.create_release(
                repo_name=repo_name,
                tag=new_version,
                title=title,
                body=body,
                draft=config.draft,
                prerelease=config.prerelease,
                target_commitish=config.target_branch,
                assets=config.assets
            )

            if release:
                logger.info(f"✅ Auto-release: {repo_name} v{current} → v{new_version}")
            return release

        except Exception as e:
            logger.error(f"❌ auto_release failed: {e}")
            return None

    def create_prerelease(self, repo_name: str, base_version: str,
                         prerelease_label: str = "beta") -> Optional[Dict]:
        """Create a prerelease version (e.g., 1.0.0-beta.1)"""
        try:
            major, minor, patch, _ = self.parse_version(base_version)
            prerelease_version = f"{major}.{minor}.{patch}-{prerelease_label}.1"

            # Check if prerelease exists and increment
            releases = self.client.list_releases(repo_name)
            for rel in releases:
                if rel["tag"].startswith(f"{major}.{minor}.{patch}-{prerelease_label}."):
                    match = re.search(rf"{prerelease_label}\.(\d+)", rel["tag"])
                    if match:
                        num = int(match.group(1)) + 1
                        prerelease_version = f"{major}.{minor}.{patch}-{prerelease_label}.{num}"
                        break

            return self.client.create_release(
                repo_name=repo_name,
                tag=prerelease_version,
                title=f"Pre-release {prerelease_version}",
                body=f"Pre-release version for testing\n\n**Base**: {base_version}",
                prerelease=True
            )
        except Exception as e:
            logger.error(f"❌ create_prerelease failed: {e}")
            return None

    def promote_prerelease(self, repo_name: str, prerelease_tag: str,
                          bump_type: str = "patch") -> Optional[Dict]:
        """Promote a prerelease to stable release"""
        try:
            # Parse prerelease tag
            match = re.match(r"v?(\d+)\.(\d+)\.(\d+)-([a-zA-Z0-9.]+)", prerelease_tag)
            if not match:
                return None

            major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))
            base_version = f"{major}.{minor}.{patch}"

            # Bump to stable
            stable_version = self.bump_version(base_version, bump_type)

            # Get prerelease body
            releases = self.client.list_releases(repo_name)
            prerelease_body = ""
            for rel in releases:
                if rel["tag"] == prerelease_tag:
                    prerelease_body = rel["body"]
                    break

            # Create stable release
            return self.client.create_release(
                repo_name=repo_name,
                tag=stable_version,
                title=f"Release {stable_version}",
                body=f"Promoted from {prerelease_tag}\n\n{prerelease_body}",
                prerelease=False
            )
        except Exception as e:
            logger.error(f"❌ promote_prerelease failed: {e}")
            return None

    def list_releases(self, repo_name: str, include_drafts: bool = False,
                     include_prereleases: bool = False) -> List[Dict]:
        """List releases with filtering"""
        releases = self.client.list_releases(repo_name)
        filtered = []
        for r in releases:
            if not include_drafts and r.get("draft"):
                continue
            if not include_prereleases and r.get("prerelease"):
                continue
            filtered.append(r)
        return filtered

    def get_release_notes(self, repo_name: str, tag: str) -> Optional[str]:
        """Get release notes for a specific tag"""
        releases = self.client.list_releases(repo_name)
        for r in releases:
            if r["tag"] == tag:
                return r.get("body", "")
        return None