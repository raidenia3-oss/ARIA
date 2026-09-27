//! Learning routes: rules, record-error, suppress.
use axum::routing::get;
use axum::Router;

pub fn router() -> Router<()> {
    Router::new()
        .route("/api/learning/rules", get(rules))
        .route("/api/learning/record-error", get(record_error))
        .route("/api/learning/suppress", get(suppress))
}

async fn rules() -> &'static str { "rules placeholder" }
async fn record_error() -> &'static str { "record error placeholder" }
async fn suppress() -> &'static str { "suppress placeholder" }