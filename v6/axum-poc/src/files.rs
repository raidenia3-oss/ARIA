//! Files routes: list, read, write.
use axum::routing::get;
use axum::Router;

pub fn router() -> Router<()> {
    Router::new()
        .route("/api/files/list", get(list_files))
        .route("/api/files/read", get(read_file))
        .route("/api/files/write", get(write_file))
}

async fn list_files() -> &'static str { "list placeholder" }
async fn read_file() -> &'static str { "read placeholder" }
async fn write_file() -> &'static str { "write placeholder" }