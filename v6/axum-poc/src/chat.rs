//! Chat routes: message, streaming, history.
use axum::{routing::post, Router, Json};
use serde::{Deserialize, Serialize};

#[derive(Deserialize)]
struct ChatRequest { message: String, session_id: Option<String> }

#[derive(Serialize)]
struct ChatResponse { response: String, provider: String, latency_ms: u64, session_id: Option<String> }

pub fn router() -> Router<()> {
    Router::new()
        .route("/api/chat", post(chat))
        .route("/api/chat/stream", post(chat_stream))
        .route("/api/chat/history", post(chat_history))
}

async fn chat(Json(req): Json<ChatRequest>) -> Json<ChatResponse> {
    Json(ChatResponse {
        response: format!("Echo: {}", req.message),
        provider: "axum".into(),
        latency_ms: 42,
        session_id: req.session_id,
    })
}

async fn chat_stream(Json(req): Json<ChatRequest>) -> &'static str {
    "streaming placeholder"
}

async fn chat_history() -> &'static str { "history placeholder" }