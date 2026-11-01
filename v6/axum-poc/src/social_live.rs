//! Canales sociales: la audiencia de ARIA.
//!
//! ## De dónde sale el diseño
//!
//! Lo que hace grande a Neuro-sama no es el modelo: es que hay *gente*.
//! Ella lee el chat de Twitch en vivo, contesta a lo que le dicen y se
//! aburre si nadie habla. Airi hace lo mismo con Discord y Telegram.
//!
//! Sin chat, una "asistente virtual" es un chatbot con avatares. Con chat, es
//! una personaje en directo que reacciona a su público. Este módulo es la
//! capa que trae ese público a ARIA.
//!
//! ## Cómo entra el chat
//!
//! Los conectores (Twitch, YouTube, Discord) viven fuera del backend, en
//! `scripts/aria_social.py`: son procesos de red y el backend no debe
//! depender de ellos para funcionar. El conector **empuja** cada mensaje a
//! `POST /api/social/messages` y **tira** de `GET /api/social/outbox` para
//! entregar las respuestas de ARIA.
//!
//! Así cualquiera puede hablar con ARIA sin tocar el backend: un bot de
//! Minecraft, un bot de Discord o un script propio que haga un POST.

use axum::{
    extract::{Path, Query},
    routing::{get, post},
    Extension, Json, Router,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::{BTreeMap, VecDeque};
use std::sync::{Arc, OnceLock};
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tokio::sync::Mutex;

use crate::state::SharedState;

/* ------------------------------------------------------------------ *
 * Constantes
 * ------------------------------------------------------------------ */

/// Canales registrados como máximo.
pub const MAX_CHANNELS: usize = 24;

/// Mensajes guardados por canal.
pub const MAX_MESSAGES: usize = 120;

/// Mensajes pendientes de entrega por canal.
pub const MAX_OUTBOX: usize = 40;

/// Segundos mínimos entre dos respuestas al mismo canal.
pub const MIN_REPLY_GAP_SECS: u64 = 12;

/// Cuántas respuestas como mucho por minuto y canal.
pub const MAX_REPLIES_PER_MINUTE: usize = 4;

/// Tipos de canal que ARIA entiende.
pub const CHANNEL_KINDS: &[&str] = &["twitch", "youtube", "discord", "telegram", "http"];

/// Archivo donde se guardan los canales.
const CHANNELS_FILE: &str = "social_channels.json";

/* ------------------------------------------------------------------ *
 * Tipos
 * ------------------------------------------------------------------ */

/// Un canal por el que habla la gente.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Channel {
    /// Identificador estable: `twitch:canal`.
    pub id: String,
    /// Tipo: `twitch`, `youtube`, `discord`, `telegram`, `http`.
    pub kind: String,
    /// A quién se sigue: nombre del canal, url, id de guild...
    pub target: String,
    /// Nombre para las personas.
    pub label: String,
    /// Si el canal está escuchando.
    pub enabled: bool,
    /// Si hay conector vivo.
    pub connected: bool,
    /// Estado legible.
    pub status: String,
    /// Mensajes recibidos.
    pub messages: u64,
    /// Respuestas enviadas.
    pub replies: u64,
    /// Último mensaje (epoch en segundos).
    pub last_message_at: u64,
    /// Último error del conector.
    #[serde(default)]
    pub last_error: String,
    pub created_at: u64,
}

/// Un mensaje de la audiencia.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SocialMessage {
    pub id: u64,
    /// Canal por el que llegó.
    pub channel: String,
    /// Quién lo escribió.
    pub author: String,
    /// Qué dijo.
    pub text: String,
    /// Epoch en segundos.
    pub at: u64,
    /// Si parece dirigido a ARIA (la nombra o pregunta).
    pub addressed: bool,
    /// Si ARIA ya contestó.
    pub replied: bool,
}

/// Una respuesta de ARIA esperando a que el conector la entregue.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OutboxMessage {
    pub id: u64,
    pub channel: String,
    pub text: String,
    pub at: u64,
    /// Si el conector ya la entregó.
    #[serde(default)]
    pub delivered: bool,
}

