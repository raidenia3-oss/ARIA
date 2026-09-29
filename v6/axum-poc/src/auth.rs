//! Auth routes and the reusable security middleware for the ARIA Axum backend.
//!
//! This module owns three things that other route modules rely on:
//!
//! 1. [`BearerToken`] — a `FromRequestParts` extractor that hands a handler the
//!    caller identity established by [`guard`]. Handlers never re-parse headers.
//! 2. [`guard`] — the `RequireAuth` middleware: per-IP rate limiting, bearer
//!    token validation on every non-public path, and structured auth-failure logs.
//! 3. [`router`] — the `/api/auth/*` route group, including token validation.
//!
//! The active key comes from `ARIA_API_KEY`. When that variable is unset or
//! blank, a random key is generated at startup and logged (see
//! [`crate::state::AuthConfig::from_env`]). Comparing a presented token against
//! the key is constant time.

use axum::{
    extract::{ConnectInfo, FromRequestParts, State},
    http::{header, request::Parts, HeaderMap, HeaderValue, StatusCode},
    middleware::Next,
    response::{IntoResponse, Response},
    routing::{get, post},
    Extension, Json, Router,
};
use serde_json::json;
use std::net::SocketAddr;
use std::sync::Arc;
use tokio::sync::Mutex;

use crate::state::{
    check_rate_limit, AuthConfig, RateDecision, SharedState, API_KEY_ENV, RATE_LIMIT_MAX,
};

/// Paths reachable without a token. `/health` is used by liveness probes and
/// `/ws` by the native orb, neither of which can attach a bearer header.
pub const PUBLIC_PATHS: &[&str] = &["/", "/health", "/ws"];

/// Credential-bootstrap endpoints. These mint tokens, so demanding a token to
/// reach them would deadlock the very first login. Everything else under
/// `/api/*` — including `/api/auth/validate` and the other `/api/auth/*` reads —
/// is protected.
pub const PUBLIC_AUTH_PATHS: &[&str] = &[
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/refresh",
];

/// Header a non-browser client may use instead of `Authorization: Bearer`.
pub const API_KEY_HEADER: &str = "x-api-key";

/// Subject reported for any token that matches the configured API key. The POC
/// has a single-machine key, so there is one implicit principal.
const DEFAULT_SUBJECT: &str = "ARIA-USB";

/// Scopes granted to a valid token.
const DEFAULT_SCOPES: &[&str] = &["read", "write", "execute", "admin"];

/// Identity attached to a request by [`guard`] once its token is accepted.
#[derive(Clone, Debug)]
pub struct AuthenticatedUser {
    /// Principal name for the authenticated token.
    pub subject: String,
    /// Role granted to the principal.
    pub role: String,
    /// True when the server's key was randomly generated, i.e. a token issued
    /// against an earlier boot no longer matches.
    pub ephemeral_key: bool,
}

impl AuthenticatedUser {
    /// JSON view of the principal, safe to return to the caller.
    fn to_json(&self) -> serde_json::Value {
        json!({
            "subject": self.subject,
            "role": self.role,
            "scopes": DEFAULT_SCOPES,
            "ephemeral_key": self.ephemeral_key,
        })
    }
}

/// Extractor yielding the caller identity established by [`guard`].
///
/// Handlers that take `BearerToken` implicitly require authentication: if the
/// middleware did not run (path is public) or rejected the request, extraction
/// fails with `401 {"error":"unauthorized"}`.
#[derive(Clone, Debug)]
pub struct BearerToken(pub AuthenticatedUser);

#[axum::async_trait]
impl<S> FromRequestParts<S> for BearerToken {
    type Rejection = ApiError;
    async fn from_request_parts(parts: &mut Parts, _state: &S) -> Result<Self, Self::Rejection> {
        match parts.extensions.get::<AuthenticatedUser>() {
            Some(user) => Ok(BearerToken(user.clone())),
            None => {
                tracing::warn!(
                    target: "aria::auth",
                    path = %parts.uri.path(),
                    "extractor used on unauthenticated request"
                );
                Err(ApiError::unauthorized())
            }
        }
    }
}

/// Uniform JSON error used by the extractor and the middleware.
#[derive(Debug)]
pub struct ApiError {
    status: StatusCode,
    code: &'static str,
    retry_after: Option<u64>,
}

impl ApiError {
    /// `401 {"error":"unauthorized"}` plus a `WWW-Authenticate: Bearer` hint.
    pub fn unauthorized() -> Self {
        Self {
            status: StatusCode::UNAUTHORIZED,
            code: "unauthorized",
            retry_after: None,
        }
    }

