//! Memory routes: direct SQLite access against aura.db.
//! Phase M.1: no FastAPI proxy — the Axum backend owns the database itself.
//!
//! Primary table: `semantic_memory(id, content, kind, vector_json, timestamp)`.
//! Every handler degrades to the same JSON shape the frontend already expects
//! when the pool is unavailable, a table is missing, or the DB is locked.

use axum::{
    routing::{get, post},
    Router,
    Extension,
    Json,
    extract::Query,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sqlx::{Row, SqlitePool};
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::Mutex;

use crate::state::SharedState;

/// Hard ceiling for any single DB call so routes answer well under 2s.
const DB_TIMEOUT_MS: u64 = 1200;
const MEMORY_TABLE: &str = "semantic_memory";
const DEFAULT_TOP_K: usize = 5;
const MAX_TOP_K: usize = 100;

type AppState = Arc<Mutex<SharedState>>;

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

pub fn router() -> Router {
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

// ── helpers ────────────────────────────────────────────────────────────────

/// Clone the pool out of the state lock so queries never hold the mutex.
async fn pool_of(state: &AppState) -> Option<SqlitePool> {
    let guard = state.lock().await;
    guard.pool()
}

fn clamp_top_k(top_k: Option<usize>) -> i64 {
    let k = top_k.unwrap_or(DEFAULT_TOP_K).clamp(1, MAX_TOP_K);
    k as i64
}

/// Escape LIKE wildcards so a user query is matched literally.
fn like_pattern(query: &str) -> String {
    let escaped: String = query
        .replace('\\', "\\\\")
        .replace('%', "\\%")
        .replace('_', "\\_");
    format!("%{}%", escaped)
}

/// Current timestamp in the same format the Python/SQLAlchemy side writes.
fn now_str() -> String {
    chrono::Utc::now()
        .naive_utc()
        .format("%Y-%m-%d %H:%M:%S%.6f")
        .to_string()
}

/// Run a DB future under a hard timeout so no route can hang.
async fn bounded<F, T>(fut: F) -> Result<T, String>
where
    F: std::future::Future<Output = Result<T, sqlx::Error>>,
{
    match tokio::time::timeout(Duration::from_millis(DB_TIMEOUT_MS), fut).await {
        Ok(Ok(v)) => Ok(v),
        Ok(Err(e)) => Err(e.to_string()),
        Err(_) => Err("db_timeout".to_string()),
    }
}

fn row_to_entry(row: &sqlx::sqlite::SqliteRow) -> Value {
    let id: i64 = row.try_get::<i64, _>("id").unwrap_or(0);
    let content: Option<String> = row.try_get::<Option<String>, _>("content").unwrap_or(None);
    let kind: Option<String> = row.try_get::<Option<String>, _>("kind").unwrap_or(None);
    let vector_json: Option<String> =
        row.try_get::<Option<String>, _>("vector_json").unwrap_or(None);
    let timestamp: Option<String> = row.try_get::<Option<String>, _>("timestamp").unwrap_or(None);

    let metadata = vector_json
        .as_deref()
        .and_then(|v| serde_json::from_str::<Value>(v).ok())
        .unwrap_or(Value::Null);
    let has_vector = vector_json
        .map(|v| !v.is_empty() && v != "[]")
        .unwrap_or(false);

    json!({
        "id": id,
        "memory_id": format!("mem_{}", id),
        "content": content.unwrap_or_default(),
        "kind": kind.unwrap_or_else(|| "memory".to_string()),
        "metadata": metadata,
        "has_vector": has_vector,
        "score": 1.0,
        "timestamp": timestamp.unwrap_or_default(),
    })
}

const SELECT_COLS: &str = "id, content, kind, vector_json, timestamp";

/// Shared search implementation used by POST /search, GET /search, /recall and RAG.
async fn query_memory(pool: &SqlitePool, query: &str, top_k: i64) -> Result<Vec<Value>, String> {
    let trimmed = query.trim();

    let (sql, pattern) = if trimmed.is_empty() {
        (
            format!(
                "SELECT {} FROM {} ORDER BY id DESC LIMIT ?1",
                SELECT_COLS, MEMORY_TABLE
            ),
            None,
        )
    } else {
        (
            format!(
                "SELECT {} FROM {} \
                 WHERE content LIKE ?1 ESCAPE '\\' OR kind LIKE ?1 ESCAPE '\\' \
                    OR IFNULL(vector_json, '') LIKE ?1 ESCAPE '\\' \
                 ORDER BY id DESC LIMIT ?2",
                SELECT_COLS, MEMORY_TABLE
            ),
            Some(like_pattern(trimmed)),
        )
    };

    let rows = match pattern {
        Some(p) => bounded(sqlx::query(&sql).bind(p).bind(top_k).fetch_all(pool)).await?,
        None => bounded(sqlx::query(&sql).bind(top_k).fetch_all(pool)).await?,
    };
    Ok(rows.iter().map(row_to_entry).collect())
}

// ── handlers ───────────────────────────────────────────────────────────────

/// POST /api/memory/store — persist an entry in `semantic_memory`.
async fn store_memory(
    Extension(state): Extension<AppState>,
    Json(req): Json<StoreRequest>,
) -> Json<StoreResponse> {
    let start = std::time::Instant::now();

    let Some(pool) = pool_of(&state).await else {
        return Json(StoreResponse {
            status: "error_no_backend".to_string(),
            memory_id: format!("mem_{}", start.elapsed().as_millis()),
            latency_ms: start.elapsed().as_millis() as u64,
        });
    };

    let kind = sanitize_kind(&req.query);
    let metadata = req
        .metadata
        .map(|m| m.to_string())
        .unwrap_or_else(|| "{}".to_string());
    let sql = format!(
        "INSERT INTO {} (content, kind, vector_json, timestamp) VALUES (?1, ?2, ?3, ?4)",
        MEMORY_TABLE
    );

    let result = bounded(
        sqlx::query(&sql)
            .bind(&req.content)
            .bind(&kind)
            .bind(&metadata)
            .bind(now_str())
            .execute(&pool),
    )
    .await;

    let latency_ms = start.elapsed().as_millis() as u64;

    match result {
        Ok(res) => Json(StoreResponse {
            status: "ok".to_string(),
            memory_id: format!("mem_{}", res.last_insert_rowid()),
            latency_ms,
        }),
        Err(e) => {
            eprintln!("⚠️  memory store failed: {}", e);
            Json(StoreResponse {
                status: "error_db".to_string(),
                memory_id: format!("mem_{}", start.elapsed().as_millis()),
                latency_ms,
            })
        }
    }
}

async fn search_memory(
    Extension(state): Extension<AppState>,
    Json(req): Json<SearchRequest>,
) -> Json<SearchResponse> {
    let top_k = clamp_top_k(req.top_k);

    let results = match pool_of(&state).await {
        Some(pool) => query_memory(&pool, &req.query, top_k)
            .await
            .unwrap_or_else(|e| {
                eprintln!("⚠️  memory search failed: {}", e);
                vec![]
            }),
        None => vec![],
    };

    Json(SearchResponse {
        count: results.len(),
        query: req.query,
        results,
    })
}

async fn recent_memory(Extension(state): Extension<AppState>) -> Json<Value> {
    let Some(pool) = pool_of(&state).await else {
        return Json(json!({ "recent": [], "results": [], "count": 0, "error": "db_unavailable" }));
    };

    match query_memory(&pool, "", DEFAULT_TOP_K as i64).await {
        Ok(results) => {
            let count = results.len();
            Json(json!({
                "recent": results.clone(),
                "results": results,
                "count": count,
                "server": "ARIA-Axum-8002",
            }))
        }
        Err(e) => {
            eprintln!("⚠️  memory recent failed: {}", e);
            Json(json!({ "recent": [], "results": [], "count": 0, "error": "db_unavailable" }))
        }
    }
}

async fn memory_stats(Extension(state): Extension<AppState>) -> Json<Value> {
    let Some(pool) = pool_of(&state).await else {
        return Json(json!({
            "total_memories": 0,
            "total_vectors": 0,
            "by_kind": {},
            "error": "db_unavailable",
        }));
    };

    let total = count_rows(&pool, MEMORY_TABLE).await;
    let vectors = bounded(
        sqlx::query(&format!(
            "SELECT COUNT(*) AS c FROM {} WHERE vector_json IS NOT NULL AND vector_json != '[]'",
            MEMORY_TABLE
        ))
        .fetch_one(&pool),
    )
    .await
    .ok()
    .map(|r| r.try_get::<i64, _>("c").unwrap_or(0))
    .unwrap_or(0);

    let mut by_kind = serde_json::Map::new();
    if let Ok(rows) = bounded(
        sqlx::query(&format!(
            "SELECT IFNULL(kind, 'memory') AS k, COUNT(*) AS c FROM {} GROUP BY k",
            MEMORY_TABLE
        ))
        .fetch_all(&pool),
    )
    .await
    {
        for row in rows {
            let k: String = row
                .try_get::<String, _>("k")
                .unwrap_or_else(|_| "memory".into());
            let c: i64 = row.try_get::<i64, _>("c").unwrap_or(0);
            by_kind.insert(k, json!(c));
        }
    }

    let mut stats = json!({
        "total_memories": total,
        "total_vectors": vectors,
        "by_kind": Value::Object(by_kind),
        "chat_history": count_rows(&pool, "chat_history").await,
        "messages": count_rows(&pool, "messages").await,
        "server": "ARIA-Axum-8002",
    });

    if let Ok(Some(row)) = bounded(
        sqlx::query(&format!("SELECT MAX(timestamp) AS ts FROM {}", MEMORY_TABLE))
            .fetch_optional(&pool),
    )
    .await
    {
        if let Ok(Some(ts)) = row.try_get::<Option<String>, _>("ts") {
            stats["last_entry"] = json!(ts);
        }
    }

    Json(stats)
}

async fn vector_add(
    Extension(state): Extension<AppState>,
    Json(req): Json<Value>,
) -> Json<Value> {
    let start = std::time::Instant::now();

    let content = req
        .get("content")
        .and_then(|v| v.as_str())
        .or_else(|| req.get("text").and_then(|v| v.as_str()))
        .unwrap_or("")
        .to_string();
    let kind = req
        .get("kind")
        .or_else(|| req.get("collection"))
        .and_then(|v| v.as_str())
        .unwrap_or("vector")
        .to_string();
    let embedding = req
        .get("vector")
        .or_else(|| req.get("embedding"))
        .cloned()
        .unwrap_or_else(|| json!([]));

    let Some(pool) = pool_of(&state).await else {
        return Json(json!({ "status": "error", "error": "db_unavailable" }));
    };

    let sql = format!(
        "INSERT INTO {} (content, kind, vector_json, timestamp) VALUES (?1, ?2, ?3, ?4)",
        MEMORY_TABLE
    );

    match bounded(
        sqlx::query(&sql)
            .bind(&content)
            .bind(&kind)
            .bind(embedding.to_string())
            .bind(now_str())
            .execute(&pool),
    )
    .await
    {
        Ok(res) => {
            let id = res.last_insert_rowid();
            let dimensions = embedding.as_array().map(|a| a.len()).unwrap_or(0);
            Json(json!({
                "status": "ok",
                "vector_id": id,
                "id": id,
                "dimensions": dimensions,
                "latency_ms": start.elapsed().as_millis() as u64,
                "server": "ARIA-Axum-8002",
            }))
        }
        Err(e) => {
            eprintln!("⚠️  vector add failed: {}", e);
            Json(json!({ "status": "error", "error": "db_unavailable" }))
        }
    }
}

async fn vector_search(
    Extension(state): Extension<AppState>,
    Json(req): Json<Value>,
) -> Json<Value> {
    let query = req
        .get("query")
        .or_else(|| req.get("text"))
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    let top_k = clamp_top_k(req.get("top_k").and_then(|v| v.as_u64()).map(|v| v as usize));

    let Some(pool) = pool_of(&state).await else {
        return Json(json!({ "results": [], "count": 0, "error": "db_unavailable" }));
    };

    match query_memory(&pool, &query, top_k).await {
        Ok(results) => {
            let count = results.len();
            Json(json!({
                "status": "ok",
                "query": query,
                "results": results,
                "count": count,
                "server": "ARIA-Axum-8002",
            }))
        }
        Err(_) => Json(json!({ "results": [], "count": 0, "error": "db_unavailable" })),
    }
}

async fn vector_rag(
    Extension(state): Extension<AppState>,
    Query(params): Query<RecallParams>,
) -> Json<Value> {
    let query = params.query.clone().unwrap_or_default();
    let top_k = clamp_top_k(params.top_k);

    let Some(pool) = pool_of(&state).await else {
        return Json(json!({
            "status": "ok",
            "context": "",
            "chunks": [],
            "sources": [],
            "error": "db_unavailable",
        }));
    };

    match query_memory(&pool, &query, top_k).await {
        Ok(results) => {
            let context = results
                .iter()
                .filter_map(|r| r.get("content").and_then(|v| v.as_str()))
                .collect::<Vec<_>>()
                .join("\n---\n");
            let sources: Vec<Value> = results
                .iter()
                .map(|r| {
                    json!({
                        "id": r.get("id").cloned().unwrap_or(Value::Null),
                        "kind": r.get("kind").cloned().unwrap_or(Value::Null),
                        "timestamp": r.get("timestamp").cloned().unwrap_or(Value::Null),
                    })
                })
                .collect();
            let count = results.len();
            Json(json!({
                "status": "ok",
                "query": query,
                "context": context,
                "chunks": results,
                "sources": sources,
                "count": count,
                "server": "ARIA-Axum-8002",
            }))
        }
        Err(_) => Json(json!({
            "status": "ok",
            "context": "",
            "chunks": [],
            "sources": [],
            "count": 0,
            "error": "db_unavailable",
        })),
    }
}

async fn vector_collections(Extension(state): Extension<AppState>) -> Json<Value> {
    let Some(pool) = pool_of(&state).await else {
        return Json(json!({ "collections": [], "error": "db_unavailable" }));
    };

    let sql = format!(
        "SELECT IFNULL(kind, 'memory') AS k, COUNT(*) AS c FROM {} GROUP BY k ORDER BY c DESC",
        MEMORY_TABLE
    );

    match bounded(sqlx::query(&sql).fetch_all(&pool)).await {
        Ok(rows) => {
            let collections: Vec<Value> = rows
                .iter()
                .map(|row| {
                    let k: String = row
                        .try_get::<String, _>("k")
                        .unwrap_or_else(|_| "memory".into());
                    let c: i64 = row.try_get::<i64, _>("c").unwrap_or(0);
                    json!({ "name": k, "kind": k, "count": c })
                })
                .collect();
            let count = collections.len();
            Json(json!({
                "status": "ok",
                "collections": collections,
                "count": count,
                "total_memories": count_rows(&pool, MEMORY_TABLE).await,
                "server": "ARIA-Axum-8002",
            }))
        }
        Err(_) => Json(json!({ "collections": [], "error": "db_unavailable" })),
    }
}

/// GET /api/memory/search — query-string variant of memory search.
async fn search_memory_get(
    Extension(state): Extension<AppState>,
    Query(params): Query<SearchQueryParams>,
) -> Json<Value> {
    let query = params.query.unwrap_or_default();
    let top_k = clamp_top_k(params.top_k);

    let results = match pool_of(&state).await {
        Some(pool) => query_memory(&pool, &query, top_k)
            .await
            .unwrap_or_default(),
        None => vec![],
    };
    let count = results.len();

    Json(json!({
        "status": "ok",
        "query": query,
        "results": results,
        "count": count,
        "server": "ARIA-Axum-8002",
    }))
}

// ── small utilities ────────────────────────────────────────────────────────

async fn count_rows(pool: &SqlitePool, table: &str) -> i64 {
    let sql = format!("SELECT COUNT(*) AS c FROM {}", table);
    bounded(sqlx::query(&sql).fetch_one(pool))
        .await
        .ok()
        .map(|r| r.try_get::<i64, _>("c").unwrap_or(0))
        .unwrap_or(0)
}

/// `kind` is a VARCHAR(32) column — keep it short and printable.
fn sanitize_kind(raw: &str) -> String {
    let cleaned: String = raw
        .chars()
        .filter(|c| c.is_alphanumeric() || *c == '_' || *c == '-' || *c == ' ')
        .take(32)
        .collect();
    if cleaned.trim().is_empty() {
        "memory".to_string()
    } else {
        cleaned
    }
}
