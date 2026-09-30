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

/// One installable ARIA capability.
///
/// The catalog lives here rather than in [`crate::control`] so the skills route
/// and the control-plane route report the same list; when the two were written
/// separately they drifted, and the dashboard showed plugins the skills API did
/// not have.
#[derive(Debug, Clone, Copy)]
pub struct PluginDef {
    pub name: &'static str,
    pub description: &'static str,
    pub status: &'static str,
}

/// Every plugin ARIA ships, in display order.
pub const PLUGIN_CATALOG: &[PluginDef] = &[
    PluginDef { name: "chat", description: "AI chat with Ollama", status: "active" },
    PluginDef { name: "system", description: "System control and monitoring", status: "active" },
    PluginDef { name: "memory", description: "Memory storage and retrieval", status: "active" },
    PluginDef { name: "voice", description: "STT/TTS voice processing", status: "active" },
    PluginDef { name: "vision", description: "Screen capture and analysis", status: "active" },
    PluginDef { name: "daemon", description: "USB-ARIA daemon coordination", status: "active" },
    PluginDef { name: "social", description: "Social media research", status: "active" },
    PluginDef { name: "github", description: "GitHub automation", status: "active" },
    PluginDef { name: "learning", description: "Compound learning system", status: "active" },
    PluginDef { name: "evolution", description: "Skill evolution engine", status: "active" },
];

/// The plugin catalog as a slice.
pub fn plugin_catalog() -> &'static [PluginDef] {
    PLUGIN_CATALOG
}

pub fn router() -> Router<()> {
    Router::new()
        .route("/api/skills", get(list_skills))
        .route("/api/skills/scan", get(scan_skills))
        .route("/api/skills/search", get(search_skills))
        .route("/api/skills/run", post(run_skill))
        .route("/api/skills/progression", get(skills_progression))
        .route("/api/traffic", get(traffic))
}

async fn skills_progression() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "skills": [
            { "name": "chat", "category": "system", "enabled": true, "level": 3, "xp": 1250, "xp_max": 2000, "description": "AI chat with Ollama" },
            { "name": "system", "category": "system", "enabled": true, "level": 5, "xp": 3200, "xp_max": 5000, "description": "System control and monitoring" },
            { "name": "memory", "category": "brain", "enabled": true, "level": 2, "xp": 800, "xp_max": 1500, "description": "Memory storage and retrieval" },
            { "name": "voice", "category": "system", "enabled": true, "level": 4, "xp": 2100, "xp_max": 3000, "description": "STT/TTS voice processing" },
            { "name": "vision", "category": "system", "enabled": true, "level": 1, "xp": 300, "xp_max": 1000, "description": "Screen capture and analysis" },
            { "name": "daemon", "category": "integration", "enabled": true, "level": 2, "xp": 650, "xp_max": 1500, "description": "USB-ARIA daemon coordination" },
            { "name": "social", "category": "web", "enabled": false, "level": 0, "xp": 0, "xp_max": 500, "description": "Social media research" },
            { "name": "github", "category": "integration", "enabled": true, "level": 3, "xp": 1400, "xp_max": 2000, "description": "GitHub automation" },
            { "name": "learning", "category": "improvement", "enabled": true, "level": 2, "xp": 900, "xp_max": 1500, "description": "Compound learning system" },
            { "name": "evolution", "category": "improvement", "enabled": true, "level": 1, "xp": 400, "xp_max": 1000, "description": "Skill evolution engine" },
        ],
        "total_xp": 11200,
        "level": 23,
        "unlocked": 9,
        "server": "ARIA-Axum-8002",
    }))
}

async fn traffic() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "traffic": [
            { "lat": 34.05, "lng": -118.24, "intensity": 0.8 },
            { "lat": 34.10, "lng": -118.20, "intensity": 0.5 },
            { "lat": 34.20, "lng": -118.30, "intensity": 0.3 },
            { "lat": 33.80, "lng": -118.10, "intensity": 0.6 },
        ],
        "timestamp": chrono::Utc::now().to_rfc3339(),
        "server": "ARIA-Axum-8002",
    }))
}

async fn list_skills() -> Json<SkillsListResponse> {
    let skills: Vec<serde_json::Value> = plugin_catalog()
        .iter()
        .map(|plugin| {
            json!({
                "name": plugin.name,
                "description": plugin.description,
                "status": plugin.status,
            })
        })
        .collect();

    let count = skills.len();
    Json(SkillsListResponse { skills, count })
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