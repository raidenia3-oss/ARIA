//! Web routes: search, weather, automation.
use axum::routing::get;
use axum::Router;

pub fn router() -> Router<()> {
    Router::new()
        .route("/api/web/search", get(search))
        .route("/api/web/weather", get(weather))
        .route("/api/web/automation", get(automation))
}

async fn search() -> &'static str { "search placeholder" }
async fn weather() -> &'static str { "weather placeholder" }
async fn automation() -> &'static str { "automation placeholder" }