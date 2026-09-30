//! Video reference library routes — `/api/videos/*`.
//!
//! The media, the index and the downloads live in `aria_video_library/`
//! (Python) on the USB stick; this module is the HTTP face of that library. It
//! deliberately does **not** reimplement it: search and listing read the same
//! `videos/index.json` the Python indexer writes, and a download is dispatched
//! as the `aria-videos download` job, so there is exactly one code path that can
//! put a file on the stick.
//!
//! # Why download answers 202
//!
//! A download runs yt-dlp, ffprobe, ffmpeg and possibly Whisper, and on a USB
//! stick it can take minutes. Running it inline would hold the request open that
//! whole time and risk the client giving up while the file lands anyway. The
//! call dispatches a detached job through
//! [`crate::control::ControlState::dispatch_job`] and returns `202` with a
//! `job_id`, read back from `GET /api/control/jobs/{id}`.
//!
//! # Why the source list is an allowlist
//!
//! These routes are authenticated but reachable by anything holding the API
//! token, and the command they dispatch takes a URL. Left open, that is a
//! general-purpose fetcher aimed at whatever the host can reach. Only the
//! platforms in [`DEFAULT_SOURCES`] are accepted unless an operator widens
//! [`VIDEO_SOURCES_ENV`].
//!
//! # Search ranking
//!
//! The canonical relevance ranking is
//! `aria_video_library.indexer.VideoIndexer.search`, which weights title above
//! tags above summary above transcript and requires every query term to match.
//! The ranking here is the same weighting over the same index file, used so a UI
//! can filter without spawning Python. It is a *scan*, not the indexer: it
//! returns the same fields, and the CLI remains the reference implementation.

use axum::{
    extract::{Path as AxumPath, Query},
    http::StatusCode,
    response::{IntoResponse, Response},
    routing::{get, post},
    Extension, Json, Router,
};
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::HashSet;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, OnceLock};
use std::time::Duration;
use tokio::sync::Mutex;

use crate::control::{json_error, JobRecord};
use crate::state::SharedState;

/// Root of the library when the operator names none.
pub const VIDEO_USB_PATH_ENV: &str = "ARIA_USB_PATH";
/// Comma-separated host allowlist that replaces [`DEFAULT_SOURCES`].
pub const VIDEO_SOURCES_ENV: &str = "ARIA_VIDEO_SOURCES";
/// Interpreter used to run the downloader.
pub const VIDEO_PYTHON_ENV: &str = "ARIA_PYTHON";
/// Location of the index inside the library root.
pub const VIDEO_INDEX_RELATIVE: &str = "videos/index.json";
/// Downloads that may run at once, per server.
pub const VIDEO_MAX_CONCURRENT_ENV: &str = "ARIA_VIDEO_MAX_CONCURRENT";

/// Default wall-clock ceiling for a download job.
///
/// Comfortably above the downloader's own sub-timeouts (300 s remote probe +
/// 3600 s transfer + 1800 s transcription) so a slow-but-healthy job is not
/// killed and reported as a failure.
pub const VIDEO_DOWNLOAD_TIMEOUT_SECS: u64 = 7200;

/// Default number of concurrent download jobs.
pub const VIDEO_MAX_CONCURRENT_DEFAULT: usize = 2;

/// Hosts accepted when no override is configured.
pub const DEFAULT_SOURCES: &[&str] = &[
    "instagram.com",
    "instagr.am",
    "tiktok.com",
    "youtube.com",
    "youtu.be",
    "x.com",
    "twitter.com",
];

/// Relevance weight per searchable field; mirrors `indexer.FIELD_WEIGHTS`.
const FIELD_WEIGHTS: &[(&str, u32)] = &[
    ("title", 10),
    ("tags", 8),
    ("summary", 5),
    ("agent_notes", 3),
    ("transcript", 2),
];

/// Bounds for `?limit=`.
const LIMIT_MAX: usize = 500;
const LIMIT_DEFAULT: usize = 50;
const SEARCH_LIMIT_DEFAULT: usize = 20;

/// Downloads dispatched but not yet handed to a child process.
static ACTIVE_DOWNLOADS: AtomicUsize = AtomicUsize::new(0);

/// Longest tag or context accepted, to keep index entries and argv sane.
const LABEL_MAX_LEN: usize = 64;