/// Lo que ARIA tiene que contestar ahora mismo.
#[derive(Debug, Clone, Serialize)]
pub struct SocialPrompt {
    pub channel: String,
    pub kind: String,
    pub author: String,
    pub text: String,
    pub at: u64,
}

/// Estado global.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct SocialState {
    pub channels: BTreeMap<String, Channel>,
    pub messages: BTreeMap<String, VecDeque<SocialMessage>>,
    pub outbox: BTreeMap<String, VecDeque<OutboxMessage>>,
    pub next_id: u64,
}

/* ------------------------------------------------------------------ *
 * Estado global
 * ------------------------------------------------------------------ */

static SOCIAL: OnceLock<Mutex<SocialState>> = OnceLock::new();

fn social() -> &'static Mutex<SocialState> {
    SOCIAL.get_or_init(|| Mutex::new(load_channels()))
}

/// Conectores vivos: por canal, el canal para pararlo.
struct ConnectorHandle {
    /// Al recibirlo, el supervisor mata al hijo y se va.
    stop: Option<tokio::sync::oneshot::Sender<()>>,
}

static CONNECTORS: OnceLock<Mutex<BTreeMap<String, ConnectorHandle>>> = OnceLock::new();

fn connectors() -> &'static Mutex<BTreeMap<String, ConnectorHandle>> {
    CONNECTORS.get_or_init(|| Mutex::new(BTreeMap::new()))
}

/// Dirección del propio backend, para los conectores.
///
/// El conector es un proceso aparte: tiene que saber a quién llamar. Si
/// `ARIA_BACKEND` está puesto, manda; si no, se supone el puerto habitual.
pub fn backend_base_url() -> String {
    std::env::var("ARIA_BACKEND")
        .ok()
        .filter(|value| !value.trim().is_empty())
        .map(|value| value.trim_end_matches('/').to_string())
        .unwrap_or_else(|| format!("http://127.0.0.1:{}", crate::control::server_port()))
}

/// Ruta del script de conectores.
fn connector_script() -> Option<std::path::PathBuf> {
    let root = crate::voice::repo_root();
    let path = root.join("scripts").join("aria_social.py");
    if path.exists() {
        Some(path)
    } else {
        None
    }
}

/// Arranca el conector de un canal.
///
/// El conector es un proceso hijo (Python) que lee la plataforma y empuja
/// los mensajes al backend. Si se muere, el supervisor lo levanta otra vez:
/// la audiencia es lo último que ARIA puede permitirse perder.
pub async fn start_connector(
    channel_id: &str,
    kind: &str,
    target: &str,
    token: &str,
) -> Result<(), String> {
    if connector_script().is_none() {
        return Err("no se encuentra scripts/aria_social.py".to_string());
    }
    stop_connector(channel_id).await;

    let (stop_tx, mut stop_rx) = tokio::sync::oneshot::channel::<()>();
    connectors()
        .lock()
        .await
        .insert(channel_id.to_string(), ConnectorHandle { stop: Some(stop_tx) });

    let channel_id = channel_id.to_string();
    let kind = kind.to_string();
    let target = target.to_string();
    let token = token.to_string();

    tokio::spawn(async move {
        let mut restarts: u32 = 0;
        loop {
            match spawn_connector_process(&kind, &target, &channel_id, &token).await {
                Ok(mut child) => {
                    // Se drena stdout y stderr para que el hijo no se
                    // bloquee escribiendo y para ver qué dice.
                    if let Some(stdout) = child.stdout.take() {
                        tokio::spawn(async move {
                            use tokio::io::{AsyncBufReadExt, BufReader};
                            let mut lines = BufReader::new(stdout).lines();
                            while let Ok(Some(line)) = lines.next_line().await {
                                tracing::info!(target: "aria::social", "{line}");
                            }
                        });
                    }
                    if let Some(stderr) = child.stderr.take() {
                        let error_channel = channel_id.clone();
                        tokio::spawn(async move {
                            use tokio::io::{AsyncBufReadExt, BufReader};
                            let mut lines = BufReader::new(stderr).lines();
                            while let Ok(Some(line)) = lines.next_line().await {
                                if line.trim().is_empty() {
                                    continue;
                                }
                                tracing::warn!(target: "aria::social", "{line}");
                                set_connector_state(&error_channel, false, &line).await;
                            }
                        });
                    }
                    tokio::select! {
                        status = child.wait() => {
                            tracing::warn!(
                                target: "aria::social",
                                channel = %channel_id,
                                code = ?status,
                                "el conector terminó"
                            );
                        }
                        _ = &mut stop_rx => {
                            // Parada solicitada: se mata al hijo, que es
                            // nuestro (nunca por nombre de imagen).
                            let _ = child.kill().await;
                            break;
                        }
                    }
                }
                Err(error) => {
                    tracing::warn!(target: "aria::social", error = %error, "el conector no arrancó");
                }
            }

            if !channel_enabled(&channel_id).await {
                break;
            }
            restarts += 1;
            let wait = u64::from(5 * restarts).min(60);
            tokio::time::sleep(Duration::from_secs(wait)).await;
        }
        connectors().lock().await.remove(&channel_id);
    });

    Ok(())
}

