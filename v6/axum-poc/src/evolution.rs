//! Evolution routes: metrics, record, evolve.
use axum::routing::get;
use axum::Router;

pub fn router() -> Router<()> {
    Router::new()
        .route("/api/evolution/metrics", get(metrics))
        .route("/api/evolution/record", get(record))
        .route("/api/evolution/evolve", get(evolve))
}

async fn metrics() -> &'static str { "metrics placeholder" }
async fn record() -> &'static str { "record placeholder" }
async fn evolve() -> &'static str { "evolve placeholder" }