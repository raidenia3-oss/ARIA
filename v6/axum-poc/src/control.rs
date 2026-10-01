//! Control Center routes — `/api/control/*`.
//!
//! This module is the HTTP half of the ARIA control center. The terminal half
//! (`aria_control/` in Python, Rich-based) is a thin client over these routes,
//! so anything the TUI can do the web UI and the marketplace can do too.
//!
//! # Why the endpoints are authenticated
//!
//! Every route here sits behind [`crate::auth::guard`]: none of them are listed
//! in `PUBLIC_PATHS`. `/api/control/restart`, `/upgrade` and `/config` mutate the
//! machine, and `/logs` can leak whatever the service logged. An open
//! control plane on `0.0.0.0:8002` would be a remote shell.
//!
//! # Why restart and upgrade answer 202
//!
//! Both are long-running and both can restart the very process serving the
//! request. Killing it inline would drop the response before it left the
//! socket. Instead each is dispatched as a detached job, the call returns
//! `202 Accepted` with a job id, and the outcome is read back from
//! `GET /api/control/jobs/{id}`. A 202 that cannot be followed is a lie.
//!
//! # Logs
//!
//! The ring buffer is fed by a `tracing` layer installed in `main.rs`, so it
//! captures every `tracing` event the service emits (auth failures, rate-limit
//! rejections, daemon activity). Legacy `println!` calls across the older
//! modules bypass `tracing` and are *not* captured unless a log file is
//! configured via `ARIA_LOG_PATH`, which is then tailed instead. See
//! [`LogRing`].

use axum::{
    extract::{
        ws::{Message, WebSocket, WebSocketUpgrade},
        Path as AxumPath, Query,
    },
    http::StatusCode,
    response::{IntoResponse, Response},
    routing::{get, post},
    Extension, Json, Router,
};
use chrono::Utc;
use serde::Deserialize;
use serde_json::json;
use std::collections::{HashMap, VecDeque};
use std::sync::{Arc, OnceLock};
use std::time::Duration;
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::sync::{broadcast, Mutex};
use tracing::field::{Field, Visit};
use tracing::{Event, Subscriber};

use crate::skills::plugin_catalog;
use crate::state::SharedState;
use crate::version::ARIA_VERSION;

// ---------------------------------------------------------------------------
// Pure helpers — no I/O, unit tested
// ---------------------------------------------------------------------------

/// How many log entries the ring buffer keeps before discarding the oldest.
pub const LOG_RING_CAPACITY: usize = 500;

/// How many finished job records are retained before the oldest is dropped.
pub const JOB_HISTORY_CAPACITY: usize = 500;

/// Upper bound on `?lines=`, so one request cannot ask the server to build a
/// gigabyte-long response.
pub const LOG_LINES_MAX: usize = 1000;

/// Default `?lines=` when the caller does not say.
pub const LOG_LINES_DEFAULT: usize = 50;

/// Channel cap for the log WebSocket broadcast. Senders that fall behind get a
/// `Lagged` error and are told to re-read `/logs`, which beats unbounded growth.
const LOG_BROADCAST_CAPACITY: usize = 256;

/// Channel cap for the progress WebSocket broadcast. Same reasoning as the log
/// channel: a subscriber that falls behind is told to re-read the snapshot.
const PROGRESS_BROADCAST_CAPACITY: usize = 256;

/// Minimum seconds a polling client should wait between
/// `GET /api/control/progress` calls. The rate limit allows 100 requests per
/// minute per IP, so a 2s poll has ample headroom.
pub const PROGRESS_POLL_INTERVAL_SECS: u64 = 2;

/// Where the persisted control config lives.
pub const CONTROL_STATE_DIR_ENV: &str = "ARIA_CONTROL_STATE_DIR";
/// Config file name inside [`CONTROL_STATE_DIR_ENV`].
pub const CONTROL_CONFIG_FILE: &str = "control.json";
/// Override for the detached restart command.
pub const CONTROL_RESTART_CMD_ENV: &str = "ARIA_RESTART_COMMAND";
/// Override for the detached upgrade command.
pub const CONTROL_UPGRADE_CMD_ENV: &str = "ARIA_UPGRADE_COMMAND";
/// Seconds an upgrade job may run before it is killed.
pub const CONTROL_UPGRADE_TIMEOUT_ENV: &str = "ARIA_UPGRADE_TIMEOUT_SECS";
/// Default upgrade budget when the env var is absent or unparseable.
pub const CONTROL_UPGRADE_TIMEOUT_DEFAULT_SECS: u64 = 300;
/// Hard ceiling on that budget, so a bad env var cannot hang a job forever.
pub const CONTROL_UPGRADE_TIMEOUT_MAX_SECS: u64 = 3600;

/// Validator for one configuration key.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ConfigKind {
    /// Accepts `true` / `false` (case-insensitive), stored lowercase.
    Bool,
    /// Accepts a decimal integer inside an inclusive range.
    Int { min: i64, max: i64 },
    /// Accepts one of a fixed set of values, case-insensitive, stored lowercase.
    Enum(&'static [&'static str]),
    /// Accepts any non-empty string, stored verbatim.
    Text,
}

/// One settable control-plane setting.
#[derive(Debug, Clone, Copy)]
pub struct ConfigField {
    pub key: &'static str,
    pub default: &'static str,
    pub kind: ConfigKind,
    pub description: &'static str,
}

/// The allowlist of settable keys.
///
/// An open key/value store is an arbitrary-write primitive on a machine that
/// also holds `ARIA_API_KEY` and a Discord token, so unknown keys are rejected
/// rather than stored. Extending this table is the only supported way to add a
/// setting.
pub const CONFIG_SCHEMA: &[ConfigField] = &[
    ConfigField {
        key: "release-channel",
        default: "stable",
        kind: ConfigKind::Enum(&["stable", "testing"]),
        description: "Rolling-release channel the updater follows.",
    },
    ConfigField {
        key: "update-check-interval-seconds",
        default: "21600",
        kind: ConfigKind::Int { min: 300, max: 86400 },
        description: "How often the updater polls for a new release.",
    },
    ConfigField {
        key: "update-check-enabled",
        default: "true",
        kind: ConfigKind::Bool,
        description: "Poll for updates in the background.",
    },
    ConfigField {
        key: "autonomy-enabled",
        default: "true",
        kind: ConfigKind::Bool,
        description: "Run the autonomous self-improvement daemon.",
    },
    ConfigField {
        key: "orb-autostart",
        default: "false",
        kind: ConfigKind::Bool,
        description: "Open the native 3D orb window at boot (headless otherwise).",
    },
    ConfigField {
        key: "log-level",
        default: "info",
        kind: ConfigKind::Enum(&["error", "warn", "info", "debug", "trace"]),
        description: "Maximum tracing level for ARIA's own targets.",
    },
    ConfigField {
        key: "daemon-port",
        default: "8002",
        kind: ConfigKind::Int { min: 1, max: 65535 },
        description: "TCP port the Axum backend listens on.",
    },
];

/// Look up a schema entry.
pub fn config_field(key: &str) -> Option<&'static ConfigField> {
    CONFIG_SCHEMA.iter().find(|field| field.key == key)
}

/// Default view of every setting, schema order.
pub fn config_defaults() -> HashMap<String, String> {
    CONFIG_SCHEMA
        .iter()
        .map(|field| (field.key.to_string(), field.default.to_string()))
        .collect()
}

/// Validate `value` against `field`, returning the normalized stored form.
///
/// Err carries a message safe to hand straight back to the caller.
pub fn validate_config_value(field: &ConfigField, value: &str) -> Result<String, String> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        return Err(format!("'{}' must not be empty", field.key));
    }
    match field.kind {
        ConfigKind::Bool => match trimmed.to_ascii_lowercase().as_str() {
            "true" | "1" | "yes" | "on" => Ok("true".to_string()),
            "false" | "0" | "no" | "off" => Ok("false".to_string()),
            _ => Err(format!("'{}' must be a boolean, got '{value}'", field.key)),
        },
        ConfigKind::Int { min, max } => {
            let parsed: i64 = trimmed.parse().map_err(|_| {
                format!("'{}' must be an integer, got '{value}'", field.key)
            })?;
            if parsed < min || parsed > max {
                return Err(format!(
                    "'{}' must be between {min} and {max}, got {parsed}",
                    field.key
                ));
            }
            Ok(parsed.to_string())
        }
        ConfigKind::Enum(allowed) => {
            let lowered = trimmed.to_ascii_lowercase();
            if allowed.contains(&lowered.as_str()) {
                Ok(lowered)
            } else {
                Err(format!(
                    "'{}' must be one of {}, got '{value}'",
                    field.key,
                    allowed.join(", ")
                ))
            }
        }
        ConfigKind::Text => Ok(trimmed.to_string()),
    }
}

/// Validate a `(key, value)` pair against the schema.
pub fn validate_config(key: &str, value: &str) -> Result<String, String> {
    let field =
        config_field(key).ok_or_else(|| format!("unknown config key '{key}'; valid keys: {}", valid_keys().join(", ")))?;
    validate_config_value(field, value)
}

/// Comma-separated list of valid keys, for error messages.
pub fn valid_keys() -> Vec<&'static str> {
    CONFIG_SCHEMA.iter().map(|field| field.key).collect()
}

/// RFC3339 timestamp, second precision.
pub fn now_rfc3339() -> String {
    Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true)
}

/// Compact human uptime: `2d 3h 45m`, `3h 12m`, `45s`.
///
/// Two units at most, largest first, so it fits a table column.
pub fn format_uptime(total_seconds: u64) -> String {
    const MINUTE: u64 = 60;
    const HOUR: u64 = 60 * MINUTE;
    const DAY: u64 = 24 * HOUR;

    if total_seconds < MINUTE {
        return format!("{total_seconds}s");
    }
    let days = total_seconds / DAY;
    let hours = (total_seconds % DAY) / HOUR;
    let minutes = (total_seconds % HOUR) / MINUTE;

    if days > 0 {
        format!("{days}d {hours}h")
    } else if hours > 0 {
        format!("{hours}h {minutes}m")
    } else {
        format!("{minutes}m")
    }
}

