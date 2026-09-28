//! Core routes: health, status, system info.
use axum::{routing::get, Router, Json};
use serde::Serialize;
use std::time::Instant;
use std::sync::OnceLock;

#[derive(Serialize)]
struct HealthResponse {
    status: String,
    framework: String,
    version: String,
    uptime_ms: u64,
}

static START_TIME: OnceLock<Instant> = OnceLock::new();

pub fn router() -> Router<()> {
    START_TIME.get_or_init(Instant::now);
    
    Router::new()
        .route("/health", get(health))
        .route("/api/system/status", get(system_status))
        .route("/api/system/health", get(health))
}

async fn health() -> Json<HealthResponse> {
    let start = START_TIME.get().unwrap();
    Json(HealthResponse {
        status: "ok".into(),
        framework: "Axum (Rust)".into(),
        version: "0.1.0-POC".into(),
        uptime_ms: start.elapsed().as_millis() as u64,
    })
}

async fn system_status() -> Json<serde_json::Value> {
    let start = START_TIME.get().unwrap();
    Json(serde_json::json!({
        "status": "ok",
        "framework": "Axum (Rust)",
        "version": "0.1.0-POC",
        "uptime_ms": start.elapsed().as_millis(),
        "memory_safety": "compile-time guaranteed",
        "gc_pauses": "0ms (deterministic)",
    }))
}