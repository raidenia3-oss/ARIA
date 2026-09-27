//! Proactive routes: alerts, reminders, owner state.
use axum::routing::get;
use axum::Router;

pub fn router() -> Router<()> {
    Router::new()
        .route("/api/proactive/alert", get(alert))
        .route("/api/proactive/reminder", get(reminder))
        .route("/api/proactive/owner-state", get(owner_state))
        .route("/api/proactive/alerts", get(alerts))
        .route("/api/proactive/reminders", get(reminders))
}

async fn alert() -> &'static str { "alert placeholder" }
async fn reminder() -> &'static str { "reminder placeholder" }
async fn owner_state() -> &'static str { "owner state placeholder" }
async fn alerts() -> &'static str { "alerts placeholder" }
async fn reminders() -> &'static str { "reminders placeholder" }