//! Auth routes: JWT, RBAC, sessions.
use axum::routing::get;
use axum::Router;

pub fn router() -> Router<()> {
    Router::new()
        .route("/api/auth/login", get(login))
        .route("/api/auth/register", get(register))
        .route("/api/auth/logout", get(logout))
        .route("/api/auth/refresh", get(refresh))
        .route("/api/auth/profile", get(profile))
        .route("/api/auth/permissions", get(permissions))
        .route("/api/auth/roles", get(roles))
        .route("/api/auth/sessions", get(sessions))
        .route("/api/auth/webhooks", get(webhooks))
        .route("/api/auth/validate", get(validate))
}

async fn login() -> &'static str { "auth login placeholder" }
async fn register() -> &'static str { "auth register placeholder" }
async fn logout() -> &'static str { "auth logout placeholder" }
async fn refresh() -> &'static str { "auth refresh placeholder" }
async fn profile() -> &'static str { "auth profile placeholder" }
async fn permissions() -> &'static str { "auth permissions placeholder" }
async fn roles() -> &'static str { "auth roles placeholder" }
async fn sessions() -> &'static str { "auth sessions placeholder" }
async fn webhooks() -> &'static str { "auth webhooks placeholder" }
async fn validate() -> &'static str { "auth validate placeholder" }