    /// `429 {"error":"rate_limited"}` with a `Retry-After` hint.
    pub fn rate_limited(retry_after: u64) -> Self {
        Self {
            status: StatusCode::TOO_MANY_REQUESTS,
            code: "rate_limited",
            retry_after: Some(retry_after),
        }
    }
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let mut response = (
            self.status,
            Json(json!({ "error": self.code, "status": self.status.as_u16() })),
        )
            .into_response();
        let headers = response.headers_mut();
        headers.insert(header::CACHE_CONTROL, HeaderValue::from_static("no-store"));
        if self.status == StatusCode::UNAUTHORIZED {
            headers.insert(
                header::WWW_AUTHENTICATE,
                HeaderValue::from_static("Bearer realm=\"aria\", header=\"Authorization\""),
            );
        }
        if let Some(retry_after) = self.retry_after {
            if let Ok(value) = HeaderValue::from_str(&retry_after.to_string()) {
                headers.insert(header::RETRY_AFTER, value);
            }
        }
        response
    }
}

/// Pull the token out of `Authorization: Bearer <token>`, falling back to the
/// `X-API-Key` header. Scheme matching is case-insensitive per RFC 7235.
pub fn extract_bearer(headers: &HeaderMap) -> Option<&str> {
    if let Some(raw) = headers.get(header::AUTHORIZATION).and_then(|v| v.to_str().ok()) {
        let (scheme, token) = raw.split_once(' ')?;
        if scheme.eq_ignore_ascii_case("bearer") {
            let token = token.trim();
            if !token.is_empty() {
                return Some(token);
            }
        }
    }
    headers
        .get(API_KEY_HEADER)
        .and_then(|v| v.to_str().ok())
        .map(str::trim)
        .filter(|token| !token.is_empty())
}

/// True when `path` may be reached without a bearer token.
pub fn is_public_path(path: &str) -> bool {
    if PUBLIC_PATHS.contains(&path) {
        return true;
    }
    PUBLIC_AUTH_PATHS.iter().any(|public| {
        path.strip_prefix(public)
            .map(|rest| rest.is_empty() || rest.starts_with('/'))
            .unwrap_or(false)
    })
}

/// Best-effort client IP: real socket peer when `ConnectInfo` is wired up,
/// then proxy headers, then a shared bucket.
fn client_ip(req: &axum::extract::Request) -> String {
    if let Some(ConnectInfo(addr)) = req.extensions().get::<ConnectInfo<SocketAddr>>() {
        return addr.ip().to_string();
    }
    for header_name in ["x-forwarded-for", "x-real-ip"] {
        if let Some(value) = req.headers().get(header_name).and_then(|v| v.to_str().ok()) {
            if let Some(first) = value.split(',').next() {
                let ip = first.trim();
                if !ip.is_empty() {
                    return ip.to_string();
                }
            }
        }
    }
    "unknown".to_string()
}

/// The `RequireAuth` middleware: rate limit, then authenticate.
///
/// Applies to every path; public paths from [`is_public_path`] skip only the
/// token check. On success the resolved [`AuthenticatedUser`] is inserted into
/// request extensions for [`BearerToken`] and the inner handler.
pub async fn guard(
    State(state): State<Arc<Mutex<SharedState>>>,
    request: axum::extract::Request,
    next: Next,
) -> Response {
    let method = request.method().clone();
    let path = request.uri().path().to_string();
    let ip = client_ip(&request);

    // Clone the rate-limit map so the state lock is not held across the check.
    let rate_limits = { state.lock().await.rate_limits.clone() };
    let remaining = match check_rate_limit(&rate_limits, &ip).await {
        RateDecision::Allow { remaining } => remaining,
        RateDecision::Deny { retry_after } => {
            tracing::warn!(
                target: "aria::ratelimit",
                method = %method,
                path = %path,
                ip = %ip,
                retry_after,
                "rate limit exceeded"
            );
            return ApiError::rate_limited(retry_after).into_response();
        }
    };

    if is_public_path(&path) {
        return stamp_rate_limit(next.run(request).await, remaining);
    }

    let presented = extract_bearer(request.headers());
    let (accepted, ephemeral) = {
        let state = state.lock().await;
        let accepted = presented.map(|token| state.verify_token(token)).unwrap_or(false);
        (accepted, state.is_generated_key())
    };

    if !accepted {
        let reason = if presented.is_some() {
            "invalid_token"
        } else {
            "missing_token"
        };
        let total = { state.lock().await.record_auth_failure().await };
        tracing::warn!(
            target: "aria::auth",
            method = %method,
            path = %path,
            ip = %ip,
            reason,
            total_failures = total,
            "authentication rejected"
        );
        println!("🚫 AUTH {reason}: {method} {path} from {ip} (total failures: {total})");
        return ApiError::unauthorized().into_response();
    }

    tracing::debug!(
        target: "aria::auth",
        method = %method,
        path = %path,
        ip = %ip,
        "request authenticated"
    );

    let mut request = request;
    request.extensions_mut().insert(AuthenticatedUser {
        subject: DEFAULT_SUBJECT.to_string(),
        role: "admin".to_string(),
        ephemeral_key: ephemeral,
    });

    stamp_rate_limit(next.run(request).await, remaining)
}

