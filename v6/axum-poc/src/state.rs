//! Shared application state for ARIA Axum backend.
//! Phase L.4: SQLite-backed state with Arc<Mutex> for thread safety.

use axum::{
    extract::ws::{WebSocket, WebSocketUpgrade, Message},
    response::Response,
};
use futures::StreamExt;
use std::collections::HashMap;
use std::str::FromStr;
use std::sync::Arc;
use std::time::{Duration, Instant};
use sqlx::sqlite::{SqliteConnectOptions, SqlitePoolOptions};
use sqlx::SqlitePool;
use tokio::sync::Mutex;
use serde_json::json;
use uuid::Uuid;

/// Max requests allowed per client IP inside a single window.
pub const RATE_LIMIT_MAX: u32 = 100;
/// Sliding-window length for [`RATE_LIMIT_MAX`].
pub const RATE_LIMIT_WINDOW: Duration = Duration::from_secs(60);
/// Hard cap on tracked IPs before the stale-entry sweep runs.
const RATE_LIMIT_SWEEP_THRESHOLD: usize = 4096;

/// Environment variable holding the shared API key.
pub const API_KEY_ENV: &str = "ARIA_API_KEY";

/// Where the active API key came from.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum KeySource {
    /// Read from [`API_KEY_ENV`].
    Env,
    /// No env value present, so a random key was generated at startup.
    Generated,
}

/// Immutable auth configuration resolved once at startup.
///
/// `Debug` is implemented by hand below and never prints `api_key`: the derived
/// impl would leak the live bearer token into any `{:?}` / `tracing::?(..)` sink
/// (including the control log ring served at `/api/control/logs`).
#[derive(Clone)]
pub struct AuthConfig {
    /// The active bearer token.
    pub api_key: String,
    /// Provenance of [`AuthConfig::api_key`].
    pub source: KeySource,
}

impl std::fmt::Debug for AuthConfig {
    /// Redacts the key: length and provenance only, never the key material.
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("AuthConfig")
            .field("api_key", &"<redacted>")
            .field("api_key_len", &self.api_key.len())
            .field("source", &self.source)
            .finish()
    }
}

impl AuthConfig {
    /// Read `ARIA_API_KEY`; if unset or blank, generate a random key and log it.
    pub fn from_env() -> Self {
        match std::env::var(API_KEY_ENV) {
            Ok(raw) if !raw.trim().is_empty() => {
                let key = raw.trim().to_string();
                tracing::info!(
                    source = "env",
                    key_len = key.len(),
                    "API key loaded from {}",
                    API_KEY_ENV
                );
                println!("   Auth: API key loaded from {} ({} chars)", API_KEY_ENV, key.len());
                Self { api_key: key, source: KeySource::Env }
            }
            _ => {
                let key = format!("aria_{}{}", Uuid::new_v4().simple(), Uuid::new_v4().simple());
                println!("⚠️  Auth: {} not set — generated ephemeral API key:", API_KEY_ENV);
                println!("   {}", key);
                println!("   Set {} to pin a stable key before mobile sync.", API_KEY_ENV);
                tracing::warn!(
                    source = "generated",
                    "ARIA_API_KEY unset; generated ephemeral API key"
                );
                Self { api_key: key, source: KeySource::Generated }
            }
        }
    }

    /// True when the key was randomly generated instead of configured.
    pub fn is_generated(&self) -> bool {
        self.source == KeySource::Generated
    }

    /// Label used in structured logs and `/api/auth/validate` payloads.
    pub fn source_label(&self) -> &'static str {
        match self.source {
            KeySource::Env => "env",
            KeySource::Generated => "generated",
        }
    }
}

/// Constant-time string comparison; avoids leaking key bytes via timing.
pub fn constant_time_eq(a: &str, b: &str) -> bool {
    let (a, b) = (a.as_bytes(), b.as_bytes());
    if a.len() != b.len() {
        return false;
    }
    let mut diff = 0u8;
    for i in 0..a.len() {
        diff |= a[i] ^ b[i];
    }
    diff == 0
}

