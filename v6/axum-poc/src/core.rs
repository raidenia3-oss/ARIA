//! Core routes: health, status, system info.
use axum::{routing::get, Router, Json};
use serde::Serialize;
use std::sync::Arc;
use tokio::sync::Mutex;
use std::time::Instant;

#[derive(Serialize)]
struct HealthResponse {
    status: String,
    framework: String,
    version: String,
    uptime_ms: u64,
}

#[derive(Clone)]
struct CoreState {
    start_time: Instant,
    request_count: Arc<Mutex<u64>>,
}

pub fn router() -> Router<CoreState> {
    let state = CoreState {
        start_time: Instant::now(),
        request_count: Arc::new(Mutex::new(0)),
    };

    Router::new()
        .route("/health", get(health))
        .route("/api/system/status", get(system_status))
        .route("/api/system/health", get(health))
        .with_state(state)
}

async fn health() -> Json<HealthResponse> {
    Json(HealthResponse {
        status: "ok".into(),
        framework: "Axum (Rust)".into(),
        version: "0.1.0-POC".into(),
        uptime_ms: 0,
    })
}

async fn system_status() -> Json<serde_json::Value> {
    Json(serde_json::json!({
        "status": "ok",
        "framework": "Axum (Rust)",
        "memory_safety": "compile-time guaranteed",
        "gc_pauses": "0ms (deterministic)",
    }))
}