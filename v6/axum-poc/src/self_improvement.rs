//! Self-improvement routes: cycle, status, proposals.
use axum::routing::get;
use axum::Router;

pub fn router() -> Router<()> {
    Router::new()
        .route("/api/self-improvement/start", get(start))
        .route("/api/self-improvement/status", get(status))
        .route("/api/self-improvement/proposals", get(proposals))
        .route("/api/self-improvement/commit", get(commit))
        .route("/api/self-improvement/analyze-prs", get(analyze_prs))
        .route("/api/self-improvement/triaging", get(triaging))
}

async fn start() -> &'static str { "self-improvement start placeholder" }
async fn status() -> &'static str { "self-improvement status placeholder" }
async fn proposals() -> &'static str { "self-improvement proposals placeholder" }
async fn commit() -> &'static str { "self-improvement commit placeholder" }
async fn analyze_prs() -> &'static str { "self-improvement analyze prs placeholder" }
async fn triaging() -> &'static str { "self-improvement triaging placeholder" }