// ---------------------------------------------------------------------------
// Pure helpers — no I/O, unit tested
// ---------------------------------------------------------------------------

/// Split a host list, ignoring case, blanks and duplicates.
pub fn parse_hosts(raw: &str) -> HashSet<String> {
    raw.split(',')
        .map(|host| host.trim().trim_start_matches('.').to_ascii_lowercase())
        .filter(|host| !host.is_empty() && host.contains('.'))
        .collect()
}

/// Hosts this deployment accepts.
pub fn allowed_sources() -> HashSet<String> {
    match std::env::var(VIDEO_SOURCES_ENV) {
        Ok(raw) if !raw.trim().is_empty() => parse_hosts(&raw),
        _ => parse_hosts(&DEFAULT_SOURCES.join(",")),
    }
}

/// Check a URL against the allowlist, returning a caller-facing reason on failure.
pub fn validate_video_url(url: &str) -> Result<(), String> {
    let trimmed = url.trim();
    if trimmed.is_empty() {
        return Err("url is required".to_string());
    }
    if !(trimmed.starts_with("http://") || trimmed.starts_with("https://")) {
        // yt-dlp also speaks file://, smb:// and whatever handlers are
        // registered; only plain web URLs are a video reference.
        return Err("only http(s) URLs are accepted".to_string());
    }
    let host = host_of(trimmed).ok_or_else(|| format!("'{trimmed}' has no host"))?;
    let hosts = allowed_sources();
    if !hosts.iter().any(|allowed| host == *allowed || host.ends_with(&format!(".{allowed}"))) {
        let mut listed = hosts.iter().cloned().collect::<Vec<_>>();
        listed.sort();
        return Err(format!(
            "'{host}' is not an allowed source; allowed: {}",
            listed.join(", ")
        ));
    }
    Ok(())
}

/// Host of an `http(s)` URL, lowercase.
pub fn host_of(url: &str) -> Option<String> {
    let rest = url
        .strip_prefix("https://")
        .or_else(|| url.strip_prefix("http://"))?;
    let authority = rest.split(['/', '?', '#']).next()?;
    let host = authority
        .rsplit('@')
        .next()
        .unwrap_or(authority)
        .split(':')
        .next()
        .unwrap_or(authority);
    (!host.is_empty()).then(|| host.to_ascii_lowercase())
}

/// Normalize one tag or agent label: lowercase, alphanumeric plus `-_`, capped.
pub fn sanitize_label(raw: &str) -> String {
    let cleaned: String = raw
        .trim()
        .to_ascii_lowercase()
        .chars()
        .map(|c| if c.is_ascii_alphanumeric() || c == '-' || c == '_' { c } else { '-' })
        .collect();
    let collapsed = cleaned
        .split('-')
        .filter(|part| !part.is_empty())
        .collect::<Vec<_>>()
        .join("-");
    collapsed.chars().take(LABEL_MAX_LEN).collect()
}

/// Clamp a caller-supplied `?limit=` into a sane band.
pub fn clamp_limit(requested: Option<usize>, fallback: usize) -> usize {
    match requested {
        Some(0) | None => fallback,
        Some(value) => value.min(LIMIT_MAX),
    }
}

/// Default library root when the operator names none and no stick is found.
///
/// Mirrors the Python fallback in `aria_video_library.storage`.
pub fn fallback_root() -> std::path::PathBuf {
    if cfg!(target_os = "windows") {
        if let Ok(local) = std::env::var("LOCALAPPDATA") {
            if !local.trim().is_empty() {
                return std::path::Path::new(&local)
                    .join("ARIA")
                    .join("usb-library");
            }
        }
    }
    if let Ok(xdg) = std::env::var("XDG_DATA_HOME") {
        if !xdg.trim().is_empty() {
            return std::path::Path::new(&xdg).join("aria-usb");
        }
    }
    let home = std::env::var("HOME")
        .or_else(|_| std::env::var("USERPROFILE"))
        .unwrap_or_else(|_| std::env::temp_dir().to_string_lossy().to_string());
    std::path::PathBuf::from(home)
        .join(".local")
        .join("share")
        .join("aria-usb")
}

