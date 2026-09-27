//! Social routes: collect, transcribe, analyze, classify, research, save, library.
use axum::routing::get;
use axum::Router;

pub fn router() -> Router<()> {
    Router::new()
        .route("/api/social-research/collect", get(collect))
        .route("/api/social-research/transcribe", get(transcribe))
        .route("/api/social-research/analyze", get(analyze))
        .route("/api/social-research/classify", get(classify))
        .route("/api/social-research/research", get(research))
        .route("/api/social-research/save", get(save))
        .route("/api/social-research/library", get(library))
        .route("/api/video-analyze", get(video_analyze))
        .route("/api/video-analyze/batch", get(video_batch))
}

async fn collect() -> &'static str { "social collect placeholder" }
async fn transcribe() -> &'static str { "social transcribe placeholder" }
async fn analyze() -> &'static str { "social analyze placeholder" }
async fn classify() -> &'static str { "social classify placeholder" }
async fn research() -> &'static str { "social research placeholder" }
async fn save() -> &'static str { "social save placeholder" }
async fn library() -> &'static str { "social library placeholder" }
async fn video_analyze() -> &'static str { "video analyze placeholder" }
async fn video_batch() -> &'static str { "video batch placeholder" }