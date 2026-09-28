//! ARIA Axum Migration Framework — Phase L.4 Architecture
//!
//! This module defines the route organization for the full v6.0 migration.
//! Routes are organized into modules mirroring the FastAPI backend structure.
//!
//! Migration strategy:
//! 1. Route groups extracted as separate modules
//! 2. Shared state via Arc<Mutex<...>> or DashMap
//! 3. Type-safe extractors (Json, Path, Query)
//! 4. Middleware: tracing, auth, rate limiting
//! 5. Gradual cutover: FastAPI (8000) → Axum (8001) → Axum (8000)

use axum::{
    routing::{get, post, put, delete},
    Router, middleware,
};
use tower::ServiceBuilder;
use tower_http::{cors::CorsLayer, trace::TraceLayer};

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

/// Build the complete Axum router with all route groups.
/// Phase L.4: Full migration architecture.
pub fn create_full_router() -> Router {
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
        .merge(daemon::router());

    // Middleware stack
    app.layer(
        ServiceBuilder::new()
            .layer(TraceLayer::new_for_http())
            .layer(CorsLayer::permissive())
            .build(),
    )
}

/// Route count estimate by module (mirrors FastAPI structure).
pub const ROUTE_ESTIMATE: &[(&str, usize)] = &[
    ("core", 12),
    ("chat", 8),
    ("skills", 15),
    ("agents", 25),
    ("memory", 20),
    ("voice", 8),
    ("vision", 6),
    ("system", 18),
    ("files", 12),
    ("web", 10),
    ("proactive", 8),
    ("evolution", 6),
    ("learning", 8),
    ("computer", 15),
    ("github", 12),
    ("social", 10),
    ("auth", 10),
    ("admin", 8),
    ("self_improvement", 6),
];

/// Total estimated routes: ~237 (plus health/status = ~245)
pub fn total_routes() -> usize {
    ROUTE_ESTIMATE.iter().map(|(_, n)| n).sum()
}