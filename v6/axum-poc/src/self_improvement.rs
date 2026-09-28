//! Self-improvement routes: cycle, status, proposals.
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
        .route("/api/self-improvement/start", post(start))
        .route("/api/self-improvement/status", get(status))
        .route("/api/self-improvement/proposals", get(proposals))
        .route("/api/self-improvement/commit", post(commit))
        .route("/api/self-improvement/analyze-prs", get(analyze_prs))
        .route("/api/self-improvement/triaging", get(triaging))
}

async fn start(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    state.increment_requests().await;
    
    Json(json!({
        "status": "ok",
        "started": true,
        "message": "Self-improvement cycle started",
        "server": "ARIA-Axum-8002",
    }))
}

async fn status() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "running": false,
        "cycles_completed": 0,
        "proposals_pending": 0,
        "server": "ARIA-Axum-8002",
    }))
}

async fn proposals() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "proposals": [],
        "count": 0,
        "server": "ARIA-Axum-8002",
    }))
}

async fn commit(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    state.increment_requests().await;
    
    Json(json!({
        "status": "ok",
        "committed": true,
        "server": "ARIA-Axum-8002",
    }))
}

async fn analyze_prs() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "prs_analyzed": 0,
        "server": "ARIA-Axum-8002",
    }))
}

async fn triaging() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "triaging": false,
        "server": "ARIA-Axum-8002",
    }))
}