/// One IP's request counter for the current window.
#[derive(Clone, Debug)]
pub struct RateBucket {
    /// Start of the active window.
    pub window_start: Instant,
    /// Requests served within the active window.
    pub count: u32,
}

/// Outcome of a rate-limit check.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RateDecision {
    /// Request is allowed; carries the remaining budget in the window.
    Allow { remaining: u32 },
    /// Budget exhausted; `retry_after` is seconds until the window resets.
    Deny { retry_after: u64 },
}

/// Fixed-window rate limiter keyed by client IP.
pub type RateLimitMap = HashMap<String, RateBucket>;

/// Record one request for `ip` and decide whether it fits in the window.
pub async fn check_rate_limit(map: &Mutex<RateLimitMap>, ip: &str) -> RateDecision {
    let now = Instant::now();
    let mut map = map.lock().await;

    if map.len() > RATE_LIMIT_SWEEP_THRESHOLD {
        map.retain(|_, bucket| now.duration_since(bucket.window_start) < RATE_LIMIT_WINDOW);
    }

    let bucket = map.entry(ip.to_string()).or_insert(RateBucket {
        window_start: now,
        count: 0,
    });

    if now.duration_since(bucket.window_start) >= RATE_LIMIT_WINDOW {
        bucket.window_start = now;
        bucket.count = 0;
    }

    if bucket.count >= RATE_LIMIT_MAX {
        let elapsed = now.duration_since(bucket.window_start);
        let retry_after = RATE_LIMIT_WINDOW.saturating_sub(elapsed).as_secs() + 1;
        return RateDecision::Deny { retry_after };
    }

    bucket.count += 1;
    RateDecision::Allow {
        remaining: RATE_LIMIT_MAX - bucket.count,
    }
}

/// WebSocket upgrade handler — accepts Socket.io-compatible connections.
pub async fn websocket_handler(ws: WebSocketUpgrade) -> Response {
    ws.on_upgrade(handle_socket)
}

async fn handle_socket(mut socket: WebSocket) {
    println!("🔌 WebSocket client connected");
    
    // Send welcome message
    let welcome = json!({
        "type": "connected",
        "message": "ARIA Axum WebSocket ready",
        "agents": ["CodeAnalyzer", "DocsWriter", "Tester", "ResearchAgent"],
    });
    
    if socket.send(Message::Text(welcome.to_string().into())).await.is_ok() {
        println!("   → Welcome sent");
    }
    
    // Echo loop
    while let Some(msg) = socket.next().await {
        match msg {
            Ok(Message::Text(text)) => {
                println!("   ← Received: {}", text.chars().take(80).collect::<String>());
                
                // Echo back with ARIA prefix
                let echo = json!({
                    "type": "echo",
                    "original": text.as_str(),
                    "server": "ARIA-Axum-8002",
                });
                
                if socket.send(Message::Text(echo.to_string().into())).await.is_err() {
                    break;
                }
            }
            Ok(Message::Binary(_)) => {
                let ack = json!({ "type": "ack", "status": "binary_received" });
                let _ = socket.send(Message::Text(ack.to_string().into())).await;
            }
            Ok(Message::Ping(data)) => {
                if socket.send(Message::Pong(data)).await.is_err() {
                    break;
                }
            }
            Ok(Message::Pong(_)) => {}
            Ok(Message::Close(_)) => {
                println!("   WebSocket client disconnected");
                break;
            }
            Err(e) => {
                eprintln!("   WebSocket error: {}", e);
                break;
            }
        }
    }
}