/// Clamp a caller-supplied `?lines=` into a sane band.
pub fn clamp_lines(requested: Option<usize>) -> usize {
    match requested {
        Some(0) | None => LOG_LINES_DEFAULT,
        Some(n) => n.min(LOG_LINES_MAX),
    }
}

/// How a service's liveness is determined.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Probe {
    /// This process; always running by definition.
    SelfProcess,
    /// A TCP connect to `port` with a short timeout.
    Tcp(u16),
    /// No in-process signal available; status is reported, never asserted.
    PidEnv(&'static str),
}

/// One known ARIA service.
#[derive(Debug, Clone, Copy)]
pub struct ServiceDef {
    pub name: &'static str,
    pub description: &'static str,
    pub probe: Probe,
}

/// The services the control center reports on.
///
/// Ported services are probed for real. Portless ones (the Python autonomous
/// controller, the USB agent, the Discord bot) have no in-process signal, so
/// their status is whatever `ARIA_*_PID` claims — reported as `unknown` when
/// the variable is unset, rather than guessed from process enumeration, which
/// would need a dependency this crate deliberately does not take.
pub const SERVICES: &[ServiceDef] = &[
    ServiceDef {
        name: "axum-backend",
        description: "Axum core backend",
        probe: Probe::SelfProcess,
    },
    ServiceDef {
        name: "fastapi-legacy",
        description: "FastAPI backend (cutover target)",
        probe: Probe::Tcp(8001),
    },
    ServiceDef {
        name: "ollama",
        description: "Local inference server",
        probe: Probe::Tcp(11434),
    },
    ServiceDef {
        name: "autonomous-controller",
        description: "Self-improvement loop, 5 min cycle",
        probe: Probe::PidEnv("ARIA_AUTONOMOUS_PID"),
    },
    ServiceDef {
        name: "usb-aria-agent",
        description: "USB device agent, 30 s polling",
        probe: Probe::PidEnv("ARIA_USB_PID"),
    },
    ServiceDef {
        name: "discord-bot",
        description: "Discord interface bot",
        probe: Probe::PidEnv("ARIA_DISCORD_PID"),
    },
];

/// Liveness verdict for a service.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ServiceStatus {
    Running,
    Stopped,
    /// The control plane has no way to tell; reported honestly as unknown.
    Unknown,
}

impl ServiceStatus {
    pub fn as_str(self) -> &'static str {
        match self {
            ServiceStatus::Running => "running",
            ServiceStatus::Stopped => "stopped",
            ServiceStatus::Unknown => "unknown",
        }
    }
}

/// A single captured log record.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct LogEntry {
    /// RFC3339 UTC capture time.
    pub ts: String,
    /// Lowercased tracing level.
    pub level: String,
    /// Emitting target, e.g. `aria::auth`.
    pub target: String,
    /// Formatted event body.
    pub message: String,
}

impl LogEntry {
    fn new(level: &str, target: &str, message: &str) -> Self {
        Self {
            ts: now_rfc3339(),
            level: level.to_ascii_lowercase(),
            target: target.to_string(),
            message: message.to_string(),
        }
    }
}

/// Bounded FIFO of [`LogEntry`], discarding the oldest on overflow.
///
/// Bounded is the point: an unbounded buffer behind an endpoint anyone can read
/// is a memory-exhaustion primitive.
#[derive(Debug)]
pub struct LogRing {
    capacity: usize,
    entries: VecDeque<LogEntry>,
}

impl LogRing {
    pub fn new(capacity: usize) -> Self {
        Self {
            capacity: capacity.max(1),
            entries: VecDeque::new(),
        }
    }

    pub fn push(&mut self, entry: LogEntry) {
        if self.entries.len() == self.capacity {
            self.entries.pop_front();
        }
        self.entries.push_back(entry);
    }

    /// The most recent `n` entries, oldest first.
    pub fn tail(&self, n: usize) -> Vec<LogEntry> {
        let skip = self.entries.len().saturating_sub(n);
        self.entries.iter().skip(skip).cloned().collect()
    }

    pub fn len(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }
}

impl Default for LogRing {
    fn default() -> Self {
        Self::new(LOG_RING_CAPACITY)
    }
}

/// One dispatched background job.
#[derive(Debug, Clone, serde::Serialize)]
pub struct JobRecord {
    pub id: String,
    /// `restart` or `upgrade`.
    pub kind: &'static str,
    pub status: &'static str,
    pub started_at: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub finished_at: Option<String>,
    /// Command line that was dispatched. Never contains secrets.
    pub command: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub exit_code: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output: Option<String>,
}

/// Latest known state of an in-flight child progress stream.
///
/// Folded from the NDJSON frames a dispatched child writes to stdout/stderr.
/// Every string inside came from a subprocess and is untrusted; it is copied
/// verbatim and never interpreted.
#[derive(Debug, Clone, serde::Serialize)]
pub struct ProgressSnapshot {
    /// `idle` until the first frame, then `running`, then `ok`/`failed`.
    pub phase: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub run_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub total: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub steps_done: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub current: Option<serde_json::Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub last: Option<serde_json::Value>,
    pub updated_at: String,
}

// Hand-written rather than `#[derive(Default)]`: the meaningful resting phase
// is `idle`, and `String::default()` would be an empty phase that no client
// knows how to render.
impl Default for ProgressSnapshot {
    fn default() -> Self {
        Self {
            phase: "idle".to_string(),
            run_id: None,
            total: None,
            steps_done: None,
            current: None,
            last: None,
            updated_at: now_rfc3339(),
        }
    }
}

/// Copy the named keys out of a frame, omitting absent ones.
///
/// An absent key is omitted rather than materialised as `null`, so a client can
/// tell "the child did not say" from "the child said null".
fn pick_fields(frame: &serde_json::Value, keys: &[&str]) -> Option<serde_json::Value> {
    let mut map = serde_json::Map::new();
    for key in keys {
        if let Some(value) = frame.get(*key) {
            map.insert((*key).to_string(), value.clone());
        }
    }
    if map.is_empty() {
        None
    } else {
        Some(serde_json::Value::Object(map))
    }
}

/// Read one frame field as a `usize`, ignoring anything that is not a
/// non-negative integer.
fn frame_usize(frame: &serde_json::Value, key: &str) -> Option<usize> {
    frame
        .get(key)
        .and_then(|value| value.as_u64())
        .and_then(|number| usize::try_from(number).ok())
}

/// Is this parsed pipe line an ARIA progress frame?
///
/// `Value::get` returns `None` for non-objects, so arrays, strings and numbers
/// are rejected without a separate type check — and `"aria_progress": "true"`
/// (a string) is rejected by `as_bool`.
pub(crate) fn is_progress_frame(value: &serde_json::Value) -> bool {
    value.get("aria_progress").and_then(|v| v.as_bool()) == Some(true)
}

/// A `step_start`/`step_end` can arrive without its `run_start` if the first
/// lines were lost. Promoting out of `idle` keeps a UI that is already
/// rendering arriving steps from looking stuck.
fn promote_running(snapshot: &mut ProgressSnapshot) {
    if snapshot.phase == "idle" {
        snapshot.phase = "running".to_string();
    }
}

/// Fold one frame into the snapshot, returning whether it was recognised.
///
/// Pure and synchronous so it needs no tokio runtime to test. An unrecognised
/// frame leaves the snapshot completely untouched, so ordinary child log noise
/// on the same pipe can never corrupt the progress state.
pub(crate) fn apply_frame(snapshot: &mut ProgressSnapshot, frame: &serde_json::Value) -> bool {
    if !is_progress_frame(frame) {
        return false;
    }
    let Some(event) = frame.get("event").and_then(|value| value.as_str()) else {
        return false;
    };
    match event {
        "run_start" => {
            snapshot.phase = "running".to_string();
            snapshot.run_id = frame
                .get("run_id")
                .and_then(|value| value.as_str())
                .map(|text| text.to_string());
            snapshot.total = frame_usize(frame, "total");
            snapshot.steps_done = None;
            snapshot.current = None;
        }
        "step_start" => {
            promote_running(snapshot);
            snapshot.current = pick_fields(frame, &["name", "tier", "index"]);
        }
        "step_end" => {
            promote_running(snapshot);
            snapshot.last = pick_fields(
                frame,
                &["name", "tier", "index", "status", "message", "elapsed_s"],
            );
            snapshot.current = None;
            // `index` is the 0-based position of the step that just finished, so
            // the executed count is `index + 1`. `steps_done` is a run-level
            // field and is deliberately NOT read from a step frame.
            snapshot.steps_done = frame_usize(frame, "index")
                .and_then(|index| index.checked_add(1))
                .or(snapshot.steps_done);
        }
        "run_end" => {
            let failed = matches!(
                frame.get("status").and_then(|value| value.as_str()),
                Some("fail" | "failed" | "error")
            );
            snapshot.phase = if failed { "failed" } else { "ok" }.to_string();
            // `index` is meaningless here and must never be read as a count.
            snapshot.steps_done = frame_usize(frame, "steps_done").or(snapshot.steps_done);
            snapshot.current = None;
        }
        _ => return false,
    }
    snapshot.updated_at = now_rfc3339();
    true
}

