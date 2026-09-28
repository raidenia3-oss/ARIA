//! Proactive routes: alerts, reminders, owner state.
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
        .route("/api/proactive/alert", get(alert))
        .route("/api/proactive/reminder", get(reminder))
        .route("/api/proactive/owner-state", get(owner_state))
        .route("/api/proactive/alerts", get(alerts))
        .route("/api/proactive/reminders", get(reminders))
        .route("/api/proactive/trigger", post(trigger_proactive))
}

async fn alert() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "message": "Alert sent",
        "server": "ARIA-Axum-8002",
    }))
}

async fn reminder() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "message": "Reminder set",
        "server": "ARIA-Axum-8002",
    }))
}

async fn owner_state() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "owner": "active",
        "session": "ARIA-USB",
        "server": "ARIA-Axum-8002",
    }))
}

async fn alerts() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "alerts": [],
        "server": "ARIA-Axum-8002",
    }))
}

async fn reminders() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "reminders": [],
        "server": "ARIA-Axum-8002",
    }))
}

async fn trigger_proactive(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<serde_json::Value>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    state.increment_requests().await;
    
    let action = req.get("action").and_then(|v| v.as_str()).unwrap_or("");
    
    Json(json!({
        "status": "ok",
        "action": action,
        "triggered": true,
        "server": "ARIA-Axum-8002",
    }))
}