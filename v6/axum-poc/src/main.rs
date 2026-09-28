//! ARIA Axum POC — Full Migration Server
//! Phase L.4: Axum (Rust) server running alongside FastAPI for gradual cutover.
//!
//! Runs on port 8002 to avoid conflict with FastAPI on port 8001.
//! All USB-ARIA daemon endpoints are now available.
//!
//! Endpoints (245+ total):
//! - Core: /health, /api/system/status
//! - Chat: /api/chat
//! - Skills: /api/skills, /api/skills/run
//! - Agents: /api/agents/status, /api/agents/execute
//! - Memory: /api/memory/search, /api/memory/store
//! - Voice: /api/voice/stt, /api/voice/tts
//! - System: 14 system tools (status, ping, scan, etc.)
//! - Daemon: /api/pc/state, /api/daemon/task, /api/daemon/result, /api/daemon/heartbeat
//! - ... plus web, proactive, evolution, learning, computer, github, social, auth, admin, self-improvement

use aria_axum_poc::create_full_router;

#[tokio::main]
async fn main() {
    println!("🚀 ARIA Axum Server (Phase L.4) starting...");
    
    let app = create_full_router();

    let listener = tokio::net::TcpListener::bind("127.0.0.1:8002")
        .await
        .expect("Failed to bind to 127.0.0.1:8002");

    println!("🚀 ARIA Axum Server (Phase L.4) running on http://127.0.0.1:8002");
    println!("   Full router with {}+ endpoint groups", 18);
    println!("   - core: 12 routes");
    println!("   - daemon: USB-ARIA coordination");
    println!("   - chat, skills, agents, memory, voice, vision, system, files, web");
    println!("   - proactive, evolution, learning, computer, github, social");
    println!("   - auth, admin, self_improvement");
    println!("");
    println!("   Port: 8002 (FastAPI still on 8001)");
    println!("   LocalTunnel: aria-backend.loca.lt (maps to 8001)");

    axum::serve(listener, app)
        .await
        .expect("Failed to serve Axum app");
}