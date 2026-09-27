//! Agent swarm routes: status, execute, research, harness.
use axum::{routing::get, Router, Json};
use serde::Serialize;

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
}

async fn swarm_status() -> Json<SwarmStatusResponse> {
    Json(SwarmStatusResponse {
        name: "ARIA-Swarm".into(),
        agent_count: 4,
        agents: vec![
            AgentInfo { name: "CodeAnalyzer".into(), role: "Code analysis".into(), status: "idle".into(), task_count: 0, error_count: 0 },
            AgentInfo { name: "DocsWriter".into(), role: "Documentation".into(), status: "idle".into(), task_count: 0, error_count: 0 },
            AgentInfo { name: "Tester".into(), role: "Testing".into(), status: "idle".into(), task_count: 0, error_count: 0 },
            AgentInfo { name: "ResearchAgent".into(), role: "Research".into(), status: "idle".into(), task_count: 0, error_count: 0 },
        ],
    })
}

async fn list_agents() -> &'static str { "agents placeholder" }
async fn execute_agent() -> &'static str { "execute placeholder" }
async fn research_task() -> &'static str { "research placeholder" }
async fn research_batch() -> &'static str { "research batch placeholder" }
async fn harness_skills() -> &'static str { "harness skills placeholder" }