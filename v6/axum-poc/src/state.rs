//! Shared application state for ARIA Axum backend.
//! Phase L.4: SQLite-backed state with Arc<Mutex> for thread safety.

use axum::{
    extract::ws::{WebSocket, WebSocketUpgrade, Message},
    response::Response,
};
use futures::StreamExt;
use std::str::FromStr;
use std::sync::Arc;
use std::time::Duration;
use sqlx::sqlite::{SqliteConnectOptions, SqlitePoolOptions};
use sqlx::SqlitePool;
use tokio::sync::Mutex;
use serde_json::json;

/// WebSocket upgrade handler — accepts Socket.io-compatible connections.
pub async fn websocket_handler(ws: WebSocketUpgrade) -> Response {
    ws.on_upgrade(handle_socket)
}

async fn handle_socket(mut socket: WebSocket) {
    println!("🔌 WebSocket client connected");
    
    // Send welcome message
    let welcome = json!({
        "type": "connected",
        "message": "ARIA Axum WebSocket ready",
        "agents": ["CodeAnalyzer", "DocsWriter", "Tester", "ResearchAgent"],
    });
    
    if socket.send(Message::Text(welcome.to_string().into())).await.is_ok() {
        println!("   → Welcome sent");
    }
    
    // Echo loop
    while let Some(msg) = socket.next().await {
        match msg {
            Ok(Message::Text(text)) => {
                println!("   ← Received: {}", text.chars().take(80).collect::<String>());
                
                // Echo back with ARIA prefix
                let echo = json!({
                    "type": "echo",
                    "original": text.as_str(),
                    "server": "ARIA-Axum-8002",
                });
                
                if socket.send(Message::Text(echo.to_string().into())).await.is_err() {
                    break;
                }
            }
            Ok(Message::Binary(_)) => {
                let ack = json!({ "type": "ack", "status": "binary_received" });
                let _ = socket.send(Message::Text(ack.to_string().into())).await;
            }
            Ok(Message::Ping(data)) => {
                if socket.send(Message::Pong(data)).await.is_err() {
                    break;
                }
            }
            Ok(Message::Pong(_)) => {}
            Ok(Message::Close(_)) => {
                println!("   WebSocket client disconnected");
                break;
            }
            Err(e) => {
                eprintln!("   WebSocket error: {}", e);
                break;
            }
        }
    }
}

/// Build a lazy SQLite pool for `path`.
/// Connections are established on first use; short busy/acquire timeouts keep
/// route latency well under 2s even if another process holds the write lock.
/// `None` signals routes to emit fallback JSON.
pub fn open_pool(path: &str) -> Option<SqlitePool> {
    if path.starts_with("memory:") {
        return None;
    }
    let url = format!("sqlite://{}?mode=rwc", path.replace('\\', "/"));

    let connect_opts = match SqliteConnectOptions::from_str(&url) {
        Ok(o) => o
            .create_if_missing(true)
            .busy_timeout(Duration::from_millis(800)),
        Err(e) => {
            eprintln!("   SQLite URL error: {}", e);
            return None;
        }
    };

    let pool = SqlitePoolOptions::new()
        .max_connections(4)
        .min_connections(0)
        .acquire_timeout(Duration::from_millis(800))
        .idle_timeout(Duration::from_secs(60))
        .max_lifetime(Duration::from_secs(300))
        .connect_lazy_with(connect_opts);

    Some(pool)
}

/// Shared state struct for the entire application.
#[derive(Clone)]
pub struct SharedState {
    pub db_path: String,
    /// Direct SQLite pool — replaces the FastAPI memory proxy.
    /// `None` when the pool could not be created (no runtime / invalid path);
    /// routes must degrade to fallback JSON in that case.
    pub db: Option<SqlitePool>,
    pub start_time: std::time::Instant,
    pub request_count: Arc<Mutex<u64>>,
    pub chat_count: Arc<Mutex<u64>>,
    pub daemon_agents: Arc<Mutex<std::collections::HashMap<String, AgentInfo>>>,
    pub task_queue: Arc<Mutex<std::collections::VecDeque<serde_json::Value>>>,
    pub task_results: Arc<Mutex<Vec<serde_json::Value>>>,
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct AgentInfo {
    pub agent_id: String,
    pub last_heartbeat: u64,
    pub status: String,
    pub current_task: Option<String>,
}

impl SharedState {
    pub fn new(db_path: &str) -> Self {
        let db = open_pool(db_path);
        match &db {
            Some(_) => println!("   SQLite pool ready: {}", db_path),
            None => eprintln!("   ⚠️  SQLite pool unavailable: {}", db_path),
        }
        SharedState {
            db_path: db_path.to_string(),
            db,
            start_time: std::time::Instant::now(),
            request_count: Arc::new(Mutex::new(0)),
            chat_count: Arc::new(Mutex::new(0)),
            daemon_agents: Arc::new(Mutex::new(std::collections::HashMap::new())),
            task_queue: Arc::new(Mutex::new(std::collections::VecDeque::new())),
            task_results: Arc::new(Mutex::new(Vec::new())),
        }
    }
    
    pub fn uptime_ms(&self) -> u64 {
        self.start_time.elapsed().as_millis() as u64
    }
    
    pub async fn increment_requests(&self) {
        let mut count = self.request_count.lock().await;
        *count += 1;
    }
    
    pub async fn increment_chats(&self) {
        let mut count = self.chat_count.lock().await;
        *count += 1;
    }

    /// Clone the pool handle so callers can release the state lock before querying.
    pub fn pool(&self) -> Option<SqlitePool> {
        self.db.clone()
    }
}