/// Build a lazy SQLite pool for `path`.
    /// Connections are established on first use; short busy/acquire timeouts keep
    /// route latency well under 2s even if another process holds the write lock.
    /// `None` signals routes to emit fallback JSON.
    pub fn open_pool(path: &str) -> Option<SqlitePool> {
        if path.starts_with("memory:") {
            return None;
        }
        let url = format!("sqlite://{}?mode=rwc", path.replace('\\', "/"));

        let connect_opts = match SqliteConnectOptions::from_str(&url) {
            Ok(o) => o
                .create_if_missing(true)
                .busy_timeout(Duration::from_millis(800)),
            Err(e) => {
                eprintln!("   SQLite URL error: {}", e);
                return None;
            }
        };

        let pool = SqlitePoolOptions::new()
            .max_connections(4)
            .min_connections(0)
            .acquire_timeout(Duration::from_millis(800))
            .idle_timeout(Duration::from_secs(60))
            .max_lifetime(Duration::from_secs(300))
            .connect_lazy_with(connect_opts);

        Some(pool)
    }

    /// Ensure the tables the Axum routes depend on exist.
    ///
    /// `semantic_memory` is owned by this crate (Phase M.1: no FastAPI proxy).
    /// `chat_history` and `messages` are read by `/api/memory/stats` and may
    /// have been created by the legacy Python side; this is idempotent so a
    /// fresh aura.db still boots the full memory API.
    pub async fn init_db(pool: &SqlitePool) {
        // 1. Ensure the tables the Axum routes depend on exist.
        let statements = [
            "CREATE TABLE IF NOT EXISTS semantic_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT,
                kind VARCHAR(32),
                vector_json TEXT,
                timestamp DATETIME
            )",
            "CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role VARCHAR(16),
                content TEXT,
                provider VARCHAR(64),
                session_id VARCHAR(64),
                context TEXT,
                created_at DATETIME
            )",
            "CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER,
                role VARCHAR,
                content TEXT,
                provider VARCHAR,
                timestamp FLOAT,
                extra TEXT
            )",
        ];
        for stmt in statements {
            if let Err(e) = sqlx::query(stmt).execute(pool).await {
                eprintln!("   init_db: {} -> {}", stmt, e);
            }
        }

        // 2. Unified memory table. The legacy `memories` table (id, key, value,
        // kind, score, created_at, updated_at) has a different schema, so if it
        // exists we rename it to `memories_legacy` before creating the new one.
        // This is idempotent: a fresh aura.db skips the rename and just creates.
        //
        // The probes below FAIL CLOSED. Treating a query error as "no legacy
        // table" (`unwrap_or(false)`) meant that lock contention on this shared
        // SQLite file silently skipped the rename, and the following
        // `CREATE TABLE IF NOT EXISTS memories` then no-op'd against the legacy
        // shape: the server booted "successfully" on the wrong schema.
        async fn table_exists(pool: &sqlx::SqlitePool, name: &str) -> Result<bool, sqlx::Error> {
            sqlx::query_scalar::<_, bool>(
                "SELECT COUNT(*) > 0 FROM sqlite_master WHERE type='table' AND name = ?",
            )
            .bind(name)
            .fetch_one(pool)
            .await
        }

        let memories_exists = match table_exists(pool, "memories").await {
            Ok(v) => v,
            Err(e) => {
                eprintln!("   init_db: no se pudo inspeccionar `memories`: {e}");
                return;
            }
        };

        if memories_exists {
            // Only rename if the legacy schema is still present (has the old `key` column).
            let has_old_key = sqlx::query_scalar::<_, bool>(
                "SELECT COUNT(*) > 0 FROM pragma_table_info('memories') WHERE name='key'",
            )
            .fetch_one(pool)
            .await;

            let has_old_key = match has_old_key {
                Ok(v) => v,
                Err(e) => {
                    eprintln!("   init_db: no se pudo inspeccionar pragma_table_info: {e}");
                    return;
                }
            };

            if has_old_key {
                // Guard the destination too. If `memories_legacy` already exists
                // the rename FAILS, and the `CREATE TABLE IF NOT EXISTS` below
                // then silently no-ops against the legacy shape — booting on the
                // wrong schema with only an eprintln to show for it.
                let legacy_exists = match table_exists(pool, "memories_legacy").await {
                    Ok(v) => v,
                    Err(e) => {
                        eprintln!("   init_db: no se pudo inspeccionar `memories_legacy`: {e}");
                        return;
                    }
                };
                if legacy_exists {
                    // `memories` is legacy-shaped but `memories_legacy` is taken
                    // (restored backup, another writer). Park the old rows under a
                    // suffixed name instead of failing, and say so loudly.
                    let parked = format!(
                        "memories_legacy_{}",
                        std::time::SystemTime::now()
                            .duration_since(std::time::UNIX_EPOCH)
                            .map(|d| d.as_secs())
                            .unwrap_or(0)
                    );
                    println!("   init_db: memories_legacy ya existe; legacy -> {parked}");
                    if let Err(e) = sqlx::query(&format!(
                        "ALTER TABLE memories RENAME TO {parked}"
                    ))
                    .execute(pool)
                    .await
                    {
                        eprintln!("   init_db: rename legacy memories -> {parked}: {e}");
                        return;
                    }
                } else if let Err(e) =
                    sqlx::query("ALTER TABLE memories RENAME TO memories_legacy")
                        .execute(pool)
                        .await
                {
                    eprintln!("   init_db: rename legacy memories -> {e}");
                    return;
                } else {
                    println!("   init_db: legacy memories table renamed to memories_legacy");
                }
            }
        }

        let memory_stmt = "CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type VARCHAR(64),
            content TEXT,
            embedding TEXT,
            confidence FLOAT,
            source_llm VARCHAR(64),
            source_agent VARCHAR(128),
            expiry_at FLOAT,
            tags TEXT,
            created_at FLOAT,
            updated_at FLOAT
        )";
        if let Err(e) = sqlx::query(memory_stmt).execute(pool).await {
            eprintln!("   init_db: memories -> {}", e);
        }
    }

