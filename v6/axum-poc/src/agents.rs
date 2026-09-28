//! Agent swarm routes: status, execute, research, harness.
//! Phase L.4: Real agent registry with SharedState.

use axum::{
    routing::{get, post},
    Router,
    Extension,
    Json,
};
use serde::Serialize;
use serde_json::json;
use std::sync::Arc;
use tokio::sync::Mutex;

use crate::state::SharedState;

#[derive(Serialize)]
struct SwarmStatusResponse {
    name: String,
    agent_count: usize,
    agents: Vec<AgentInfo>,
}

#[derive(Serialize, Clone)]
struct AgentInfo {
    name: String,
    role: String,
    status: String,
    task_count: u64,
    error_count: u64,
}

pub fn router() -> Router<()> {
    Router::new()
        .route("/api/agents/status", get(swarm_status))
        .route("/api/agents", get(list_agents))
        .route("/api/agents/execute", post(execute_agent))
        .route("/api/agents/research", post(research_task))
        .route("/api/agents/research/batch", post(research_batch))
        .route("/api/agents/harness/skills", get(harness_skills))
        .route("/api/agents/geospatial/status", get(geospatial_status))
        .route("/api/agents/voice/process", post(voice_process))
}

async fn swarm_status(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
) -> Json<SwarmStatusResponse> {
    let state = state.lock().await;
    let daemon_agents = state.daemon_agents.lock().await;
    
    let mut agents = vec![
        AgentInfo { name: "CodeAnalyzer".into(), role: "Code analysis".into(), status: "idle".into(), task_count: 0, error_count: 0 },
        AgentInfo { name: "DocsWriter".into(), role: "Documentation".into(), status: "idle".into(), task_count: 0, error_count: 0 },
        AgentInfo { name: "Tester".into(), role: "Testing".into(), status: "idle".into(), task_count: 0, error_count: 0 },
        AgentInfo { name: "ResearchAgent".into(), role: "Research".into(), status: "idle".into(), task_count: 0, error_count: 0 },
    ];
    
    // Add daemon agents from USB-ARIA
    for (id, info) in daemon_agents.iter() {
        agents.push(AgentInfo {
            name: id.clone(),
            role: "USB-ARIA Daemon".into(),
            status: info.status.clone(),
            task_count: 0,
            error_count: 0,
        });
    }
    
    Json(SwarmStatusResponse {
        name: "ARIA-Swarm".into(),
        agent_count: agents.len(),
        agents,
    })
}

async fn list_agents() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "agents": ["CodeAnalyzer", "DocsWriter", "Tester", "ResearchAgent"],
        "server": "ARIA-Axum-8002",
    }))
}

async fn execute_agent(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<serde_json::Value>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    state.increment_requests().await;
    
    let agent = req.get("agent").and_then(|v| v.as_str()).unwrap_or("unknown");
    let task = req.get("task").and_then(|v| v.as_str()).unwrap_or("");
    
    Json(json!({
        "status": "ok",
        "agent": agent,
        "task": task,
        "result": "Executed via Axum backend",
        "server": "ARIA-Axum-8002",
    }))
}

async fn research_task(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<serde_json::Value>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    state.increment_requests().await;
    
    let query = req.get("query").and_then(|v| v.as_str()).unwrap_or("");
    
    Json(json!({
        "status": "ok",
        "query": query,
        "results": [],
        "server": "ARIA-Axum-8002",
    }))
}

async fn research_batch(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<serde_json::Value>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    state.increment_requests().await;
    
    let queries = req.get("queries").and_then(|v| v.as_array()).map(|a| a.len()).unwrap_or(0);
    
    Json(json!({
        "status": "ok",
        "queries_processed": queries,
        "results": [],
        "server": "ARIA-Axum-8002",
    }))
}

async fn harness_skills() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "skills": ["chat", "system", "memory", "voice", "vision", "daemon", "social", "github", "learning", "evolution"],
        "server": "ARIA-Axum-8002",
    }))
}

async fn geospatial_status() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "layers": ["traffic", "fleet", "satellite", "infrastructure"],
        "agents_online": 4,
        "server": "ARIA-Axum-8002",
    }))
}

async fn voice_process(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<serde_json::Value>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    state.increment_requests().await;
    
    let text = req.get("text").and_then(|v| v.as_str()).unwrap_or("");
    
    Json(json!({
        "status": "ok",
        "text": text,
        "processed": true,
        "server": "ARIA-Axum-8002",
    }))
}