/// Control-plane state, hung off [`SharedState::control`].
pub struct ControlState {
    config: Mutex<HashMap<String, String>>,
    config_path: Option<std::path::PathBuf>,
    logs: Mutex<LogRing>,
    log_tx: broadcast::Sender<String>,
    jobs: Mutex<HashMap<String, JobRecord>>,
    last_update_check: Mutex<Option<String>>,
    progress: Mutex<ProgressSnapshot>,
    progress_tx: broadcast::Sender<String>,
}

impl ControlState {
    /// Build the state, seeding config from `config_path` when readable.
    pub fn new(config_path: Option<std::path::PathBuf>) -> Self {
        let (log_tx, _) = broadcast::channel(LOG_BROADCAST_CAPACITY);
        let (progress_tx, _) = broadcast::channel(PROGRESS_BROADCAST_CAPACITY);
        let mut values = config_defaults();
        if let Some(path) = config_path.as_ref() {
            if let Ok(raw) = std::fs::read_to_string(path) {
                if let Ok(stored) = serde_json::from_str::<HashMap<String, String>>(&raw) {
                    // Re-validate on load: a hand-edited or stale file must not
                    // be able to inject an out-of-schema value at boot.
                    for (key, value) in stored {
                        if let Some(field) = config_field(&key) {
                            if let Ok(normalized) = validate_config_value(field, &value) {
                                values.insert(key, normalized);
                            }
                        }
                    }
                }
            }
        }
        Self {
            config: Mutex::new(values),
            config_path,
            logs: Mutex::new(LogRing::default()),
            log_tx,
            jobs: Mutex::new(HashMap::new()),
            last_update_check: Mutex::new(None),
            progress: Mutex::new(ProgressSnapshot::default()),
            progress_tx,
        }
    }

    /// Directory used to persist config when `ARIA_CONTROL_STATE_DIR` is unset.
    ///
    /// Deliberately a per-user location, not a relative `.aria/`: the server's
    /// working directory depends on how it was launched (repo root, `target/release`,
    /// a service wrapper), so a relative path would silently write a *different*
    /// config depending on the launch method — and a config file that a `cargo
    /// clean` can delete is not a config file.
    pub fn default_config_path() -> std::path::PathBuf {
        if let Some(dir) = std::env::var(CONTROL_STATE_DIR_ENV)
            .ok()
            .filter(|value| !value.trim().is_empty())
        {
            return std::path::Path::new(&dir).join(CONTROL_CONFIG_FILE);
        }
        default_state_dir().join(CONTROL_CONFIG_FILE)
    }

    pub async fn config_snapshot(&self) -> HashMap<String, String> {
        self.config.lock().await.clone()
    }

    /// Validate, store and persist one setting.
    pub async fn set_config(&self, key: &str, value: &str) -> Result<String, String> {
        let normalized = validate_config(key, value)?;
        {
            let mut guard = self.config.lock().await;
            guard.insert(key.to_string(), normalized.clone());
        }
        self.persist_config().await;
        tracing::info!(target: "aria::control", key, value = %normalized, "control config updated");
        Ok(normalized)
    }

    async fn persist_config(&self) {
        let Some(path) = self.config_path.as_ref() else {
            return;
        };
        let snapshot = self.config.lock().await;
        if let Some(parent) = path.parent() {
            if let Err(err) = std::fs::create_dir_all(parent) {
                eprintln!("control: cannot create {}: {err}", parent.display());
                return;
            }
        }
        match serde_json::to_string_pretty(&*snapshot) {
            Ok(body) => {
                if let Err(err) = std::fs::write(path, body) {
                    eprintln!("control: cannot write {}: {err}", path.display());
                }
            }
            Err(err) => eprintln!("control: cannot serialize config: {err}"),
        }
    }

    /// Record a log line into the ring and fan it out to live subscribers.
    pub async fn record(&self, level: &str, target: &str, message: &str) {
        let entry = LogEntry::new(level, target, message);
        let payload = serde_json::to_string(&entry).unwrap_or_else(|_| "{}".to_string());
        self.logs.lock().await.push(entry);
        // No subscribers is the common case and not an error worth logging.
        let _ = self.log_tx.send(payload);
    }

    pub async fn tail_logs(&self, lines: usize) -> Vec<LogEntry> {
        self.logs.lock().await.tail(lines)
    }

    pub fn subscribe_logs(&self) -> broadcast::Receiver<String> {
        self.log_tx.subscribe()
    }

    /// Current folded progress of the in-flight run.
    pub async fn progress_snapshot(&self) -> ProgressSnapshot {
        self.progress.lock().await.clone()
    }

    pub fn subscribe_progress(&self) -> broadcast::Receiver<String> {
        self.progress_tx.subscribe()
    }

    /// Fold one progress frame and publish the new snapshot to live subscribers.
    pub(crate) async fn apply_progress_frame(&self, frame: &serde_json::Value) {
        let payload = {
            let mut snapshot = self.progress.lock().await;
            if !apply_frame(&mut snapshot, frame) {
                return;
            }
            serde_json::to_string(&*snapshot).unwrap_or_default()
        };
        // No subscribers is the common case and not an error worth logging.
        let _ = self.progress_tx.send(payload);
    }

    /// Push a progress frame from a non-subprocess source (an in-process Python
    /// emitter, a direct API call). Same folding path as `apply_progress_frame`,
    /// so a frame pushed over HTTP and one read off a child pipe behave
    /// identically downstream.
    pub async fn push_progress_frame(&self, frame: serde_json::Value) -> bool {
        let payload = {
            let mut snapshot = self.progress.lock().await;
            let recognised = apply_frame(&mut snapshot, &frame);
            if !recognised {
                return false;
            }
            serde_json::to_string(&*snapshot).unwrap_or_default()
        };
        let _ = self.progress_tx.send(payload);
        true
    }

    /// Clear the folded progress back to idle and notify subscribers.
    pub async fn reset_progress(&self) -> ProgressSnapshot {
        let snapshot = {
            let mut guard = self.progress.lock().await;
            *guard = ProgressSnapshot::default();
            guard.clone()
        };
        let _ = self.progress_tx.send(serde_json::to_string(&snapshot).unwrap_or_default());
        snapshot
    }

    pub async fn note_update_check(&self) {
        *self.last_update_check.lock().await = Some(now_rfc3339());
    }

    pub async fn last_update_check(&self) -> Option<String> {
        self.last_update_check.lock().await.clone()
    }

    async fn put_job(&self, record: JobRecord) {
        let mut jobs = self.jobs.lock().await;
        if jobs.len() >= JOB_HISTORY_CAPACITY && !jobs.contains_key(&record.id) {
            // Same reasoning as `LogRing`: the map is reachable by every route
            // that dispatches work, so an unbounded one is a slow memory leak.
            if let Some(oldest) = jobs
                .iter()
                .min_by_key(|(_, entry)| entry.started_at.clone())
                .map(|(id, _)| id.clone())
            {
                jobs.remove(&oldest);
            }
        }
        jobs.insert(record.id.clone(), record);
    }

    async fn get_job(&self, id: &str) -> Option<JobRecord> {
        self.jobs.lock().await.get(id).cloned()
    }

    async fn patch_job<F: FnOnce(&mut JobRecord)>(&self, id: &str, patch: F) {
        if let Some(record) = self.jobs.lock().await.get_mut(id) {
            patch(record);
        }
    }

    /// Run a detached command, record it as a job, and return the record.
    ///
    /// Shared with [`crate::videos`] so long operations have exactly one job
    /// lifecycle: 202 on dispatch, a pollable record, and a bounded runtime. A
    /// second implementation would be a second set of bugs in the thing agents
    /// use to tell whether work actually happened.
    ///
    /// `timeout` of `None` means no wall-clock ceiling; callers that run
    /// third-party binaries should pass one.
    pub async fn dispatch_job(
        self: &Arc<Self>,
        kind: &'static str,
        program: &str,
        args: &[String],
        timeout: Option<Duration>,
    ) -> JobRecord {
        let id = uuid::Uuid::new_v4().to_string();
        let command = std::iter::once(program.to_string())
            .chain(args.iter().cloned())
            .collect::<Vec<_>>()
            .join(" ");
        let record = JobRecord {
            id: id.clone(),
            kind,
            status: "running",
            started_at: now_rfc3339(),
            finished_at: None,
            command,
            exit_code: None,
            output: None,
        };
        self.put_job(record.clone()).await;

        let job_id = id;
        let owned_program = program.to_string();
        let owned_args = args.to_vec();
        let control = self.clone();
        tokio::spawn(async move {
            // The pipes are drained as the child runs, so the future has to be
            // created before the match; the timeout must still cover the whole
            // read, not just the wait.
            let run = stream_child(&control, &owned_program, &owned_args);
            let outcome = match timeout {
                Some(budget) => match tokio::time::timeout(budget, run).await {
                    Ok(result) => result,
                    Err(_) => {
                        control
                            .patch_job(&job_id, |record| {
                                record.status = "timeout";
                                record.output = Some(format!(
                                    "exceeded {}s budget and was killed",
                                    budget.as_secs()
                                ));
                                record.finished_at = Some(now_rfc3339());
                            })
                            .await;
                        return;
                    }
                },
                None => run.await,
            };
            let (status, exit_code, output) = outcome;
            control
                .patch_job(&job_id, |record| {
                    record.status = status;
                    record.exit_code = exit_code;
                    record.output = Some(output);
                    record.finished_at = Some(now_rfc3339());
                })
                .await;
        });

        record
    }
}

