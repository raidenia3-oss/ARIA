//! Web routes: browser automation integration.
use axum::{routing::{get, post}, Router, Json};
use serde::{Deserialize, Serialize};
use serde_json::Value;

#[derive(Deserialize)]
struct WebActionRequest {
    action: String,
    params: Option<Value>,
}

#[derive(Serialize)]
struct WebActionResponse {
    status: String,
    action: String,
    result: Value,
}

pub fn router() -> Router<()> {
    Router::new()
        .route("/api/web/browser", post(browser_action))
        .route("/api/web/screenshot", post(capture_screenshot))
        .route("/api/web/navigate", post(navigate_url))
        .route("/api/web/evaluate", post(evaluate_js))
        .route("/api/web/status", get(web_status))
}

async fn browser_action(Json(_req): Json<WebActionRequest>) -> Json<WebActionResponse> {
    Json(WebActionResponse {
        status: "ok".to_string(),
        action: "browser".to_string(),
        result: serde_json::json!({}),
    })
}

async fn capture_screenshot(Json(_req): Json<WebActionRequest>) -> Json<WebActionResponse> {
    Json(WebActionResponse {
        status: "ok".to_string(),
        action: "screenshot".to_string(),
        result: serde_json::json!({}),
    })
}

async fn navigate_url(Json(_req): Json<WebActionRequest>) -> Json<WebActionResponse> {
    Json(WebActionResponse {
        status: "ok".to_string(),
        action: "navigate".to_string(),
        result: serde_json::json!({}),
    })
}

async fn evaluate_js(Json(_req): Json<WebActionRequest>) -> Json<WebActionResponse> {
    Json(WebActionResponse {
        status: "ok".to_string(),
        action: "evaluate".to_string(),
        result: serde_json::json!({}),
    })
}

async fn web_status() -> Json<Value> {
    Json(serde_json::json!({
        "status": "ready",
        "browser": "playwright-chromium",
        "active_sessions": 0
    }))
}