/// Mounted drive letters to look at when locating the library.
///
/// `std` cannot tell a removable drive from a fixed one without platform APIs,
/// so instead of guessing which volume is the stick this only checks whether
/// each letter holds a library, and only reads: nothing is ever created here.
fn candidate_roots() -> Vec<std::path::PathBuf> {
    let mut roots = Vec::new();
    if cfg!(target_os = "windows") {
        for letter in b'A'..=b'Z' {
            roots.push(std::path::PathBuf::from(format!("{}:\\", letter as char)));
        }
        return roots;
    }
    for base in ["/media", "/mnt", "/run/media", "/Volumes"] {
        if let Ok(entries) = std::fs::read_dir(base) {
            for entry in entries.flatten() {
                roots.push(entry.path());
            }
        }
    }
    roots
}

/// Where this server believes the library lives.
///
/// The order matches `aria_video_library.storage.resolve_usb_root`: the explicit
/// `ARIA_USB_PATH`, then the per-user fallback. When neither holds an index, any
/// mounted drive that does is used, so a stick plugged in after boot is found
/// instead of an empty per-user directory.
pub fn library_root() -> std::path::PathBuf {
    if let Ok(root) = std::env::var(VIDEO_USB_PATH_ENV) {
        if !root.trim().is_empty() {
            return std::path::PathBuf::from(root);
        }
    }
    let fallback = fallback_root();
    if fallback.join(VIDEO_INDEX_RELATIVE).exists() {
        return fallback;
    }
    for root in candidate_roots() {
        if root.join(VIDEO_INDEX_RELATIVE).exists() {
            return root;
        }
    }
    fallback
}

/// Absolute path of `videos/index.json`.
pub fn index_path() -> std::path::PathBuf {
    library_root().join(VIDEO_INDEX_RELATIVE)
}

/// Python interpreter used to run the downloader.
pub fn python_program() -> String {
    std::env::var(VIDEO_PYTHON_ENV)
        .ok()
        .filter(|value| !value.trim().is_empty())
        .unwrap_or_else(|| {
            if cfg!(target_os = "windows") {
                "python".to_string()
            } else {
                "python3".to_string()
            }
        })
}

/// Build the `aria_video_library` command line for one download.
///
/// The URL is a single argv element: nothing here is ever handed to a shell, so
/// a title or tag cannot turn into a command.
///
/// `--root` is passed only when `ARIA_USB_PATH` is set. Forcing this server's
/// guess would override Python's own resolution — including its removable-drive
/// probe — and silently write to the wrong place.
pub fn download_args(
    url: &str,
    tags: &[String],
    agent_type: Option<&str>,
    context: &str,
    transcribe: bool,
) -> Vec<String> {
    let mut args = vec!["-m".to_string(), "aria_video_library".to_string()];
    if let Ok(root) = std::env::var(VIDEO_USB_PATH_ENV) {
        if !root.trim().is_empty() {
            args.push("--root".to_string());
            args.push(root);
        }
    }
    args.push("download".to_string());
    args.push(url.to_string());
    for tag in tags {
        let clean = sanitize_label(tag);
        if !clean.is_empty() {
            args.push("--tag".to_string());
            args.push(clean);
        }
    }
    if let Some(agent) = agent_type.map(sanitize_label).filter(|value| !value.is_empty()) {
        args.push("--agent".to_string());
        args.push(agent);
    }
    if !context.trim().is_empty() {
        args.push("--context".to_string());
        args.push(context.chars().take(240).collect());
    }
    if !transcribe {
        args.push("--no-transcribe".to_string());
    }
    args.push("--json".to_string());
    args
}

/// Parse `index.json` into video entries.
///
/// Unknown fields and missing fields are both tolerated: the file is written by
/// a Python process that may be a different version than this server, and a
/// schema mismatch should degrade the listing, not fail it.
pub fn parse_index(raw: &str) -> Result<Vec<Value>, String> {
    let data: Value = serde_json::from_str(raw).map_err(|err| format!("invalid JSON: {err}"))?;
    let videos = data
        .get("videos")
        .and_then(Value::as_array)
        .ok_or_else(|| "no 'videos' array in the index".to_string())?;
    Ok(videos
        .iter()
        .filter(|entry| entry.is_object() && entry["id"].is_string())
        .cloned()
        .collect())
}

