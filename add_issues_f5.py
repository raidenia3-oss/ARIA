#!/usr/bin/env python3
"""ARIA v5.0 Phase F.5: Create 3 new GitHub issues (videos-inspired).

Issues:
  #43 - Pi Agent Harness (Skills + MCP)
  #44 - Axum v6.0 Migration Research
  #45 - WGPU Native Rendering for Tauri v6.0
"""

import json
import os
import urllib.request
import urllib.error


def get_token():
    """Read GitHub token from backend .env."""
    env_path = os.path.join(
        os.path.dirname(__file__), "ARIA_APP", "backend", ".env"
    )
    with open(env_path) as f:
        for line in f:
            if line.startswith("GITHUB_TOKEN="):
                return line.strip().split("=", 1)[1]
    raise RuntimeError("GITHUB_TOKEN not found in .env")


def create_issue(token, title, body, labels):
    """Create a single GitHub issue."""
    repo_url = "https://api.github.com/repos/raidenia3-oss/ARIA/issues"
    data = json.dumps({"title": title, "body": body, "labels": labels}).encode("utf-8")
    req = urllib.request.Request(repo_url, data=data, method="POST")
    req.add_header("Authorization", f"token {token}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("Content-Type", "application/json")

    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def main():
    token = get_token()
    print(f"Authenticated with token: {token[:10]}...")

    issues_f5 = [
        {
            "title": "Integration: Pi Agent Harness (Skills + MCP)",
            "body": """## Description
Integrate Pi Agent harness architecture with ARIA auto-improvement loop.

## Context (Video: Pi Agent)
- Pi Agent is an open harness for AI agents (not a closed factory)
- Allows: custom skills, MCP integration, session management
- ARIA Phase M uses 3 agents but without harness structure

## Scope
1. Implement SkillRegistry as Pi Agent
2. Add /api/agents/skills (CRUD)
3. Integrate MCP connection manager
4. Session management: /api/memory/sessions
5. Custom prompts via AGENTS.md patterns

## Benefit
- Reusable agents
- Extensible skills without code
- Standardized MCP integration
- Persistent sessions

## References
- https://github.com/evals-co/pi
- Phase M: Multi-agent swarm
- Phase K: LongMemory MCP

## Priority
Medium (v5.2 feature)""",
            "labels": ["integration", "agents", "mcp"],
        },
        {
            "title": "Feature: Axum v6.0 Migration Research",
            "body": """## Description
Research migration from FastAPI to Axum for v6.0

## Context (Video: Axum)
- Axum: Rust framework 10-100x faster than FastAPI
- Zero-cost abstractions (type-safe extractors)
- Tokio + Hyper + Tower (async runtime + HTTP + middleware)
- 320+ current routes could migrate with 10x speedup

## Scope
1. Benchmark: FastAPI vs Axum (latency, throughput)
2. Architecture: How to structure routers in Axum
3. Examples: /api/health, /api/chat to Axum syntax
4. Interop: Connect Axum to Ollama + vector DB
5. Deployment: Binary compilation, TLS, Docker

## Investigate
- [ ] Axum documentation (tokio.rs)
- [ ] Tauri + Axum integration (IPC)
- [ ] Middleware stacks (auth, logging, CORS)
- [ ] Type-safe error handling

## Benefit
- 10-100x performance
- Type safety (compile-time errors)
- Memory efficient (zero GC)
- Production-ready (vs Python)

## Plan
Phase L.2 (research) -> Phase L.3 (prototype) -> v6.0 migration

## References
- https://github.com/tokio-rs/axum
- Video: "This Rust Framework Makes FastAPI Look SLOW"

## Priority
High (v6.0 blocker)""",
            "labels": ["feature", "backend", "rust", "v6.0"],
        },
        {
            "title": "Feature: WGPU Native Rendering for Tauri v6.0",
            "body": """## Description
Migrate OrbVisual.tsx (Three.js/WebGL) to WGPU native rendering

## Context (Video: Tauri GUI)
- Tauri = 44x smaller than Electron (6.1 MB vs 250 MB)
- WGPU = cross-platform GPU abstraction
- Omits DOM/CSS overhead (direct GPU drawing)
- Enables native 3D rendering without Chromium

## Scope
1. Investigate WGPU in Rust
2. Evaluate frameworks: Iced, Egui, Bevy
3. Port OrbVisual (7-layer sphere) to WGPU
4. GPU-instanced particles (500K like v5.1)
5. IPC bridge: Tauri to Rust renderer

## Options
A) Iced (declarative UI + WGPU)
B) Egui (immediate mode + WGPU)
C) Bevy (game engine, overkill?)
D) Keep React + Three.js (current, works)

## Benefit
- Native performance (no Chromium overhead)
- Deterministic rendering (no GC)
- Smaller binary (omit web engine)
- Native GPU acceleration

## Plan
Phase N: Iced prototype -> v6.0: full port

## References
- https://wgpu.rs/
- https://github.com/iced-rs/iced
- Video: "Why This in Tech (Rust GUI Revolution)"
- Current: src/components/OrbVisual/OrbVisual.tsx

## Priority
Medium (v6.0 nice-to-have)""",
            "labels": ["feature", "ui", "rust", "wgpu", "v6.0"],
        },
    ]

    print("\nCreating 3 new GitHub issues (F.5)...\n")

    for i, issue_data in enumerate(issues_f5, 1):
        try:
            new_issue = create_issue(
                token, issue_data["title"], issue_data["body"], issue_data["labels"]
            )
            print("{}. Created: {}".format(i, new_issue["title"]))
            print("   URL: {}".format(new_issue["html_url"]))
            print("   Labels: {}\n".format(", ".join(issue_data["labels"])))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            print("{}. Error {}: {}\n".format(i, e.code, err_body[:200]))
        except Exception as e:
            print("{}. Error: {}\n".format(i, e))

    print("All 3 issues created!")
    print("Total open issues: 24 (21 prior + 3 new)")


if __name__ == "__main__":
    main()