// Whisper.cpp STT module for local speech-to-text
// Provides GPU-accelerated transcription using whisper-rs

use std::path::Path;
use whisper_rs::{FullParams, SamplingStrategy, WhisperContext, WhisperContextParameters};
use serde::{Deserialize, Serialize};
use std::time::Instant;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WhisperModelInfo {
    pub name: String,
    pub path: String,
    pub size_mb: u64,
    pub languages: Vec<String>,
    pub loaded: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TranscriptionRequest {
    pub model: String,
    pub audio_data: Vec<f32>,  // 16kHz mono audio samples
    pub language: Option<String>,
    pub translate: Option<bool>,
    pub word_timestamps: Option<bool>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TranscriptionResponse {
    pub text: String,
    pub language: String,
    pub duration_ms: u64,
    pub segments: Vec<TranscriptionSegment>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TranscriptionSegment {
    pub start_ms: u64,
    pub end_ms: u64,
    pub text: String,
    pub tokens: Vec<u32>,
    pub avg_logprob: f32,
}

pub struct WhisperEngine {
    contexts: std::collections::HashMap<String, WhisperContext>,
    models_dir: std::path::PathBuf,
}

impl WhisperEngine {
    pub fn new(models_dir: Option<std::path::PathBuf>) -> Self {
        let models_dir = models_dir.unwrap_or_else(|| {
            dirs::data_dir()
                .unwrap_or_else(|| std::path::PathBuf::from("."))
                .join("aria")
                .join("models")
                .join("whisper")
        });
        
        std::fs::create_dir_all(&models_dir).ok();
        
        Self {
            contexts: std::collections::HashMap::new(),
            models_dir,
        }
    }

    pub fn get_available_models() -> Vec<WhisperModelInfo> {
        vec![
            WhisperModelInfo {
                name: "tiny".to_string(),
                path: "models/ggml-tiny.bin".to_string(),
                size_mb: 39,
                languages: vec!["en".to_string(), "es".to_string(), "multilingual".to_string()],
                loaded: false,
            },
            WhisperModelInfo {
                name: "base".to_string(),
                path: "models/ggml-base.bin".to_string(),
                size_mb: 74,
                languages: vec!["en".to_string(), "es".to_string(), "multilingual".to_string()],
                loaded: false,
            },
            WhisperModelInfo {
                name: "small".to_string(),
                path: "models/ggml-small.bin".to_string(),
                size_mb: 244,
                languages: vec!["en".to_string(), "es".to_string(), "multilingual".to_string()],
                loaded: false,
            },
            WhisperModelInfo {
                name: "medium".to_string(),
                path: "models/ggml-medium.bin".to_string(),
                size_mb: 769,
                languages: vec!["en".to_string(), "es".to_string(), "multilingual".to_string()],
                loaded: false,
            },
            WhisperModelInfo {
                name: "large-v3".to_string(),
                path: "models/ggml-large-v3.bin".to_string(),
                size_mb: 1550,
                languages: vec!["multilingual".to_string()],
                loaded: false,
            },
        ]
    }

    pub fn load_model(&mut self, model_name: &str) -> Result<(), String> {
        if self.contexts.contains_key(model_name) {
            return Ok(());
        }

        let model_path = self.models_dir.join(format!("ggml-{}.bin", model_name));
        
        if !model_path.exists() {
            return Err(format!("Model file not found: {:?}. Download from https://huggingface.co/ggerganov/whisper.cpp", model_path));
        }

        let params = WhisperContextParameters::default();
        let ctx = WhisperContext::new_with_params(&model_path, params)
            .map_err(|e| format!("Failed to load whisper model: {}", e))?;

        self.contexts.insert(model_name.to_string(), ctx);
        Ok(())
    }

    pub fn transcribe(&self, request: TranscriptionRequest) -> Result<TranscriptionResponse, String> {
        let ctx = self.contexts.get(&request.model)
            .ok_or_else(|| format!("Model not loaded: {}", request.model))?;

        let start = Instant::now();

        let mut params = FullParams::new(SamplingStrategy::Greedy { best_of: 1 });
        
        if let Some(lang) = &request.language {
            params.set_language(Some(lang));
        }
        
        params.set_translate(request.translate.unwrap_or(false));
        params.set_print_special(false);
        params.set_print_progress(false);
        params.set_print_realtime(false);
        params.set_print_timestamps(request.word_timestamps.unwrap_or(true));
        
        // Get number of threads
        params.set_n_threads(std::thread::available_parallelism().map(|n| n.get()).unwrap_or(4) as i32);

        let mut state = ctx.create_state().map_err(|e| e.to_string())?;
        
        state.full(params, &request.audio_data)
            .map_err(|e| format!("Transcription failed: {}", e))?;

        let num_segments = state.full_n_segments()
            .map_err(|e| e.to_string())?;

        let mut segments = Vec::new();
        let mut full_text = String::new();

        for i in 0..num_segments {
            let text = state.full_get_segment_text(i)
                .map_err(|e| e.to_string())?;
            
            let start_ts = state.full_get_segment_t0(i)
                .map_err(|e| e.to_string())?;
            let end_ts = state.full_get_segment_t1(i)
                .map_err(|e| e.to_string())?;

            let tokens: Vec<u32> = (0..state.full_get_segment_n_tokens(i).unwrap_or(0))
                .filter_map(|j| state.full_get_segment_token(i, j).ok())
                .collect();

            let avg_logprob = state.full_get_segment_avg_logprob(i)
                .map_err(|e| e.to_string())?;

            segments.push(TranscriptionSegment {
                start_ms: start_ts as u64 * 10,
                end_ms: end_ts as u64 * 10,
                text: text.clone(),
                tokens,
                avg_logprob,
            });

            full_text.push_str(&text);
            full_text.push(' ');
        }

        let detected_language = state.full_lang_id(0)
            .map_err(|e| e.to_string())?
            .map(|l| l.to_string())
            .unwrap_or_else(|| "unknown".to_string());

        Ok(TranscriptionResponse {
            text: full_text.trim().to_string(),
            language: detected_language,
            duration_ms: start.elapsed().as_millis() as u64,
            segments,
        })
    }

    pub fn is_loaded(&self, model_name: &str) -> bool {
        self.contexts.contains_key(model_name)
    }

    pub fn unload_model(&mut self, model_name: &str) -> bool {
        self.contexts.remove(model_name).is_some()
    }

    pub fn list_loaded_models(&self) -> Vec<String> {
        self.contexts.keys().cloned().collect()
    }
}

// Tauri commands for Whisper STT
#[tauri::command]
async fn whisper_init(models_dir: Option<String>) -> Result<String, String> {
    let dir = models_dir.map(std::path::PathBuf::from);
    let _engine = WhisperEngine::new(dir);
    Ok("Whisper engine initialized".to_string())
}

#[tauri::command]
async fn whisper_list_models() -> Result<Vec<WhisperModelInfo>, String> {
    Ok(WhisperEngine::get_available_models())
}

#[tauri::command]
async fn whisper_load(model: String) -> Result<bool, String> {
    let models_dir = dirs::data_dir()
        .unwrap_or_else(|| std::path::PathBuf::from("."))
        .join("aria")
        .join("models")
        .join("whisper");
    
    let mut engine = WhisperEngine::new(Some(models_dir));
    engine.load_model(&model)?;
    Ok(true)
}

#[tauri::command]
async fn whisper_transcribe(request: TranscriptionRequest) -> Result<TranscriptionResponse, String> {
    let models_dir = dirs::data_dir()
        .unwrap_or_else(|| std::path::PathBuf::from("."))
        .join("aria")
        .join("models")
        .join("whisper");
    
    let engine = WhisperEngine::new(Some(models_dir));
    
    // Ensure model is loaded
    if !engine.is_loaded(&request.model) {
        engine.load_model(&request.model)?;
    }
    
    engine.transcribe(request)
}

#[tauri::command]
async fn whisper_unload(model: String) -> Result<bool, String> {
    let models_dir = dirs::data_dir()
        .unwrap_or_else(|| std::path::PathBuf::from("."))
        .join("aria")
        .join("models")
        .join("whisper");
    
    let mut engine = WhisperEngine::new(Some(models_dir));
    Ok(engine.unload_model(&model))
}