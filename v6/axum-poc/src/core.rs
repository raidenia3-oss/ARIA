//! Core routes: health, status, system info.
//! Phase L.4: Enhanced with SharedState for real metrics.

use axum::{
    routing::get,
    Router,
    Extension,
    Json,
};
use serde::Serialize;
use std::sync::Arc;
use tokio::sync::Mutex;

use crate::state::SharedState;
use crate::version::ARIA_VERSION;

#[derive(Serialize)]
struct HealthResponse {
    status: String,
    framework: String,
    version: String,
    uptime_ms: u64,
}

pub fn router() -> Router<()> {
    Router::new()
        .route("/health", get(health))
        .route("/api/system/status", get(system_status))
        .route("/api/system/health", get(health))
}

async fn health(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
) -> Json<HealthResponse> {
    let state = state.lock().await;
    Json(HealthResponse {
        status: "ok".into(),
        framework: "Axum (Rust)".into(),
        version: ARIA_VERSION.into(),
        uptime_ms: state.uptime_ms(),
    })
}

async fn system_status(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    let req_count = *state.request_count.lock().await;
    let chat_count = *state.chat_count.lock().await;
    let agent_count = state.daemon_agents.lock().await.len();
    let task_count = state.task_queue.lock().await.len();
    let result_count = state.task_results.lock().await.len();
    let auth_failures = state.auth_failure_count().await;

    Json(serde_json::json!({
        "status": "ok",
        "framework": "Axum (Rust)",
        "version": ARIA_VERSION,
        "uptime_ms": state.uptime_ms(),
        "memory_safety": "compile-time guaranteed",
        "gc_pauses": "0ms (deterministic)",
        "requests_served": req_count,
        "chats_processed": chat_count,
        "daemon_agents": agent_count,
        "pending_tasks": task_count,
        "completed_results": result_count,
        "auth_failures": auth_failures,
        "security": crate::auth::auth_summary(&state.auth),
        "port": 8002,
        "mode": "ARIA-Axum-v6.0",
    }))
}