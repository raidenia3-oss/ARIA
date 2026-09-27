//! Admin routes: system management, users, settings.
use axum::routing::get;
use axum::Router;

pub fn router() -> Router<()> {
    Router::new()
        .route("/api/admin/users", get(users))
        .route("/api/admin/roles", get(roles))
        .route("/api/admin/permissions", get(permissions))
        .route("/api/admin/settings", get(settings))
        .route("/api/admin/system", get(system))
        .route("/api/admin/logs", get(logs))
        .route("/api/admin/backup", get(backup))
        .route("/api/admin/restore", get(restore))
}

async fn users() -> &'static str { "admin users placeholder" }
async fn roles() -> &'static str { "admin roles placeholder" }
async fn permissions() -> &'static str { "admin permissions placeholder" }
async fn settings() -> &'static str { "admin settings placeholder" }
async fn system() -> &'static str { "admin system placeholder" }
async fn logs() -> &'static str { "admin logs placeholder" }
async fn backup() -> &'static str { "admin backup placeholder" }
async fn restore() -> &'static str { "admin restore placeholder" }