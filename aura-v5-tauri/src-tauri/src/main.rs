#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod local_llm;
mod whisper_stt;
mod piper_tts;

use tauri::{AppHandle, Manager};
use std::process::Command;
use local_llm::{LocalLLMEngine, InferenceRequest, InferenceResponse, ModelInfo};
use whisper_stt::{WhisperEngine, TranscriptionRequest, TranscriptionResponse, WhisperModelInfo};
use piper_tts::{PiperEngine, TTSRequest, TTSResponse, PiperVoice};

fn create_menu(app: &AppHandle) -> Result<tauri::menu::Menu<tauri::Wry>, Box<dyn std::error::Error>> {
    let quit = tauri::menu::MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
    let submenu = tauri::menu::Submenu::with_id_and_items(app, "file", "File", true, &[&quit])?;
    let menu = tauri::menu::Menu::with_items(app, &[&submenu])?;
    Ok(menu)
}

fn main() {
    // Spawn FastAPI backend
    let backend_path = if cfg!(debug_assertions) {
        "ARIA_APP/backend/main.py"  // Dev: relative path
    } else {
        "./ARIA_APP/backend/main.py" // Prod: bundled path
    };

    let _backend_process = Command::new("python")
        .arg(backend_path)
        .spawn()
        .expect("Failed to spawn backend");

    tauri::Builder::default()
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_clipboard_manager::init())
        .setup(|app| {
            let menu = create_menu(app.app_handle())?;
            app.set_menu(menu)?;
            
            // Register global shortcut for orb summon (Ctrl+Space)
            let app_handle = app.app_handle().clone();
            let _ = app.global_shortcut().register("Ctrl+Space", move || {
                if let Some(window) = app_handle.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            });
            
            Ok(())
        })
        .on_menu_event(|_app_handle, event| {
            if event.id() == "quit" {
                std::process::exit(0);
            }
        })
        .invoke_handler(tauri::generate_handler![
            chat_send,
            skills_load,
            settings_get,
            settings_set,
            window_opacity,
            // Local LLM commands
            local_llm_init,
            local_llm_load,
            local_llm_generate,
            local_llm_list,
            local_llm_unload,
            local_llm_device_info,
            // Whisper STT commands
            whisper_init,
            whisper_list_models,
            whisper_load,
            whisper_transcribe,
            whisper_unload,
            // Piper TTS commands
            piper_init,
            piper_list_voices,
            piper_synthesize,
            piper_synthesize_stream,
            piper_download_voice,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[tauri::command]
async fn chat_send(message: String) -> Result<String, String> {
    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:8000/api/chat")
        .json(&serde_json::json!({"message": message}))
        .send()
        .await
        .map_err(|e| e.to_string())?;

    let text = response.text().await.map_err(|e| e.to_string())?;
    Ok(text)
}

#[tauri::command]
async fn skills_load() -> Result<Vec<serde_json::Value>, String> {
    let client = reqwest::Client::new();
    let response = client
        .get("http://localhost:8000/api/skills")
        .send()
        .await
        .map_err(|e| e.to_string())?;

    let json = response.json().await.map_err(|e| e.to_string())?;
    Ok(json)
}

#[tauri::command]
fn settings_get(_key: String) -> Option<String> {
    None
}

#[tauri::command]
fn settings_set(_key: String, _value: String) {
}

#[tauri::command]
fn window_opacity(_window: tauri::WebviewWindow, _opacity: f64) {
    // Opacity not supported in this version
}