/// Append one captured line to the job accumulator, bounding it on overflow.
///
/// Overflow is dropped from the FRONT: the tail is what explains a failure, and
/// an updater's last words are the error. The in-loop cap can cut mid-
/// codepoint, which is why callers go through `String::from_utf8_lossy`
/// instead of slicing the buffer as `str`.
fn append_captured(buffer: &mut Vec<u8>, line: &[u8]) {
    if line.len() > JOB_LINE_LIMIT {
        // Keep the tail of an enormous line; the cut is moved forward to the
        // next char boundary so the lossless prefix stays valid. `str` owns
        // `is_char_boundary`, so we probe with a lossy view and then slice the
        // original bytes at the matching offset.
        let lossy = String::from_utf8_lossy(line);
        let mut start = line.len() - JOB_LINE_LIMIT;
        while start < lossy.len() && !lossy.is_char_boundary(start) {
            start += 1;
        }
        buffer.extend_from_slice(&line[start..]);
    } else {
        buffer.extend_from_slice(line);
    }
    buffer.push(b'\n');
    if buffer.len() > JOB_ACCUMULATE_LIMIT {
        let overflow = buffer.len() - JOB_ACCUMULATE_LIMIT;
        buffer.drain(..overflow.min(buffer.len()));
    }
}

/// Read one child pipe to EOF, folding progress frames and accumulating text.
///
/// `read_until` is used rather than `lines()` so a child emitting non-UTF-8
/// noise loses only that one line instead of failing the whole read.
async fn drain_child_pipe<R: tokio::io::AsyncRead + Unpin>(
    pipe: Option<R>,
    control: Arc<ControlState>,
    buffer: Arc<Mutex<Vec<u8>>>,
) {
    let Some(pipe) = pipe else {
        return;
    };
    let mut reader = BufReader::new(pipe);
    let mut line = Vec::new();
    loop {
        line.clear();
        match reader.read_until(b'\n', &mut line).await {
            Ok(0) => break,
            Ok(_) => {}
            // A pipe error means the child is gone. The job result is still
            // worth recording, so break rather than failing the job.
            Err(_) => break,
        }
        while matches!(line.last(), Some(b'\n') | Some(b'\r')) {
            line.pop();
        }
        if let Ok(value) = serde_json::from_str::<serde_json::Value>(&String::from_utf8_lossy(&line))
        {
            if is_progress_frame(&value) {
                control.apply_progress_frame(&value).await;
            }
        }
        // Progress lines are accumulated too: the job record is what an
        // operator reads after the fact, and dropping the frames from it would
        // make the transcript incomplete.
        {
            let mut acc = buffer.lock().await;
            append_captured(&mut acc, &line);
        }
    }
}

/// Run a child with both pipes drained live, returning
/// `(status, exit_code, trimmed_output)`.
///
/// `status` is `"succeeded"`/`"failed"`. stdout and stderr are INTERLEAVED
/// rather than concatenated stdout-then-stderr — that is deliberate: a progress
/// frame on stderr and a log line on stdout only make sense in emission order.
async fn stream_child(
    control: &Arc<ControlState>,
    program: &str,
    args: &[String],
) -> (&'static str, Option<i32>, String) {
    let mut command = tokio::process::Command::new(program);
    command
        .args(args)
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        // Without this, a timed-out job leaves the child running.
        .kill_on_drop(true);
    let mut child = match command.spawn() {
        Ok(child) => child,
        Err(err) => return ("failed", None, err.to_string()),
    };

    let buffer = Arc::new(Mutex::new(Vec::<u8>::new()));
    // BOTH drains must be running before the wait. This is load-bearing, not
    // an optimisation: a child that fills the 64 KiB pipe buffer while nobody
    // reads blocks forever, and the job would then hit its timeout for a reason
    // that has nothing to do with the child's work.
    let (_stdout_drain, _stderr_drain) = tokio::join!(
        drain_child_pipe(child.stdout.take(), control.clone(), buffer.clone()),
        drain_child_pipe(child.stderr.take(), control.clone(), buffer.clone()),
    );
    let status = child.wait().await;

    let bytes = {
        let guard = buffer.lock().await;
        guard.clone()
    };
    let text = String::from_utf8_lossy(&bytes).to_string();
    match status {
        Ok(status) => (
            if status.success() { "succeeded" } else { "failed" },
            status.code(),
            trim_output(&text),
        ),
        Err(err) => {
            let detail = if text.trim().is_empty() {
                err.to_string()
            } else {
                text
            };
            ("failed", None, detail)
        }
    }
}

// ---------------------------------------------------------------------------
// Global for the tracing layer
// ---------------------------------------------------------------------------

static CONTROL_STATE: OnceLock<Arc<ControlState>> = OnceLock::new();

/// Publish the control state so [`ControlLogLayer`] can reach it without every
/// event carrying a span-local copy.
pub fn install_control_state(state: Arc<ControlState>) {
    let _ = CONTROL_STATE.set(state);
}

fn active_control_state() -> Option<Arc<ControlState>> {
    CONTROL_STATE.get().cloned()
}

/// `tracing` layer that mirrors events into the control log ring.
pub struct ControlLogLayer;

impl<S> tracing_subscriber::Layer<S> for ControlLogLayer
where
    S: Subscriber + for<'a> tracing_subscriber::registry::LookupSpan<'a>,
{
    fn on_event(&self, event: &Event<'_>, _ctx: tracing_subscriber::layer::Context<'_, S>) {
        let metadata = event.metadata();
        let mut visitor = EventVisitor::default();
        event.record(&mut visitor);
        let state = match active_control_state() {
            Some(state) => state,
            None => return,
        };
        // `on_event` is sync and the ring is behind an async mutex, so hand the
        // write to the runtime. A full queue drops the line rather than blocking
        // the request path that produced it.
        let message = if visitor.message.is_empty() {
            visitor.fields
        } else if visitor.fields.is_empty() {
            visitor.message
        } else {
            format!("{} {}", visitor.message, visitor.fields)
        };
        if let Ok(handle) = tokio::runtime::Handle::try_current() {
            handle.spawn(async move {
                state.record(metadata.level().as_str(), metadata.target(), &message).await;
            });
        }
    }
}

/// Collects an event's `message` field plus every other field it carries.
#[derive(Default)]
struct EventVisitor {
    message: String,
    fields: String,
}

impl EventVisitor {
    fn push(&mut self, field: &Field, value: &dyn std::fmt::Debug) {
        if field.name() == "message" {
            self.message = format!("{value:?}");
            return;
        }
        if self.fields.is_empty() {
            self.fields = format!("{}={:?}", field.name(), value);
        } else {
            self.fields.push_str(&format!(" {}={:?}", field.name(), value));
        }
    }
}

impl Visit for EventVisitor {
    fn record_debug(&mut self, field: &Field, value: &dyn std::fmt::Debug) {
        self.push(field, value);
    }

    fn record_str(&mut self, field: &Field, value: &str) {
        if field.name() == "message" {
            self.message = value.to_string();
        } else if self.fields.is_empty() {
            self.fields = format!("{}={value}", field.name());
        } else {
            self.fields.push_str(&format!(" {}={value}", field.name()));
        }
    }
}

// ---------------------------------------------------------------------------
// Probing helpers
// ---------------------------------------------------------------------------

/// TCP connect with a deadline. Anything slower counts as down.
pub async fn probe_tcp(port: u16) -> bool {
    match tokio::time::timeout(
        Duration::from_millis(400),
        tokio::net::TcpStream::connect(("127.0.0.1", port)),
    )
    .await
    {
        Ok(Ok(_)) => true,
        Ok(Err(_)) | Err(_) => false,
    }
}

/// Read a PID from the environment, rejecting anything non-numeric or zero.
pub fn pid_from_env(var: &str) -> Option<u32> {
    std::env::var(var)
        .ok()
        .and_then(|raw| raw.trim().parse::<u32>().ok())
        .filter(|pid| *pid > 0)
}

/// Resolve a service's live status.
pub async fn service_status(def: &ServiceDef) -> (ServiceStatus, Option<u32>, Option<u16>) {
    match def.probe {
        Probe::SelfProcess => (
            ServiceStatus::Running,
            Some(std::process::id()),
            None,
        ),
        Probe::Tcp(port) => {
            let running = probe_tcp(port).await;
            (
                if running { ServiceStatus::Running } else { ServiceStatus::Stopped },
                None,
                Some(port),
            )
        }
        Probe::PidEnv(var) => match pid_from_env(var) {
            Some(pid) => (ServiceStatus::Unknown, Some(pid), None),
            None => (ServiceStatus::Unknown, None, None),
        },
    }
}

/// The command used to restart services, honouring the env override.
///
/// Returns `Err` with a caller-facing reason when the override is unusable.
pub fn restart_command() -> Result<String, String> {
    Ok(std::env::var(CONTROL_RESTART_CMD_ENV)
        .ok()
        .filter(|value| !value.trim().is_empty())
        .unwrap_or_else(|| default_restart_command()))
}

/// Windows cannot relaunch a process from inside itself without help, so the
/// default is a separate script; elsewhere the packaged binary is reused.
fn default_restart_command() -> String {
    if cfg!(target_os = "windows") {
        "aria-updater.exe --restart-services".to_string()
    } else {
        "aria-updater --restart-services".to_string()
    }
}

/// The command used to apply an upgrade.
pub fn upgrade_command() -> String {
    std::env::var(CONTROL_UPGRADE_CMD_ENV)
        .ok()
        .filter(|value| !value.trim().is_empty())
        .unwrap_or_else(|| {
            if cfg!(target_os = "windows") {
                "aria-updater.exe --apply".to_string()
            } else {
                "aria-updater --apply".to_string()
            }
        })
}

/// Budget for an upgrade job, clamped to [`CONTROL_UPGRADE_TIMEOUT_MAX_SECS`].
pub fn upgrade_timeout() -> Duration {
    let secs = std::env::var(CONTROL_UPGRADE_TIMEOUT_ENV)
        .ok()
        .and_then(|raw| raw.trim().parse::<u64>().ok())
        .unwrap_or(CONTROL_UPGRADE_TIMEOUT_DEFAULT_SECS)
        .clamp(1, CONTROL_UPGRADE_TIMEOUT_MAX_SECS);
    Duration::from_secs(secs)
}

