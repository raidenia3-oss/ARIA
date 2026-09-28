//! ARIA Axum POC — Full Migration Server
//! Phase L.4: Axum (Rust) backend running alongside FastAPI for gradual cutover.
//!
//! Runs on port 8002 to avoid conflict with FastAPI on port 8001.
//! USB-ARIA daemon endpoints are available at /api/pc/state and /api/daemon/*.

use aria_axum_poc::create_full_router;

#[tokio::main]
async fn main() {
    println!("🚀 ARIA Axum Server (Phase L.4) starting...");
    
    let app = create_full_router();

    let listener = tokio::net::TcpListener::bind("127.0.0.1:8002")
        .await
        .expect("Failed to bind to 127.0.0.1:8002");

    println!("🚀 ARIA Axum Server (Phase L.4) running on http://127.0.0.1:8002");
    println!("   Full router with daemon endpoints for USB-ARIA");
    println!("   - GET  /health");
    println!("   - GET  /api/system/status");
    println!("   - POST /api/chat");
    println!("   - POST /api/pc/state (USB-ARIA)");
    println!("   - POST /api/daemon/task (USB-ARIA)");
    println!("   - POST /api/daemon/result (USB-ARIA)");
    println!("   - POST /api/daemon/heartbeat (USB-ARIA)");
    println!("");
    println!("   Port: 8002 (FastAPI running on 8001)");

    axum::serve(listener, app)
        .await
        .expect("Failed to serve Axum app");
}