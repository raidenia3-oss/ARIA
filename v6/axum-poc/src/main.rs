//! ARIA Axum POC — Full Migration Server
//! Phase L.4: Axum (Rust) backend running alongside FastAPI for gradual cutover.
//!
//! Runs on port 8002 to avoid conflict with FastAPI on port 8001.
//! USB-ARIA daemon endpoints are available at /api/pc/state and /api/daemon/*.
//! The native 3D orb launches automatically on startup (no manual command needed).

use aria_axum_poc::create_full_router;
use aria_axum_poc::state::SharedState;
use aria_axum_poc::daemon::orb_running;
use aria_axum_poc::orb::OrbPhase;
use axum::Extension;
use std::sync::Arc;
use std::sync::atomic::Ordering;
use tokio::sync::Mutex;

#[tokio::main]
async fn main() {
    println!("🚀 ARIA Axum Server (Phase L.4) starting...");
    
    // Initialize shared state
    let db_path = std::env::var("ARIA_DB_PATH")
        .unwrap_or_else(|_| "C:\\Users\\User\\Downloads\\AURA\\aura.db".to_string());
    
    let shared_state = Arc::new(Mutex::new(SharedState::new(&db_path)));
    println!("   DB Path: {}", db_path);
    
    let app = create_full_router()
        .layer(Extension(shared_state.clone()));

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

    // Auto-launch the 3D orb window on startup (no manual command needed)
    orb_running().store(true, Ordering::SeqCst);
    
    // Sync initial phase to Idle
    {
        let phase_guard = aria_axum_poc::daemon::orb_phase();
        *phase_guard.lock().unwrap() = OrbPhase::Idle;
    }
    
    // The orb window runs on its own thread with internal rendering loop
    let stop_flag = Arc::new(std::sync::atomic::AtomicBool::new(true));
    std::thread::spawn(move || {
        aria_axum_poc::orb::run_orb_window(stop_flag);
    });
    
    println!("   Orb visualization auto-started (native GPU window)");

    // Start the autonomy daemon in the background (idle detection -> self-improvement)
    let autonomy_state = shared_state.clone();
    tokio::spawn(async move {
        aria_axum_poc::daemon::start_autonomy_daemon_inner(autonomy_state).await;
    });
    println!("   Autonomy daemon started (idle detection + self-improvement)");

    axum::serve(listener, app)
        .await
        .expect("Failed to serve Axum app");
}
