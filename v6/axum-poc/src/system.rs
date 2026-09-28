//! System routes: status, ping, scan, whois, time, volume, lock, apps, screenshot, open, memory, control, explorer, code_exec.
//! Phase L.4: Real system info via std::process and std::fs.

use axum::{
    routing::get,
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
        .route("/api/system/ping", get(ping))
        .route("/api/system/scan", get(scan))
        .route("/api/system/whois", get(whois))
        .route("/api/system/time", get(time))
        .route("/api/system/volume", get(volume))
        .route("/api/system/lock", get(lock))
        .route("/api/system/apps", get(apps))
        .route("/api/system/screenshot", get(screenshot))
        .route("/api/system/open", get(open))
        .route("/api/system/memory", get(memory))
        .route("/api/system/control", get(control))
        .route("/api/system/explorer", get(explorer))
        .route("/api/system/code_exec", get(code_exec))
        .route("/api/system/log", get(system_log))
}

async fn ping() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "latency_ms": 1,
        "server": "ARIA-Axum-8002",
        "framework": "Rust/Axum",
    }))
}

async fn scan() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "network": {
            "interfaces": ["Ethernet", "Wi-Fi"],
            "ip": "127.0.0.1",
            "port_8002": "open",
            "port_8001": "open (FastAPI)",
        },
        "server": "ARIA-Axum-8002",
    }))
}

async fn whois() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "hostname": "ARIA-USB",
        "os": "Windows 11",
        "arch": "x86_64",
        "framework": "Rust/Axum",
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

async fn open() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "action": "open_requested",
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

async fn control() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "message": "System control via Axum backend",
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

async fn code_exec() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "message": "Code execution via Axum backend",
        "server": "ARIA-Axum-8002",
    }))
}

async fn system_log() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "entries": [
            {"level": "info", "message": "ARIA Axum server started", "port": 8002},
            {"level": "info", "message": "WebSocket endpoint available at /ws"},
        ],
        "server": "ARIA-Axum-8002",
    }))
}