//! Chat routes: message, streaming, history.
//! Phase L.4: Connects to Ollama for AI inference, tracks via SharedState.

use axum::{
    routing::{get, post},
    Router,
    Extension,
    Json,
};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::sync::Arc;
use tokio::sync::Mutex;

use crate::state::SharedState;

#[derive(Deserialize)]
struct ChatRequest {
    message: String,
    session_id: Option<String>,
    provider: Option<String>,
}

#[derive(Serialize)]
struct ChatResponse {
    response: String,
    provider: String,
    latency_ms: u64,
    session_id: Option<String>,
}

#[derive(Deserialize)]
struct OllamaResponse {
    model: String,
    created_at: String,
    response: String,
    done: bool,
}

#[derive(Serialize)]
struct ChatHistoryResponse {
    history: Vec<Value>,
    session_id: String,
}

pub fn router() -> Router<()> {
    Router::new()
        .route("/api/chat", post(chat))
        .route("/api/chat/stream", post(chat_stream))
        .route("/api/chat/history", get(chat_history))
}

async fn chat(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<ChatRequest>,
) -> Json<ChatResponse> {
    let start = std::time::Instant::now();
    let provider = req.provider.clone().unwrap_or_else(|| "dolphin-2_6-phi-2".to_string());

    // Call Ollama
    let ollama_response = call_ollama(&req.message, &provider).await;
    
    // Increment chat counter
    {
        let state = state.lock().await;
        state.increment_chats().await;
    }

    Json(ChatResponse {
        response: ollama_response,
        provider: format!("ollama:{}", provider),
        latency_ms: start.elapsed().as_millis() as u64,
        session_id: req.session_id,
    })
}

async fn call_ollama(message: &str, model: &str) -> String {
    let client = reqwest::Client::new();
    
    let payload = serde_json::json!({
        "model": model,
        "prompt": message,
        "stream": false
    });

    match client
        .post("http://localhost:11434/api/generate")
        .json(&payload)
        .timeout(std::time::Duration::from_secs(60))
        .send()
        .await
    {
        Ok(resp) => {
            match resp.json::<OllamaResponse>().await {
                Ok(data) => {
                    if data.done {
                        return data.response;
                    }
                    format!("[ARIA-Axum] Ollama response: {}", data.response)
                }
                Err(_) => "[ARIA-Axum] Ollama response parse error".to_string(),
            }
        }
        Err(e) => format!("[ARIA-Axum] Ollama error: {}. Running in echo mode.", e),
    }
}

async fn chat_stream(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<ChatRequest>,
) -> Json<ChatResponse> {
    // For streaming, just call non-streaming and return
    let response = call_ollama(&req.message, "dolphin-2_6-phi-2").await;
    
    {
        let state = state.lock().await;
        state.increment_chats().await;
    }
    
    Json(ChatResponse {
        response,
        provider: "ollama:stream".to_string(),
        latency_ms: 0,
        session_id: req.session_id,
    })
}

async fn chat_history() -> Json<ChatHistoryResponse> {
    Json(ChatHistoryResponse {
        history: vec![],
        session_id: "default".to_string(),
    })
}