/// Shared state struct for the entire application.
#[derive(Clone)]
pub struct SharedState {
    pub db_path: String,
    /// Direct SQLite pool — replaces the FastAPI memory proxy.
    /// `None` when the pool could not be created (no runtime / invalid path);
    /// routes must degrade to fallback JSON in that case.
    pub db: Option<SqlitePool>,
    pub start_time: std::time::Instant,
    pub request_count: Arc<Mutex<u64>>,
    pub chat_count: Arc<Mutex<u64>>,
    pub daemon_agents: Arc<Mutex<std::collections::HashMap<String, AgentInfo>>>,
    pub task_queue: Arc<Mutex<std::collections::VecDeque<serde_json::Value>>>,
    pub task_results: Arc<Mutex<Vec<serde_json::Value>>>,
    /// Bearer-token configuration resolved from the environment at startup.
    pub auth: AuthConfig,
    /// Per-IP fixed-window request counters for rate limiting.
    pub rate_limits: Arc<Mutex<RateLimitMap>>,
    /// Rejected requests, for the security counters surfaced in status routes.
    pub auth_failures: Arc<Mutex<u64>>,
    /// Control-plane state: settings, log ring, dispatched jobs.
    pub control: Arc<crate::control::ControlState>,
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct AgentInfo {
    pub agent_id: String,
    pub last_heartbeat: u64,
    pub status: String,
    pub current_task: Option<String>,
}

impl SharedState {
    pub fn new(db_path: &str) -> Self {
        let db = open_pool(db_path);
        match &db {
            Some(_) => println!("   SQLite pool ready: {}", db_path),
            None => eprintln!("   ⚠️  SQLite pool unavailable: {}", db_path),
        }
        let control = std::sync::Arc::new(crate::control::ControlState::new(Some(
            crate::control::ControlState::default_config_path(),
        )));
        // Publish before serving so the tracing layer can reach the log ring for
        // every event, including the first ones after boot.
        crate::control::install_control_state(control.clone());
        SharedState {
            db_path: db_path.to_string(),
            db,
            start_time: std::time::Instant::now(),
            request_count: Arc::new(Mutex::new(0)),
            chat_count: Arc::new(Mutex::new(0)),
            daemon_agents: Arc::new(Mutex::new(std::collections::HashMap::new())),
            task_queue: Arc::new(Mutex::new(std::collections::VecDeque::new())),
            task_results: Arc::new(Mutex::new(Vec::new())),
            auth: AuthConfig::from_env(),
            rate_limits: Arc::new(Mutex::new(HashMap::new())),
            auth_failures: Arc::new(Mutex::new(0)),
            control,
        }
    }
    
