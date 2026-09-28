//! Memory routes: proxy to FastAPI backend (port 8001) for SQLite access.
use axum::{routing::{get, post}, Router, Json};
use serde::{Deserialize, Serialize};
use serde_json::Value;

const FASTAPI_URL: &str = "http://127.0.0.1:8001";

#[derive(Deserialize)]
struct StoreRequest {
    query: String,
    content: String,
    metadata: Option<Value>,
}

#[derive(Serialize)]
struct StoreResponse {
    status: String,
    memory_id: String,
    latency_ms: u64,
}

#[derive(Deserialize)]
struct SearchRequest {
    query: String,
    top_k: Option<usize>,
}

#[derive(Serialize)]
struct SearchResponse {
    query: String,
    results: Vec<Value>,
    count: usize,
}

pub fn router() -> Router<()> {
    Router::new()
        .route("/api/memory/store", post(store_memory))
        .route("/api/memory/search", post(search_memory))
        .route("/api/memory/stats", get(memory_stats))
        .route("/api/memory/recent", get(recent_memory))
}

async fn store_memory(Json(req): Json<StoreRequest>) -> Json<StoreResponse> {
    let start = std::time::Instant::now();
    let client = reqwest::Client::new();

    let payload = serde_json::json!({
        "query": req.query,
        "content": req.content,
        "metadata": req.metadata.unwrap_or(serde_json::json!({}))
    });

    let resp = client
        .post(format!("{}/api/memory/save", FASTAPI_URL))
        .json(&payload)
        .timeout(std::time::Duration::from_secs(10))
        .send()
        .await;

    match resp {
        Ok(r) => {
            let data: Value = r.json().await.unwrap_or(serde_json::json!({}));
            Json(StoreResponse {
                status: data.get("status").and_then(|v| v.as_str()).unwrap_or("error").to_string(),
                memory_id: data.get("memory_id").and_then(|v| v.as_str()).unwrap_or("mem_proxy").to_string(),
                latency_ms: start.elapsed().as_millis() as u64,
            })
        }
        Err(_) => Json(StoreResponse {
            status: "error_no_backend".to_string(),
            memory_id: format!("mem_{}", start.elapsed().as_millis()),
            latency_ms: start.elapsed().as_millis() as u64,
        }),
    }
}

async fn search_memory(Json(req): Json<SearchRequest>) -> Json<SearchResponse> {
    let client = reqwest::Client::new();

    let payload = serde_json::json!({
        "query": req.query,
        "top_k": req.top_k.unwrap_or(5)
    });

    let resp = client
        .post(format!("{}/api/memory/search", FASTAPI_URL))
        .json(&payload)
        .timeout(std::time::Duration::from_secs(10))
        .send()
        .await;

    match resp {
        Ok(r) => {
            let data: Value = r.json().await.unwrap_or(serde_json::json!({}));
            Json(SearchResponse {
                query: req.query,
                count: data.get("count").and_then(|v| v.as_u64()).unwrap_or(0) as usize,
                results: data.get("results").and_then(|v| v.as_array().cloned()).unwrap_or_default(),
            })
        }
        Err(_) => Json(SearchResponse {
            query: req.query,
            count: 0,
            results: vec![],
        }),
    }
}

async fn recent_memory() -> Json<Value> {
    let client = reqwest::Client::new();

    let resp = client
        .get(format!("{}/api/memory/recent", FASTAPI_URL))
        .timeout(std::time::Duration::from_secs(10))
        .send()
        .await;

    match resp {
        Ok(r) => {
            let data: Value = r.json().await.unwrap_or(serde_json::json!({}));
            Json(data)
        }
        Err(_) => Json(serde_json::json!({ "recent": [], "error": "backend_unavailable" })),
    }
}

async fn memory_stats() -> Json<Value> {
    let client = reqwest::Client::new();

    let resp = client
        .get(format!("{}/api/memory/stats", FASTAPI_URL))
        .timeout(std::time::Duration::from_secs(10))
        .send()
        .await;

    match resp {
        Ok(r) => {
            let data: Value = r.json().await.unwrap_or(serde_json::json!({}));
            Json(data)
        }
        Err(_) => Json(serde_json::json!({ "total_memories": 0, "error": "backend_unavailable" })),
    }
}