/// Last `output` bytes kept in a job record.
const JOB_OUTPUT_LIMIT: usize = 4096;

/// Ceiling on the raw byte accumulator WHILE a child is being drained.
///
/// Larger than [`JOB_OUTPUT_LIMIT`] because [`trim_output`] only trims at the
/// end; without an in-loop cap a chatty child could grow the buffer without
/// bound before the job finished.
const JOB_ACCUMULATE_LIMIT: usize = JOB_OUTPUT_LIMIT * 4;

/// Ceiling on a single captured line. One enormous line must not become the
/// whole job record.
const JOB_LINE_LIMIT: usize = JOB_OUTPUT_LIMIT * 4;

/// Trim captured output to [`JOB_OUTPUT_LIMIT`], keeping the tail.
///
/// The tail is what matters: an updater's last words are the error, and a
/// versioned rollout must not be able to balloon server memory with stdout.
pub fn trim_output(raw: &str) -> String {
    let trimmed = raw.trim_end();
    if trimmed.len() <= JOB_OUTPUT_LIMIT {
        return trimmed.to_string();
    }
    // Move the cut point back to the nearest char boundary; slicing mid-codepoint
    // would panic, and the output may be multi-byte.
    let wanted = trimmed.len() - JOB_OUTPUT_LIMIT;
    let safe = trimmed
        .char_indices()
        .map(|(idx, _)| idx)
        .take_while(|idx| *idx <= wanted)
        .last()
        .unwrap_or(0);
    format!("...[truncated]\n{}", &trimmed[safe..])
}

/// Per-user state directory, matching platform convention.
///
/// Windows: `%LOCALAPPDATA%\ARIA`. Elsewhere: `$XDG_DATA_HOME/aria`, falling
/// back to `~/.local/share/aria`.
pub fn default_state_dir() -> std::path::PathBuf {
    if cfg!(target_os = "windows") {
        if let Ok(local) = std::env::var("LOCALAPPDATA") {
            if !local.trim().is_empty() {
                return std::path::Path::new(&local).join("ARIA");
            }
        }
    }
    if let Ok(xdg) = std::env::var("XDG_DATA_HOME") {
        if !xdg.trim().is_empty() {
            return std::path::Path::new(&xdg).join("aria");
        }
    }
    if let Ok(home) = std::env::var("HOME").or_else(|_| std::env::var("USERPROFILE")) {
        if !home.trim().is_empty() {
            return std::path::Path::new(&home)
                .join(".local")
                .join("share")
                .join("aria");
        }
    }
    // Last resort. Absolute, so it at least does not depend on the launch cwd.
    std::env::temp_dir().join("aria")
}

/// Split a command string into a program and arguments.
///
/// Deliberately naive: no quoting or shell expansion, because passing a config
/// value to a shell is how argument injection happens. Operators who need a
/// pipeline set the whole command in the env var.
pub fn split_command(command: &str) -> Result<(String, Vec<String>), String> {
    let mut parts = command.split_whitespace().map(str::to_string);
    let program = parts
        .next()
        .ok_or_else(|| format!("empty command: '{command}'"))?;
    Ok((program, parts.collect()))
}

// ---------------------------------------------------------------------------
// Routes
// ---------------------------------------------------------------------------
//
// Path parameters use axum 0.7's `:name` syntax. `{name}` is axum 0.8+; written
// here it matches nothing and every such request comes back a bare 404.

/// Query for `GET /api/control/logs`.
#[derive(Debug, Deserialize)]
pub struct LogsQuery {
    pub lines: Option<usize>,
}

/// Route table for the control plane.
pub fn router() -> Router<()> {
    Router::new()
        .route("/api/control/status", get(status))
        .route("/api/control/services", get(services))
        .route("/api/control/logs", get(logs))
        .route("/api/control/logs/stream", get(logs_stream))
        .route("/api/control/progress", get(progress))
        .route("/api/control/progress/stream", get(progress_stream))
        .route("/api/control/progress/push", post(push_progress))
        .route("/api/control/progress/reset", post(reset_progress))
        .route("/api/control/config", get(get_config).post(set_config))
        .route("/api/control/restart", post(restart))
        .route("/api/control/upgrade", post(upgrade))
        .route("/api/control/jobs/:id", get(job_status))
        .route("/api/control/plugins", get(plugins))
        .route("/api/control/plugins/:name/install", post(install_plugin))
}

/// `GET /api/control/status` — the dashboard's primary source.
async fn status(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
) -> Response {
    let (services_json, services_count, healthy) = {
        let guard = state.lock().await;
        guard.increment_requests().await;
        let snapshot: Vec<_> = futures::future::join_all(
            SERVICES.iter().map(|def| async move {
                let (status, pid, port) = service_status(def).await;
                json!({
                    "name": def.name,
                    "description": def.description,
                    "status": status.as_str(),
                    "pid": pid,
                    "port": port,
                })
            }),
        )
        .await;
        let healthy = snapshot
            .iter()
            .filter(|entry| entry["status"] == "running")
            .count();
        (json!(snapshot), snapshot.len(), healthy)
    };

    let (version, uptime_ms, config, last_check, config_path, auth) = {
        let guard = state.lock().await;
        let config = guard.control.config_snapshot().await;
        let last_check = guard.control.last_update_check().await;
        let config_path = guard
            .control
            .config_path
            .as_ref()
            .map(|path| path.display().to_string());
        let uptime_ms = guard.uptime_ms();
        let auth = crate::auth::auth_summary(&guard.auth);
        drop(guard);
        (guard_version(), uptime_ms, config, last_check, config_path, auth)
    };

    Json(json!({
        "aria_version": version,
        "channel": ARIA_CHANNEL,
        "uptime_seconds": uptime_ms / 1000,
        "uptime": format_uptime(uptime_ms / 1000),
        "services": services_json,
        "services_total": services_count,
        "services_healthy": healthy,
        "last_update_check": last_check,
        "config": config,
        "config_path": config_path,
        "auth": auth,
        "checked_at": now_rfc3339(),
        "server": "ARIA-Axum-8002",
    }))
    .into_response()
}

/// The release channel. Mirrors `aria_version.ARIA_CHANNEL` on the Python side.
pub const ARIA_CHANNEL: &str = "stable";

fn guard_version() -> String {
    ARIA_VERSION.to_string()
}

/// `GET /api/control/services` — one row per known service.
async fn services(Extension(state): Extension<Arc<Mutex<SharedState>>>) -> Response {
    {
        let guard = state.lock().await;
        guard.increment_requests().await;
    }
    let snapshot: Vec<_> = futures::future::join_all(
        SERVICES.iter().map(|def| async move {
            let (status, pid, port) = service_status(def).await;
            json!({
                "name": def.name,
                "description": def.description,
                "status": status.as_str(),
                "pid": pid,
                "port": port,
            })
        }),
    )
    .await;

    Json(json!({
        "services": snapshot,
        "count": snapshot.len(),
        "checked_at": now_rfc3339(),
        "server": "ARIA-Axum-8002",
    }))
    .into_response()
}

/// `GET /api/control/logs?lines=50` — ring-buffer tail.
async fn logs(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Query(query): Query<LogsQuery>,
) -> Response {
    {
        let guard = state.lock().await;
        guard.increment_requests().await;
    }
    let lines = clamp_lines(query.lines);
    let entries = state.lock().await.control.tail_logs(lines).await;
    Json(json!({
        "lines": entries,
        "count": entries.len(),
        "requested": lines,
        "capacity": LOG_RING_CAPACITY,
        "note": "captured from tracing events; set ARIA_LOG_PATH to include legacy stdout",
        "server": "ARIA-Axum-8002",
    }))
    .into_response()
}

/// `GET /api/control/logs/stream` — WebSocket tail.
///
/// Sends the current buffer on connect so a late subscriber is not blind, then
/// streams new entries until the client goes away.
async fn logs_stream(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    ws: WebSocketUpgrade,
) -> Response {
    let (control, backlog) = {
        let guard = state.lock().await;
        guard.increment_requests().await;
        let control = guard.control.clone();
        let backlog = control.tail_logs(LOG_LINES_DEFAULT).await;
        drop(guard);
        (control, backlog)
    };
    ws.on_upgrade(move |socket| stream_logs(socket, control, backlog))
}

async fn stream_logs(
    mut socket: WebSocket,
    control: Arc<ControlState>,
    backlog: Vec<LogEntry>,
) {
    for entry in backlog {
        if socket
            .send(Message::Text(
                serde_json::to_string(&entry).unwrap_or_default().into(),
            ))
            .await
            .is_err()
        {
            return;
        }
    }

    let mut rx = control.subscribe_logs();
    loop {
        match rx.recv().await {
            Ok(payload) => {
                if socket.send(Message::Text(payload.into())).await.is_err() {
                    break;
                }
            }
            // The consumer fell behind the ring; tell it to re-read rather than
            // silently skipping lines it will never see.
            Err(broadcast::error::RecvError::Lagged(missed)) => {
                let notice = json!({
                    "ts": now_rfc3339(),
                    "level": "warn",
                    "target": "aria::control",
                    "message": format!("subscriber lagged, {missed} entries dropped; re-read /api/control/logs"),
                });
                if socket.send(Message::Text(notice.to_string().into())).await.is_err() {
                    break;
                }
            }
            Err(broadcast::error::RecvError::Closed) => break,
        }
    }
}

