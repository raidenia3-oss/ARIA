//! Social routes: collect, transcribe, analyze, classify, research, save, library.
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
        .route("/api/social-research/collect", post(collect))
        .route("/api/social-research/transcribe", post(transcribe))
        .route("/api/social-research/analyze", post(analyze))
        .route("/api/social-research/classify", post(classify))
        .route("/api/social-research/research", post(research))
        .route("/api/social-research/save", post(save))
        .route("/api/social-research/library", get(library))
        .route("/api/social-research/status", get(status))
        .route("/api/video-analyze", post(video_analyze))
        .route("/api/video-analyze/batch", post(video_batch))
}

async fn collect(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<serde_json::Value>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    state.increment_requests().await;
    
    let source = req.get("source").and_then(|v| v.as_str()).unwrap_or("");
    
    Json(json!({
        "status": "ok",
        "source": source,
        "collected": true,
        "server": "ARIA-Axum-8002",
    }))
}

async fn transcribe(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<serde_json::Value>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    state.increment_requests().await;
    
    let audio = req.get("audio").and_then(|v| v.as_str()).unwrap_or("");
    
    Json(json!({
        "status": "ok",
        "audio": audio,
        "transcript": "",
        "server": "ARIA-Axum-8002",
    }))
}

async fn analyze(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<serde_json::Value>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    state.increment_requests().await;
    
    let content = req.get("content").and_then(|v| v.as_str()).unwrap_or("");
    
    Json(json!({
        "status": "ok",
        "content": content,
        "analysis": "Social content analysis via Axum backend",
        "server": "ARIA-Axum-8002",
    }))
}

async fn classify(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<serde_json::Value>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    state.increment_requests().await;
    
    let content = req.get("content").and_then(|v| v.as_str()).unwrap_or("");
    
    Json(json!({
        "status": "ok",
        "content": content,
        "classification": "unclassified",
        "importance": 0.5,
        "server": "ARIA-Axum-8002",
    }))
}

async fn research(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<serde_json::Value>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    state.increment_requests().await;
    
    let query = req.get("query").and_then(|v| v.as_str()).unwrap_or("");
    
    Json(json!({
        "status": "ok",
        "query": query,
        "results": [],
        "server": "ARIA-Axum-8002",
    }))
}

async fn save(
    Extension(_state): Extension<Arc<Mutex<SharedState>>>,
    Json(_req): Json<serde_json::Value>,
) -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "saved": true,
        "server": "ARIA-Axum-8002",
    }))
}

async fn library() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "items": [],
        "count": 0,
        "server": "ARIA-Axum-8002",
    }))
}

async fn status() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "collectors": 4,
        "analysers": 3,
        "server": "ARIA-Axum-8002",
    }))
}

async fn video_analyze(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<serde_json::Value>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    state.increment_requests().await;
    
    let url = req.get("url").and_then(|v| v.as_str()).unwrap_or("");
    
    Json(json!({
        "status": "ok",
        "url": url,
        "analysis": "Video analysis via Axum backend",
        "server": "ARIA-Axum-8002",
    }))
}

async fn video_batch(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<serde_json::Value>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    state.increment_requests().await;
    
    let urls = req.get("urls").and_then(|v| v.as_array()).map(|a| a.len()).unwrap_or(0);
    
    Json(json!({
        "status": "ok",
        "urls_processed": urls,
        "server": "ARIA-Axum-8002",
    }))
}