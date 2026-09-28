//! Skills routes: list, run, scan, search.
//! Phase L.4: Returns structured JSON responses.

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
struct SkillsListResponse {
    skills: Vec<serde_json::Value>,
    count: usize,
}

pub fn router() -> Router<()> {
    Router::new()
        .route("/api/skills", get(list_skills))
        .route("/api/skills/scan", get(scan_skills))
        .route("/api/skills/search", get(search_skills))
        .route("/api/skills/run", post(run_skill))
}

async fn list_skills() -> Json<SkillsListResponse> {
    let skills = vec![
        json!({"name": "chat", "description": "AI chat with Ollama", "status": "active"}),
        json!({"name": "system", "description": "System control and monitoring", "status": "active"}),
        json!({"name": "memory", "description": "Memory storage and retrieval", "status": "active"}),
        json!({"name": "voice", "description": "STT/TTS voice processing", "status": "active"}),
        json!({"name": "vision", "description": "Screen capture and analysis", "status": "active"}),
        json!({"name": "daemon", "description": "USB-ARIA daemon coordination", "status": "active"}),
        json!({"name": "social", "description": "Social media research", "status": "active"}),
        json!({"name": "github", "description": "GitHub automation", "status": "active"}),
        json!({"name": "learning", "description": "Compound learning system", "status": "active"}),
        json!({"name": "evolution", "description": "Skill evolution engine", "status": "active"}),
    ];
    
    Json(SkillsListResponse {
        skills,
        count: 10,
    })
}

async fn scan_skills() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "skills_found": 10,
        "server": "ARIA-Axum-8002",
    }))
}

async fn search_skills() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "results": [],
        "server": "ARIA-Axum-8002",
    }))
}

async fn run_skill(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<serde_json::Value>,
) -> Json<serde_json::Value> {
    let skill_name = req.get("skill").and_then(|v| v.as_str()).unwrap_or("unknown");
    let state = state.lock().await;
    state.increment_requests().await;
    
    Json(json!({
        "status": "ok",
        "skill": skill_name,
        "result": "Executed via Axum backend",
        "server": "ARIA-Axum-8002",
    }))
}