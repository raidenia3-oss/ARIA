//! GitHub routes: repos, PRs, issues, webhooks.
//! Phase L.4: Real JSON responses.

use axum::{
    body::Bytes,
    http::HeaderMap,
    routing::{get, post},
    Router,
    Extension,
    Json,
};
use serde_json::json;
use std::sync::Arc;
use tokio::sync::Mutex;

use crate::state::SharedState;

pub fn router() -> Router<()> {
    Router::new()
        .route("/api/github/repos", get(repos))
        .route("/api/github/prs", get(prs))
        .route("/api/github/issues", get(issues))
        .route("/api/github/webhooks", post(webhooks))
        .route("/api/github/auto-pr/test", get(auto_pr_test))
}

async fn repos() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "repos": [],
        "server": "ARIA-Axum-8002",
    }))
}

async fn prs() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "prs": [],
        "server": "ARIA-Axum-8002",
    }))
}

async fn issues() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "issues": [],
        "server": "ARIA-Axum-8002",
    }))
}

/// `POST /api/github/webhooks` — accept a GitHub delivery.
///
/// The body is read as raw [`Bytes`] instead of `Json<Value>`: GitHub pings with
/// an empty payload, and a manual `curl -X POST` often sends no body or no
/// `Content-Type`. The `Json` extractor rejects all of those with an empty-body
/// 4xx before the handler runs, so the response is parsed leniently here and the
/// handler always answers with the ARIA ack payload.
async fn webhooks(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    headers: HeaderMap,
    body: Bytes,
) -> Json<serde_json::Value> {
    state.lock().await.increment_requests().await;

    let event = headers
        .get("x-github-event")
        .and_then(|value| value.to_str().ok())
        .unwrap_or("unknown")
        .to_string();

    let delivery = headers
        .get("x-github-delivery")
        .and_then(|value| value.to_str().ok())
        .unwrap_or("")
        .to_string();

    let parsed: Option<serde_json::Value> = serde_json::from_slice(&body).ok();
    let action = parsed
        .as_ref()
        .and_then(|value| value.get("action"))
        .and_then(|value| value.as_str())
        .unwrap_or("")
        .to_string();
    let payload_bytes = body.len();

    Json(json!({
        "status": "ok",
        "webhook_received": true,
        "event": event,
        "action": action,
        "delivery": delivery,
        "payload_bytes": payload_bytes,
        "valid_json": parsed.is_some(),
        "server": "ARIA-Axum-8002",
    }))
}

async fn auto_pr_test() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "message": "Auto-PR test via Axum backend",
        "server": "ARIA-Axum-8002",
    }))
}