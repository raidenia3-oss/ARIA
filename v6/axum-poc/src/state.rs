//! Shared application state for ARIA Axum backend.
//! Phase L.4: SQLite-backed state with Arc<Mutex> for thread safety.

use axum::{
    extract::ws::{WebSocket, WebSocketUpgrade, Message},
    response::Response,
};
use futures::StreamExt;
use std::sync::Arc;
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

/// Shared state struct for the entire application.
#[derive(Clone)]
pub struct SharedState {
    pub db_path: String,
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
        SharedState {
            db_path: db_path.to_string(),
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
}