# -*- coding: utf-8 -*-
"""ARIA OS - GitHub Webhook Handler.

Endpoints para webhooks de GitHub:
  POST /api/github/webhook    - Receive GitHub webhook events
  GET  /api/github/webhook/config - Get webhook configuration (SIN secreto)
  POST /api/github/webhook/config  - Configure webhook
  POST /api/github/webhook/test  - Send test event

Este router NO exige autenticacion (ARIA_APP/backend/app.py no registra auth),
asi que ninguna respuesta puede incluir material de credencial.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, Field

logger = logging.getLogger("ARIA.GitHubWebhooks")

router = APIRouter(prefix="/api/github/webhook", tags=["github-webhook"])


class WebhookConfig(BaseModel):
    events: List[str] = Field(default_factory=lambda: ["push", "pull_request", "issues", "release", "workflow_run"])
    secret: str = ""
    url: str = ""
    active: bool = True


class WebhookEvent(BaseModel):
    event_type: str
    action: Optional[str] = None
    payload: Dict[str, Any]


# ============================================================================
# Webhook Configuration
# ============================================================================

def _load_webhook_config() -> Dict[str, Any]:
    """Load webhook config from .env or config file.

    Uso INTERNO: el dict devuelto puede contener `secret`, asi que nunca debe
    devolverse tal cual por HTTP. Para responder use `_public_webhook_config`.
    """
    config_file = os.path.join(os.path.dirname(__file__), "..", "..", ".github_webhook_config.json")
    config_file = os.path.normpath(config_file)

    if os.path.exists(config_file):
        try:
            with open(config_file, "r") as f:
                return json.load(f)
        except Exception:
            pass

    return {
        "events": ["push", "pull_request", "issues", "release", "workflow_run"],
        "secret": os.getenv("GITHUB_WEBHOOK_SECRET", ""),
        "active": True
    }


def _save_webhook_config(config: Dict[str, Any]) -> bool:
    """Save webhook config to file."""
    config_file = os.path.join(os.path.dirname(__file__), "..", "..", ".github_webhook_config.json")
    config_file = os.path.normpath(config_file)
    try:
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Failed to save webhook config: {e}")
        return False


def _verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify GitHub webhook signature."""
    if not secret:
        logger.warning("Webhook secret not configured - skipping verification")
        return True

    expected = hmac.new(
        key=secret.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256
    ).hexdigest()

    expected_signature = f"sha256={expected}"
    return hmac.compare_digest(signature, expected_signature)


# Claves que NUNCA salen por HTTP en este router: material de credencial.
# La lista es amplia a proposito para que anadir un campo con token al config
# no reintroduzca la fuga por olvido.
_SECRET_KEYS = frozenset({"secret", "token", "api_key", "apikey", "webhook_secret", "password"})