/// `GET /api/control/progress` — latest folded progress of the in-flight run.
///
/// Cheap by construction: one lock, one clone, no I/O, so polling it costs
/// nothing beyond the request itself. Clients without a WebSocket should poll
/// no faster than [`PROGRESS_POLL_INTERVAL_SECS`] seconds — the rate limit
/// allows 100 requests per minute per IP, so 2s has ample headroom.
async fn progress(Extension(state): Extension<Arc<Mutex<SharedState>>>) -> Response {
    let control = {
        let guard = state.lock().await;
        guard.increment_requests().await;
        guard.control.clone()
    };
    let snapshot = control.progress_snapshot().await;
    Json(json!({
        "progress": snapshot,
        "poll_interval_seconds": PROGRESS_POLL_INTERVAL_SECS,
        "stream": "/api/control/progress/stream",
        "note": "sampled from NDJSON progress frames on a dispatched child's stdout/stderr",
        "server": "ARIA-Axum-8002",
    }))
    .into_response()
}

/// `GET /api/control/progress/stream` — WebSocket of progress snapshots.
///
/// Sends the current snapshot on connect so a late subscriber is not blind,
/// then streams the folded snapshot on every recognised frame.
async fn progress_stream(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    ws: WebSocketUpgrade,
) -> Response {
    let (control, backlog) = {
        let guard = state.lock().await;
        guard.increment_requests().await;
        let control = guard.control.clone();
        let backlog = control.progress_snapshot().await;
        drop(guard);
        (control, backlog)
    };
    ws.on_upgrade(move |socket| stream_progress(socket, control, backlog))
}

async fn stream_progress(
    mut socket: WebSocket,
    control: Arc<ControlState>,
    backlog: ProgressSnapshot,
) {
    let backlog = serde_json::to_string(&backlog).unwrap_or_default();
    if socket
        .send(Message::Text(backlog.into()))
        .await
        .is_err()
    {
        return;
    }

    let mut rx = control.subscribe_progress();
    loop {
        match rx.recv().await {
            Ok(payload) => {
                if socket.send(Message::Text(payload.into())).await.is_err() {
                    break;
                }
            }
            // The consumer fell behind; tell it to re-read the snapshot rather
            // than silently skipping states it will never see.
            Err(broadcast::error::RecvError::Lagged(missed)) => {
                let notice = json!({
                    "ts": now_rfc3339(),
                    "level": "warn",
                    "target": "aria::control",
                    "message": format!("progress subscriber lagged, {missed} updates dropped; re-read /api/control/progress"),
                });
                if socket.send(Message::Text(notice.to_string().into())).await.is_err() {
                    break;
                }
            }
            Err(broadcast::error::RecvError::Closed) => break,
        }
    }
}

/// `POST /api/control/progress/push` — inject a progress frame from a
/// non-subprocess source.
///
/// Any process that wants the UI to show progress (a Python emitter, a
/// background job, a test fixture) posts frames here instead of shelling
/// out. The body is the raw frame: it must carry ``aria_progress: true`` and
/// one of ``run_start`` / ``step_start`` / ``step_end`` / ``run_end``.
///
/// Returns 202 with the folded snapshot on success, 400 when the frame is not
/// a recognised progress frame (so callers can tell "server ignored me" from
/// "server applied me" without parsing the body).
async fn push_progress(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(frame): Json<serde_json::Value>,
) -> Response {
    {
        let guard = state.lock().await;
        guard.increment_requests().await;
    }
    let control = state.lock().await.control.clone();
    let applied = control.push_progress_frame(frame).await;
    if !applied {
        return (
            StatusCode::BAD_REQUEST,
            Json(json!({
                "status": "error",
                "error": "unrecognised_progress_frame",
                "hint": "frame must carry aria_progress:true and one of run_start/step_start/step_end/run_end",
            })),
        )
            .into_response();
    }
    let snapshot = control.progress_snapshot().await;
    (
        StatusCode::ACCEPTED,
        Json(json!({
            "status": "accepted",
            "progress": snapshot,
        })),
    )
        .into_response()
}

/// `POST /api/control/progress/reset` — clear the folded progress back to idle.
    ///
    /// Useful between runs so a stale "ok" snapshot does not greet the next run.
    async fn reset_progress(Extension(state): Extension<Arc<Mutex<SharedState>>>) -> Response {
        {
            let guard = state.lock().await;
            guard.increment_requests().await;
        }
        let control = state.lock().await.control.clone();
        let snapshot = control.reset_progress().await;
        Json(json!({ "status": "reset", "progress": snapshot }))
            .into_response()
    }

/// `GET /api/control/config` — schema, defaults, and current values.
async fn get_config(Extension(state): Extension<Arc<Mutex<SharedState>>>) -> Response {
    {
        let guard = state.lock().await;
        guard.increment_requests().await;
    }
    let values = state.lock().await.control.config_snapshot().await;
    let fields: Vec<_> = CONFIG_SCHEMA
        .iter()
        .map(|field| {
            json!({
                "key": field.key,
                "default": field.default,
                "description": field.description,
                "value": values.get(field.key).cloned().unwrap_or_else(|| field.default.to_string()),
            })
        })
        .collect();
    Json(json!({
        "config": values,
        "fields": fields,
        "checked_at": now_rfc3339(),
        "server": "ARIA-Axum-8002",
    }))
    .into_response()
}

/// `POST /api/control/config` — `{"key": "...", "value": "..."}`.
async fn set_config(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(body): Json<serde_json::Value>,
) -> Response {
    {
        let guard = state.lock().await;
        guard.increment_requests().await;
    }
    let key = body.get("key").and_then(|v| v.as_str()).unwrap_or("").to_string();
    // Accept a string, or render a scalar (number/bool) as its JSON text so
    // `{"key":"daemon-port","value":8002}` is not a needless client-side error.
    let value = match body.get("value") {
        Some(serde_json::Value::String(text)) => text.clone(),
        Some(serde_json::Value::Number(number)) => number.to_string(),
        Some(serde_json::Value::Bool(flag)) => flag.to_string(),
        _ => String::new(),
    };
    if key.is_empty() {
        return json_error(StatusCode::BAD_REQUEST, "missing_key", "'key' is required");
    }

    match state.lock().await.control.set_config(&key, &value).await {
        Ok(normalized) => Json(json!({
            "status": "ok",
            "key": key,
            "value": normalized,
            "updated_at": now_rfc3339(),
            "server": "ARIA-Axum-8002",
        }))
        .into_response(),
        Err(reason) => json_error(StatusCode::BAD_REQUEST, "invalid_config", &reason),
    }
}

/// `POST /api/control/restart` — dispatch a detached restart, return `202`.
async fn restart(Extension(state): Extension<Arc<Mutex<SharedState>>>) -> Response {
    {
        let guard = state.lock().await;
        guard.increment_requests().await;
    }
    let command = match restart_command() {
        Ok(command) => command,
        Err(reason) => {
            return json_error(StatusCode::INTERNAL_SERVER_ERROR, "bad_command", &reason)
        }
    };
    let (program, args) = match split_command(&command) {
        Ok(parts) => parts,
        Err(reason) => return json_error(StatusCode::BAD_REQUEST, "bad_command", &reason),
    };

    let control = state.lock().await.control.clone();
    let record = control.dispatch_job("restart", &program, &args, None).await;

    Json(json!({
        "status": "accepted",
        "job_id": record.id,
        "kind": "restart",
        "command": command,
        "poll": format!("/api/control/jobs/{}", record.id),
        "note": "services are restarted by a detached command; this process is not killed inline",
        "server": "ARIA-Axum-8002",
    }))
    .into_response()
}

/// `POST /api/control/upgrade` — dispatch an upgrade, return `202`.
async fn upgrade(Extension(state): Extension<Arc<Mutex<SharedState>>>) -> Response {
    {
        let guard = state.lock().await;
        guard.increment_requests().await;
    }
    let command = upgrade_command();
    let (program, args) = match split_command(&command) {
        Ok(parts) => parts,
        Err(reason) => return json_error(StatusCode::BAD_REQUEST, "bad_command", &reason),
    };
    let budget = upgrade_timeout();

    let control = state.lock().await.control.clone();
    let record = control
        .dispatch_job("upgrade", &program, &args, Some(budget))
        .await;

    Json(json!({
        "status": "accepted",
        "job_id": record.id,
        "kind": "upgrade",
        "command": command,
        "timeout_seconds": budget.as_secs(),
        "poll": format!("/api/control/jobs/{}", record.id),
        "server": "ARIA-Axum-8002",
    }))
    .into_response()
}

/// `GET /api/control/jobs/{id}` — outcome of a dispatched job.
async fn job_status(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    AxumPath(id): AxumPath<String>,
) -> Response {
    {
        let guard = state.lock().await;
        guard.increment_requests().await;
    }
    match state.lock().await.control.get_job(&id).await {
        Some(record) => Json(json!({
            "job": record,
            "server": "ARIA-Axum-8002",
        }))
        .into_response(),
        None => json_error(StatusCode::NOT_FOUND, "unknown_job", "no such job"),
    }
}

/// `GET /api/control/plugins` — the installable skill/plugin catalog.
async fn plugins(Extension(state): Extension<Arc<Mutex<SharedState>>>) -> Response {
    {
        let guard = state.lock().await;
        guard.increment_requests().await;
    }
    let catalog: Vec<_> = plugin_catalog()
        .iter()
        .map(|plugin| {
            json!({
                "name": plugin.name,
                "description": plugin.description,
                "status": plugin.status,
                "installed": true,
            })
        })
        .collect();
    Json(json!({
        "plugins": catalog,
        "count": catalog.len(),
        "checked_at": now_rfc3339(),
        "server": "ARIA-Axum-8002",
    }))
    .into_response()
}

