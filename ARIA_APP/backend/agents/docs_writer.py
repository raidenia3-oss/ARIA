# -*- coding: utf-8 -*-
"""ARIA OS - DocsWriter Agent.

Generates documentation, READMEs, API docs, and code comments.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from agents.base import Agent

logger = logging.getLogger("ARIA.Agents.DocsWriter")


class DocsWriterAgent(Agent):
    """Generates documentation, READMEs, and code comments."""

    def __init__(self):
        super().__init__(
            name="DocsWriter",
            role="Generates documentation, READMEs, comments",
        )

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Generate documentation of the specified type."""
        doc_type = task.get("type", "README")
        content = task.get("content", "")
        output_path = task.get("path", "")
        title = task.get("title", "Untitled")

        templates = {
            "README": self._readme_template,
            "API": self._api_template,
            "CHANGELOG": self._changelog_template,
            "CONTRIBUTING": self._contributing_template,
            "INSTALL": self._install_template,
        }

        generator = templates.get(doc_type.upper(), self._generic_template)
        generated = generator(title, content)

        # Estimate quality
        lines = len(generated.split("\n"))
        has_headers = any(l.startswith("#") for l in generated.split("\n"))
        has_code_blocks = "```" in generated
        quality_score = 0.5
        if has_headers:
            quality_score += 0.2
        if has_code_blocks:
            quality_score += 0.15
        if lines > 20:
            quality_score += 0.15

        return {
            "type": doc_type,
            "generated": True,
            "path": output_path or f"docs/{doc_type.lower()}.md",
            "lines": lines,
            "quality_score": round(quality_score, 2),
            "has_headers": has_headers,
            "has_code_blocks": has_code_blocks,
        }

    def _readme_template(self, title: str, content: str) -> str:
        return f"""# {title}

## Overview

{content or 'A project by ARIA OS.'}

## Features

- Feature 1
- Feature 2
- Feature 3

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```python
# Example usage
```

## License

MIT
"""

    def _api_template(self, title: str, content: str) -> str:
        return f"""# {title} API

## Endpoints

{content or 'See endpoint documentation below.'}

## Authentication

Bearer token required.

## Rate Limit

100 requests per minute.
"""

    def _changelog_template(self, title: str, content: str) -> str:
        return f"""# Changelog

## [Unreleased]

{content or '- Initial release.'}

## [1.0.0] - 2026-09-26

### Added
- Initial release
"""

    def _contributing_template(self, title: str, content: str) -> str:
        return f"""# Contributing to {title}

{content or 'Fork the repo and submit a PR.'}

## Setup

```bash
git clone <repo>
cd {title.lower()}
pip install -r requirements.txt
```

## Testing

```bash
pytest
```
"""

    def _install_template(self, title: str, content: str) -> str:
        return f"""# Installing {title}

## Requirements

- Python 3.11+
- pip

## Install

```bash
pip install {title.lower().replace(' ', '-')}
```
"""

    def _generic_template(self, title: str, content: str) -> str:
        return f"""# {title}

{content or 'Documentation pending.'}
"""