//! GitHub routes: repos, PRs, issues, webhooks.
use axum::routing::get;
use axum::Router;

pub fn router() -> Router<()> {
    Router::new()
        .route("/api/github/repos", get(repos))
        .route("/api/github/prs", get(prs))
        .route("/api/github/issues", get(issues))
        .route("/api/github/webhooks", get(webhooks))
        .route("/api/github/auto-pr/test", get(auto_pr_test))
}

async fn repos() -> &'static str { "github repos placeholder" }
async fn prs() -> &'static str { "github prs placeholder" }
async fn issues() -> &'static str { "github issues placeholder" }
async fn webhooks() -> &'static str { "github webhooks placeholder" }
async fn auto_pr_test() -> &'static str { "auto pr test placeholder" }