/// Score one entry against every query term; `0` means a term was missing.
///
/// Requiring all terms is what makes a two-word query a filter rather than an
/// OR, and it matches `indexer._score`. Each field is scored at its own weight:
/// checking tags inside the title's iteration would score a tags-only hit at
/// the title weight and drift from the Python ranking.
pub fn score_entry(entry: &Value, terms: &[String]) -> u32 {
    if terms.is_empty() {
        return 0;
    }
    let tags = entry
        .get("tags")
        .and_then(Value::as_array)
        .map(|values| {
            values
                .iter()
                .filter_map(Value::as_str)
                .map(|tag| tag.to_lowercase())
                .collect::<Vec<_>>()
        })
        .unwrap_or_default();
    let mut total = 0;
    for term in terms {
        let mut best = 0;
        for (name, weight) in FIELD_WEIGHTS {
            let hit = if *name == "tags" {
                tags.iter().any(|tag| tag.contains(term))
            } else {
                entry
                    .get(*name)
                    .and_then(Value::as_str)
                    .unwrap_or("")
                    .to_lowercase()
                    .contains(term)
            };
            if hit {
                best = best.max(*weight);
            }
        }
        if best == 0 {
            return 0;
        }
        total += best;
    }
    total
}

/// Lowercase word list of a query, matching `indexer._tokens`.
pub fn query_terms(query: &str) -> Vec<String> {
    let mut terms: Vec<String> = query
        .split(|c: char| !c.is_alphanumeric())
        .map(|token| token.to_lowercase())
        .filter(|token| token.chars().count() > 1)
        .collect();
    terms.sort();
    terms.dedup();
    terms
}

/// Rank entries by relevance, best first, id as the tie-break.
///
/// Stored `relevance_score` settles ties, mirroring `VideoIndexer.search`, so
/// agent feedback recorded by the Python side changes the order here too.
pub fn rank_entries(entries: &[Value], query: &str, limit: usize) -> Vec<Value> {
    let terms = query_terms(query);
    if terms.is_empty() {
        return Vec::new();
    }
    let mut scored: Vec<(u32, f64, String, Value)> = entries
        .iter()
        .filter_map(|entry| {
            let score = score_entry(entry, &terms);
            if score == 0 {
                return None;
            }
            let id = entry
                .get("id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .to_string();
            let relevance = entry
                .get("relevance_score")
                .and_then(Value::as_f64)
                .unwrap_or(0.0);
            Some((score, relevance, id, entry.clone()))
        })
        .collect();
    scored.sort_by(|a, b| {
        b.0.cmp(&a.0)
            .then_with(|| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal))
            .then_with(|| a.2.cmp(&b.2))
    });
    scored
        .into_iter()
        .take(limit)
        .map(|(_, _, _, entry)| entry)
        .collect()
}

/// Drop the transcript from an entry unless the caller asked for it.
///
/// The full text of every video turns a 50-entry listing into megabytes of JSON
/// on a polling UI, for a field almost no reader wants.
pub fn project_entry(entry: &Value, include_transcript: bool) -> Value {
    if include_transcript {
        return entry.clone();
    }
    let mut slim = entry.clone();
    if let Some(object) = slim.as_object_mut() {
        object.remove("transcript");
    }
    slim
}

// ---------------------------------------------------------------------------
// Request shapes
// ---------------------------------------------------------------------------

/// Query for the listing and search routes.
#[derive(Debug, Deserialize)]
pub struct ListQuery {
    pub limit: Option<usize>,
    #[serde(alias = "query")]
    pub q: Option<String>,
    /// `1` keeps the full transcript in the response.
    #[serde(default)]
    pub transcript: Option<bool>,
}

/// Body of `POST /api/videos/download`.
#[derive(Debug, Deserialize)]
pub struct DownloadRequest {
    pub url: String,
    #[serde(default)]
    pub tags: Vec<String>,
    #[serde(default)]
    pub agent_type: Option<String>,
    #[serde(default)]
    pub context: String,
    /// Defaults to true; only `false` skips transcription.
    #[serde(default)]
    pub transcribe: Option<bool>,
}

// ---------------------------------------------------------------------------
// Routes
// ---------------------------------------------------------------------------

/// Route table for the video reference library.
pub fn router() -> Router<()> {
    Router::new()
        .route("/api/videos/list", get(list))
        .route("/api/videos/search", get(search))
        .route("/api/videos/download", post(download))
        .route("/api/videos/:id", get(show))
}

