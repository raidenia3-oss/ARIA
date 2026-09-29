//! Web routes: search, fetch, automation, browser.
//! Phase L.4: Real JSON responses with SharedState.

use axum::{
    routing::{get, post},
    Router,
    Extension,
    Json,
};
use serde::Deserialize;
use serde_json::json;
use std::sync::Arc;
use tokio::sync::Mutex;

use crate::state::SharedState;

#[derive(Deserialize)]
struct WebActionRequest {
    action: String,
    params: Option<serde_json::Value>,
}

pub fn router() -> Router<()> {
    Router::new()
        .route("/api/web/search", post(web_search))
        .route("/api/web/fetch", post(web_fetch))
        .route("/api/web/automate", post(web_automate))
        .route("/api/web/browser", post(browser_action))
        .route("/api/web/screenshot", post(capture_screenshot))
        .route("/api/web/navigate", post(navigate_url))
        .route("/api/web/evaluate", post(evaluate_js))
        .route("/api/web/status", get(web_status))
}

async fn web_search(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<WebActionRequest>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    state.increment_requests().await;

    let query = req.params.and_then(|p| p.get("query").and_then(|v| v.as_str()).map(String::from)).unwrap_or_default();

    Json(json!({
        "status": "ok",
        "query": query,
        "results": [],
        "server": "ARIA-Axum-8002",
    }))
}

async fn web_fetch(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<WebActionRequest>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    state.increment_requests().await;

    let url = req.params.and_then(|p| p.get("url").and_then(|v| v.as_str()).map(String::from)).unwrap_or_default();

    Json(json!({
        "status": "ok",
        "url": url,
        "content": "",
        "server": "ARIA-Axum-8002",
    }))
}

async fn web_automate(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<WebActionRequest>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    state.increment_requests().await;

    Json(json!({
        "status": "ok",
        "action": req.action,
        "server": "ARIA-Axum-8002",
    }))
}

async fn browser_action(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<WebActionRequest>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    state.increment_requests().await;

    Json(json!({
        "status": "ok",
        "action": req.action,
        "server": "ARIA-Axum-8002",
    }))
}

async fn capture_screenshot(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(_req): Json<WebActionRequest>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    state.increment_requests().await;

    Json(json!({
        "status": "ok",
        "action": "screenshot",
        "server": "ARIA-Axum-8002",
    }))
}

async fn navigate_url(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<WebActionRequest>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    state.increment_requests().await;

    let url = req.params.and_then(|p| p.get("url").and_then(|v| v.as_str()).map(String::from)).unwrap_or_default();

    Json(json!({
        "status": "ok",
        "url": url,
        "server": "ARIA-Axum-8002",
    }))
}

async fn evaluate_js(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<WebActionRequest>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    state.increment_requests().await;

    Json(json!({
        "status": "ok",
        "action": req.action,
        "server": "ARIA-Axum-8002",
    }))
}

async fn web_status() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "browser": "playwright-chromium",
        "active_sessions": 0,
        "server": "ARIA-Axum-8002",
    }))
}