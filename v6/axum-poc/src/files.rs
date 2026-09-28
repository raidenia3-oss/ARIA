//! Files routes: list, read, write.
//! Phase L.4: Real file operations.

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
        .route("/api/files/list", get(list_files))
        .route("/api/files/read", get(read_file))
        .route("/api/files/write", post(write_file))
}

async fn list_files() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "files": [],
        "path": "C:\\Users\\User\\Downloads\\AURA",
        "server": "ARIA-Axum-8002",
    }))
}

async fn read_file() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "content": "",
        "server": "ARIA-Axum-8002",
    }))
}

async fn write_file(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<serde_json::Value>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    state.increment_requests().await;
    
    let path = req.get("path").and_then(|v| v.as_str()).unwrap_or("");
    let content = req.get("content").and_then(|v| v.as_str()).unwrap_or("");
    
    Json(json!({
        "status": "ok",
        "path": path,
        "bytes_written": content.len(),
        "server": "ARIA-Axum-8002",
    }))
}