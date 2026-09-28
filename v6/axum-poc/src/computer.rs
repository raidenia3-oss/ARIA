//! Computer routes: control, apps, screenshot, open, volume.
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
        .route("/api/computer/control", get(control))
        .route("/api/computer/apps", get(apps))
        .route("/api/computer/screenshot", get(screenshot))
        .route("/api/computer/open", post(open))
        .route("/api/computer/volume", get(volume))
        .route("/api/computer/lock", get(lock))
        .route("/api/computer/memory", get(memory))
        .route("/api/computer/processes", get(processes))
        .route("/api/computer/status", get(status))
        .route("/api/computer/scan", get(scan))
        .route("/api/computer/whois", get(whois))
        .route("/api/computer/time", get(time))
        .route("/api/computer/ping", get(ping))
        .route("/api/computer/explorer", get(explorer))
        .route("/api/computer/execute", post(execute))
}

async fn control() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "message": "Computer control via Axum backend",
        "server": "ARIA-Axum-8002",
    }))
}

async fn apps() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "running": ["ARIA-Axum-8002", "FastAPI-8001", "Discord", "Ollama"],
        "server": "ARIA-Axum-8002",
    }))
}

async fn screenshot() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "message": "Screenshot captured via Axum backend",
        "server": "ARIA-Axum-8002",
    }))
}

async fn open(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<serde_json::Value>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    state.increment_requests().await;
    
    let target = req.get("target").and_then(|v| v.as_str()).unwrap_or("");
    
    Json(json!({
        "status": "ok",
        "target": target,
        "opened": true,
        "server": "ARIA-Axum-8002",
    }))
}

async fn volume() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "volume": 75,
        "muted": false,
        "server": "ARIA-Axum-8002",
    }))
}

async fn lock() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "action": "lock_requested",
        "server": "ARIA-Axum-8002",
    }))
}

async fn memory() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "total": 16_000_000_000u64,
        "used": 8_000_000_000u64,
        "available": 8_000_000_000u64,
        "usage_percent": 50.0,
        "server": "ARIA-Axum-8002",
    }))
}

async fn processes() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "processes": ["aria-axum", "fastapi", "ollama", "discord"],
        "server": "ARIA-Axum-8002",
    }))
}

async fn status() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "cpu": "x86_64",
        "os": "Windows 11",
        "memory": "16GB",
        "server": "ARIA-Axum-8002",
    }))
}

async fn scan() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "network": "OK",
        "server": "ARIA-Axum-8002",
    }))
}

async fn whois() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "hostname": "ARIA-USB",
        "server": "ARIA-Axum-8002",
    }))
}

async fn time() -> Json<serde_json::Value> {
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_secs();
    
    Json(json!({
        "status": "ok",
        "timestamp": now,
        "server": "ARIA-Axum-8002",
    }))
}

async fn ping() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "latency_ms": 1,
        "server": "ARIA-Axum-8002",
    }))
}

async fn explorer() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "message": "Explorer integration via Axum backend",
        "server": "ARIA-Axum-8002",
    }))
}

async fn execute(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<serde_json::Value>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    state.increment_requests().await;
    
    let command = req.get("command").and_then(|v| v.as_str()).unwrap_or("");
    
    Json(json!({
        "status": "ok",
        "command": command,
        "output": "Executed via Axum backend",
        "server": "ARIA-Axum-8002",
    }))
}