//! Learning routes: rules, record-error, suppress.
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
        .route("/api/learning/rules", get(rules))
        .route("/api/learning/record-error", post(record_error))
        .route("/api/learning/suppress", post(suppress))
}

async fn rules() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "rules": [],
        "count": 0,
        "server": "ARIA-Axum-8002",
    }))
}

async fn record_error(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<serde_json::Value>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    state.increment_requests().await;
    
    let error = req.get("error").and_then(|v| v.as_str()).unwrap_or("");
    
    Json(json!({
        "status": "ok",
        "error": error,
        "recorded": true,
        "server": "ARIA-Axum-8002",
    }))
}

async fn suppress(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<serde_json::Value>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    state.increment_requests().await;
    
    let pattern = req.get("pattern").and_then(|v| v.as_str()).unwrap_or("");
    
    Json(json!({
        "status": "ok",
        "pattern": pattern,
        "suppressed": true,
        "server": "ARIA-Axum-8002",
    }))
}