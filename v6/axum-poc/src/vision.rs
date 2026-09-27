//! Vision routes: capture, analyze, last.
use axum::routing::get;
use axum::Router;

pub fn router() -> Router<()> {
    Router::new()
        .route("/api/vision/capture", get(capture))
        .route("/api/vision/analyze", get(analyze))
        .route("/api/vision/last", get(last))
}

async fn capture() -> &'static str { "capture placeholder" }
async fn analyze() -> &'static str { "analyze placeholder" }
async fn last() -> &'static str { "last placeholder" }