/// Lanza el proceso del conector.
async fn spawn_connector_process(
    kind: &str,
    target: &str,
    channel_id: &str,
    token: &str,
) -> Result<tokio::process::Child, String> {
    let python = crate::voice::python_executable().ok_or_else(|| {
        "no hay intérprete de Python (ARIA_PYTHON, .venv o PATH)".to_string()
    })?;
    let script = connector_script().ok_or_else(|| "falta scripts/aria_social.py".to_string())?;

    let mut command = tokio::process::Command::new(&python);
    command
        .arg(&script)
        .arg("--kind")
        .arg(kind)
        .arg("--target")
        .arg(target)
        .arg("--channel")
        .arg(channel_id)
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped());
    crate::child_env::sanitize(&mut command);
    // El conector necesita poder llamar al backend: la dirección y el
    // token van en el entorno del hijo, nunca en la línea de órdenes.
    command.env("ARIA_BACKEND", backend_base_url());
    command.env("ARIA_TOKEN", token);
    command.env("PYTHONUNBUFFERED", "1");

    command.spawn().map_err(|error| format!("no se pudo arrancar: {error}"))
}

/// Para el conector de un canal (mata al hijo que ARIA lancé).
pub async fn stop_connector(channel_id: &str) {
    let handle = connectors().lock().await.remove(channel_id);
    if let Some(mut handle) = handle {
        if let Some(stop) = handle.stop.take() {
            let _ = stop.send(());
        }
    }
}

/// ¿Está el canal encendido?
pub async fn channel_enabled(channel_id: &str) -> bool {
    let guard = social().lock().await;
    guard
        .channels
        .get(channel_id)
        .map(|channel| channel.enabled)
        .unwrap_or(false)
}

fn now_secs() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

/* ------------------------------------------------------------------ *
 * Persistencia
 * ------------------------------------------------------------------ */

fn state_dir() -> std::path::PathBuf {
    std::env::var("ARIA_AUTONOMY_STATE_DIR")
        .ok()
        .filter(|v| !v.trim().is_empty())
        .map(std::path::PathBuf::from)
        .unwrap_or_else(crate::control::default_state_dir)
}

fn channels_path() -> std::path::PathBuf {
    state_dir().join(CHANNELS_FILE)
}

fn load_channels() -> SocialState {
    let mut state = SocialState {
        channels: BTreeMap::new(),
        messages: BTreeMap::new(),
        outbox: BTreeMap::new(),
        next_id: 1,
    };
    let Ok(raw) = std::fs::read_to_string(channels_path()) else {
        return state;
    };
    let Ok(saved) = serde_json::from_str::<SocialState>(&raw) else {
        eprintln!("social: canales ilegibles, se empiezan de cero");
        return state;
    };
    state.channels = saved.channels;
    state.next_id = saved.next_id.max(1);
    state
}