/// Parsed index plus the mtime/size it was built from, so a re-read can be
/// skipped without trusting a cache that cannot notice a USB swap.
#[derive(Clone)]
struct CachedIndex {
    mtime_ns: u128,
    len: u64,
    entries: Arc<Vec<Value>>,
}

static INDEX_CACHE: OnceLock<tokio::sync::RwLock<Option<CachedIndex>>> = OnceLock::new();

fn index_cache() -> &'static tokio::sync::RwLock<Option<CachedIndex>> {
    INDEX_CACHE.get_or_init(|| tokio::sync::RwLock::new(None))
}

async fn read_index() -> Result<(std::path::PathBuf, Arc<Vec<Value>>), (StatusCode, String)> {
    let path = index_path();
    let stamp = match tokio::fs::metadata(&path).await {
        Ok(meta) => match meta.modified() {
            Ok(modified) => (
                modified
                    .duration_since(std::time::UNIX_EPOCH)
                    .map(|d| d.as_nanos())
                    .unwrap_or_default(),
                meta.len(),
            ),
            // No mtime available: fall through and read every time.
            Err(_) => (u128::MAX, 0),
        },
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => {
            *index_cache().write().await = None;
            return Ok((path, Arc::new(Vec::new())));
        }
        Err(err) => {
            return Err((
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("cannot stat {}: {err}", path.display()),
            ))
        }
    };

    {
        let guard = index_cache().read().await;
        if let Some(cached) = guard.as_ref() {
            if cached.mtime_ns == stamp.0 && cached.len == stamp.1 {
                return Ok((path, cached.entries.clone()));
            }
        }
    }

    let entries = match tokio::fs::read_to_string(&path).await {
        Ok(raw) => match parse_index(&raw) {
            Ok(entries) => Arc::new(entries),
            Err(reason) => {
                return Err((
                    StatusCode::INTERNAL_SERVER_ERROR,
                    format!("{} is not a usable video index: {reason}", path.display()),
                ))
            }
        },
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => Arc::new(Vec::new()),
        Err(err) => {
            return Err((
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("cannot read {}: {err}", path.display()),
            ))
        }
    };

    *index_cache().write().await = Some(CachedIndex {
        mtime_ns: stamp.0,
        len: stamp.1,
        entries: entries.clone(),
    });
    Ok((path, entries))
}

/// `GET /api/videos/list` — every indexed video, newest first.
async fn list(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Query(params): Query<ListQuery>,
) -> Response {
    {
        let guard = state.lock().await;
        guard.increment_requests().await;
    }
    let (path, entries) = match read_index().await {
        Ok(value) => value,
        Err((code, reason)) => return json_error(code, "index_unreadable", &reason),
    };
    let include_transcript = params.transcript.unwrap_or(false);
    let limit = clamp_limit(params.limit, LIMIT_DEFAULT);
    let mut videos: Vec<Value> = entries.iter().map(|entry| project_entry(entry, include_transcript)).collect();
    videos.sort_by(|a, b| {
        let left = a.get("date_downloaded").and_then(Value::as_str).unwrap_or("");
        let right = b.get("date_downloaded").and_then(Value::as_str).unwrap_or("");
        right.cmp(left)
    });
    let total = videos.len();
    videos.truncate(limit);

    Json(json!({
        "videos": videos,
        "count": videos.len(),
        "total": total,
        "truncated": total > videos.len(),
        "transcript_included": include_transcript,
        "index_file": path.to_string_lossy(),
        "library_root": library_root().to_string_lossy(),
        "server": "ARIA-Axum-8002",
    }))
    .into_response()
}

/// `GET /api/videos/search?q=…` — ranked hits from the same index.
async fn search(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Query(params): Query<ListQuery>,
) -> Response {
    {
        let guard = state.lock().await;
        guard.increment_requests().await;
    }
    let query = params.q.clone().unwrap_or_default();
    if query_terms(&query).is_empty() {
        return json_error(
            StatusCode::BAD_REQUEST,
            "invalid_query",
            "q must contain at least one word of two or more characters",
        );
    }
    let (path, entries) = match read_index().await {
        Ok(value) => value,
        Err((code, reason)) => return json_error(code, "index_unreadable", &reason),
    };
    let limit = clamp_limit(params.limit, SEARCH_LIMIT_DEFAULT);
    let include_transcript = params.transcript.unwrap_or(false);
    let ranked = rank_entries(&entries, &query, limit);
    let videos: Vec<Value> = ranked
        .iter()
        .map(|entry| project_entry(entry, include_transcript))
        .collect();

    Json(json!({
        "videos": videos,
        "count": videos.len(),
        "query": query,
        "transcript_included": include_transcript,
        "index_file": path.to_string_lossy(),
        "note": "ranking mirrors aria_video_library.indexer; the CLI is the reference implementation",
        "server": "ARIA-Axum-8002",
    }))
    .into_response()
}

