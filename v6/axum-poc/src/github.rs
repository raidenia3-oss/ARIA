//! GitHub routes: repos, PRs, issues, webhooks.
//! Phase L.4: Real JSON responses.

use axum::{
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

async fn webhooks(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(_req): Json<serde_json::Value>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    state.increment_requests().await;
    
    Json(json!({
        "status": "ok",
        "webhook_received": true,
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