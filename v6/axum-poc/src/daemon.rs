//! Daemon routes: USB-ARIA coordination endpoints.
//! Phase L.4: USB-ARIA distributed autonomous infrastructure.
//! Uses SharedState for cross-module state sharing.

use axum::{
    extract::Json,
    routing::post,
    Router,
    Extension,
};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::sync::Mutex;
use std::time::{SystemTime, UNIX_EPOCH};

use crate::state::{SharedState, AgentInfo};

#[derive(Debug, Clone, Serialize, Deserialize)]
struct Task {
    id: String,
    task_type: String,
    payload: serde_json::Value,
    assigned_to: Option<String>,
    status: String,
    created_at: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct TaskResult {
    task_id: String,
    agent_id: String,
    status: String,
    output: serde_json::Value,
    executed_at: String,
}

#[derive(Deserialize)]
struct DaemonRequest {
    agent_id: Option<String>,
    action: Option<String>,
    status: Option<String>,
    task: Option<serde_json::Value>,
    result: Option<serde_json::Value>,
    pc_state: Option<serde_json::Value>,
}

#[derive(Serialize)]
struct PCStateResponse {
    active: bool,
    idle_seconds: u64,
    session_user: String,
    timestamp: u64,
}

#[derive(Serialize)]
struct TaskResponse {
    available: bool,
    task: Option<Task>,
    status: String,
}

#[derive(Serialize)]
struct HeartbeatResponse {
    status: String,
    timestamp: u64,
}

pub fn router() -> Router<()> {
    Router::new()
        .route("/api/pc/state", post(pc_state))
        .route("/api/daemon/task", post(daemon_task))
        .route("/api/daemon/result", post(daemon_result))
        .route("/api/daemon/heartbeat", post(daemon_heartbeat))
}

fn now_secs() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs()
}

async fn pc_state(
    Extension(_state): Extension<Arc<Mutex<SharedState>>>,
    Json(_req): Json<DaemonRequest>,
) -> Json<PCStateResponse> {
    let now = now_secs();
    
    Json(PCStateResponse {
        active: true,
        idle_seconds: 0,
        session_user: "ARIA-USB".to_string(),
        timestamp: now,
    })
}

async fn daemon_task(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<DaemonRequest>,
) -> Json<TaskResponse> {
    let mut state = state.lock().await;
    let now = now_secs();

    match req.action.as_deref() {
        Some("get_pending") => {
            let agent_id = req.agent_id.clone();
            let mut queue = state.task_queue.lock().await;
            
            let task_idx = queue.iter().position(|t| {
                t.get("status").and_then(|v| v.as_str()) == Some("pending") && 
                (t.get("assigned_to").is_none() || t.get("assigned_to").and_then(|v| v.as_str()) == agent_id.as_deref())
            });

            if let Some(idx) = task_idx {
                if let Some(task) = queue.get_mut(idx) {
                    if let Some(status) = task.get_mut("status") {
                        *status = serde_json::Value::String("assigned".to_string());
                    }
                    if let Some(assigned) = task.get_mut("assigned_to") {
                        *assigned = serde_json::Value::String(agent_id.clone().unwrap_or_default());
                    }
                }
                
                let task_data = queue.get(idx).unwrap().clone();
                
                Json(TaskResponse {
                    available: true,
                    task: Some(Task {
                        id: task_data.get("id").and_then(|v| v.as_str()).unwrap_or("unknown").to_string(),
                        task_type: task_data.get("task_type").and_then(|v| v.as_str()).unwrap_or("generic").to_string(),
                        payload: task_data.get("payload").cloned().unwrap_or(serde_json::json!({})),
                        assigned_to: task_data.get("assigned_to").and_then(|v| v.as_str().map(String::from)),
                        status: "assigned".to_string(),
                        created_at: now,
                    }),
                    status: "task_assigned".to_string(),
                })
            } else {
                Json(TaskResponse {
                    available: false,
                    task: None,
                    status: "no_tasks".to_string(),
                })
            }
        }
        Some("report_status") => {
            let agent_id = req.agent_id.clone().unwrap_or_else(|| "unknown".to_string());
            let agent_status = req.status.clone().unwrap_or_else(|| "idle".to_string());
            
            let mut registry = state.daemon_agents.lock().await;
            registry.insert(agent_id.clone(), AgentInfo {
                agent_id: agent_id.clone(),
                last_heartbeat: now,
                status: agent_status,
                current_task: None,
            });

            Json(TaskResponse {
                available: false,
                task: None,
                status: "status_reported".to_string(),
            })
        }
        _ => {
            Json(TaskResponse {
                available: false,
                task: None,
                status: "unknown_action".to_string(),
            })
        }
    }
}

async fn daemon_result(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<DaemonRequest>,
) -> Json<serde_json::Value> {
    let mut state = state.lock().await;
    if let (Some(agent_id), Some(result)) = (req.agent_id, req.result) {
        let task_result = TaskResult {
            task_id: result.get("task_id").and_then(|v| v.as_str()).unwrap_or("unknown").to_string(),
            agent_id,
            status: result.get("status").and_then(|v| v.as_str()).unwrap_or("unknown").to_string(),
            output: result.get("output").cloned().unwrap_or(serde_json::json!({})),
            executed_at: result.get("executed_at").and_then(|v| v.as_str()).unwrap_or("").to_string(),
        };

        let mut results = state.task_results.lock().await;
        results.push(serde_json::json!({
            "task_id": task_result.task_id,
            "agent_id": task_result.agent_id,
            "status": task_result.status,
            "output": task_result.output,
            "executed_at": task_result.executed_at,
        }));

        Json(serde_json::json!({
            "status": "result_recorded",
            "total_results": results.len()
        }))
    } else {
        Json(serde_json::json!({
            "status": "error",
            "error": "Missing agent_id or result"
        }))
    }
}

async fn daemon_heartbeat(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<DaemonRequest>,
) -> Json<HeartbeatResponse> {
    let mut state = state.lock().await;
    let now = now_secs();

    let agent_id = req.agent_id.clone().unwrap_or_else(|| "unknown".to_string());
    let agent_status = req.status.clone().unwrap_or_else(|| "alive".to_string());

    let mut registry = state.daemon_agents.lock().await;
    if let Some(agent) = registry.get_mut(&agent_id) {
        agent.last_heartbeat = now;
        agent.status = agent_status;
    } else {
        registry.insert(agent_id.clone(), AgentInfo {
            agent_id: agent_id.clone(),
            last_heartbeat: now,
            status: agent_status,
            current_task: None,
        });
    }

    Json(HeartbeatResponse {
        status: "alive".to_string(),
        timestamp: now,
    })
}