/// `GET /api/videos/{id}` — one entry, or 404.
async fn show(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    AxumPath(id): AxumPath<String>,
    Query(params): Query<ListQuery>,
) -> Response {
    {
        let guard = state.lock().await;
        guard.increment_requests().await;
    }
    let (_, entries) = match read_index().await {
        Ok(value) => value,
        Err((code, reason)) => return json_error(code, "index_unreadable", &reason),
    };
    let include_transcript = params.transcript.unwrap_or(false);
    match entries
        .iter()
        .find(|entry| entry.get("id").and_then(Value::as_str) == Some(id.as_str()))
    {
        Some(entry) => Json(json!({
            "video": project_entry(entry, include_transcript),
            "transcript_included": include_transcript,
            "server": "ARIA-Axum-8002",
        }))
        .into_response(),
        None => json_error(StatusCode::NOT_FOUND, "unknown_video", "no such video"),
    }
}

/// Whether the configured interpreter can import the library.
///
/// Checked before answering `202`: a `202` promises work that can only fail when
/// the default `python` is not the environment the package is installed in, and
/// the caller would only learn that by polling a doomed job.
async fn downloader_importable(program: &str) -> bool {
    tokio::process::Command::new(program)
        .args(["-c", "import aria_video_library"])
        .stdin(std::process::Stdio::null())
        .output()
        .await
        .map(|result| result.status.success())
        .unwrap_or(false)
}

/// How many downloads may run at once.
pub fn max_concurrent_downloads() -> usize {
    std::env::var(VIDEO_MAX_CONCURRENT_ENV)
        .ok()
        .and_then(|raw| raw.trim().parse::<usize>().ok())
        .filter(|value| *value > 0)
        .unwrap_or(VIDEO_MAX_CONCURRENT_DEFAULT)
}

/// `POST /api/videos/download` — dispatch the downloader, answer `202`.
///
/// The download itself belongs to `aria_video_library`; this route validates the
/// request, then hands it to the CLI as a detached job so the client can poll
/// `/api/control/jobs/{id}` instead of holding a socket open for ten minutes.
async fn download(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(payload): Json<DownloadRequest>,
) -> Response {
    {
        let guard = state.lock().await;
        guard.increment_requests().await;
    }

    if let Err(reason) = validate_video_url(&payload.url) {
        return json_error(StatusCode::BAD_REQUEST, "invalid_url", &reason);
    }
    if payload.tags.len() > 16 {
        return json_error(
            StatusCode::BAD_REQUEST,
            "too_many_tags",
            "at most 16 tags per video",
        );
    }

    let program = python_program();
    if !downloader_importable(&program).await {
        return json_error(
            StatusCode::SERVICE_UNAVAILABLE,
            "downloader_unavailable",
            &format!(
                "'{program}' cannot import aria_video_library; set {VIDEO_PYTHON_ENV} to the \
                 interpreter the package is installed in (and PYTHONPATH to the repo root)"
            ),
        );
    }

    // One process per request, each writing to the same removable volume: without
    // a cap, a token holder can queue an hour of downloads per minute and starve
    // every other one through `InsufficientSpaceError`.
    let control = state.lock().await.control.clone();
    let active = ACTIVE_DOWNLOADS.fetch_add(1, Ordering::SeqCst);
    if active >= max_concurrent_downloads() {
        ACTIVE_DOWNLOADS.fetch_sub(1, Ordering::SeqCst);
        return json_error(
            StatusCode::TOO_MANY_REQUESTS,
            "too_many_downloads",
            &format!(
                "{active} downloads already running (limit {})",
                max_concurrent_downloads()
            ),
        );
    }

    let transcribe = payload.transcribe.unwrap_or(true);
    let args = download_args(
        payload.url.trim(),
        &payload.tags,
        payload.agent_type.as_deref(),
        &payload.context,
        transcribe,
    );
    let budget = Duration::from_secs(VIDEO_DOWNLOAD_TIMEOUT_SECS);

    let record: JobRecord = control
        .dispatch_job("video-download", &program, &args, Some(budget))
        .await;
    let job_id = record.id.clone();
    ACTIVE_DOWNLOADS.fetch_sub(1, Ordering::SeqCst);

    tracing::info!(
        target: "aria::videos",
        url = %payload.url,
        job = %job_id,
        "video download dispatched"
    );

    Json(json!({
        "status": "accepted",
        "job_id": job_id,
        "kind": "video-download",
        "url": payload.url.trim(),
        "transcribe": transcribe,
        "timeout_seconds": budget.as_secs(),
        "poll": format!("/api/control/jobs/{job_id}"),
        "library_root": library_root().to_string_lossy(),
        "server": "ARIA-Axum-8002",
    }))
    .into_response()
}