/// `POST /api/control/plugins/{name}/install` — not yet available.
///
/// Deliberately a 501 rather than a fake success. Plugin installation needs the
/// signed marketplace (entry-point resolution, signature verification,
/// dependency resolution) which does not exist yet; a stub that returns 200
/// would let a UI claim a plugin is installed when nothing happened.
async fn install_plugin(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    AxumPath(name): AxumPath<String>,
) -> Response {
    {
        let guard = state.lock().await;
        guard.increment_requests().await;
    }
    let known = plugin_catalog()
        .iter()
        .any(|plugin| plugin.name == name);
    let detail = if known {
        format!("'{name}' is already installed")
    } else {
        format!("no marketplace entry for '{name}'")
    };
    json_error(
        StatusCode::NOT_IMPLEMENTED,
        "marketplace_unavailable",
        &format!(
            "{detail}; remote installation requires the signed marketplace, which is not built yet"
        ),
    )
}

/// Uniform error body so clients never have to guess the failure shape.
pub fn json_error(status: StatusCode, code: &str, detail: &str) -> Response {
    (
        status,
        Json(json!({
            "error": code,
            "detail": detail,
            "status": status.as_u16(),
        })),
    )
        .into_response()
}

#[cfg(test)]
mod tests {
    use super::*;

    // --- config ---------------------------------------------------------

    #[test]
    fn schema_keys_are_unique() {
        let mut keys: Vec<&str> = CONFIG_SCHEMA.iter().map(|f| f.key).collect();
        let count = keys.len();
        keys.sort_unstable();
        keys.dedup();
        assert_eq!(keys.len(), count, "duplicate key in CONFIG_SCHEMA");
    }

    #[test]
    fn release_channel_accepts_only_known_channels() {
        let field = config_field("release-channel").expect("key exists");
        assert_eq!(validate_config_value(field, "testing").unwrap(), "testing");
        assert_eq!(validate_config_value(field, " STABLE ").unwrap(), "stable");
        let err = validate_config_value(field, "beta").unwrap_err();
        assert!(err.contains("stable"), "error should list valid values: {err}");
    }

    #[test]
    fn interval_is_range_checked() {
        assert!(validate_config("update-check-interval-seconds", "300").is_ok());
        assert!(validate_config("update-check-interval-seconds", "86400").is_ok());
        assert!(validate_config("update-check-interval-seconds", "299").is_err());
        assert!(validate_config("update-check-interval-seconds", "86401").is_err());
        assert!(validate_config("update-check-interval-seconds", "soon").is_err());
    }

    #[test]
    fn booleans_normalize_to_true_false() {
        assert_eq!(validate_config("autonomy-enabled", "YES").unwrap(), "true");
        assert_eq!(validate_config("autonomy-enabled", "off").unwrap(), "false");
        assert!(validate_config("autonomy-enabled", "maybe").is_err());
    }

    #[test]
    fn unknown_key_is_rejected_with_the_valid_set() {
        let err = validate_config("rm-rf-slash", "x").unwrap_err();
        assert!(err.contains("unknown config key"));
        assert!(err.contains("release-channel"));
    }

    #[test]
    fn defaults_cover_every_schema_entry() {
        let defaults = config_defaults();
        for field in CONFIG_SCHEMA {
            assert!(defaults.contains_key(field.key));
            // A default must itself validate, or boot state can be illegal.
            validate_config_value(field, field.default)
                .unwrap_or_else(|e| panic!("bad default for {}: {e}", field.key));
        }
    }

    // --- formatting -----------------------------------------------------

    #[test]
    fn uptime_is_two_units_max() {
        assert_eq!(format_uptime(0), "0s");
        assert_eq!(format_uptime(45), "45s");
        assert_eq!(format_uptime(60), "1m");
        assert_eq!(format_uptime(60 * 59 + 30), "59m");
        assert_eq!(format_uptime(3600), "1h 0m");
        assert_eq!(format_uptime(3600 * 3 + 60 * 12), "3h 12m");
        assert_eq!(format_uptime(86400 * 2 + 3600 * 3 + 60 * 45), "2d 3h");
    }

    #[test]
    fn lines_are_clamped_into_a_sane_band() {
        assert_eq!(clamp_lines(None), LOG_LINES_DEFAULT);
        assert_eq!(clamp_lines(Some(0)), LOG_LINES_DEFAULT);
        assert_eq!(clamp_lines(Some(10)), 10);
        assert_eq!(clamp_lines(Some(usize::MAX)), LOG_LINES_MAX);
    }

    #[test]
    fn service_names_are_unique() {
        let mut names: Vec<&str> = SERVICES.iter().map(|s| s.name).collect();
        let count = names.len();
        names.sort_unstable();
        names.dedup();
        assert_eq!(names.len(), count, "duplicate service name");
    }

    #[test]
    fn service_status_strings_are_stable() {
        assert_eq!(ServiceStatus::Running.as_str(), "running");
        assert_eq!(ServiceStatus::Stopped.as_str(), "stopped");
        assert_eq!(ServiceStatus::Unknown.as_str(), "unknown");
    }

    // --- log ring -------------------------------------------------------

    #[test]
    fn ring_drops_oldest_on_overflow() {
        let mut ring = LogRing::new(3);
        for i in 0..5 {
            ring.push(LogEntry::new("info", "t", &format!("line {i}")));
        }
        assert_eq!(ring.len(), 3);
        let tail = ring.tail(10);
        let messages: Vec<&str> = tail.iter().map(|e| e.message.as_str()).collect();
        assert_eq!(messages, ["line 2", "line 3", "line 4"]);
    }

    #[test]
    fn ring_tail_returns_most_recent_in_order() {
        let mut ring = LogRing::new(10);
        for i in 0..5 {
            ring.push(LogEntry::new("warn", "aria::auth", &format!("e{i}")));
        }
        let tail = ring.tail(2);
        assert_eq!(tail.len(), 2);
        assert_eq!(tail[0].message, "e3");
        assert_eq!(tail[1].message, "e4");
        assert_eq!(tail[0].level, "warn");
        assert_eq!(tail[0].target, "aria::auth");
    }

    #[test]
    fn ring_capacity_is_at_least_one() {
        let mut ring = LogRing::new(0);
        ring.push(LogEntry::new("info", "t", "only"));
        assert_eq!(ring.len(), 1);
    }

    #[test]
    fn ring_is_empty_by_default() {
        assert!(LogRing::default().is_empty());
    }

    // --- job plumbing ---------------------------------------------------

    #[test]
    fn command_splitting_is_whitespace_only() {
        let (program, args) = split_command("aria-updater.exe --apply --force").unwrap();
        assert_eq!(program, "aria-updater.exe");
        assert_eq!(args, ["--apply", "--force"]);
        assert!(split_command("   ").is_err());
    }

    #[test]
    fn output_trim_keeps_the_tail() {
        let short = "done".repeat(10);
        assert_eq!(trim_output(&short), short);

        let long = "x".repeat(JOB_OUTPUT_LIMIT * 2);
        let trimmed = trim_output(&long);
        assert!(trimmed.starts_with("...[truncated]\n"));
        assert!(trimmed.len() < long.len());
        assert!(trimmed.ends_with('x'));
    }

    #[test]
    fn output_trim_never_splits_a_character() {
        // Multi-byte content must not be cut mid-codepoint.
        let long = "é".repeat(JOB_OUTPUT_LIMIT);
        let trimmed = trim_output(&long);
        assert!(trimmed.starts_with("...[truncated]\n"));
        let body = trimmed.trim_start_matches("...[truncated]\n");
        assert!(body.ends_with('é'), "truncation cut a character in half");
        assert!(body.chars().all(|c| c == 'é'), "stray character in trimmed body");
    }

    // --- pid handling ---------------------------------------------------

    #[test]
    fn pid_zero_is_not_a_pid() {
        // A PID of 0 means "no process" on POSIX and is never a real service.
        assert!(pid_from_env("ARIA_DEFINITELY_UNSET_PID_VAR_12345").is_none());
    }

    // --- state ----------------------------------------------------------

    #[tokio::test]
    async fn set_config_validates_and_stores() {
        let state = ControlState::new(None);
        assert_eq!(state.set_config("release-channel", "TESTING").await.unwrap(), "testing");
        let snapshot = state.config_snapshot().await;
        assert_eq!(snapshot.get("release-channel").unwrap(), "testing");
    }

    #[tokio::test]
    async fn set_config_rejects_unknown_keys_without_mutating() {
        let state = ControlState::new(None);
        let before = state.config_snapshot().await;
        assert!(state.set_config("nope", "1").await.is_err());
        assert_eq!(state.config_snapshot().await, before);
    }

    #[tokio::test]
    async fn recorded_logs_are_returned_newest_last() {
        let state = ControlState::new(None);
        state.record("info", "aria::auth", "first").await;
        state.record("warn", "aria::ratelimit", "second").await;
        let tail = state.tail_logs(10).await;
        assert_eq!(tail.len(), 2);
        assert_eq!(tail[1].message, "second");
        assert!(tail[1].ts.ends_with('Z') || tail[1].ts.contains('+'));
    }

    #[tokio::test]
    async fn jobs_round_trip() {
        let state = ControlState::new(None);
        state
            .put_job(JobRecord {
                id: "abc".into(),
                kind: "upgrade",
                status: "running",
                started_at: now_rfc3339(),
                finished_at: None,
                command: "aria-updater --apply".into(),
                exit_code: None,
                output: None,
            })
            .await;
        assert!(state.get_job("abc").await.is_some());
        state
            .patch_job("abc", |record| {
                record.status = "succeeded";
                record.exit_code = Some(0);
            })
            .await;
        let record = state.get_job("abc").await.unwrap();
        assert_eq!(record.status, "succeeded");
        assert_eq!(record.exit_code, Some(0));
        assert!(state.get_job("missing").await.is_none());
    }

    #[tokio::test]
    async fn subscribers_receive_recorded_entries() {
        let state = ControlState::new(None);
        let mut rx = state.subscribe_logs();
        state.record("error", "aria::control", "boom").await;
        let payload = rx.recv().await.unwrap();
        assert!(payload.contains("boom"));
    }

