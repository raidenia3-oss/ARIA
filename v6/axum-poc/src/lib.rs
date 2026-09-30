//! ARIA Axum Migration Framework — Phase L.4 Architecture
//!
//! This module defines the route organization for the full v6.0 migration.
//! Routes are organized into modules mirroring the FastAPI backend structure.
//!
//! Migration strategy:
//! 1. Route groups extracted as separate modules
//! 2. Shared state via Arc<Mutex<...>>
//! 3. Type-safe extractors (Json, Path, Query)
//! 4. Middleware: tracing, auth, rate limiting
//! 5. Gradual cutover: FastAPI (8000) → Axum (8001) → Axum (8000)

use axum::{
    extract::State,
    middleware,
    routing::get,
    Router,
};
use std::sync::Arc;
use tokio::sync::Mutex;
use tower_http::{cors::CorsLayer, trace::TraceLayer};

use crate::state::SharedState;

pub mod core;
pub mod chat;
pub mod skills;
pub mod agents;
pub mod memory;
pub mod voice;
pub mod vision;
pub mod system;
pub mod files;
pub mod web;
pub mod proactive;
pub mod evolution;
pub mod learning;
pub mod computer;
pub mod github;
pub mod social;
pub mod auth;
pub mod admin;
pub mod self_improvement;
pub mod daemon;
pub mod state;
pub mod orb;
pub mod version;
pub mod control;

/// CORS policy for the native orb and the desktop shell.
///
/// Auth is a bearer header rather than a cookie, so credentials stay off; the
/// rate-limit headers are exposed so clients can back off before a 429.
fn cors_layer() -> CorsLayer {
    use axum::http::HeaderName;
    use tower_http::cors::Any;
    CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any)
        .expose_headers([
            HeaderName::from_static("x-ratelimit-limit"),
            HeaderName::from_static("x-ratelimit-remaining"),
            HeaderName::from_static("retry-after"),
        ])
}

/// Build the complete Axum router with all route groups.
/// Phase L.4: Full migration architecture.
///
/// `state` is handed to the security middleware (see [`auth::guard`]) for token
/// verification and per-IP rate limiting, and is also layered as an `Extension`
/// so route handlers can reach it through their existing signature.
pub fn create_full_router(state: Arc<Mutex<SharedState>>) -> Router {
    let app = Router::new()
        .merge(core::router())
        .merge(chat::router())
        .merge(skills::router())
        .merge(agents::router())
        .merge(memory::router())
        .merge(voice::router())
        .merge(vision::router())
        .merge(system::router())
        .merge(files::router())
        .merge(web::router())
        .merge(proactive::router())
        .merge(evolution::router())
        .merge(learning::router())
        .merge(computer::router())
        .merge(github::router())
        .merge(social::router())
        .merge(auth::router())
        .merge(admin::router())
        .merge(self_improvement::router())
        .merge(daemon::router())
        .merge(control::router())
        .route("/ws", get(state::websocket_handler));

    app.layer(middleware::from_fn(move |request, next| {
        let state = state.clone();
        async move { auth::guard(State(state), request, next).await }
    }))
    .layer(TraceLayer::new_for_http())
    .layer(cors_layer())
}