#[cfg(test)]
mod tests {
    use super::*;

    // --- url validation --------------------------------------------------

    #[test]
    fn accepts_known_hosts() {
        for url in [
            "https://www.instagram.com/reel/abc/",
            "https://tiktok.com/@user/video/1",
            "https://youtu.be/abc",
        ] {
            assert!(validate_video_url(url).is_ok(), "{url} should be allowed");
        }
    }

    #[test]
    fn rejects_other_hosts() {
        let err = validate_video_url("https://evil.example.com/x.mp4").unwrap_err();
        assert!(err.contains("not an allowed source"), "{err}");
    }

    #[test]
    fn rejects_non_http_schemes() {
        for url in ["file:///etc/passwd", "ftp://instagram.com/a", "instagram.com/reel/x"] {
            assert!(validate_video_url(url).is_err(), "{url} should be rejected");
        }
    }

    #[test]
    fn rejects_empty_url() {
        assert!(validate_video_url("   ").is_err());
    }

    // --- host parsing ---------------------------------------------------

    #[test]
    fn host_of_strips_credentials_and_port() {
        assert_eq!(
            host_of("https://user:pw@Instagram.com:443/reel/x"),
            Some("instagram.com".to_string())
        );
        assert_eq!(host_of("not a url"), None);
    }

    #[test]
    fn parse_hosts_normalizes_and_dedupes() {
        let hosts = parse_hosts(" .Instagram.com , tiktok.com, ,tiktok.com ");
        assert_eq!(hosts.len(), 2);
        assert!(hosts.contains("instagram.com"));
    }

    // --- labels ---------------------------------------------------------

    #[test]
    fn sanitize_label_cleans_and_caps() {
        assert_eq!(sanitize_label("  Agent Image Analysis!! "), "agent-image-analysis");
        assert_eq!(sanitize_label(""), "");
        assert_eq!(sanitize_label(&"a".repeat(200)).len(), LABEL_MAX_LEN);
    }

    // --- limits ---------------------------------------------------------

    #[test]
    fn clamp_limit_uses_fallback_and_ceiling() {
        assert_eq!(clamp_limit(None, 20), 20);
        assert_eq!(clamp_limit(Some(0), 20), 20);
        assert_eq!(clamp_limit(Some(5), 20), 5);
        assert_eq!(clamp_limit(Some(100_000), 20), LIMIT_MAX);
    }

    // --- command line ---------------------------------------------------

    #[test]
    fn download_args_are_argv_only_and_complete() {
        let args = download_args(
            "https://instagram.com/reel/x",
            &["AI Tools".to_string(), "  ".to_string()],
            Some("Agent Image Analysis"),
            "reference for orb work",
            false,
        );
        assert_eq!(&args[0..2], &["-m".to_string(), "aria_video_library".to_string()]);
        assert!(args.windows(2).any(|pair| pair == ["--tag".to_string(), "ai-tools".to_string()]));
        assert!(args
            .windows(2)
            .any(|pair| pair == ["--agent".to_string(), "agent-image-analysis".to_string()]));
        assert!(args.iter().any(|arg| arg == "--no-transcribe"));
        assert!(args.iter().any(|arg| arg == "--json"));
        // No shell metacharacter survives into a label.
        assert!(!args.iter().any(|arg| arg.contains(';') || arg.contains('`')));
    }

    // --- index parsing --------------------------------------------------

