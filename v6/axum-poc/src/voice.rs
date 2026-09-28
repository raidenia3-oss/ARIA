//! Voice routes: STT, TTS, wake word, listen.
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
        .route("/api/voice/stt", get(stt_status))
        .route("/api/voice/tts", get(tts_status))
        .route("/api/voice/wake", get(wake_status))
        .route("/api/voice/listen", get(listen_status))
        .route("/api/voice/status", get(voice_status))
        .route("/api/voice/process", post(voice_process))
}

async fn stt_status() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "engine": "whisper",
        "models": ["base", "small", "medium"],
        "server": "ARIA-Axum-8002",
    }))
}

async fn tts_status() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "engine": "piper",
        "voices": ["en_US-amy-medium", "en_US-danny-medium"],
        "server": "ARIA-Axum-8002",
    }))
}

async fn wake_status() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "engine": "vosk",
        "wake_words": ["ARIA", "Aria", "Hey Aria"],
        "server": "ARIA-Axum-8002",
    }))
}

async fn listen_status() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "state": "idle",
        "server": "ARIA-Axum-8002",
    }))
}

async fn voice_status() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "stt": "available",
        "tts": "available",
        "wake_word": "available",
        "server": "ARIA-Axum-8002",
    }))
}

async fn voice_process(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<serde_json::Value>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    state.increment_requests().await;
    
    let text = req.get("text").and_then(|v| v.as_str()).unwrap_or("");
    
    Json(json!({
        "status": "ok",
        "text": text,
        "processed": true,
        "server": "ARIA-Axum-8002",
    }))
}