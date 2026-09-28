//! Daemon routes: USB-ARIA coordination endpoints.
//! Phase L.4: USB-ARIA distributed autonomous infrastructure.
use axum::{
    extract::Json,
    routing::post,
    Router,
};
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, VecDeque};
use std::sync::{Arc, OnceLock};
use tokio::sync::Mutex;
use std::time::{SystemTime, UNIX_EPOCH};

// Static state using OnceLock
static DAEMON_STATE: OnceLock<DaemonState> = OnceLock::new();

#[derive(Clone)]
struct DaemonState {
    pc_active: Arc<Mutex<bool>>,
    idle_seconds: Arc<Mutex<u64>>,
    session_user: Arc<Mutex<String>>,
    task_queue: Arc<Mutex<VecDeque<Task>>>,
    agent_registry: Arc<Mutex<HashMap<String, AgentInfo>>>,
    task_results: Arc<Mutex<Vec<TaskResult>>>,
}

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
struct AgentInfo {
    agent_id: String,
    last_heartbeat: u64,
    status: String,
    current_task: Option<String>,
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

fn get_state() -> &'static DaemonState {
    DAEMON_STATE.get_or_init(|| DaemonState {
        pc_active: Arc::new(Mutex::new(false)),
        idle_seconds: Arc::new(Mutex::new(0)),
        session_user: Arc::new(Mutex::new("unknown".to_string())),
        task_queue: Arc::new(Mutex::new(VecDeque::new())),
        agent_registry: Arc::new(Mutex::new(HashMap::new())),
        task_results: Arc::new(Mutex::new(Vec::new())),
    })
}

pub fn router() -> Router<()> {
    let _ = get_state();
    
    Router::new()
        .route("/api/pc/state", post(pc_state))
        .route("/api/daemon/task", post(daemon_task))
        .route("/api/daemon/result", post(daemon_result))
        .route("/api/daemon/heartbeat", post(daemon_heartbeat))
}

async fn pc_state(Json(_req): Json<DaemonRequest>) -> Json<PCStateResponse> {
    let state = get_state();
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs();

    Json(PCStateResponse {
        active: *state.pc_active.lock().await,
        idle_seconds: *state.idle_seconds.lock().await,
        session_user: state.session_user.lock().await.clone(),
        timestamp: now,
    })
}

async fn daemon_task(Json(req): Json<DaemonRequest>) -> Json<TaskResponse> {
    let state = get_state();
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs();

    match req.action.as_deref() {
        Some("get_pending") => {
            let agent_id = req.agent_id.clone();
            let mut queue = state.task_queue.lock().await;
            
            let task = queue.iter_mut().find(|t| {
                t.status == "pending" && 
                (t.assigned_to.is_none() || t.assigned_to.as_ref() == agent_id.as_ref())
            });

            if let Some(task) = task {
                task.status = "assigned".to_string();
                task.assigned_to = agent_id;
                Json(TaskResponse {
                    available: true,
                    task: Some(task.clone()),
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
            let agent_id = req.agent_id.clone();
            let agent_status = req.status.clone().unwrap_or_else(|| "idle".to_string());
            
            let mut registry = state.agent_registry.lock().await;
            let id = agent_id.clone().unwrap_or_else(|| "unknown".to_string());
            registry.insert(id.clone(), AgentInfo {
                agent_id: id,
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

async fn daemon_result(Json(req): Json<DaemonRequest>) -> Json<serde_json::Value> {
    let state = get_state();
    if let (Some(agent_id), Some(result)) = (req.agent_id, req.result) {
        let task_result = TaskResult {
            task_id: result.get("task_id").and_then(|v| v.as_str()).unwrap_or("unknown").to_string(),
            agent_id,
            status: result.get("status").and_then(|v| v.as_str()).unwrap_or("unknown").to_string(),
            output: result.get("output").cloned().unwrap_or(serde_json::json!({})),
            executed_at: result.get("executed_at").and_then(|v| v.as_str()).unwrap_or("").to_string(),
        };

        let mut results = state.task_results.lock().await;
        results.push(task_result);

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

async fn daemon_heartbeat(Json(req): Json<DaemonRequest>) -> Json<HeartbeatResponse> {
    let state = get_state();
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs();

    let agent_id = req.agent_id.clone();
    let agent_status = req.status.clone().unwrap_or_else(|| "alive".to_string());

    if let Some(agent_id) = agent_id {
        let mut registry = state.agent_registry.lock().await;
        if let Some(agent) = registry.get_mut(&agent_id.clone()) {
            agent.last_heartbeat = now;
            agent.status = agent_status;
        } else {
            let id = agent_id.clone();
            registry.insert(agent_id, AgentInfo {
                agent_id: id,
                last_heartbeat: now,
                status: agent_status,
                current_task: None,
            });
        }
    } else {
        let mut registry = state.agent_registry.lock().await;
        registry.insert("unknown".to_string(), AgentInfo {
            agent_id: "unknown".to_string(),
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