def _public_webhook_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Copia de la config apta para responder por HTTP: sin material de credencial.

    `GET /api/github/webhook/config` no exige autenticacion (ARIA_APP/backend/app.py
    no registra middleware de auth ni dependencias de auth en ninguna ruta, y el
    CORS va con `allow_origins=["*"]` + `allow_credentials=True`), asi que
    devolver `secret` allowia leer el secreto del webhook sin credenciales.

    Devuelve en su lugar dos booleanos:
      - `secret_configured`: hay un secreto configurado (no vacio).
      - `verification_enabled`: la firma se verifica DE VERDAD. Hoy coincide con
        el anterior porque `_verify_signature` es el unico verificador y acepta
        cualquier payload cuando el secreto esta vacio; se reportan por separado
        porque dejarian de coincidir en cuanto ese vacio se cambie por fail-closed.
    """
    secret = config.get("secret") or ""
    public = {k: v for k, v in config.items() if k not in _SECRET_KEYS}
    public["secret_configured"] = bool(secret)
    public["verification_enabled"] = bool(secret)
    return public


# ============================================================================
# Webhook Handlers
# ============================================================================

@router.get("/config", response_model=Dict[str, Any])
async def get_webhook_config():
    """Get webhook configuration.

    Nunca devuelve el secreto: este router no exige autenticacion.
    """
    config = _load_webhook_config()
    config["url"] = os.getenv("GITHUB_WEBHOOK_URL", "http://localhost:8000/api/github/webhook")
    return _public_webhook_config(config)


@router.post("/config", response_model=Dict[str, Any])
async def set_webhook_config(config: WebhookConfig):
    """Update webhook configuration."""
    data = config.model_dump()
    data["url"] = config.url  # Keep URL in config
    _save_webhook_config(data)
    # El eco tampoco devuelve el secreto (mismo motivo que en GET /config).
    return {"status": "updated", "config": _public_webhook_config(data)}


@router.get("/test", response_model=Dict[str, Any])
async def test_webhook():
    """Test webhook endpoint."""
    return {
        "status": "ok",
        "message": "Webhook handler is running",
        "timestamp": time.time()
    }


@router.post("/test", response_model=Dict[str, Any])
async def send_test_event(event: WebhookEvent):
    """Send a test event through the webhook handler."""
    try:
        result = await _handle_webhook_event(event.event_type, event.action, event.payload, BackgroundTasks())
        return {"status": "processed", "result": result}
    except Exception as e:
        logger.error(f"Test event failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=Dict[str, Any])
@router.post("/", response_model=Dict[str, Any])
async def webhook_handler(
    request: Request,
    background_tasks: BackgroundTasks
):
    """Main webhook handler for GitHub events."""
    config = _load_webhook_config()

    # Verify signature
    signature = request.headers.get("X-Hub-Signature-256", "")
    payload = await request.body()

    if not _verify_signature(payload, signature, config.get("secret", "")):
        logger.warning("Webhook signature verification failed")
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse payload
    try:
        event_payload = json.loads(payload.decode("utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Get event type
    event_type = request.headers.get("X-GitHub-Event", "unknown")
    action = event_payload.get("action", "")

    logger.info(f"Received GitHub webhook: {event_type} / {action}")

    # Handle in background to avoid timeout
    background_tasks.add_task(
        _handle_webhook_event,
        event_type,
        action,
        event_payload,
        background_tasks
    )

    return {
        "status": "accepted",
        "event_type": event_type,
        "action": action,
        "timestamp": time.time()
    }


# ============================================================================
# Event Processing
# ============================================================================

async def _handle_webhook_event(
    event_type: str,
    action: str,
    payload: Dict[str, Any],
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """Process webhook event."""
    from skills.custom.self_improvement import get_self_improvement

    try:
        engine = get_self_improvement()
        if not engine._initialized:
            engine.initialize()

        if event_type == "push":
            return await _handle_push_event(payload, engine)
        elif event_type == "pull_request":
            return await _handle_pr_event(action, payload, engine)
        elif event_type == "issues":
            return await _handle_issues_event(action, payload, engine)
        elif event_type == "release":
            return await _handle_release_event(action, payload)
        elif event_type == "workflow_run":
            return await _handle_workflow_run_event(action, payload)
        else:
            logger.info(f"Ignoring unhandled event type: {event_type}")
            return {"status": "ignored"}

    except Exception as e:
        logger.error(f"Webhook event processing failed: {e}")
        return {"status": "error", "error": str(e)}


async def _handle_push_event(payload: Dict[str, Any], engine) -> Dict[str, Any]:
    """Handle push event."""
    ref = payload.get("ref", "")
    commits = payload.get("commits", [])
    repo = payload.get("repository", {})

    logger.info(f"Push to {ref} with {len(commits)} commits")

    result = {
        "action": "push",
        "ref": ref,
        "commits": len(commits),
        "repo": repo.get("full_name", "")
    }

    # Trigger improvement cycle on main branch
    if ref.endswith("main") or ref.endswith("master"):
        logger.info("Push to main branch - triggering improvement check")
        result["improvement_check"] = engine.run_improvement_cycle() if len(commits) > 0 else "skipped"

    return result


async def _handle_pr_event(action: str, payload: Dict[str, Any], engine) -> Dict[str, Any]:
    """Handle pull request event."""
    pr = payload.get("pull_request", {})
    repo = payload.get("repository", {})

    logger.info(f"PR {action}: #{pr.get('number')}")

    if action in ("opened", "synchronize", "reopened"):
        # Analyze PR quality and security
        try:
            pr_number = pr.get("number")
            repo_name = repo.get("name", "")
            if pr_number and repo_name:
                analysis = engine.pr_analyzer.analyze_pr(repo_name, pr_number)
                if analysis:
                    # Auto-approve if low risk
                    if engine.pr_analyzer.auto_approve_if_safe(repo_name, pr_number, max_risk="low"):
                        engine.pr_analyzer.post_review_comment(
                            repo_name, pr_number,
                            "ARIA Auto-approval: PR passes quality and security checks (low risk).",
                            line=1
                        )
                    return {"status": "analyzed", "pr": pr_number, "risk": analysis.risk_level}
        except Exception as e:
            logger.error(f"PR analysis failed: {e}")

    return {"status": "processed", "action": action}


async def _handle_issues_event(action: str, payload: Dict[str, Any], engine) -> Dict[str, Any]:
    """Handle issues event."""
    issue = payload.get("issue", {})
    repo = payload.get("repository", {})

    logger.info(f"Issue {action}: #{issue.get('number')}")

    if action == "opened":
        # Auto-triage new issues
        try:
            issue_number = issue.get("number")
            repo_name = repo.get("name", "")
            if issue_number and repo_name:
                engine.issue_manager.triage_issue(repo_name, issue_number)
        except Exception as e:
            logger.error(f"Issue triage failed: {e}")

    return {"status": "processed", "action": action}


async def _handle_release_event(action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Handle release event."""
    release = payload.get("release", {})
    repo = payload.get("repository", {})

    logger.info(f"Release {action}: {release.get('tag_name')}")

    if action == "published":
        # Could trigger notification or update
        return {"status": "notify", "release": release.get("tag_name")}

    return {"status": "processed", "action": action}