/// Attach the current window's budget so clients can back off before a 429.
fn stamp_rate_limit(mut response: Response, remaining: u32) -> Response {
    if let Ok(value) = HeaderValue::from_str(&remaining.to_string()) {
        response.headers_mut().insert("x-ratelimit-limit", HeaderValue::from_static("100"));
        response.headers_mut().insert("x-ratelimit-remaining", value);
    }
    response
}

pub fn router() -> Router<()> {
    Router::new()
        .route("/api/auth/login", post(login))
        .route("/api/auth/register", post(register))
        .route("/api/auth/logout", post(logout))
        .route("/api/auth/refresh", post(refresh))
        .route("/api/auth/profile", get(profile))
        .route("/api/auth/permissions", get(permissions))
        .route("/api/auth/roles", get(roles))
        .route("/api/auth/sessions", get(sessions))
        .route("/api/auth/webhooks", get(webhooks))
        .route("/api/auth/validate", get(validate).post(validate_token))
}

async fn login(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<serde_json::Value>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    state.increment_requests().await;

    let username = req.get("username").and_then(|v| v.as_str()).unwrap_or("");
    let token = state.api_key().to_string();

    Json(json!({
        "status": "ok",
        "username": username,
        "token": token,
        "token_type": "Bearer",
        "server": "ARIA-Axum-8002",
    }))
}

async fn register(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<serde_json::Value>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    state.increment_requests().await;
    
    let username = req.get("username").and_then(|v| v.as_str()).unwrap_or("");
    
    Json(json!({
        "status": "ok",
        "username": username,
        "registered": true,
        "server": "ARIA-Axum-8002",
    }))
}

async fn logout() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "logged_out": true,
        "server": "ARIA-Axum-8002",
    }))
}

async fn refresh() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "token": "axum-jwt-refreshed-token",
        "server": "ARIA-Axum-8002",
    }))
}

async fn profile(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
) -> Json<serde_json::Value> {
    let state = state.lock().await;
    state.increment_requests().await;
    Json(json!({
        "status": "ok",
        "user": DEFAULT_SUBJECT,
        "role": "admin",
        "server": "ARIA-Axum-8002",
    }))
}

async fn permissions() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "permissions": DEFAULT_SCOPES,
        "server": "ARIA-Axum-8002",
    }))
}

async fn roles() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "roles": ["admin", "user", "viewer"],
        "server": "ARIA-Axum-8002",
    }))
}

async fn sessions() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "sessions": [],
        "server": "ARIA-Axum-8002",
    }))
}

async fn webhooks() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "webhooks": [],
        "server": "ARIA-Axum-8002",
    }))
}

/// `GET /api/auth/validate` — liveness check for a stored token.
async fn validate(user: BearerToken) -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "valid": true,
        "method": "header",
        "user": user.0.to_json(),
        "server": "ARIA-Axum-8002",
    }))
}

/// `POST /api/auth/validate` — validate the bearer header, or a token supplied
/// in the body.
///
/// The body form exists for the mobile sync client, which wants to check a token
/// it just restored from storage without first wiring it into a header. Because
/// the middleware already admitted this request, verifying a second token does
/// not widen access; a mismatch is reported, not served.
async fn validate_token(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    user: BearerToken,
    body: Option<Json<serde_json::Value>>,
) -> Json<serde_json::Value> {
    state.lock().await.increment_requests().await;

    let candidate = body
        .as_ref()
        .and_then(|Json(body)| body.get("token"))
        .and_then(|value| value.as_str())
        .map(str::to_string);

    let (valid, method) = match candidate {
        Some(token) => {
            let matched = { state.lock().await.verify_token(&token) };
            (matched, "body")
        }
        None => (true, "header"),
    };

    Json(json!({
        "status": "ok",
        "valid": valid,
        "method": method,
        "user": user.0.to_json(),
        "server": "ARIA-Axum-8002",
    }))
}

/// Auth metadata safe to expose on a status route: never the key itself.
pub fn auth_summary(config: &AuthConfig) -> serde_json::Value {
    json!({
        "scheme": "Bearer",
        "env_var": API_KEY_ENV,
        "key_source": config.source_label(),
        "rate_limit_per_minute": RATE_LIMIT_MAX,
    })
}
