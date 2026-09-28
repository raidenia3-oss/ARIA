//! Memory routes: store, retrieve, sessions, vector, longterm.
use axum::{routing::{get, post}, Router, Json};
use serde::{Deserialize, Serialize};

#[derive(Deserialize)]
struct StoreRequest { query: String, response: String }

#[derive(Serialize)]
struct StoreResponse { status: String, memory_id: String }

pub fn router() -> Router<()> {
    Router::new()
        .route("/api/memory/store", post(store_memory))
        .route("/api/memory/retrieve", post(retrieve_memory))
        .route("/api/memory/recent", get(recent_memory))
        .route("/api/memory/search", post(search_memory))
        .route("/api/memory/longmemory/health", get(lm_health))
        .route("/api/memory/longmemory/store", post(lm_store))
        .route("/api/memory/longmemory/retrieve", post(lm_retrieve))
        .route("/api/memory/longmemory/sessions", get(lm_sessions))
        .route("/api/memory/vector/store", post(vector_store))
        .route("/api/memory/vector/search", post(vector_search))
}

async fn store_memory(Json(req): Json<StoreRequest>) -> Json<StoreResponse> {
    Json(StoreResponse { status: "ok".into(), memory_id: "mem_001".into() })
}

async fn retrieve_memory() -> &'static str { "retrieve placeholder" }
async fn recent_memory() -> &'static str { "recent placeholder" }
async fn search_memory() -> &'static str { "search placeholder" }
async fn lm_health() -> &'static str { "lm health placeholder" }
async fn lm_store() -> &'static str { "lm store placeholder" }
async fn lm_retrieve() -> &'static str { "lm retrieve placeholder" }
async fn lm_sessions() -> &'static str { "lm sessions placeholder" }
async fn vector_store() -> &'static str { "vector store placeholder" }
async fn vector_search() -> &'static str { "vector search placeholder" }