fn persist_channels(state: &SocialState) {
    let path = channels_path();
    if let Some(parent) = path.parent() {
        if let Err(err) = std::fs::create_dir_all(parent) {
            eprintln!("social: no se pudo crear {}: {err}", parent.display());
            return;
        }
    }
    match serde_json::to_string_pretty(state) {
        Ok(body) => {
            if let Err(err) = std::fs::write(&path, body) {
                eprintln!("social: no se pudo escribir {}: {err}", path.display());
            }
        }
        Err(err) => eprintln!("social: no se pudo serializar: {err}"),
    }
}

/* ------------------------------------------------------------------ *
 * Detección de "hablan con ARIA"
 * ------------------------------------------------------------------ */

/// ¿El mensaje va dirigido a ARIA?
///
/// Es el mismo criterio que usa la autonomía para el chat local, pero aquí
/// importa más: un canal puede tener mil mensajes por minuto y ARIA no puede
/// contestar a todos. Contesta a quien la nombra o a quien pregunta.
pub fn is_addressed(text: &str) -> bool {
    let lower = text.to_lowercase();
    if lower.contains("aria") {
        return true;
    }
    // Una pregunta va con interrogación, en español o en inglés.
    lower.contains('?') || lower.contains('¿')
}

/// ¿Vale la pena contestar este mensaje?
///
/// Además de estar dirigido a ARIA, tiene que tener contenido: un "aria" a
/// secas no merece una respuesta.
pub fn worth_answering(text: &str) -> bool {
    let trimmed = text.trim();
    // Un "aria" a secas no es una pregunta: contestarlo es ruido.
    if trimmed.chars().count() < 5 {
        return false;
    }
    is_addressed(trimmed)
}

/// Normaliza el identificador de un canal.
fn channel_id(kind: &str, target: &str) -> String {
    let kind = kind.trim().to_lowercase();
    let clean: String = target
        .trim()
        .to_lowercase()
        .chars()
        .map(|c| if c.is_alphanumeric() || c == '-' || c == '_' { c } else { '-' })
        .collect();
    let clean = clean.trim_matches('-').to_string();
    format!("{kind}:{clean}")
}

/* ------------------------------------------------------------------ *
 * API interna
 * ------------------------------------------------------------------ */

/// Registra un canal nuevo (o devuelve el que ya había).
pub async fn register_channel(kind: &str, target: &str, label: &str) -> Result<Channel, String> {
    let kind = kind.trim().to_lowercase();
    if !CHANNEL_KINDS.contains(&kind.as_str()) {
        return Err(format!(
            "tipo de canal desconocido '{kind}' (validos: {})",
            CHANNEL_KINDS.join(", ")
        ));
    }
    if target.trim().is_empty() {
        return Err("el canal necesita un destino".to_string());
    }
    let id = channel_id(&kind, target);
    let mut guard = social().lock().await;
    if guard.channels.len() >= MAX_CHANNELS && !guard.channels.contains_key(&id) {
        return Err("no caben más canales".to_string());
    }
    let now = now_secs();
    let channel = guard.channels.entry(id.clone()).or_insert_with(|| Channel {
        id: id.clone(),
        kind: kind.clone(),
        target: target.trim().to_string(),
        label: label.trim().to_string(),
        enabled: false,
        connected: false,
        status: "registrado".to_string(),
        messages: 0,
        replies: 0,
        last_message_at: 0,
        last_error: String::new(),
        created_at: now,
    });
    if !label.trim().is_empty() {
        channel.label = label.trim().to_string();
    }
    if channel.label.is_empty() {
        channel.label = channel.target.clone();
    }
    let view = channel.clone();
    persist_channels(&guard);
    Ok(view)
}

/// Activa o desactiva un canal.
///
/// Desactivar no borra nada: el canal sigue ahí con su historial, sólo deja
/// de escuchar.
pub async fn set_enabled(id: &str, enabled: bool) -> Result<Channel, String> {
    let mut guard = social().lock().await;
    let Some(channel) = guard.channels.get_mut(id) else {
        return Err(format!("no existe el canal '{id}'"));
    };
    channel.enabled = enabled;
    channel.status = if enabled {
        "conectando".to_string()
    } else {
        "apagado".to_string()
    };
    if !enabled {
        channel.connected = false;
    }
    let view = channel.clone();
    persist_channels(&guard);
    Ok(view)
}

