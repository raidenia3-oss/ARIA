//! Computer routes: control, apps, screenshot, open, volume.
//!
//! Honesty contract (ARIA Phase A). Every `/api/computer/*` response is one of
//! three shapes, never anything else:
//!   * 501 from `control::not_implemented`, when the route advertises an action
//!     and this build performs none of it.
//!   * 200 with `data_source: "unavailable"` plus explicit `null`s, when the
//!     datum was never measured. The key is present and null so a client can
//!     tell "not measured" apart from "field I do not know about".
//!   * 200 with values read from the running process or OS (`SystemTime`,
//!     `std::env::consts`, `COMPUTERNAME`), when a key is present it was
//!     measured here and now.

use axum::{
    routing::{get, post},
    Router,
    Extension,
    Json,
};
use serde_json::json;
use std::sync::Arc;
use tokio::sync::Mutex;

use crate::control::not_implemented;
use crate::state::SharedState;

pub fn router() -> Router<()> {
    Router::new()
        .route("/api/computer/control", get(control))
        .route("/api/computer/apps", get(apps))
        .route("/api/computer/screenshot", get(screenshot))
        .route("/api/computer/open", post(open))
        .route("/api/computer/volume", get(volume))
        .route("/api/computer/lock", get(lock))
        .route("/api/computer/memory", get(memory))
        .route("/api/computer/processes", get(processes))
        .route("/api/computer/status", get(status))
        .route("/api/computer/scan", get(scan))
        .route("/api/computer/whois", get(whois))
        .route("/api/computer/time", get(time))
        .route("/api/computer/ping", get(ping))
        .route("/api/computer/explorer", get(explorer))
        .route("/api/computer/execute", post(execute))
}

// --- acciones: nada se ejecuta, así que 501 ---------------------------------

async fn control() -> axum::response::Response {
    not_implemented("computer_control", "System control not implemented in this build")
}

async fn screenshot() -> axum::response::Response {
    not_implemented("computer_screenshot", "Screenshot capture not implemented in this build")
}

async fn open(Extension(state): Extension<Arc<Mutex<SharedState>>>) -> axum::response::Response {
    // El extractor `Json` se eliminó a propósito: sin extractor de body, un
    // POST con o sin body cae siempre en el 501 y nunca en un 422 de validación.
    // La métrica se conserva: la petición sí se contó.
    let state = state.lock().await;
    state.increment_requests().await;
    not_implemented(
        "computer_open",
        "Opening applications not implemented in this build; nothing was launched",
    )
}

async fn lock() -> axum::response::Response {
    not_implemented("computer_lock", "Session lock not implemented in this build")
}

async fn explorer() -> axum::response::Response {
    not_implemented("computer_explorer", "File explorer integration not implemented in this build")
}

// --- datos no medidos: 200 + unavailable + null ------------------------------

async fn apps() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "running": null,
        "data_source": "unavailable",
        "detail": "Running applications not enumerated in this build",
        "server": "ARIA-Axum-8002",
    }))
}

async fn processes() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "processes": null,
        "data_source": "unavailable",
        "detail": "Process list not collected in this build",
        "server": "ARIA-Axum-8002",
    }))
}

async fn memory() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "total": null,
        "used": null,
        "available": null,
        "usage_percent": null,
        "data_source": "unavailable",
        "detail": "Memory metrics not measured in this build",
        "server": "ARIA-Axum-8002",
    }))
}

async fn volume() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "volume": null,
        "muted": null,
        "data_source": "unavailable",
        "detail": "Volume level not measured in this build",
        "server": "ARIA-Axum-8002",
    }))
}

async fn scan() -> Json<serde_json::Value> {
    // Sin clave de red: este build no sondea nada, así que no hay estado que
    // reportar. Poner un literal en su lugar afirmaría un sondeo inexistente.
    Json(json!({
        "status": "ok",
        "data_source": "unavailable",
        "detail": "Network scan not performed in this build",
        "server": "ARIA-Axum-8002",
    }))
}

async fn ping() -> Json<serde_json::Value> {
    // Este endpoint no tiene un destino real al que hacer ping, así que reportar
    // milisegundos sería fiction: el cuerpo no lleva ninguna medida de ida y vuelta.
    Json(json!({
        "status": "ok",
        "pong": true,
        "data_source": "unavailable",
        "detail": "Latency not measured in this build",
        "server": "ARIA-Axum-8002",
    }))
}

// --- datos medidos: valores del proceso/OS real ------------------------------

async fn whois() -> Json<serde_json::Value> {
    // hostname viene de COMPUTERNAME; si falta o viene vacío se OMITE la clave en
    // vez de rellenarla con un nombre inventado. os/arch son constantes de
    // compilación del propio binario.
    let mut obj = serde_json::Map::new();
    obj.insert("status".into(), json!("ok"));
    if let Ok(host) = std::env::var("COMPUTERNAME") {
        if !host.trim().is_empty() {
            obj.insert("hostname".into(), json!(host));
        }
    }
    obj.insert("os".into(), json!(std::env::consts::OS));
    obj.insert("arch".into(), json!(std::env::consts::ARCH));
    obj.insert("framework".into(), json!("Rust/Axum"));
    Json(serde_json::Value::Object(obj))
}