    #[test]
    fn state_dir_is_absolute_and_launch_independent() {
        // A relative default would write a different config depending on the
        // working directory the server happened to be launched from.
        let dir = default_state_dir();
        assert!(
            dir.is_absolute(),
            "state dir must be absolute, got {}",
            dir.display()
        );
    }

    #[test]
    fn config_load_drops_out_of_schema_values() {
        let dir = std::env::temp_dir().join(format!("aria-control-{}", uuid::Uuid::new_v4()));
        std::fs::create_dir_all(&dir).expect("temp dir");
        let path = dir.join(CONTROL_CONFIG_FILE);
        std::fs::write(
            &path,
            r#"{"release-channel": "testing", "daemon-port": "99999", "bogus": "x"}"#,
        )
        .expect("write");

        let state = ControlState::new(Some(path.clone()));
        let values = tokio::runtime::Runtime::new()
            .expect("runtime")
            .block_on(state.config_snapshot());
        assert_eq!(values.get("release-channel").unwrap(), "testing");
        assert_eq!(values.get("daemon-port").unwrap(), "8002", "out-of-range value dropped");
        assert!(!values.contains_key("bogus"), "unknown key dropped");

        let _ = std::fs::remove_dir_all(&dir);
    }

    // --- progress folding -----------------------------------------------

    /// Every synthetic frame is a progress frame; the tests below vary the rest.
    fn frame(extra: serde_json::Value) -> serde_json::Value {
        let mut value = extra;
        if let serde_json::Value::Object(map) = &mut value {
            map.insert("aria_progress".to_string(), serde_json::Value::Bool(true));
        }
        value
    }

    #[test]
    fn progress_snapshot_starts_idle() {
        assert_eq!(ProgressSnapshot::default().phase, "idle");
    }

    #[test]
    fn run_start_opens_the_run() {
        let mut snapshot = ProgressSnapshot::default();
        assert!(apply_frame(
            &mut snapshot,
            &frame(json!({
                "event": "run_start",
                "run_id": "a1b2c3d4e5f6",
                "total": 12,
            }))
        ));
        assert_eq!(snapshot.phase, "running");
        assert_eq!(snapshot.run_id.as_deref(), Some("a1b2c3d4e5f6"));
        assert_eq!(snapshot.total, Some(12));
        assert!(snapshot.steps_done.is_none());
    }

    #[test]
    fn step_start_publishes_the_current_step_only() {
        let mut snapshot = ProgressSnapshot::default();
        apply_frame(
            &mut snapshot,
            &frame(json!({
                "event": "step_start",
                "name": "detect-environment",
                "tier": "core",
                "index": 0,
                "total": 12,
                "status": "running",
            })),
        );
        let current = snapshot.current.expect("current step");
        assert_eq!(current["name"], "detect-environment");
        assert_eq!(current["tier"], "core");
        assert_eq!(current["index"], 0);
        assert!(
            current.get("message").is_none(),
            "step_start must not invent a message: {current}"
        );
    }

    #[test]
    fn step_end_closes_the_step_and_counts_it() {
        let mut snapshot = ProgressSnapshot::default();
        apply_frame(
            &mut snapshot,
            &frame(json!({
                "event": "step_start",
                "name": "detect-environment",
                "index": 0,
            })),
        );
        apply_frame(
            &mut snapshot,
            &frame(json!({
                "event": "step_end",
                "name": "detect-environment",
                "tier": "core",
                "index": 0,
                "status": "ok",
                "message": "toolchain found",
                "elapsed_s": 1.23,
            })),
        );
        assert!(snapshot.current.is_none(), "step_end clears current");
        let last = snapshot.last.clone().expect("last step");
        assert_eq!(last["name"], "detect-environment");
        assert_eq!(last["status"], "ok");
        assert_eq!(last["message"], "toolchain found");
        // 0-based index 0 means the first step just finished.
        assert_eq!(snapshot.steps_done, Some(1));
    }

    #[test]
    fn run_end_status_drives_the_phase() {
        let mut failed = ProgressSnapshot::default();
        apply_frame(
            &mut failed,
            &frame(json!({"event": "run_end", "steps_done": 11, "status": "fail"})),
        );
        assert_eq!(failed.phase, "failed");
        assert_eq!(failed.steps_done, Some(11));

        let mut ok = ProgressSnapshot::default();
        apply_frame(
            &mut ok,
            &frame(json!({"event": "run_end", "steps_done": 12, "status": "ok"})),
        );
        assert_eq!(ok.phase, "ok");
        assert_eq!(ok.steps_done, Some(12));
    }

    #[test]
    fn run_end_index_is_never_read_as_a_step_count() {
        // Regression: `index` is a step field. A run_end frame must not have it
        // turned into `steps_done`.
        let mut snapshot = ProgressSnapshot::default();
        apply_frame(
            &mut snapshot,
            &frame(json!({"event": "run_end", "index": 7, "status": "ok"})),
        );
        assert_eq!(snapshot.phase, "ok");
        assert_eq!(
            snapshot.steps_done, None,
            "run_end without steps_done must not derive a count from index"
        );
    }

    #[test]
    fn step_end_ignores_a_run_level_steps_done_field() {
        // Regression: `steps_done` is a run field. A step frame must derive the
        // count from `index` alone.
        let mut snapshot = ProgressSnapshot::default();
        apply_frame(
            &mut snapshot,
            &frame(json!({
                "event": "step_end",
                "name": "install",
                "index": 2,
                "steps_done": 12,
                "status": "ok",
            })),
        );
        assert_eq!(
            snapshot.steps_done,
            Some(3),
            "step_end must count from index + 1, not from steps_done"
        );
    }

    #[test]
    fn non_progress_lines_change_nothing() {
        let mut snapshot = ProgressSnapshot::default();
        for noise in [
            serde_json::json!(["aria_progress"]),
            serde_json::json!("aria_progress"),
            serde_json::json!(7),
            serde_json::json!({"event": "step_start", "name": "x"}),
            serde_json::json!({"aria_progress": false, "event": "step_start"}),
            serde_json::json!({"aria_progress": "true", "event": "step_start"}),
        ] {
            assert!(!apply_frame(&mut snapshot, &noise), "recognised {noise}");
        }
        assert_eq!(snapshot.phase, "idle");
        assert!(snapshot.current.is_none());
    }

    #[test]
    fn unknown_event_is_dropped_and_state_survives() {
        let mut snapshot = ProgressSnapshot::default();
        apply_frame(
            &mut snapshot,
            &frame(json!({"event": "run_start", "run_id": "a1b2c3d4e5f6", "total": 3})),
        );
        apply_frame(&mut snapshot, &frame(json!({"event": "run_panic"})));
        assert_eq!(snapshot.phase, "running");
        assert_eq!(snapshot.run_id.as_deref(), Some("a1b2c3d4e5f6"));
        assert_eq!(snapshot.total, Some(3));
    }

    #[test]
    fn missed_run_start_still_leaves_the_ui_running() {
        let mut snapshot = ProgressSnapshot::default();
        apply_frame(
            &mut snapshot,
            &frame(json!({"event": "step_start", "name": "detect", "index": 0})),
        );
        assert_eq!(snapshot.phase, "running");
    }

    #[test]
    fn warn_and_skip_runs_are_not_failures() {
        for status in ["warn", "skip"] {
            let mut snapshot = ProgressSnapshot::default();
            apply_frame(
                &mut snapshot,
                &frame(json!({"event": "run_end", "status": status, "steps_done": 2})),
            );
            assert_eq!(snapshot.phase, "ok", "status {status} is not a failure");
        }
    }

    #[test]
    fn accumulator_stays_bounded_and_keeps_the_tail() {
        let mut buffer: Vec<u8> = Vec::new();
        for i in 0..20_000 {
            let line = format!("log line {i} with some padding to make bytes");
            append_captured(&mut buffer, line.as_bytes());
        }
        assert!(
            buffer.len() <= JOB_ACCUMULATE_LIMIT,
            "accumulator grew to {}",
            buffer.len()
        );
        let text = trim_output(&String::from_utf8_lossy(&buffer));
        assert!(
            text.ends_with("log line 19999 with some padding to make bytes"),
            "tail was not kept: {:?}",
            &text[text.len().saturating_sub(80)..]
        );
    }

    #[test]
    fn accumulator_never_splits_a_character() {
        // The in-loop cap drops bytes from the FRONT, so the retained buffer can
        // start in the middle of a multi-byte codepoint. The guarantee is that
        // this costs at most that one partial character: `from_utf8_lossy` must
        // not panic, and the tail must survive intact.
        let mut buffer: Vec<u8> = Vec::new();
        for _ in 0..5_000 {
            append_captured(&mut buffer, "✓ ok".as_bytes());
        }
        assert!(buffer.len() <= JOB_ACCUMULATE_LIMIT);
        let text = trim_output(&String::from_utf8_lossy(&buffer));
        assert!(text.ends_with("ok"), "tail was not kept: {text}");
        assert!(
            text.chars()
                .all(|c| c == '✓' || c == '\u{fffd}' || c == '\n' || c.is_ascii()),
            "unexpected character in lossy output: {text}"
        );
    }

    #[test]
    fn an_oversized_line_keeps_only_its_tail() {
        let mut buffer: Vec<u8> = Vec::new();
        let mut line = "x".repeat(JOB_LINE_LIMIT + 1024);
        line.push_str("NEEDLE");
        append_captured(&mut buffer, line.as_bytes());
        let text = String::from_utf8_lossy(&buffer).to_string();
        assert!(text.ends_with("NEEDLE"), "head of the line was kept: {text}");
        assert!(text.len() <= JOB_LINE_LIMIT + 1);
    }
}
