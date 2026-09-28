//! Vision routes: capture, analyze, last.
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
        .route("/api/vision/capture", get(capture))
        .route("/api/vision/analyze", get(analyze))
        .route("/api/vision/last", get(last))
        .route("/api/vision/analyze", post(vision_analyze))
}

async fn capture() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "message": "Screen capture initiated",
        "server": "ARIA-Axum-8002",
    }))
}

async fn analyze() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "message": "Vision analysis ready",
        "server": "ARIA-Axum-8002",
    }))
}

async fn last() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "last_capture": null,
        "server": "ARIA-Axum-8002",
    }))
}

async fn vision_analyze(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<serde_json::Value>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    state.increment_requests().await;
    
    let image = req.get("image").and_then(|v| v.as_str()).unwrap_or("");
    
    Json(json!({
        "status": "ok",
        "image": image,
        "analysis": "Vision analysis via Axum backend",
        "server": "ARIA-Axum-8002",
    }))
}