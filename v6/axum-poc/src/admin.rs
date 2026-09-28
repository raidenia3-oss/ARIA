//! Admin routes: system management, users, settings.
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
        .route("/api/admin/users", get(users))
        .route("/api/admin/roles", get(roles))
        .route("/api/admin/permissions", get(permissions))
        .route("/api/admin/settings", get(settings))
        .route("/api/admin/system", get(system))
        .route("/api/admin/logs", get(logs))
        .route("/api/admin/backup", post(backup))
        .route("/api/admin/restore", post(restore))
}

async fn users() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "users": [],
        "count": 0,
        "server": "ARIA-Axum-8002",
    }))
}

async fn roles() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "roles": ["admin", "user", "viewer"],
        "server": "ARIA-Axum-8002",
    }))
}

async fn permissions() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "permissions": ["read", "write", "execute", "admin"],
        "server": "ARIA-Axum-8002",
    }))
}

async fn settings() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "settings": {
            "port": 8002,
            "framework": "Axum (Rust)",
            "mode": "ARIA-Axum-v6.0",
        },
        "server": "ARIA-Axum-8002",
    }))
}

async fn system() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "system": {
            "framework": "Axum (Rust)",
            "version": "0.1.0-POC",
            "port": 8002,
            "mode": "ARIA-Axum-v6.0",
        },
        "server": "ARIA-Axum-8002",
    }))
}

async fn logs() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "logs": [],
        "server": "ARIA-Axum-8002",
    }))
}

async fn backup(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    state.increment_requests().await;
    
    Json(json!({
        "status": "ok",
        "backup": "created",
        "server": "ARIA-Axum-8002",
    }))
}

async fn restore(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    state.increment_requests().await;
    
    Json(json!({
        "status": "ok",
        "restored": true,
        "server": "ARIA-Axum-8002",
    }))
}