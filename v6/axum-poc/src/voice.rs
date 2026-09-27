//! Voice routes: STT, TTS, wake word, listen.
use axum::routing::get;
use axum::Router;

pub fn router() -> Router<()> {
    Router::new()
        .route("/api/voice/stt", get(stt_status))
        .route("/api/voice/tts", get(tts_status))
        .route("/api/voice/wake", get(wake_status))
        .route("/api/voice/listen", get(listen_status))
        .route("/api/voice/status", get(voice_status))
}

async fn stt_status() -> &'static str { "stt placeholder" }
async fn tts_status() -> &'static str { "tts placeholder" }
async fn wake_status() -> &'static str { "wake placeholder" }
async fn listen_status() -> &'static str { "listen placeholder" }
async fn voice_status() -> &'static str { "voice status placeholder" }