/// Borra un canal y su historial.
pub async fn remove_channel(id: &str) -> bool {
    let mut guard = social().lock().await;
    guard.messages.remove(id);
    guard.outbox.remove(id);
    let removed = guard.channels.remove(id).is_some();
    persist_channels(&guard);
    removed
}

/// Lista los canales.
pub async fn channels() -> Vec<Channel> {
    let guard = social().lock().await;
    guard.channels.values().cloned().collect()
}

/// Marca el estado del conector de un canal.
pub async fn set_connector_state(id: &str, connected: bool, error: &str) {
    let mut guard = social().lock().await;
    if let Some(channel) = guard.channels.get_mut(id) {
        channel.connected = connected;
        channel.last_error = error.to_string();
        channel.status = if connected {
            "conectado".to_string()
        } else if channel.enabled {
            "reconectando".to_string()
        } else {
            "apagado".to_string()
        };
    }
}

/// Recibe un mensaje del mundo social.
///
/// El mensaje entra también como evento de la autonomía: así ARIA lo ve en
/// su historia, sube la pulsión social y puede contestar.
pub async fn ingest(channel_id: &str, author: &str, text: &str) -> Result<SocialMessage, String> {
    let text = text.trim().to_string();
    if text.is_empty() {
        return Err("mensaje vacío".to_string());
    }
    let author = author.trim();
    let author = if author.is_empty() { "alguien" } else { author };

    let message = {
        let mut guard = social().lock().await;
        if !guard.channels.contains_key(channel_id) {
            // Un canal que llega sin registrarse se registra: el conector
            // puede haber apuntado antes de que el usuario lo creara.
            let kind = channel_id.split(':').next().unwrap_or("http").to_string();
            let target = channel_id.split(':').nth(1).unwrap_or(channel_id).to_string();
            let now = now_secs();
            guard.channels.insert(
                channel_id.to_string(),
                Channel {
                    id: channel_id.to_string(),
                    kind,
                    target,
                    label: channel_id.to_string(),
                    enabled: true,
                    connected: true,
                    status: "conectado".to_string(),
                    messages: 0,
                    replies: 0,
                    last_message_at: 0,
                    last_error: String::new(),
                    created_at: now,
                },
            );
        }
        let id = guard.next_id;
        guard.next_id += 1;
        let now = now_secs();
        let message = SocialMessage {
            id,
            channel: channel_id.to_string(),
            author: author.to_string(),
            text: text.clone(),
            at: now,
            addressed: worth_answering(&text),
            replied: false,
        };
        let bucket = guard.messages.entry(channel_id.to_string()).or_default();
        bucket.push_back(message.clone());
        while bucket.len() > MAX_MESSAGES {
            bucket.pop_front();
        }
        if let Some(channel) = guard.channels.get_mut(channel_id) {
            channel.messages += 1;
            channel.last_message_at = now;
        }
        persist_channels(&guard);
        message
    };

    // El mensaje también es un evento de la autonomía: entra en su historia,
    // despierta la pulsión social y puede provocar una respuesta inmediata.
    crate::autonomy::push_world_event(
        "chat",
        channel_id,
        &message.text,
        json!({
            "author": message.author,
            "channel": channel_id,
            "addressed": message.addressed,
        }),
    )
    .await;

    Ok(message)
}

