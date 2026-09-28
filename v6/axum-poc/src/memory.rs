//! Memory routes: store, retrieve, search using SQLite (aura.db).
use axum::{routing::{get, post}, Router, Json};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::sync::OnceLock;
use std::sync::Mutex;
use rusqlite::Connection;

static DB_PATH: &str = "C:\\Users\\User\\Downloads\\AURA\\aura.db";
static DB_CONN: OnceLock<Mutex<Connection>> = OnceLock::new();

fn get_db() -> &'static Mutex<Connection> {
    DB_CONN.get_or_init(|| {
        let conn = Connection::open(DB_PATH).expect("Failed to open aura.db");
        Mutex::new(conn)
    })
}

#[derive(Deserialize)]
struct StoreRequest {
    query: String,
    response: String,
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

#[derive(Serialize)]
struct StatsResponse {
    total_memories: usize,
    total_tokens: usize,
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
    let db = get_db();
    
    let result = {
        let mut conn = db.lock().unwrap();
        conn.execute(
            "CREATE TABLE IF NOT EXISTS memory (id INTEGER PRIMARY KEY, query TEXT, response TEXT, metadata TEXT, created_at TEXT DEFAULT (datetime('now'))",
            [],
        ).ok();
        
        conn.execute(
            "INSERT INTO memory (query, response, metadata) VALUES (?1, ?2, ?3)",
            (&req.query, &req.response, &req.metadata.to_string()),
        ).ok()
    };

    let memory_id = format!("mem_{}", start.elapsed().as_millis());
    
    Json(StoreResponse {
        status: if result.is_some() { "success" } else { "error" }.to_string(),
        memory_id,
        latency_ms: start.elapsed().as_millis() as u64,
    })
}

async fn search_memory(Json(req): Json<SearchRequest>) -> Json<SearchResponse> {
    let db = get_db();
    let top_k = req.top_k.unwrap_or(5);

    let results: Vec<Value> = {
        let mut conn = db.lock().unwrap();
        
        if conn.execute("CREATE TABLE IF NOT EXISTS memory (id INTEGER PRIMARY KEY, query TEXT, response TEXT, metadata TEXT, created_at TEXT DEFAULT (datetime('now'))", []).is_ok() {
            let mut stmt = conn.prepare("SELECT query, response FROM memory WHERE query LIKE ?1 LIMIT ?2").unwrap();
            
            stmt.query_row([format!("%{}%", req.query), top_k], |row| {
                Ok((row.get::<_, String>(0), row.get::<_, String>(1)))
            }).ok()
            .map(|(q, r)| vec![serde_json::json!({"query": q, "response": r})])
            .unwrap_or_default()
        } else {
            vec![]
        }
    };

    Json(SearchResponse {
        query: req.query,
        count: results.len(),
        results,
    })
}

async fn recent_memory() -> Json<serde_json::Value> {
    let db = get_db();
    
    let memories: Vec<String> = {
        let mut conn = db.lock().unwrap();
        
        if conn.execute("CREATE TABLE IF NOT EXISTS memory (id INTEGER PRIMARY KEY, query TEXT, response TEXT, metadata TEXT, created_at TEXT DEFAULT (datetime('now'))", []).is_ok() {
            let mut stmt = conn.prepare("SELECT query FROM memory ORDER BY created_at DESC LIMIT 10").unwrap();
            
            stmt.query_map([], |row| {
                Ok(row.get::<_, String>(0))
            }).filter_map(|r| r.ok())
            .filter_map(|r| r.ok())
            .collect()
        } else {
            vec![]
        }
    };

    Json(serde_json::json!({ "recent": memories }))
}

async fn memory_stats() -> Json<StatsResponse> {
    let db = get_db();
    
    let (total, tokens) = {
        let mut conn = db.lock().unwrap();
        
        let create = conn.execute("CREATE TABLE IF NOT EXISTS memory (id INTEGER PRIMARY KEY, query TEXT, response TEXT, metadata TEXT, created_at TEXT DEFAULT (datetime('now'))", []);
        let total = conn.query_row("SELECT COUNT(*) FROM memory", [], |r| r.get::<_, i64>(0)).unwrap_or(0) as usize;
        let tokens = conn.query_row("SELECT COALESCE(SUM(LENGTH(query || response)), 0) FROM memory", [], |r| r.get::<_, i64>(0)).unwrap_or(0) as usize;
        
        (total, tokens)
    };

    Json(StatsResponse { total_memories: total, total_tokens: tokens })
}