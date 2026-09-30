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

/// Upper bound on `?lines=`, so one request cannot ask the server to build a
/// gigabyte-long response.
pub const LOG_LINES_MAX: usize = 1000;

/// Default `?lines=` when the caller does not say.
pub const LOG_LINES_DEFAULT: usize = 50;

/// Channel cap for the log WebSocket broadcast. Senders that fall behind get a
/// `Lagged` error and are told to re-read `/logs`, which beats unbounded growth.
const LOG_BROADCAST_CAPACITY: usize = 256;

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

/// Control-plane state, hung off [`SharedState::control`].
pub struct ControlState {
    config: Mutex<HashMap<String, String>>,
    config_path: Option<std::path::PathBuf>,
    logs: Mutex<LogRing>,
    log_tx: broadcast::Sender<String>,
    jobs: Mutex<HashMap<String, JobRecord>>,
    last_update_check: Mutex<Option<String>>,
}

impl ControlState {
    /// Build the state, seeding config from `config_path` when readable.
    pub fn new(config_path: Option<std::path::PathBuf>) -> Self {
        let (log_tx, _) = broadcast::channel(LOG_BROADCAST_CAPACITY);
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

    pub async fn note_update_check(&self) {
        *self.last_update_check.lock().await = Some(now_rfc3339());
    }

    pub async fn last_update_check(&self) -> Option<String> {
        self.last_update_check.lock().await.clone()
    }

    async fn put_job(&self, record: JobRecord) {
        self.jobs.lock().await.insert(record.id.clone(), record);
    }

    async fn get_job(&self, id: &str) -> Option<JobRecord> {
        self.jobs.lock().await.get(id).cloned()
    }

    async fn patch_job<F: FnOnce(&mut JobRecord)>(&self, id: &str, patch: F) {
        if let Some(record) = self.jobs.lock().await.get_mut(id) {
            patch(record);
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
    let id = uuid::Uuid::new_v4().to_string();
    control
        .put_job(JobRecord {
            id: id.clone(),
            kind: "restart",
            status: "running",
            started_at: now_rfc3339(),
            finished_at: None,
            command: command.clone(),
            exit_code: None,
            output: None,
        })
        .await;

    let job_id = id.clone();
    tokio::spawn(async move {
        let outcome = tokio::process::Command::new(&program)
            .args(&args)
            .stdin(std::process::Stdio::null())
            .output()
            .await;
        let (status, exit_code, output) = match outcome {
            Ok(result) => {
                let mut text = String::from_utf8_lossy(&result.stdout).to_string();
                text.push_str(&String::from_utf8_lossy(&result.stderr));
                (
                    if result.status.success() { "succeeded" } else { "failed" },
                    result.status.code(),
                    trim_output(&text),
                )
            }
            Err(err) => ("failed", None, err.to_string()),
        };
        control
            .patch_job(&job_id, |record| {
                record.status = status;
                record.exit_code = exit_code;
                record.output = Some(output);
                record.finished_at = Some(now_rfc3339());
            })
            .await;
    });

    Json(json!({
        "status": "accepted",
        "job_id": id,
        "kind": "restart",
        "command": command,
        "poll": format!("/api/control/jobs/{id}"),
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

    let control = state.lock().await.control.clone();
    let id = uuid::Uuid::new_v4().to_string();
    control.note_update_check().await;
    control
        .put_job(JobRecord {
            id: id.clone(),
            kind: "upgrade",
            status: "running",
            started_at: now_rfc3339(),
            finished_at: None,
            command: command.clone(),
            exit_code: None,
            output: None,
        })
        .await;

    let job_id = id.clone();
    let budget = upgrade_timeout();
    tokio::spawn(async move {
        let child = tokio::process::Command::new(&program)
            .args(&args)
            .stdin(std::process::Stdio::null())
            .kill_on_drop(false)
            .output();
        let outcome = match tokio::time::timeout(budget, child).await {
            Ok(result) => result,
            Err(_) => {
                control
                    .patch_job(&job_id, |record| {
                        record.status = "timeout";
                        record.output = Some(format!(
                            "upgrade exceeded {}s budget and was abandoned",
                            budget.as_secs()
                        ));
                        record.finished_at = Some(now_rfc3339());
                    })
                    .await;
                return;
            }
        };
        let (status, exit_code, output) = match outcome {
            Ok(result) => {
                let mut text = String::from_utf8_lossy(&result.stdout).to_string();
                text.push_str(&String::from_utf8_lossy(&result.stderr));
                (
                    if result.status.success() { "succeeded" } else { "failed" },
                    result.status.code(),
                    trim_output(&text),
                )
            }
            Err(err) => ("failed", None, err.to_string()),
        };
        control
            .patch_job(&job_id, |record| {
                record.status = status;
                record.exit_code = exit_code;
                record.output = Some(output);
                record.finished_at = Some(now_rfc3339());
            })
            .await;
    });

    Json(json!({
        "status": "accepted",
        "job_id": id,
        "kind": "upgrade",
        "command": command,
        "timeout_seconds": budget.as_secs(),
        "poll": format!("/api/control/jobs/{id}"),
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
fn json_error(status: StatusCode, code: &str, detail: &str) -> Response {
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
}