/// Lo que ARIA debería contestar ahora mismo.
///
/// Devuelve `None` si nadie le ha Directed la palabra o si ya ha hablado
/// demasiado hace un momento (un bot que contesta a todo se vuelve ruido).
pub async fn pending_prompt() -> Option<SocialPrompt> {
    let guard = social().lock().await;
    let now = now_secs();

    for (channel_id, bucket) in guard.messages.iter().rev() {
        let Some(channel) = guard.channels.get(channel_id) else {
            continue;
        };
        if !channel.enabled {
            continue;
        }
        // ¿Ha hablado demasiado hace un momento?
        let recent_replies = bucket
            .iter()
            .rev()
            .filter(|m| m.replied && now.saturating_sub(m.at) < 60)
            .count();
        if recent_replies >= MAX_REPLIES_PER_MINUTE {
            continue;
        }
        let last_reply_at = bucket
            .iter()
            .rev()
            .find(|m| m.replied)
            .map(|m| m.at)
            .unwrap_or(0);
        if now.saturating_sub(last_reply_at) < MIN_REPLY_GAP_SECS {
            continue;
        }
        if let Some(message) = bucket.iter().rev().find(|m| m.addressed && !m.replied) {
            return Some(SocialPrompt {
                channel: channel_id.clone(),
                kind: channel.kind.clone(),
                author: message.author.clone(),
                text: message.text.clone(),
                at: message.at,
            });
        }
    }
    None
}

/// ARIA responde en un canal.
///
/// La respuesta se queda en la bandeja de salida; el conector la recoge y la
/// publica. Si no hay conector, la respuesta sigue ahí para cuando lo haya.
pub async fn reply(channel_id: &str, text: &str) -> Result<String, String> {
    let text = text.trim();
    if text.is_empty() {
        return Err("no hay nada que decir".to_string());
    }
    let mut guard = social().lock().await;
    if !guard.channels.contains_key(channel_id) {
        return Err(format!("no existe el canal '{channel_id}'"));
    }
    let id = guard.next_id;
    guard.next_id += 1;
    let now = now_secs();
    let bucket = guard.outbox.entry(channel_id.to_string()).or_default();
    bucket.push_back(OutboxMessage {
        id,
        channel: channel_id.to_string(),
        text: text.to_string(),
        at: now,
        delivered: false,
    });
    while bucket.len() > MAX_OUTBOX {
        bucket.pop_front();
    }
    // Marca como contestados los mensajes dirigidos a ARIA de este canal.
    if let Some(messages) = guard.messages.get_mut(channel_id) {
        for message in messages.iter_mut().rev() {
            if message.addressed && !message.replied {
                message.replied = true;
                break;
            }
        }
    }
    if let Some(channel) = guard.channels.get_mut(channel_id) {
        channel.replies += 1;
    }
    persist_channels(&guard);
    Ok(format!("respuesta encolada en {channel_id}"))
}

/// La bandeja de salida de un canal (lo que el conector tiene que publicar).
pub async fn take_outbox(channel_id: &str) -> Vec<OutboxMessage> {
    let mut guard = social().lock().await;
    guard
        .outbox
        .get_mut(channel_id)
        .map(|bucket| {
            let items: Vec<OutboxMessage> = bucket.drain(..).collect();
            items
        })
        .unwrap_or_default()
}

/// Los últimos mensajes de un canal (o de todos).
pub async fn recent_messages(channel_id: Option<&str>, limit: usize) -> Vec<SocialMessage> {
    let guard = social().lock().await;
    let limit = limit.clamp(1, 200);
    let mut out: Vec<SocialMessage> = Vec::new();
    match channel_id {
        Some(id) => {
            if let Some(bucket) = guard.messages.get(id) {
                out.extend(bucket.iter().rev().take(limit).cloned());
            }
        }
        None => {
            for bucket in guard.messages.values() {
                out.extend(bucket.iter().rev().take(limit).cloned());
            }
            out.sort_by(|a, b| b.at.cmp(&a.at));
            out.truncate(limit);
        }
    }
    out
}

/// Resumen para el prompt del modelo.
pub fn prompt_summary() -> String {
    let guard = match social().try_lock() {
        Ok(guard) => guard,
        Err(_) => return String::new(),
    };
    let mut out = String::new();
    for channel in guard.channels.values() {
        if !channel.enabled {
            continue;
        }
        out.push_str(&format!(
            "- {} ({}, {} mensajes, {} respuestas)\n",
            channel.label, channel.kind, channel.messages, channel.replies
        ));
    }
    out
}

