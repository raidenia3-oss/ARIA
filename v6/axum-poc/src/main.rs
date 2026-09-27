//! ARIA Axum POC — Proof of Concept for v6.0 FastAPI → Axum migration.
//!
//! Tests:
//! 1. Basic routing (health, echo)
//! 2. JSON extractors (type-safe)
//! 3. Shared state (Arc<Mutex>)
//! 4. Benchmark vs FastAPI (port 8000)

use axum::{
    extract::{Json, State},
    response::Json as ResponseJson,
    routing::{get, post},
    Router,
};
use serde::{Deserialize, Serialize};
use std::{sync::Arc, time::Instant};
use tokio::sync::Mutex;

// ── Request/Response Types ──────────────────────────────────────────────

#[derive(Deserialize)]
struct ChatRequest {
    message: String,
    session_id: Option<String>,
}

#[derive(Serialize)]
struct ChatResponse {
    response: String,
    provider: String,
    latency_ms: u64,
    session_id: Option<String>,
}

#[derive(Deserialize)]
struct MemorySearchRequest {
    query: String,
    top_k: Option<usize>,
}

#[derive(Serialize)]
struct MemorySearchResponse {
    query: String,
    results: Vec<String>,
    count: usize,
    latency_ms: u64,
}

#[derive(Serialize)]
struct HealthResponse {
    status: String,
    framework: String,
    version: String,
    uptime_ms: u64,
}

// ── Shared State ────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
struct AxumState {
    request_count: Arc<Mutex<u64>>,
    start_time: Instant,
}

impl AxumState {
    fn new() -> Self {
        Self {
            request_count: Arc::new(Mutex::new(0)),
            start_time: Instant::now(),
        }
    }
}

// ── Handlers ────────────────────────────────────────────────────────────

async fn health(State(state): State<AxumState>) -> ResponseJson<HealthResponse> {
    let _count = *state.request_count.lock().await;
    ResponseJson(HealthResponse {
        status: "ok".into(),
        framework: "Axum (Rust)".into(),
        version: "0.1.0-POC".into(),
        uptime_ms: state.start_time.elapsed().as_millis() as u64,
    })
}

async fn chat(
    State(state): State<AxumState>,
    Json(req): Json<ChatRequest>,
) -> ResponseJson<ChatResponse> {
    let start = Instant::now();
    *state.request_count.lock().await += 1;

    // Simulate Ollama-like processing (in real POC, this calls Ollama via reqwest)
    let response = format!("Echo: {}", req.message);

    ResponseJson(ChatResponse {
        response,
        provider: "axum-poc".into(),
        latency_ms: start.elapsed().as_millis() as u64,
        session_id: req.session_id,
    })
}

async fn memory_search(
    State(state): State<AxumState>,
    Json(req): Json<MemorySearchRequest>,
) -> ResponseJson<MemorySearchResponse> {
    let start = Instant::now();
    *state.request_count.lock().await += 1;

    // Simulate vector DB search
    let results: Vec<String> = (0..req.top_k.unwrap_or(3))
        .map(|i| format!("Result {} for '{}'", i + 1, req.query))
        .collect();

    ResponseJson(MemorySearchResponse {
        query: req.query,
        count: results.len(),
        results,
        latency_ms: start.elapsed().as_millis() as u64,
    })
}

async fn status(State(state): State<AxumState>) -> ResponseJson<serde_json::Value> {
    let count = *state.request_count.lock().await;
    let uptime = state.start_time.elapsed().as_millis() as u64;
    ResponseJson(serde_json::json!({
        "status": "ok",
        "framework": "Axum (Rust)",
        "request_count": count,
        "uptime_ms": uptime,
        "memory_safety": "compile-time guaranteed",
        "gc_pauses": "0ms (deterministic)",
    }))
}

// ── Router ──────────────────────────────────────────────────────────────

fn create_router() -> Router {
    let state = AxumState::new();

    Router::new()
        .route("/health", get(health))
        .route("/api/chat", post(chat))
        .route("/api/memory/search", post(memory_search))
        .route("/api/system/status", get(status))
        .with_state(state)
}

#[tokio::main]
async fn main() {
    let app = create_router();

    let listener = tokio::net::TcpListener::bind("127.0.0.1:8001")
        .await
        .expect("Failed to bind to 127.0.0.1:8001");

    println!("🚀 ARIA Axum POC running on http://127.0.0.1:8001");
    println!("   Endpoints:");
    println!("   - GET  /health");
    println!("   - POST /api/chat");
    println!("   - POST /api/memory/search");
    println!("   - GET  /api/system/status");

    axum::serve(listener, app)
        .await
        .expect("Failed to serve Axum app");
}