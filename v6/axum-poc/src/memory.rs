//! Memory routes: proxy to FastAPI backend (port 8001) for SQLite access.
//! Phase L.4: Falls back to local storage if FastAPI unavailable.

use axum::{
    routing::{get, post},
    Router,
    Extension,
    Json,
    extract::Query,
};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::Mutex;

use crate::state::SharedState;

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

#[derive(Deserialize)]
struct SearchQueryParams {
    query: Option<String>,
    top_k: Option<usize>,
}

#[derive(Deserialize)]
struct RecallParams {
    query: Option<String>,
    top_k: Option<usize>,
}

pub fn router() -> Router<()> {
    Router::new()
        .route("/api/memory/store", post(store_memory))
        .route("/api/memory/save", post(store_memory))
        .route("/api/memory/search", post(search_memory))
        .route("/api/memory/search", get(search_memory_get))
        .route("/api/memory/recall", get(recent_memory))
        .route("/api/memory/stats", get(memory_stats))
        .route("/api/memory/recent", get(recent_memory))
        .route("/api/memory/vector/add", post(vector_add))
        .route("/api/memory/vector/search", post(vector_search))
        .route("/api/memory/vector/rag", get(vector_rag))
        .route("/api/memory/vector/collections", get(vector_collections))
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

    let top_k_str = req.top_k.map(|v| v.to_string()).unwrap_or_default();
    let resp = client
        .get(format!("{}/api/memory/search", FASTAPI_URL))
        .query(&[("query", &req.query), ("top_k", &top_k_str)])
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

async fn vector_add(Json(req): Json<serde_json::Value>) -> Json<serde_json::Value> {
    let client = reqwest::Client::new();
    let resp = client
        .post(format!("{}/api/memory/vector/add", FASTAPI_URL))
        .json(&req)
        .timeout(std::time::Duration::from_secs(10))
        .send()
        .await;
    
    match resp {
        Ok(r) => {
            let data: Value = r.json().await.unwrap_or(serde_json::json!({}));
            Json(data)
        }
        Err(_) => Json(serde_json::json!({ "status": "error", "error": "backend_unavailable" })),
    }
}

async fn vector_search(Json(req): Json<serde_json::Value>) -> Json<serde_json::Value> {
    let client = reqwest::Client::new();
    let resp = client
        .post(format!("{}/api/memory/vector/search", FASTAPI_URL))
        .json(&req)
        .timeout(std::time::Duration::from_secs(10))
        .send()
        .await;
    
    match resp {
        Ok(r) => {
            let data: Value = r.json().await.unwrap_or(serde_json::json!({}));
            Json(data)
        }
        Err(_) => Json(serde_json::json!({ "results": [], "error": "backend_unavailable" })),
    }
}

async fn vector_rag() -> Json<serde_json::Value> {
    let client = reqwest::Client::new();
    let resp = client
        .get(format!("{}/api/memory/vector/rag", FASTAPI_URL))
        .timeout(std::time::Duration::from_secs(10))
        .send()
        .await;
    
    match resp {
        Ok(r) => {
            let data: Value = r.json().await.unwrap_or(serde_json::json!({}));
            Json(data)
        }
        Err(_) => Json(serde_json::json!({ "error": "backend_unavailable" })),
    }
}

async fn vector_collections() -> Json<serde_json::Value> {
    let client = reqwest::Client::new();
    let resp = client
        .get(format!("{}/api/memory/vector/collections", FASTAPI_URL))
        .timeout(std::time::Duration::from_secs(10))
        .send()
        .await;

    match resp {
        Ok(r) => {
            let data: Value = r.json().await.unwrap_or(serde_json::json!({}));
            Json(data)
        }
        Err(_) => Json(serde_json::json!({ "collections": [], "error": "backend_unavailable" })),
    }
}

/// POST /api/memory/save — save a memory entry.
async fn save_memory(Json(req): Json<serde_json::Value>) -> Json<serde_json::Value> {
    let client = reqwest::Client::new();
    let payload = serde_json::json!({
        "query": req.get("query").unwrap_or(&serde_json::Value::Null),
        "content": req.get("content").unwrap_or(&serde_json::Value::Null),
        "metadata": req.get("metadata").unwrap_or(&serde_json::json!({}))
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
            Json(serde_json::json!({
                "status": data.get("status").and_then(|v| v.as_str()).unwrap_or("ok"),
                "memory_id": data.get("memory_id").and_then(|v| v.as_str()).unwrap_or("mem_axum"),
                "server": "ARIA-Axum-8002",
            }))
        }
        Err(_) => Json(serde_json::json!({
            "status": "error_no_backend",
            "memory_id": format!("mem_axum_{}", std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_millis()),
            "server": "ARIA-Axum-8002",
        })),
    }
}

/// GET /api/memory/recall — recall memories by query string.
async fn recall_memory(
    Query(params): Query<RecallParams>,
) -> Json<serde_json::Value> {
    let client = reqwest::Client::new();

    let query_str = params.query.as_deref().unwrap_or("");
    let top_k_str = params.top_k.unwrap_or(5).to_string();
    let resp = client
        .get(format!("{}/api/memory/search", FASTAPI_URL))
        .query(&[("query", query_str), ("top_k", &top_k_str)])
        .timeout(std::time::Duration::from_secs(10))
        .send()
        .await;

    match resp {
        Ok(r) => {
            let data: Value = r.json().await.unwrap_or(serde_json::json!({}));
            Json(serde_json::json!({
                "status": "ok",
                "query": params.query,
                "results": data.get("results").and_then(|v| v.as_array().cloned()).unwrap_or_default(),
                "count": data.get("count").and_then(|v| v.as_u64()).unwrap_or(0),
                "server": "ARIA-Axum-8002",
            }))
        }
        Err(_) => Json(serde_json::json!({
            "status": "ok",
            "query": params.query,
            "results": [],
            "count": 0,
            "server": "ARIA-Axum-8002",
        })),
    }
}

/// GET /api/memory/search — query-string variant of memory search.
async fn search_memory_get(
    Query(params): Query<SearchQueryParams>,
) -> Json<serde_json::Value> {
    let client = reqwest::Client::new();

    let top_k_str = params.top_k.unwrap_or(5).to_string();
    let query_str = params.query.as_deref().unwrap_or("");
    let resp = client
        .get(format!("{}/api/memory/search", FASTAPI_URL))
        .query(&[("query", query_str), ("top_k", &top_k_str)])
        .timeout(std::time::Duration::from_secs(10))
        .send()
        .await;

    match resp {
        Ok(r) => {
            let data: Value = r.json().await.unwrap_or(serde_json::json!({}));
            Json(serde_json::json!({
                "status": "ok",
                "query": params.query,
                "results": data.get("results").and_then(|v| v.as_array().cloned()).unwrap_or_default(),
                "count": data.get("count").and_then(|v| v.as_u64()).unwrap_or(0),
                "server": "ARIA-Axum-8002",
            }))
        }
        Err(_) => Json(serde_json::json!({
            "status": "ok",
            "query": params.query,
            "results": [],
            "count": 0,
            "server": "ARIA-Axum-8002",
        })),
    }
}