    pub fn uptime_ms(&self) -> u64 {
        self.start_time.elapsed().as_millis() as u64
    }
    
    pub async fn increment_requests(&self) {
        let mut count = self.request_count.lock().await;
        *count += 1;
    }
    
    pub async fn increment_chats(&self) {
        let mut count = self.chat_count.lock().await;
        *count += 1;
    }

    /// Clone the pool handle so callers can release the state lock before querying.
    pub fn pool(&self) -> Option<SqlitePool> {
        self.db.clone()
    }

    /// Verify a candidate bearer token against the configured API key.
    /// Comparison is constant time to avoid leaking the key via timing.
    pub fn verify_token(&self, token: &str) -> bool {
        constant_time_eq(token, &self.auth.api_key)
    }

    /// Return the active API key (for login/refresh responses).
    pub fn api_key(&self) -> &str {
        &self.auth.api_key
    }

    /// True when the active key was randomly generated at startup.
    pub fn is_generated_key(&self) -> bool {
        self.auth.is_generated()
    }

    /// Record one rejected request and return the new total.
    pub async fn record_auth_failure(&self) -> u64 {
        let mut counter = self.auth_failures.lock().await;
        *counter += 1;
        *counter
    }

    /// Total rejected requests since startup.
    pub async fn auth_failure_count(&self) -> u64 {
        *self.auth_failures.lock().await
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // Fixture obviousamente falsa: no es una credencial, solo material para
    // comprobar que `Debug` no lo imprime.
    const FAKE_KEY: &str = "aria_test_key_not_a_real_credential";

    #[test]
    fn auth_config_debug_redacts_the_api_key() {
        let cfg = AuthConfig {
            api_key: FAKE_KEY.to_string(),
            source: KeySource::Env,
        };

        let rendered = format!("{:?}", cfg);

        assert!(
            !rendered.contains(FAKE_KEY),
            "Debug de AuthConfig filtró la clave: {rendered}"
        );
        assert!(
            rendered.contains("<redacted>"),
            "Debug de AuthConfig debería marcar la clave como redactada: {rendered}"
        );
    }

    #[test]
    fn auth_config_alternate_debug_also_redacts() {
        let cfg = AuthConfig {
            api_key: FAKE_KEY.to_string(),
            source: KeySource::Generated,
        };

        let rendered = format!("{:#?}", cfg);

        assert!(
            !rendered.contains(FAKE_KEY),
            "Debug alterno de AuthConfig filtró la clave: {rendered}"
        );
        assert!(rendered.contains("<redacted>"), "falta la marca de redaccion");
    }

    #[test]
    fn auth_config_debug_keeps_the_non_secret_fields() {
        let cfg = AuthConfig {
            api_key: FAKE_KEY.to_string(),
            source: KeySource::Env,
        };

        let rendered = format!("{:?}", cfg);

        assert!(
            rendered.contains("Env"),
            "se perdió la procedencia: {rendered}"
        );
        assert!(
            rendered.contains(&format!("api_key_len: {}", FAKE_KEY.len())),
            "se perdió la longitud de la clave: {rendered}"
        );
    }

    #[test]
    fn auth_config_is_still_cloneable() {
        let cfg = AuthConfig {
            api_key: FAKE_KEY.to_string(),
            source: KeySource::Env,
        };

        let copy = cfg.clone();

        assert_eq!(copy.api_key, cfg.api_key);
        assert_eq!(copy.source, cfg.source);
        assert!(!format!("{:?}", copy).contains(FAKE_KEY));
    }
}