"""ARIA Doc Generator — Auto-generate README, CHANGELOG, and documentation."""

import logging
import re
import os
from typing import Optional, Dict, List, Any
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RepoInfo:
    """Repository information for documentation"""
    name: str
    description: str
    url: str
    stars: int
    forks: int
    language: str
    license: str
    topics: List[str]
    default_branch: str
    latest_release: Optional[str]
    contributors: int


class DocGenerator:
    """
    ARIA Documentation Generator
    Auto-generates README, CHANGELOG, CONTRIBUTING, etc.
    """

    def __init__(self, github_client):
        self.client = github_client

    def generate_readme(self, repo_name: str, template: str = "default",
                       custom_sections: Dict[str, str] = None) -> str:
        """Generate README.md content"""
        repo_info = self._get_repo_info(repo_name)

        if template == "default":
            return self._generate_default_readme(repo_info, custom_sections)
        elif template == "minimal":
            return self._generate_minimal_readme(repo_info)
        elif template == "detailed":
            return self._generate_detailed_readme(repo_info, custom_sections)
        else:
            return self._generate_default_readme(repo_info, custom_sections)

    def _get_repo_info(self, repo_name: str) -> RepoInfo:
        """Get repository info for documentation"""
        stats = self.client.get_repo_stats(repo_name)
        releases = self.client.list_releases(repo_name)
        contributors = self.client.get_contributors(repo_name)

        return RepoInfo(
            name=repo_name,
            description=stats.get("description", "") if stats else "",
            url=f"https://github.com/{self.client.org}/{repo_name}",
            stars=stats.get("stars", 0) if stats else 0,
            forks=stats.get("forks", 0) if stats else 0,
            language=stats.get("language", "") if stats else "",
            license=stats.get("license", "") if stats else "",
            topics=stats.get("topics", []) if stats else [],
            default_branch=stats.get("default_branch", "main") if stats else "main",
            latest_release=releases[0]["tag"] if releases else None,
            contributors=len(contributors)
        )

    def _generate_default_readme(self, info: RepoInfo, custom: Dict = None) -> str:
        """Generate default README template"""
        custom = custom or {}
        badge_style = "flat-square"
        org = self.client.org

        readme = f"""# {info.name}

{info.description or f"A project by {org}"}

"""

        # Badges
        badges = [
            f"![Stars](https://img.shields.io/github/stars/{org}/{info.name}?style={badge_style})",
            f"![Forks](https://img.shields.io/github/forks/{org}/{info.name}?style={badge_style})",
            f"![Issues](https://img.shields.io/github/issues/{org}/{info.name}?style={badge_style})",
            f"![License](https://img.shields.io/github/license/{org}/{info.name}?style={badge_style})",
        ]

        if info.latest_release:
            badges.append(f"![Release](https://img.shields.io/github/v/release/{org}/{info.name}?style={badge_style})")

        if info.language:
            badges.append(f"![Language](https://img.shields.io/github/languages/top/{org}/{info.name}?style={badge_style})")

        readme += " ".join(badges) + "\n\n"

        # Table of contents
        readme += """## Table of Contents
- [Installation](#installation)
- [Usage](#usage)
- [Features](#features)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)

"""

        # Installation
        readme += custom.get("installation", f"""## Installation

```bash
git clone {info.url}.git
cd {info.name}
# Add installation instructions here
```

""")

        # Usage
        readme += custom.get("usage", f"""## Usage

```bash
# Add usage examples here
```

""")

        # Features
        readme += custom.get("features", f"""## Features

- Feature 1
- Feature 2
- Feature 3

""")

        # Contributing
        readme += custom.get("contributing", f"""## Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

""")

        # License
        license_text = info.license or "MIT"
        readme += custom.get("license", f"""## License

Distributed under the {license_text} License. See `LICENSE` for more information.

""")

        # Contact
        readme += custom.get("contact", f"""## Contact

{org} - [GitHub]({info.url})

Project Link: [{info.url}]({info.url})

""")

        # Footer
        readme += f"""---

*This README was auto-generated by [ARIA](https://github.com/{org}/ARIA) on {datetime.now().strftime('%Y-%m-%d')}*
"""

        return readme

    def _generate_minimal_readme(self, info: RepoInfo) -> str:
        """Generate minimal README"""
        return f"""# {info.name}

{info.description or "No description provided."}

## Quick Start

```bash
git clone {info.url}.git
```

## License

{info.license or "MIT"}
"""

    def _generate_detailed_readme(self, info: RepoInfo, custom: Dict = None) -> str:
        """Generate detailed README with more sections"""
        custom = custom or {}
        base = self._generate_default_readme(info, custom)

        # Add extra sections
        extra = f"""

## Architecture

```mermaid
graph TD
    A[Input] --> B[Process]
    B --> C[Output]
```

## Configuration

See [config.example.yaml](config.example.yaml) for all options.

## API Reference

API documentation available at [docs.api.example.com](https://docs.api.example.com)

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for release history.

## Security

See [SECURITY.md](SECURITY.md) for vulnerability reporting.

## Code of Conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

"""

        return base + extra

    def generate_changelog(self, repo_name: str, from_tag: str = None,
                          to_tag: str = None, format: str = "markdown") -> str:
        """Generate CHANGELOG.md from releases and commits"""
        releases = self.client.list_releases(repo_name)
        repo = self.client.get_repo(repo_name)

        if format == "markdown":
            return self._generate_markdown_changelog(repo_name, releases, repo, from_tag, to_tag)
        elif format == "keepachangelog":
            return self._generate_keepachangelog(repo_name, releases, repo, from_tag, to_tag)
        else:
            return self._generate_markdown_changelog(repo_name, releases, repo, from_tag, to_tag)

    def _generate_markdown_changelog(self, repo_name: str, releases: List[Dict],
                                    repo, from_tag: str = None, to_tag: str = None) -> str:
        """Generate markdown changelog"""
        changelog = f"""# Changelog

All notable changes to `{repo_name}` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

"""

        # Filter releases
        filtered = releases
        if from_tag:
            # Find index of from_tag
            from_idx = next((i for i, r in enumerate(releases) if r["tag"] == from_tag), len(releases))
            filtered = releases[:from_idx]
        if to_tag:
            to_idx = next((i for i, r in enumerate(releases) if r["tag"] == to_tag), -1)
            if to_idx >= 0:
                filtered = filtered[to_idx+1:]

        for release in filtered:
            tag = release["tag"]
            title = release["title"]
            date = release["published_at"][:10] if release.get("published_at") else "Unreleased"
            body = release.get("body", "No release notes provided.")

            changelog += f"## [{tag}] - {date}\n\n{body}\n\n"

        # Add unreleased section if no releases or if latest is not latest commit
        if not releases:
            changelog += """## [Unreleased]

### Added
- Initial release

"""

        return changelog

    def _generate_keepachangelog(self, repo_name: str, releases: List[Dict],
                                repo, from_tag: str = None, to_tag: str = None) -> str:
        """Generate Keep a Changelog format"""
        # Similar to markdown but with specific sections
        return self._generate_markdown_changelog(repo_name, releases, repo, from_tag, to_tag)

    def generate_contributing(self, repo_name: str) -> str:
        """Generate CONTRIBUTING.md"""
        return f"""# Contributing to {repo_name}

Thank you for your interest in contributing! This guide will help you get started.

## Code of Conduct

By participating, you agree to uphold our [Code of Conduct](CODE_OF_CONDUCT.md).

## How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported in [Issues](https://github.com/{self.client.org}/{repo_name}/issues)
2. If not, create a new issue using the **Bug Report** template
3. Include as much detail as possible (steps to reproduce, environment, logs)

### Suggesting Features

1. Check existing [Feature Requests](https://github.com/{self.client.org}/{repo_name}/issues?q=label%3Aenhancement)
2. Create a new issue using the **Feature Request** template
3. Explain the problem and your proposed solution

### Pull Requests

1. Fork the repository
2. Create a branch from `main`: `git checkout -b feature/your-feature`
3. Make your changes
4. Run tests: `./run-tests.sh`
5. Ensure code style: `./lint.sh`
6. Commit with clear messages: `git commit -m "feat: add amazing feature"`
7. Push and create a Pull Request

## Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/{repo_name}.git
cd {repo_name}

# Install dependencies
# Add setup instructions here

# Run tests
./run-tests.sh
```

## Coding Standards

- Follow the existing code style
- Write tests for new features
- Update documentation for API changes
- Keep commits atomic and well-described

## Commit Message Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Formatting, missing semi-colons, etc.
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `perf`: Performance improvement
- `test`: Adding missing tests
- `chore`: Maintenance

## Review Process

1. All PRs require at least 1 approval
2. All CI checks must pass
3. Maintainers will review within 48 hours

## License

By contributing, you agree that your contributions will be licensed under the project's license.

---

*Generated by ARIA on {datetime.now().strftime('%Y-%m-%d')}*
"""

    def generate_security_policy(self, repo_name: str) -> str:
        """Generate SECURITY.md"""
        return f"""# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| Latest  | ✅ Yes             |
| Older   | ❌ No              |

## Reporting a Vulnerability

We take security seriously. If you discover a vulnerability, please report it responsibly:

1. **Do not** create a public issue
2. Email security@{self.client.org}.dev with details
3. Include steps to reproduce if possible
4. We'll acknowledge within 48 hours

## Disclosure Policy

- We'll investigate and verify the vulnerability
- We'll work on a fix and coordinate disclosure
- Credit will be given (unless you prefer anonymity)

## Security Best Practices

- Keep dependencies updated
- Use secrets management (GitHub Secrets, Vault)
- Enable 2FA on all accounts
- Review dependency licenses

---

*Generated by ARIA on {datetime.now().strftime('%Y-%m-%d')}*
"""

    def generate_code_of_conduct(self, repo_name: str) -> str:
        """Generate CODE_OF_CONDUCT.md (Contributor Covenant)"""
        return f"""# Contributor Covenant Code of Conduct

## Our Pledge

We as members, contributors, and leaders pledge to make participation in our
community a harassment-free experience for everyone.

## Our Standards

Examples of behavior that contributes to a positive environment:

* Using welcoming and inclusive language
* Being respectful of differing viewpoints and experiences
* Gracefully accepting constructive criticism
* Focusing on what is best for the community
* Showing empathy towards other community members

Examples of unacceptable behavior:

* The use of sexualized language or imagery
* Trolling, insulting, or derogatory comments
* Public or private harassment
* Publishing others' private information without permission
* Other conduct which could reasonably be considered inappropriate

## Enforcement Responsibilities

Community leaders are responsible for clarifying and enforcing our standards of
acceptable behavior and will take appropriate and fair corrective action in
response to any behavior that they deem inappropriate, threatening, offensive,
or harmful.

## Scope

This Code of Conduct applies within all community spaces, and also applies when
an individual is officially representing the community in public spaces.

## Enforcement

Instances of abusive, harassing, or otherwise unacceptable behavior may be
reported to the community leaders responsible for enforcement at
conduct@{self.client.org}.dev.

All complaints will be reviewed and investigated promptly and fairly.

## Attribution

This Code of Conduct is adapted from the [Contributor Covenant](https://www.contributor-covenant.org),
version 2.1, available at https://www.contributor-covenant.org/version/2/1/code_of_conduct.html.

---

*Generated by ARIA on {datetime.now().strftime('%Y-%m-%d')}*
"""

    def write_docs_to_repo(self, repo_name: str, docs: Dict[str, str],
                          commit_message: str = "📚 ARIA: Update documentation") -> bool:
        """Write generated documentation files to repository (creates PR)"""
        try:
            # This would create files in the repo and open a PR
            # For now, return the content that would be written
            logger.info(f"📝 Documentation generated for {repo_name}: {list(docs.keys())}")
            return True
        except Exception as e:
            logger.error(f"❌ write_docs_to_repo failed: {e}")
            return False

    def generate_all_docs(self, repo_name: str) -> Dict[str, str]:
        """Generate all standard documentation files"""
        return {
            "README.md": self.generate_readme(repo_name),
            "CHANGELOG.md": self.generate_changelog(repo_name),
            "CONTRIBUTING.md": self.generate_contributing(repo_name),
            "SECURITY.md": self.generate_security_policy(repo_name),
            "CODE_OF_CONDUCT.md": self.generate_code_of_conduct(repo_name),
        }