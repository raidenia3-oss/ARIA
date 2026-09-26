// Local LLM inference module using Candle.rs
// Provides in-process inference for GGUF/SafeTensors models

use std::path::Path;
use std::sync::Arc;
use candle_core::{Device, Tensor, DType, Result as CandleResult};
use candle_nn::VarBuilder;
use candle_transformers::models::llama::{Model, Config as LlamaConfig};
use candle_transformers::models::gemma::{Model as GemmaModel, Config as GemmaConfig};
use candle_transformers::models::qwen2::{Model as Qwen2Model, Config as Qwen2Config};
use candle_transformers::models::phi::{Model as PhiModel, Config as PhiConfig};
use candle_transformers::models::mistral::{Model as MistralModel, Config as MistralConfig};
use tokenizers::Tokenizer;
use hf_hub::{api::sync::Api, Repo, RepoType};
use safetensors::tensor::SafeTensors;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelInfo {
    pub name: String,
    pub model_type: String,
    pub path: String,
    pub size_gb: f32,
    pub context_length: usize,
    pub loaded: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InferenceRequest {
    pub model: String,
    pub prompt: String,
    pub max_tokens: Option<usize>,
    pub temperature: Option<f32>,
    pub top_p: Option<f32>,
    pub stream: Option<bool>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InferenceResponse {
    pub text: String,
    pub tokens_generated: usize,
    pub latency_ms: u64,
}

pub struct LocalLLMEngine {
    models: HashMap<String, LoadedModel>,
    device: Device,
    tokenizer: Option<Tokenizer>,
}

enum LoadedModel {
    Llama(Model),
    Gemma(GemmaModel),
    Qwen2(Qwen2Model),
    Phi(PhiModel),
    Mistral(MistralModel),
}

impl LocalLLMEngine {
    pub fn new() -> CandleResult<Self> {
        let device = Device::new_cuda(0)
            .or_else(|_| Device::new_metal(0))
            .or_else(|_| Device::new_vulkan(0))
            .unwrap_or(Device::Cpu);
        
        println!("🔧 LocalLLMEngine initialized on device: {:?}", device);
        
        Ok(Self {
            models: HashMap::new(),
            device,
            tokenizer: None,
        })
    }

    pub fn get_device_info(&self) -> String {
        format!("{:?}", self.device)
    }

    pub async fn load_model(&mut self, model_id: &str, model_path: Option<&str>) -> CandleResult<ModelInfo> {
        let path = if let Some(p) = model_path {
            Path::new(p).to_path_buf()
        } else {
            // Download from Hugging Face Hub
            self.download_model(model_id).await?
        };

        let model_type = self.detect_model_type(&path)?;
        let size_gb = self.get_model_size(&path)?;
        
        let config = self.load_config(&path, &model_type)?;
        let vb = unsafe { VarBuilder::from_mmaped_safetensors(&[path.clone()], DType::F16, &self.device)? };
        
        let model = match model_type.as_str() {
            "llama" => {
                let m = Model::new(&config, vb)?;
                LoadedModel::Llama(m)
            }
            "gemma" => {
                let m = GemmaModel::new(&config, vb)?;
                LoadedModel::Gemma(m)
            }
            "qwen2" => {
                let m = Qwen2Model::new(&config, vb)?;
                LoadedModel::Qwen2(m)
            }
            "phi" => {
                let m = PhiModel::new(&config, vb)?;
                LoadedModel::Phi(m)
            }
            "mistral" => {
                let m = MistralModel::new(&config, vb)?;
                LoadedModel::Mistral(m)
            }
            _ => return Err(candle_core::Error::Msg(format!("Unsupported model type: {}", model_type))),
        };

        self.models.insert(model_id.to_string(), model);
        
        // Load tokenizer
        let tokenizer_path = path.parent().unwrap().join("tokenizer.json");
        if tokenizer_path.exists() {
            self.tokenizer = Some(Tokenizer::from_file(tokenizer_path).map_err(|e| candle_core::Error::Msg(e.to_string()))?);
        }

        Ok(ModelInfo {
            name: model_id.to_string(),
            model_type,
            path: path.display().to_string(),
            size_gb,
            context_length: config.max_seq_len,
            loaded: true,
        })
    }

    fn detect_model_type(&self, path: &Path) -> CandleResult<String> {
        // Check config.json for model type
        let config_path = path.parent().unwrap().join("config.json");
        if config_path.exists() {
            let content = std::fs::read_to_string(&config_path)?;
            let json: serde_json::Value = serde_json::from_str(&content)?;
            if let Some(arch) = json.get("architectures").and_then(|a| a.as_array()).and_then(|a| a.first()) {
                let arch_str = arch.as_str().unwrap_or("");
                if arch_str.contains("Llama") { return Ok("llama".to_string()); }
                if arch_str.contains("Gemma") { return Ok("gemma".to_string()); }
                if arch_str.contains("Qwen2") { return Ok("qwen2".to_string()); }
                if arch_str.contains("Phi") { return Ok("phi".to_string()); }
                if arch_str.contains("Mistral") { return Ok("mistral".to_string()); }
            }
        }
        // Default to llama
        Ok("llama".to_string())
    }

    fn load_config(&self, path: &Path, model_type: &str) -> CandleResult<Box<dyn std::any::Any>> {
        let config_path = path.parent().unwrap().join("config.json");
        let content = std::fs::read_to_string(&config_path)?;
        
        match model_type {
            "llama" => {
                let config: LlamaConfig = serde_json::from_str(&content)?;
                Ok(Box::new(config))
            }
            "gemma" => {
                let config: GemmaConfig = serde_json::from_str(&content)?;
                Ok(Box::new(config))
            }
            "qwen2" => {
                let config: Qwen2Config = serde_json::from_str(&content)?;
                Ok(Box::new(config))
            }
            "phi" => {
                let config: PhiConfig = serde_json::from_str(&content)?;
                Ok(Box::new(config))
            }
            "mistral" => {
                let config: MistralConfig = serde_json::from_str(&content)?;
                Ok(Box::new(config))
            }
            _ => Err(candle_core::Error::Msg("Unknown model type".to_string())),
        }
    }

    fn get_model_size(&self, path: &Path) -> CandleResult<f32> {
        let metadata = std::fs::metadata(path)?;
        Ok(metadata.len() as f32 / 1_073_741_824.0)
    }

    async fn download_model(&self, model_id: &str) -> CandleResult<std::path::PathBuf> {
        let api = Api::new()?;
        let repo = api.repo(Repo::new(model_id.to_string(), RepoType::Model));
        
        // Download model.safetensors or model-*.safetensors
        let model_file = repo.get("model.safetensors")
            .or_else(|_| repo.get("model-00001-of-00002.safetensors"))
            .or_else(|_| repo.get("pytorch_model.bin"))?;
        
        Ok(model_file)
    }

    pub fn generate(&self, request: InferenceRequest) -> CandleResult<InferenceResponse> {
        let start = std::time::Instant::now();
        
        let model = self.models.get(&request.model)
            .ok_or_else(|| candle_core::Error::Msg(format!("Model not loaded: {}", request.model)))?;

        let tokenizer = self.tokenizer.as_ref()
            .ok_or_else(|| candle_core::Error::Msg("Tokenizer not loaded"))?;

        let max_tokens = request.max_tokens.unwrap_or(512);
        let temperature = request.temperature.unwrap_or(0.7);
        let top_p = request.top_p.unwrap_or(0.9);

        // Tokenize prompt
        let encoding = tokenizer.encode(request.prompt, true)
            .map_err(|e| candle_core::Error::Msg(e.to_string()))?;
        let tokens = encoding.get_ids();
        let mut input_ids = Tensor::new(tokens, &self.device)?.unsqueeze(0)?;

        // Generate tokens
        let mut generated = Vec::new();
        let mut logits_processor = candle_transformers::generation::LogitsProcessor::new(
            max_tokens,
            temperature,
            top_p,
        );

        for _ in 0..max_tokens {
            let logits = match model {
                LoadedModel::Llama(m) => m.forward(&input_ids, 0)?,
                LoadedModel::Gemma(m) => m.forward(&input_ids, 0)?,
                LoadedModel::Qwen2(m) => m.forward(&input_ids, 0)?,
                LoadedModel::Phi(m) => m.forward(&input_ids, 0)?,
                LoadedModel::Mistral(m) => m.forward(&input_ids, 0)?,
            };

            let next_token = logits_processor.sample(&logits)?;
            
            if next_token == tokenizer.token_to_id("<|endoftext|>").unwrap_or(2) {
                break;
            }

            generated.push(next_token);
            input_ids = Tensor::cat(&[&input_ids, &Tensor::new(&[next_token], &self.device)?.unsqueeze(0)?], 1)?;
        }

        // Decode generated tokens
        let text = tokenizer.decode(&generated, true)
            .map_err(|e| candle_core::Error::Msg(e.to_string()))?;

        Ok(InferenceResponse {
            text,
            tokens_generated: generated.len(),
            latency_ms: start.elapsed().as_millis() as u64,
        })
    }

    pub fn list_models(&self) -> Vec<ModelInfo> {
        self.models.iter().map(|(name, _)| ModelInfo {
            name: name.clone(),
            model_type: "unknown".to_string(), // Would need to track this
            path: "".to_string(),
            size_gb: 0.0,
            context_length: 0,
            loaded: true,
        }).collect()
    }

    pub fn unload_model(&mut self, model_id: &str) -> bool {
        self.models.remove(model_id).is_some()
    }
}

// Tauri commands for local LLM
#[tauri::command]
async fn local_llm_init() -> Result<String, String> {
    let engine = LocalLLMEngine::new().map_err(|e| e.to_string())?;
    Ok(format!("Local LLM engine initialized on {}", engine.get_device_info()))
}

#[tauri::command]
async fn local_llm_load(model: String, path: Option<String>) -> Result<ModelInfo, String> {
    // In a real implementation, this would use a global engine state
    // For now, return mock response
    Ok(ModelInfo {
        name: model,
        model_type: "llama".to_string(),
        path: path.unwrap_or_default(),
        size_gb: 4.0,
        context_length: 4096,
        loaded: true,
    })
}

#[tauri::command]
async fn local_llm_generate(request: InferenceRequest) -> Result<InferenceResponse, String> {
    // Mock response for now
    Ok(InferenceResponse {
        text: "This is a mock response from local LLM".to_string(),
        tokens_generated: 10,
        latency_ms: 100,
    })
}

#[tauri::command]
async fn local_llm_list() -> Result<Vec<ModelInfo>, String> {
    Ok(vec![])
}

#[tauri::command]
async fn local_llm_unload(model: String) -> Result<bool, String> {
    Ok(true)
}

#[tauri::command]
async fn local_llm_device_info() -> Result<String, String> {
    let engine = LocalLLMEngine::new().map_err(|e| e.to_string())?;
    Ok(engine.get_device_info())
}