/* ------------------------------------------------------------------ *
 * Rutas
 * ------------------------------------------------------------------ */

pub fn router() -> Router<()> {
    Router::new()
        .route("/api/social/channels", get(list_channels).post(create_channel))
        .route(
            "/api/social/channels/:id",
            get(get_channel).delete(delete_channel),
        )
        .route("/api/social/channels/:id/toggle", post(toggle_channel))
        .route("/api/social/channels/:id/state", post(channel_state))
        .route("/api/social/channels/:id/say", post(say_in_channel))
        .route("/api/social/channels/:id/outbox", get(outbox))
        .route("/api/social/messages", get(list_messages).post(ingest_message))
        .route("/api/social/pending", get(pending))
}

async fn list_channels() -> Json<Value> {
    let channels = channels().await;
    Json(json!({
        "status": "ok",
        "channels": channels,
        "count": channels.len(),
        "kinds": CHANNEL_KINDS,
        "server": "ARIA-Axum-8002",
    }))
}

#[derive(Deserialize)]
struct CreateChannel {
    #[serde(default)]
    kind: String,
    #[serde(default)]
    target: String,
    #[serde(default)]
    label: String,
}

async fn create_channel(Json(req): Json<CreateChannel>) -> Json<Value> {
    match register_channel(&req.kind, &req.target, &req.label).await {
        Ok(channel) => Json(json!({
            "status": "ok",
            "channel": channel,
            "server": "ARIA-Axum-8002",
        })),
        Err(error) => Json(json!({ "status": "error", "error": error })),
    }
}

async fn get_channel(Path(id): Path<String>) -> Json<Value> {
    let channels = channels().await;
    match channels.into_iter().find(|c| c.id == id) {
        Some(channel) => Json(json!({ "status": "ok", "channel": channel })),
        None => Json(json!({
            "status": "error",
            "error": format!("no existe el canal '{id}'"),
        })),
    }
}

async fn delete_channel(Path(id): Path<String>) -> Json<Value> {
    let removed = remove_channel(&id).await;
    Json(json!({ "status": if removed { "ok" } else { "error" }, "removed": removed }))
}

#[derive(Deserialize)]
struct ToggleRequest {
    #[serde(default)]
    enabled: Option<bool>,
}

/// Activa o desactiva el canal.
///
/// Si no viene `enabled`, se alterna: es lo cómodo desde la UI, que manda el
/// valor explícito, y el resto de clientes pueden usar el modo alterno.
///
/// Al activar se levanta el conector (el proceso que lee la plataforma) y al
/// desactivar se para. El token del backend se pasa por el entorno del hijo:
/// nunca viaja en la línea de órdenes, donde se vería en la lista de
/// procesos.
async fn toggle_channel(
    Path(id): Path<String>,
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<ToggleRequest>,
) -> Json<Value> {
    let current = channels().await;
    let Some(channel) = current.into_iter().find(|c| c.id == id) else {
        return Json(json!({
            "status": "error",
            "error": format!("no existe el canal '{id}'"),
        }));
    };
    let enabled = req.enabled.unwrap_or(!channel.enabled);
    let channel = match set_enabled(&id, enabled).await {
        Ok(channel) => channel,
        Err(error) => return Json(json!({ "status": "error", "error": error })),
    };

    if enabled {
        // Sólo hay conector para las plataformas con script propio; el resto
        // (telegram, http) se alimentan por POST desde fuera.
        let token = { state.lock().await.api_key().to_string() };
        if let Err(error) = start_connector(&id, &channel.kind, &channel.target, &token).await {
            set_connector_state(&id, false, &error).await;
            return Json(json!({
                "status": "error",
                "error": error,
                "channel": channel,
                "server": "ARIA-Axum-8002",
            }));
        }
    } else {
        stop_connector(&id).await;
    }

    Json(json!({
        "status": "ok",
        "channel": channel,
        "server": "ARIA-Axum-8002",
    }))
}

#[derive(Deserialize)]
struct StateRequest {
    #[serde(default)]
    connected: bool,
    #[serde(default)]
    status: Option<String>,
}