async fn status() -> Json<serde_json::Value> {
    // No hay endpoint de carga de CPU medido: la clave `cpu` desaparece (el
    // cliente leía la arquitectura como porcentaje) y tampoco se publica una
    // cifra de memoria. Aquí solo hay hechos del sistema tomados de este proceso.
    let mut obj = serde_json::Map::new();
    obj.insert("status".into(), json!("ok"));
    if let Ok(host) = std::env::var("COMPUTERNAME") {
        if !host.trim().is_empty() {
            obj.insert("hostname".into(), json!(host));
        }
    }
    obj.insert("os".into(), json!(std::env::consts::OS));
    obj.insert("arch".into(), json!(std::env::consts::ARCH));
    obj.insert("server".into(), json!("ARIA-Axum-8002"));
    Json(serde_json::Value::Object(obj))
}

async fn time() -> Json<serde_json::Value> {
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_secs();
    
    Json(json!({
        "status": "ok",
        "timestamp": now,
        "server": "ARIA-Axum-8002",
    }))
}

async fn execute(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(_req): Json<serde_json::Value>,
) -> axum::response::Response {
    // computer_execute NO ejecuta nada hoy: el body anterior devolvía
    // "Executed via Axum backend" sin spawnear nada. 501 honesto.
    let state = state.lock().await;
    state.increment_requests().await;
    crate::control::not_implemented(
        "computer_execute",
        "Ejecución remota no implementada; ningún comando fue ejecutado.",
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::http::StatusCode;

    // --- helpers ---------------------------------------------------------

    fn test_state() -> Arc<Mutex<SharedState>> {
        let dir =
            std::env::temp_dir().join(format!("aria-computer-test-{}", uuid::Uuid::new_v4()));
        std::fs::create_dir_all(&dir).expect("tmpdir");
        let db = dir.join("test.db");
        let state = SharedState::new(db.to_str().expect("utf8 db path"));
        Arc::new(Mutex::new(state))
    }

    async fn body_json(resp: axum::response::Response) -> serde_json::Value {
        let body = axum::body::to_bytes(resp.into_body(), usize::MAX)
            .await
            .expect("body readable");
        serde_json::from_slice(&body).expect("json body")
    }

    fn json_body(handler: Json<serde_json::Value>) -> serde_json::Value {
        handler.0
    }

    fn keys_of(value: &serde_json::Value) -> Vec<&str> {
        let mut keys: Vec<&str> = value
            .as_object()
            .expect("json object")
            .keys()
            .map(|k| k.as_str())
            .collect();
        keys.sort_unstable();
        keys
    }

    async fn assert_501(resp: axum::response::Response, feature: &str) {
        assert_eq!(resp.status(), StatusCode::NOT_IMPLEMENTED, "status");
        let body = body_json(resp).await;
        assert_eq!(
            body.get("error").and_then(|v| v.as_str()),
            Some("not_implemented")
        );
        assert_eq!(body.get("feature").and_then(|v| v.as_str()), Some(feature));
        assert_eq!(body.get("status").and_then(|v| v.as_u64()), Some(501));
        assert_eq!(
            body.get("server").and_then(|v| v.as_str()),
            Some("ARIA-Axum-8002")
        );
        assert!(
            body.get("detail").and_then(|v| v.as_str()).is_some(),
            "every 501 body carries a detail"
        );
    }

    fn assert_unavailable(body: &serde_json::Value) -> serde_json::Value {
        assert_eq!(body.get("status").and_then(|v| v.as_str()), Some("ok"));
        assert_eq!(
            body.get("data_source").and_then(|v| v.as_str()),
            Some("unavailable")
        );
        assert_eq!(
            body.get("server").and_then(|v| v.as_str()),
            Some("ARIA-Axum-8002")
        );
        assert!(
            body.get("detail").and_then(|v| v.as_str()).is_some(),
            "every unavailable body carries a detail"
        );
        body.clone()
    }

    fn assert_null(body: &serde_json::Value, key: &str) {
        assert!(
            body.get(key).map(|v| v.is_null()).unwrap_or(false),
            "{key} must be present and null, never a fabricated value"
        );
    }

    // --- acciones: 501 ---------------------------------------------------

    #[tokio::test]
    async fn action_endpoints_are_501_and_name_their_feature() {
        assert_501(control().await, "computer_control").await;
        assert_501(screenshot().await, "computer_screenshot").await;
        assert_501(lock().await, "computer_lock").await;
        assert_501(explorer().await, "computer_explorer").await;
    }

    #[tokio::test]
    async fn open_is_501_without_a_json_extractor_and_still_counts_the_request() {
        let state = test_state();
        let before = *state.lock().await.request_count.lock().await;
        let resp = open(Extension(state.clone())).await;
        assert_501(resp, "computer_open").await;
        let after = *state.lock().await.request_count.lock().await;
        assert_eq!(after, before + 1, "the metric survives the honest 501");
    }

    // --- datos no medidos: 200 + unavailable + null -----------------------

    #[tokio::test]
    async fn apps_and_processes_report_unavailable_with_null_lists() {
        let apps_body = assert_unavailable(&json_body(apps().await));
        assert_null(&apps_body, "running");
        assert_eq!(
            keys_of(&apps_body),
            vec!["data_source", "detail", "running", "server", "status"]
        );

        let proc_body = assert_unavailable(&json_body(processes().await));
        assert_null(&proc_body, "processes");
        assert_eq!(
            keys_of(&proc_body),
            vec!["data_source", "detail", "processes", "server", "status"]
        );
    }

    #[tokio::test]
    async fn memory_and_volume_report_unavailable_with_null_measurements() {
        let mem = assert_unavailable(&json_body(memory().await));
        for key in ["total", "used", "available", "usage_percent"] {
            assert_null(&mem, key);
        }
        assert_eq!(
            keys_of(&mem),
            vec![
                "available",
                "data_source",
                "detail",
                "server",
                "status",
                "total",
                "usage_percent",
                "used"
            ]
        );

        let vol = assert_unavailable(&json_body(volume().await));
        for key in ["volume", "muted"] {
            assert_null(&vol, key);
        }
        assert_eq!(
            keys_of(&vol),
            vec!["data_source", "detail", "muted", "server", "status", "volume"]
        );
    }

    #[tokio::test]
    async fn scan_has_no_network_key_at_all() {
        let body = assert_unavailable(&json_body(scan().await));
        assert!(
            body.get("network").is_none(),
            "no scan happened, so no network state may be published"
        );
        assert_eq!(
            keys_of(&body),
            vec!["data_source", "detail", "server", "status"]
        );
    }

    #[tokio::test]
    async fn ping_publishes_no_round_trip_measurement() {
        let body = assert_unavailable(&json_body(ping().await));
        assert_eq!(body.get("pong").and_then(|v| v.as_bool()), Some(true));
        // Closed set: adding any timing key later has to break this test.
        assert_eq!(
            keys_of(&body),
            vec!["data_source", "detail", "pong", "server", "status"]
        );
    }

    // --- datos medidos ---------------------------------------------------

    #[tokio::test]
    async fn whois_reports_the_real_target_os() {
        let body = json_body(whois().await);
        assert_eq!(body.get("status").and_then(|v| v.as_str()), Some("ok"));
        assert_eq!(
            body.get("os").and_then(|v| v.as_str()),
            Some(std::env::consts::OS)
        );
        assert_eq!(
            body.get("arch").and_then(|v| v.as_str()),
            Some(std::env::consts::ARCH)
        );
        assert_eq!(
            body.get("framework").and_then(|v| v.as_str()),
            Some("Rust/Axum")
        );
        match std::env::var("COMPUTERNAME") {
            Ok(host) if !host.trim().is_empty() => {
                assert_eq!(
                    body.get("hostname").and_then(|v| v.as_str()),
                    Some(host.as_str())
                );
            }
            _ => {
                assert!(
                    body.get("hostname").is_none(),
                    "hostname must be absent, never invented"
                );
            }
        }
    }

    #[tokio::test]
    async fn status_publishes_only_measured_os_facts() {
        let body = json_body(status().await);
        assert_eq!(
            body.get("os").and_then(|v| v.as_str()),
            Some(std::env::consts::OS)
        );
        assert_eq!(
            body.get("arch").and_then(|v| v.as_str()),
            Some(std::env::consts::ARCH)
        );
        assert!(
            body.get("cpu").is_none(),
            "there is no measured CPU load endpoint to report"
        );
        assert!(
            body.get("memory").is_none(),
            "no memory figure is measured for this route"
        );

        // The key set is conditional on COMPUTERNAME, so it cannot be asserted
        // as one fixed list.
        let host_present = std::env::var("COMPUTERNAME")
            .map(|h| !h.trim().is_empty())
            .unwrap_or(false);
        let expected: Vec<&str> = if host_present {
            vec!["arch", "hostname", "os", "server", "status"]
        } else {
            vec!["arch", "os", "server", "status"]
        };
        assert_eq!(keys_of(&body), expected);
    }

    #[tokio::test]
    async fn time_still_reports_a_measured_timestamp() {
        let body = json_body(time().await);
        assert_eq!(body.get("status").and_then(|v| v.as_str()), Some("ok"));
        let reported = body
            .get("timestamp")
            .and_then(|v| v.as_u64())
            .expect("timestamp present");
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .expect("clock is past the epoch")
            .as_secs();
        assert!(reported <= now, "timestamp must not be in the future");
        assert!(now - reported <= 5, "timestamp must come from the system clock");
    }
}