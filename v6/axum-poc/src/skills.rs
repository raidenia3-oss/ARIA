//! Skills routes: list, run, scan, search.
use axum::{routing::get, Router, Json};
use serde::Serialize;

#[derive(Serialize)]
struct SkillsListResponse { skills: Vec<serde_json::Value>, count: usize }

pub fn router() -> Router<()> {
    Router::new()
        .route("/api/skills", get(list_skills))
        .route("/api/skills/scan", get(scan_skills))
        .route("/api/skills/search", get(search_skills))
}

async fn list_skills() -> Json<SkillsListResponse> {
    Json(SkillsListResponse { skills: vec![], count: 0 })
}

async fn scan_skills() -> &'static str { "scan placeholder" }
async fn search_skills() -> &'static str { "search placeholder" }