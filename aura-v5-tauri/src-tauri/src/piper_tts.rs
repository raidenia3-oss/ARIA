// Piper TTS module for offline neural text-to-speech
// Provides streaming synthesis with multiple voice support

use std::path::Path;
use std::process::{Command, Stdio};
use std::io::{Write, BufReader, BufRead};
use serde::{Deserialize, Serialize};
use std::time::Instant;
use std::sync::Arc;
use tokio::sync::Mutex;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PiperVoice {
    pub name: String,
    pub language: String,
    pub quality: String,  // "low", "medium", "high"
    pub model_path: String,
    pub config_path: String,
    pub sample_rate: u32,
    pub speaker_id: Option<u32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TTSRequest {
    pub voice: String,
    pub text: String,
    pub output_path: Option<String>,
    pub stream: Option<bool>,
    pub speed: Option<f32>,
    pub noise_scale: Option<f32>,
    pub noise_w: Option<f32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TTSResponse {
    pub audio_path: Option<String>,
    pub audio_data: Option<Vec<u8>>,  // For streaming
    pub sample_rate: u32,
    pub duration_ms: u64,
    pub latency_ms: u64,
}

pub struct PiperEngine {
    voices: std::collections::HashMap<String, PiperVoice>,
    models_dir: std::path::PathBuf,
    piper_binary: std::path::PathBuf,
}

impl PiperEngine {
    pub fn new(models_dir: Option<std::path::PathBuf>) -> Result<Self, String> {
        let models_dir = models_dir.unwrap_or_else(|| {
            dirs::data_dir()
                .unwrap_or_else(|| std::path::PathBuf::from("."))
                .join("aria")
                .join("models")
                .join("piper")
        });
        
        std::fs::create_dir_all(&models_dir).map_err(|e| e.to_string())?;
        
        // Find piper binary
        let piper_binary = Self::find_piper_binary()?;
        
        let mut engine = Self {
            voices: std::collections::HashMap::new(),
            models_dir,
            piper_binary,
        };
        
        engine.discover_voices();
        Ok(engine)
    }

    fn find_piper_binary() -> Result<std::path::PathBuf, String> {
        // Check common locations
        let candidates = vec![
            "piper",
            "piper.exe",
            "./piper",
            "./piper.exe",
        ];
        
        for candidate in candidates {
            if let Ok(output) = Command::new(candidate).arg("--version").output() {
                if output.status.success() {
                    return Ok(std::path::PathBuf::from(candidate));
                }
            }
        }
        
        // Return default, will fail at runtime if not found
        Ok(std::path::PathBuf::from("piper"))
    }

    fn discover_voices(&mut self) {
        // Scan models directory for .onnx files
        if let Ok(entries) = std::fs::read_dir(&self.models_dir) {
            for entry in entries.flatten() {
                let path = entry.path();
                if path.extension().and_then(|s| s.to_str()) == Some("onnx") {
                    let stem = path.file_stem().and_then(|s| s.to_str()).unwrap_or("");
                    
                    // Look for corresponding .onnx.json config
                    let config_path = path.with_extension("onnx.json");
                    
                    let (language, quality) = Self::parse_voice_name(stem);
                    
                    let voice = PiperVoice {
                        name: stem.to_string(),
                        language,
                        quality,
                        model_path: path.display().to_string(),
                        config_path: config_path.display().to_string(),
                        sample_rate: 22050,  // Default, will be read from config
                        speaker_id: None,
                    };
                    
                    self.voices.insert(stem.to_string(), voice);
                }
            }
        }
        
        // Add default voices if none found
        if self.voices.is_empty() {
            self.add_default_voices();
        }
    }

    fn parse_voice_name(name: &str) -> (String, String) {
        // Parse names like "en_US-lessac-medium", "es_MX-clara-low"
        let parts: Vec<&str> = name.split('-').collect();
        if parts.len() >= 3 {
            (parts[0..2].join("-"), parts[2].to_string())
        } else {
            ("unknown".to_string(), "medium".to_string())
        }
    }

    fn add_default_voices(&mut self) {
        let defaults = vec![
            ("en_US-lessac-medium", "en-US", "medium"),
            ("en_US-amy-low", "en-US", "low"),
            ("es_MX-clara-medium", "es-MX", "medium"),
            ("es_MX-dalia-low", "es-MX", "low"),
        ];
        
        for (name, lang, qual) in defaults {
            let model_path = self.models_dir.join(format!("{}.onnx", name));
            let config_path = self.models_dir.join(format!("{}.onnx.json", name));
            
            if model_path.exists() && config_path.exists() {
                let voice = PiperVoice {
                    name: name.to_string(),
                    language: lang.to_string(),
                    quality: qual.to_string(),
                    model_path: model_path.display().to_string(),
                    config_path: config_path.display().to_string(),
                    sample_rate: 22050,
                    speaker_id: None,
                };
                self.voices.insert(name.to_string(), voice);
            }
        }
    }

    pub fn list_voices(&self) -> Vec<PiperVoice> {
        self.voices.values().cloned().collect()
    }

    pub fn synthesize(&self, request: TTSRequest) -> Result<TTSResponse, String> {
        let start = Instant::now();
        
        let voice = self.voices.get(&request.voice)
            .ok_or_else(|| format!("Voice not found: {}", request.voice))?;

        let output_path = request.output_path.clone().unwrap_or_else(|| {
            std::env::temp_dir().join(format!("aria_tts_{}.wav", uuid::Uuid::new_v4()))
                .display().to_string()
        });

        let mut cmd = Command::new(&self.piper_binary);
        cmd.arg("--model").arg(&voice.model_path);
        cmd.arg("--config").arg(&voice.config_path);
        cmd.arg("--output_file").arg(&output_path);
        
        if let Some(speed) = request.speed {
            cmd.arg("--length_scale").arg(speed.to_string());
        }
        if let Some(noise_scale) = request.noise_scale {
            cmd.arg("--noise_scale").arg(noise_scale.to_string());
        }
        if let Some(noise_w) = request.noise_w {
            cmd.arg("--noise_w").arg(noise_w.to_string());
        }
        if let Some(speaker_id) = voice.speaker_id {
            cmd.arg("--speaker").arg(speaker_id.to_string());
        }
        
        cmd.stdin(Stdio::piped());
        cmd.stdout(Stdio::piped());
        cmd.stderr(Stdio::piped());

        let mut child = cmd.spawn().map_err(|e| format!("Failed to spawn piper: {}", e))?;
        
        // Write text to stdin
        if let Some(stdin) = child.stdin.as_mut() {
            stdin.write_all(request.text.as_bytes()).map_err(|e| e.to_string())?;
        }
        
        let output = child.wait_with_output().map_err(|e| e.to_string())?;
        
        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            return Err(format!("Piper synthesis failed: {}", stderr));
        }

        // Read generated audio file
        let audio_data = if request.stream.unwrap_or(false) {
            Some(std::fs::read(&output_path).map_err(|e| e.to_string())?)
        } else {
            None
        };

        let latency_ms = start.elapsed().as_millis() as u64;

        Ok(TTSResponse {
            audio_path: Some(output_path),
            audio_data,
            sample_rate: voice.sample_rate,
            duration_ms: 0,  // Would need to parse WAV header
            latency_ms,
        })
    }

    pub fn synthesize_streaming(&self, request: TTSRequest) -> Result<std::process::Child, String> {
        let voice = self.voices.get(&request.voice)
            .ok_or_else(|| format!("Voice not found: {}", request.voice))?;

        let mut cmd = Command::new(&self.piper_binary);
        cmd.arg("--model").arg(&voice.model_path);
        cmd.arg("--config").arg(&voice.config_path);
        cmd.arg("--output_raw");  // Raw audio to stdout for streaming
        
        if let Some(speed) = request.speed {
            cmd.arg("--length_scale").arg(speed.to_string());
        }
        
        cmd.stdin(Stdio::piped());
        cmd.stdout(Stdio::piped());
        cmd.stderr(Stdio::piped());

        let mut child = cmd.spawn().map_err(|e| format!("Failed to spawn piper: {}", e))?;
        
        if let Some(stdin) = child.stdin.as_mut() {
            stdin.write_all(request.text.as_bytes()).map_err(|e| e.to_string())?;
        }
        
        Ok(child)
    }

    pub fn get_voice(&self, name: &str) -> Option<&PiperVoice> {
        self.voices.get(name)
    }
}

// Tauri commands for Piper TTS
#[tauri::command]
async fn piper_init(models_dir: Option<String>) -> Result<Vec<PiperVoice>, String> {
    let dir = models_dir.map(std::path::PathBuf::from);
    let engine = PiperEngine::new(dir)?;
    Ok(engine.list_voices())
}

#[tauri::command]
async fn piper_list_voices() -> Result<Vec<PiperVoice>, String> {
    let models_dir = dirs::data_dir()
        .unwrap_or_else(|| std::path::PathBuf::from("."))
        .join("aria")
        .join("models")
        .join("piper");
    
    let engine = PiperEngine::new(Some(models_dir))?;
    Ok(engine.list_voices())
}

#[tauri::command]
async fn piper_synthesize(request: TTSRequest) -> Result<TTSResponse, String> {
    let models_dir = dirs::data_dir()
        .unwrap_or_else(|| std::path::PathBuf::from("."))
        .join("aria")
        .join("models")
        .join("piper");
    
    let engine = PiperEngine::new(Some(models_dir))?;
    engine.synthesize(request)
}

#[tauri::command]
async fn piper_synthesize_stream(request: TTSRequest) -> Result<Vec<u8>, String> {
    let models_dir = dirs::data_dir()
        .unwrap_or_else(|| std::path::PathBuf::from("."))
        .join("aria")
        .join("models")
        .join("piper");
    
    let engine = PiperEngine::new(Some(models_dir))?;
    let mut child = engine.synthesize_streaming(request)?;
    
    // Read streaming audio from stdout
    let mut audio_data = Vec::new();
    if let Some(stdout) = child.stdout.as_mut() {
        let mut reader = BufReader::new(stdout);
        let mut buffer = Vec::new();
        reader.read_to_end(&mut buffer).map_err(|e| e.to_string())?;
        audio_data = buffer;
    }
    
    child.wait().map_err(|e| e.to_string())?;
    
    Ok(audio_data)
}

#[tauri::command]
async fn piper_download_voice(voice: String, language: String) -> Result<PiperVoice, String> {
    // This would download from Hugging Face Hub
    // For now, return mock
    Ok(PiperVoice {
        name: voice,
        language,
        quality: "medium".to_string(),
        model_path: "".to_string(),
        config_path: "".to_string(),
        sample_rate: 22050,
        speaker_id: None,
    })
}