async def _handle_workflow_run_event(action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Handle workflow run event."""
    workflow_run = payload.get("workflow_run", {})

    logger.info(f"Workflow run: {workflow_run.get('display_title')} - {workflow_run.get('conclusion')}")

    return {"status": "processed", "workflow": workflow_run.get("display_title")}


# ============================================================================
# Auto-commit & PR Endpoints
# ============================================================================

class AutoCommitRequest(BaseModel):
    message: str = "Auto-commit by ARIA"
    branch: str = "main"
    push: bool = True
    include_patterns: List[str] = Field(default_factory=list)
    exclude_patterns: List[str] = Field(default_factory=list)


class CreatePRRequest(BaseModel):
    repo: str
    title: str
    body: str
    head: str = "main"
    base: str = "main"
    reviewers: List[str] = Field(default_factory=list)


class CreatePRResponse(BaseModel):
    pr_number: int
    url: str
    status: str


@router.post("/autocommit", response_model=Dict[str, Any])
async def auto_commit_changes(req: AutoCommitRequest):
    """Auto-commit changes to the ARIA repository."""
    from skills.custom.self_improvement import get_self_improvement

    engine = get_self_improvement()
    if not engine._initialized and not engine.initialize():
        raise HTTPException(status_code=500, detail="Self-improvement engine not initialized")

    try:
        result = engine._auto_commit_changes()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pr/create", response_model=CreatePRResponse)
async def create_pr(req: CreatePRRequest):
    """Create a PR from current changes."""
    from github_admin import GitHubAdminClient, PRAnalyzer

    client = GitHubAdminClient(token=os.getenv("GITHUB_TOKEN", ""), org="raidenia3-oss")

    try:
        # Create branch, commit, and PR
        import subprocess
        import uuid

        # Generate unique branch name
        branch_name = f"aria/auto-improve-{uuid.uuid4().hex[:8]}"

        # Stage files (filter by patterns if specified)
        if req.include_patterns:
            for pattern in req.include_patterns:
                subprocess.run(["git", "add", pattern], cwd=engine.repo_path, capture_output=True)
        else:
            subprocess.run(["git", "add", "-A"], cwd=engine.repo_path, capture_output=True)

        # Commit
        commit_result = subprocess.run(
            ["git", "commit", "-m", req.title],
            cwd=engine.repo_path,
            capture_output=True,
            text=True
        )

        if commit_result.returncode != 0 and "nothing to commit" not in commit_result.stdout:
            raise HTTPException(status_code=500, detail=f"Commit failed: {commit_result.stderr}")

        # Create branch and push
        subprocess.run(["git", "checkout", "-b", branch_name], cwd=engine.repo_path, capture_output=True)
        push_result = subprocess.run(
            ["git", "push", "origin", branch_name],
            cwd=engine.repo_path,
            capture_output=True,
            text=True
        )

        # Create PR
        pr = client.create_pull_request(
            repo=req.repo,
            title=req.title,
            body=req.body,
            head=branch_name,
            base=req.base
        )

        return CreatePRResponse(
            pr_number=pr.get("number", 0),
            url=pr.get("html_url", ""),
            status="created"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Event Log
# ============================================================================

_event_log: List[Dict[str, Any]] = []
MAX_EVENTS = 100


@router.get("/events", response_model=List[Dict[str, Any]])
async def get_webhook_events(limit: int = 50):
    """Get recent webhook events (last 24h)."""
    return _event_log[-limit:]


@router.get("/stats", response_model=Dict[str, Any])
async def get_webhook_stats():
    """Get webhook statistics."""
    from collections import Counter

    event_types = Counter(e.get("event_type", "unknown") for e in _event_log)
    actions = Counter(e.get("action", "none") for e in _event_log)

    return {
        "total_events": len(_event_log),
        "event_types": dict(event_types),
        "actions": dict(actions),
        "last_event": _event_log[-1] if _event_log else None
    }