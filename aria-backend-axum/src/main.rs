use axum::{
    routing::{get, post},
    extract::Json,
    response::IntoResponse,
    http::StatusCode,
    Router,
};
use serde::{Deserialize, Serialize};
use std::net::SocketAddr;
use tower_http::cors::CorsLayer;

// ═══ MODELS ═══

#[derive(Debug, Serialize)]
pub struct HealthResponse {
    status: String,
    version: String,
    routes: usize,
    timestamp: String,
}

#[derive(Debug, Deserialize)]
pub struct ChatRequest {
    prompt: String,
    #[serde(default)]
    max_tokens: Option<usize>,
}

#[derive(Debug, Serialize)]
pub struct ChatResponse {
    response: String,
    latency_ms: u64,
    model: String,
}

// ═══ HANDLERS ═══

async fn health() -> impl IntoResponse {
    let response = HealthResponse {
        status: "ok".to_string(),
        version: "6.0.0".to_string(),
        routes: 312,
        timestamp: chrono::Utc::now().to_rfc3339(),
    };
    (StatusCode::OK, Json(response))
}

async fn chat(
    Json(request): Json<ChatRequest>,
) -> impl IntoResponse {
    let start = std::time::Instant::now();

    // Call Ollama
    let client = reqwest::Client::new();
    let ollama_url = "http://127.0.0.1:11434/api/generate";

    let body = serde_json::json!({
        "model": "dolphin-2_6-phi-2",
        "prompt": request.prompt,
        "stream": false,
    });

    let response = match client.post(ollama_url).json(&body).send().await {
        Ok(resp) => match resp.json::<serde_json::Value>().await {
            Ok(data) => data["response"]
                .as_str()
                .unwrap_or("Error: no response field")
                .to_string(),
            Err(_) => "Error parsing Ollama response".to_string(),
        },
        Err(e) => format!("Error connecting to Ollama: {}", e),
    };

    (
        StatusCode::OK,
        Json(ChatResponse {
            response,
            latency_ms: start.elapsed().as_millis() as u64,
            model: "dolphin-2_6-phi-2".to_string(),
        }),
    )
}

// ═══ ROUTER ═══

fn create_router() -> Router {
    Router::new()
        .route("/api/health", get(health))
        .route("/api/chat", post(chat))
        .layer(CorsLayer::permissive())
}

// ═══ MAIN ═══

#[tokio::main]
async fn main() {
    // Init logging
    tracing_subscriber::fmt::init();

    // Create router
    let app = create_router();

    // Bind to port
    let addr = SocketAddr::from(([127, 0, 0, 1], 8001));
    println!("🚀 Axum v6.0 listening on http://{}", addr);

    // Run
    let listener = tokio::net::TcpListener::bind(addr)
        .await
        .expect("Failed to bind to port 8001");

    axum::serve(listener, app)
        .await
        .expect("Server error");
}