/// El conector informa de cómo va.
async fn channel_state(Path(id): Path<String>, Json(req): Json<StateRequest>) -> Json<Value> {
    let status = req.status.clone().unwrap_or_default();
    set_connector_state(&id, req.connected, &status).await;
    Json(json!({
        "status": "ok",
        "channel": id,
        "connected": req.connected,
        "server": "ARIA-Axum-8002",
    }))
}

#[derive(Deserialize)]
struct SayRequest {
    #[serde(default)]
    text: String,
}

async fn say_in_channel(Path(id): Path<String>, Json(req): Json<SayRequest>) -> Json<Value> {
    match reply(&id, &req.text).await {
        Ok(result) => Json(json!({ "status": "ok", "result": result })),
        Err(error) => Json(json!({ "status": "error", "error": error })),
    }
}

async fn outbox(Path(id): Path<String>) -> Json<Value> {
    let messages = take_outbox(&id).await;
    Json(json!({
        "status": "ok",
        "messages": messages,
        "count": messages.len(),
        "server": "ARIA-Axum-8002",
    }))
}

#[derive(Deserialize)]
struct MessagesQuery {
    channel: Option<String>,
    limit: Option<usize>,
}

async fn list_messages(Query(query): Query<MessagesQuery>) -> Json<Value> {
    let messages = recent_messages(query.channel.as_deref(), query.limit.unwrap_or(50)).await;
    Json(json!({
        "status": "ok",
        "messages": messages,
        "count": messages.len(),
        "server": "ARIA-Axum-8002",
    }))
}

#[derive(Deserialize)]
struct IngestRequest {
    /// Canal: `twitch:canal`, `discord:mi-bot`, ...
    #[serde(default)]
    channel: String,
    #[serde(default)]
    author: String,
    #[serde(default)]
    text: String,
}

/// Entra un mensaje del mundo social.
async fn ingest_message(Json(req): Json<IngestRequest>) -> Json<Value> {
    if req.channel.trim().is_empty() {
        return Json(json!({
            "status": "error",
            "error": "falta el canal",
        }));
    }
    match ingest(req.channel.trim(), &req.author, &req.text).await {
        Ok(message) => Json(json!({
            "status": "ok",
            "message": message,
            "server": "ARIA-Axum-8002",
        })),
        Err(error) => Json(json!({ "status": "error", "error": error })),
    }
}

async fn pending() -> Json<Value> {
    match pending_prompt().await {
        Some(prompt) => Json(json!({
            "status": "ok",
            "pending": prompt,
            "server": "ARIA-Axum-8002",
        })),
        None => Json(json!({
            "status": "ok",
            "pending": Value::Null,
            "server": "ARIA-Axum-8002",
        })),
    }
}

/* ------------------------------------------------------------------ *
 * Tests
 * ------------------------------------------------------------------ */

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn un_mensaje_que_nombra_a_aria_va_dirigido_a_ella() {
        assert!(is_addressed("aria, ¿qué haces?"));
        assert!(is_addressed("ARIA mira esto"));
        assert!(is_addressed("hola, ¿alguien ahí?"));
        assert!(!is_addressed("hola a todos"));
    }

    #[test]
    fn un_saludo_suelto_no_merece_una_respuesta() {
        assert!(!worth_answering("aria"));
        assert!(!worth_answering("  "));
        assert!(worth_answering("aria, ¿qué tal?"));
    }

    #[test]
    fn los_identificadores_de_canal_se_normalizan() {
        assert_eq!(channel_id("twitch", "Vedal987"), "twitch:vedal987");
        assert_eq!(channel_id("Discord", "mi bot!"), "discord:mi-bot");
    }

    #[test]
    fn los_tipos_de_canal_conocidos_estan_cerrados() {
        assert!(CHANNEL_KINDS.contains(&"twitch"));
        assert!(CHANNEL_KINDS.contains(&"youtube"));
        assert!(CHANNEL_KINDS.contains(&"discord"));
        assert!(!CHANNEL_KINDS.contains(&"inventado"));
    }
}