    #[test]
    fn parse_index_accepts_partial_entries() {
        let raw = r#"{"videos":[{"id":"a"},{"id":123},{"title":"no id"}]}"#;
        let entries = parse_index(raw).unwrap();
        assert_eq!(entries.len(), 1);
        assert_eq!(entries[0]["id"], "a");
    }

    #[test]
    fn parse_index_rejects_garbage() {
        assert!(parse_index("not json").is_err());
        assert!(parse_index(r#"{"items":[]}"#).is_err());
    }

    // --- ranking --------------------------------------------------------

    fn entry(id: &str, title: &str, tags: &str, summary: &str, transcript: &str) -> Value {
        json!({
            "id": id,
            "title": title,
            "tags": tags.split(' ').filter(|t| !t.is_empty()).collect::<Vec<_>>(),
            "summary": summary,
            "agent_notes": "",
            "transcript": transcript,
        })
    }

    #[test]
    fn query_terms_need_two_characters() {
        assert_eq!(query_terms("AI a Tools"), vec!["ai".to_string(), "tools".to_string()]);
        assert!(query_terms("a ???").is_empty());
    }

    #[test]
    fn title_match_outranks_transcript_match() {
        let entries = vec![
            entry("b", "unrelated", "", "", "a long talk about agents"),
            entry("a", "agents explained", "", "", ""),
        ];
        let ranked = rank_entries(&entries, "agents", 10);
        assert_eq!(ranked[0]["id"], "a");
        assert_eq!(ranked[1]["id"], "b");
    }

    #[test]
    fn tags_outrank_summary() {
        let entries = vec![
            entry("a", "t", "agents", "unrelated text", ""),
            entry("b", "t", "", "agents appear here", ""),
        ];
        let ranked = rank_entries(&entries, "agents", 10);
        assert_eq!(ranked[0]["id"], "a");
    }

    #[test]
    fn a_title_hit_outranks_a_tags_hit() {
        // Regression: tags were checked inside every field's iteration, so a
        // tags-only match scored the title weight and tied with a real title.
        let entries = vec![
            entry("tagged", "unrelated", "agents", "", ""),
            entry("titled", "agents in the title", "", "", ""),
        ];
        let ranked = rank_entries(&entries, "agents", 10);
        assert_eq!(ranked[0]["id"], "titled");
    }

    #[test]
    fn relevance_score_breaks_score_ties() {
        let mut low = entry("low", "agents", "", "", "");
        low["relevance_score"] = json!(0.1);
        let mut high = entry("high", "agents", "", "", "");
        high["relevance_score"] = json!(0.9);
        let ranked = rank_entries(&[low, high], "agents", 10);
        assert_eq!(ranked[0]["id"], "high");
    }

    #[test]
    fn project_entry_drops_the_transcript_unless_asked() {
        let raw = json!({"id": "a", "transcript": "long text", "title": "t"});
        assert!(project_entry(&raw, true).get("transcript").is_some());
        assert!(project_entry(&raw, false).get("transcript").is_none());
        assert_eq!(project_entry(&raw, false)["title"], "t");
    }

    #[test]
    fn index_path_is_built_from_the_documented_relative_path() {
        assert!(VIDEO_INDEX_RELATIVE.contains("index.json"));
        assert_eq!(
            index_path(),
            library_root().join(std::path::Path::new(VIDEO_INDEX_RELATIVE))
        );
    }

    #[test]
    fn concurrency_limit_defaults_and_overrides() {
        // The env var is process-wide, so only the unset path is asserted here.
        if std::env::var(VIDEO_MAX_CONCURRENT_ENV).is_err() {
            assert_eq!(max_concurrent_downloads(), VIDEO_MAX_CONCURRENT_DEFAULT);
        }
    }

    #[test]
    fn every_term_must_match() {
        let entries = vec![entry("a", "agents", "tools", "", "")];
        assert!(rank_entries(&entries, "agents quantum", 10).is_empty());
        assert_eq!(rank_entries(&entries, "agents tools", 10).len(), 1);
    }

    #[test]
    fn limit_truncates_and_empty_query_returns_nothing() {
        let entries = vec![entry("a", "agents", "", "", ""), entry("b", "agents", "", "", "")];
        assert_eq!(rank_entries(&entries, "agents", 1).len(), 1);
        assert!(rank_entries(&entries, "", 10).is_empty());
    }
}
