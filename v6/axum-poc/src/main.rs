//! ARIA Axum POC — Full Migration Server
//! Phase L.4: Axum (Rust) backend running alongside FastAPI for gradual cutover.
//!
//! Runs on port 8002 to avoid conflict with FastAPI on port 8001.
//! USB-ARIA daemon endpoints are available at /api/pc/state and /api/daemon/*.
//! The native 3D orb is opt-in: it does NOT auto-start (so the server is
//! headless by default) and is controlled through /api/orb/{start,stop,state,phase}.

use aria_axum_poc::create_full_router;
use aria_axum_poc::state::SharedState;
use aria_axum_poc::orb::OrbPhase;
use axum::Extension;
use std::net::SocketAddr;
use std::sync::Arc;
use tokio::sync::Mutex;
// `with` on Registry and `init` are extension traits, not inherent methods.
use tracing_subscriber::layer::SubscriberExt;
use tracing_subscriber::util::SubscriberInitExt;

#[tokio::main]
async fn main() {
    // ARIA runs headlessly in the background, so keep the global level at INFO
    // and only raise verbosity for ARIA's own targets. tower_http stays at INFO
    // to avoid a trace line per request. ControlLogLayer sits on the same
    // registry, so /api/control/logs sees exactly the events the operator sees.
    let filter = tracing_subscriber::EnvFilter::builder()
        .with_default_directive(tracing::Level::INFO.into())
        .parse_lossy(
            "aria=debug,aria::auth=debug,aria::ratelimit=debug,aria::control=debug",
        );
    tracing_subscriber::registry()
        .with(filter)
        .with(
            tracing_subscriber::fmt::layer()
                .with_target(true)
                .with_level(true),
        )
        .with(aria_axum_poc::control::ControlLogLayer)
        .init();

    println!("🚀 ARIA Axum Server (Phase L.4) starting...");
    
    // Initialize shared state
    let db_path = std::env::var("ARIA_DB_PATH")
        .unwrap_or_else(|_| "C:\\Users\\User\\Downloads\\AURA\\aura.db".to_string());
    
    let shared_state = Arc::new(Mutex::new(SharedState::new(&db_path)));
    println!("   DB Path: {}", db_path);

    // The security middleware needs the state before the Extension layer exists,
    // so hand it a clone.
    let app = create_full_router(shared_state.clone())
        .layer(Extension(shared_state.clone()));

    let listener = tokio::net::TcpListener::bind("0.0.0.0:8002")
        .await
        .expect("Failed to bind to 0.0.0.0:8002");

    println!("🚀 ARIA Axum Server (Phase L.4) running on http://0.0.0.0:8002");
    println!("   Full router with daemon endpoints for USB-ARIA");
    println!("   - GET  /health");
    println!("   - GET  /api/system/status");
    println!("   - POST /api/chat");
    println!("   - POST /api/pc/state (USB-ARIA)");
    println!("   - POST /api/daemon/task (USB-ARIA)");
    println!("   - POST /api/daemon/result (USB-ARIA)");
    println!("   - POST /api/daemon/heartbeat (USB-ARIA)");
    println!("   - GET  /api/control/status | /services | /logs | /config | /plugins");
    println!("   - WS   /api/control/logs/stream");
    println!("   - POST /api/control/config | /restart | /upgrade");
    println!("   - GET  /api/videos/list | /search?q= | /:id");
    println!("   - POST /api/videos/download (USB reference library)");
    println!("");
    println!("   Port: 8002 (FastAPI running on 8001)");

    // Headless by default: the orb is optional visual feedback and must never
    // block or destabilize the HTTP server. Set ARIA_ORB_AUTOSTART=1 to open it
    // at boot, otherwise use POST /api/orb/start.
    if std::env::var("ARIA_ORB_AUTOSTART")
        .map(|v| v == "1" || v.eq_ignore_ascii_case("true"))
        .unwrap_or(false)
    {
        match aria_axum_poc::orb::spawn_orb_window() {
            Ok(()) => {
                println!("   Orb visualization started (native GPU window, ARIA_ORB_AUTOSTART=1)");
            }
            Err(e) => {
                println!("   Orb autostart failed ({}). Server continues headless.", e);
            }
        }
    } else {
        println!("   Orb window: NOT started (headless). Start it with POST /api/orb/start");
    }

    // Sync initial phase to Idle
    {
        let phase_guard = aria_axum_poc::daemon::orb_phase();
        *phase_guard.lock().unwrap() = OrbPhase::Idle;
    }

    // Start the autonomy daemon in the background (idle detection -> self-improvement)
    let autonomy_state = shared_state.clone();
    tokio::spawn(async move {
        aria_axum_poc::daemon::start_autonomy_daemon_inner(autonomy_state).await;
    });
    println!("   Autonomy daemon started (idle detection + self-improvement)");

    axum::serve(
        listener,
        app.into_make_service_with_connect_info::<SocketAddr>(),
    )
        .await
        .expect("Failed to serve Axum app");
}
