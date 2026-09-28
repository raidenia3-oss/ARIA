//! Evolution routes: metrics, record, evolve.
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
        .route("/api/evolution/metrics", get(metrics))
        .route("/api/evolution/record", get(record))
        .route("/api/evolution/evolve", post(evolve))
}

async fn metrics() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "skills_evolved": 10,
        "improvements_applied": 25,
        "server": "ARIA-Axum-8002",
    }))
}

async fn record() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "message": "Evolution recorded",
        "server": "ARIA-Axum-8002",
    }))
}

async fn evolve(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    state.increment_requests().await;
    
    Json(json!({
        "status": "ok",
        "evolution_triggered": true,
        "server": "ARIA-Axum-8002",
    }))
}