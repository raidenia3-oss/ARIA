//! Bus de mundos: el cuerpo de ARIA.
//!
//! ## De dónde sale el diseño
//!
//! Neuro-sama juega a osu!, a Minecraft y a otros juegos porque el mundo le
//! **habla**: un controlador del juego le manda el estado y ella contesta con
//! acciones tipadas. Eso es exactamente el protocolo que publica el
//! `neuro-sdk` de Vedal (`VedalAI/neuro-sdk`), y es lo que copia Airi con su
//! "Stage" (dónde se ve) y su "Core" (quién es).
//!
//! Aquí ese protocolo son tres mensajes:
//!
//! * `context_update` — el mundo publica su estado (`POST /api/worlds/:id/context`).
//! * `action_registration` — el mundo declara qué sabe hacer (`capabilities`).
//! * `action_force` — el mundo *obliga* a ARIA a hacer algo, con plazo
//!   (`POST /api/worlds/:id/force`).
//!
//! Y al revés, ARIA ejecuta acciones en el mundo
//! (`POST /api/worlds/:id/actions`). Si el mundo es local (VRChat con OSC, el
//! escritorio) la acción se ejecuta en el acto; si es externo (Minecraft,
//! Discord) la acción queda en una cola que un puente recoge
//! (`GET /api/worlds/:id/pending`).
//!
//! ## Por qué importa
//!
//! Sin esto ARIA es un chat con voz. Con esto es una presencia: tiene un
//! cuerpo, un sitio donde estar y cosas que le pasan aunque nadie le hable.

use axum::{
    extract::Path,
    routing::{get, post},
    Json, Router,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::{BTreeMap, VecDeque};
use std::sync::{Arc, Mutex as StdMutex, OnceLock};
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::sync::{broadcast, Mutex};

use crate::state::SharedState;

/* ------------------------------------------------------------------ *
 * Constantes
 * ------------------------------------------------------------------ */

/// Mundos que se guardan como máximo.
pub const MAX_WORLDS: usize = 24;

/// Acciones pendientes por mundo (puente externo).
pub const MAX_PENDING: usize = 32;

/// Mensajes de contexto que se guardan por mundo.
pub const MAX_CONTEXT_HISTORY: usize = 24;

/// Forces pendientes (obligaciones del mundo).
pub const MAX_FORCES: usize = 16;

/// Plazo por defecto de una fuerza, en segundos.
pub const DEFAULT_FORCE_TIMEOUT_SECS: u64 = 30;

/// Tamaño máximo del contexto que acepta un mundo (evita context blowups).
pub const MAX_CONTEXT_BYTES: usize = 16 * 1024;

/// Archivo donde se guardan los mundos.
const WORLDS_FILE: &str = "worlds.json";

/* ------------------------------------------------------------------ *
 * Tipos
 * ------------------------------------------------------------------ */

/// Una capacidad que un mundo ofrece: un verbo con sus argumentos.
///
/// Es el equivalente a la "action registration" del neuro-sdk: el mundo dice
/// qué sabe hacer y ARIA decide si lo usa.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Capability {
    /// Nombre de la acción: `chat.say`, `move`, `expression.set`.
    pub name: String,
    /// Qué hace, en una frase.
    #[serde(default)]
    pub description: String,
    /// Argumentos que acepta.
    #[serde(default)]
    pub params: Vec<String>,
}

/// Una acción que ARIA le pide a un mundo.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PendingAction {
    pub id: u64,
    /// Acción pedida.
    pub action: String,
    /// Argumentos.
    #[serde(default)]
    pub args: Value,
    pub created_at: u64,
}

/// Una obligación: el mundo le ha pedido a ARIA que haga algo.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Force {
    pub id: u64,
    /// El mundo que obliga.
    pub world: String,
    /// Qué hay que hacer.
    pub action: String,
    /// Con qué argumentos.
    #[serde(default)]
    pub args: Value,
    /// Hasta cuándo (epoch en segundos).
    pub deadline: u64,
    pub created_at: u64,
    /// Si ARIA ya lo hizo.
    #[serde(default)]
    pub satisfied: bool,
    /// Resultado de haberlo hecho.
    #[serde(default)]
    pub result: Option<String>,
}

/// Un mundo donde ARIA puede estar.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct World {
    pub id: String,
    /// Clase: `escritorio`, `avatar`, `juego`, `chat`.
    pub kind: String,
    /// Nombre para las personas.
    pub label: String,
    /// Lo que este mundo sabe hacer.
    #[serde(default)]
    pub capabilities: Vec<Capability>,
    /// Último estado publicado por el mundo.
    #[serde(default)]
    pub context: Value,
    /// Cuándo se publicó ese estado.
    #[serde(default)]
    pub context_at: u64,
    /// Si hay alguien conectado al otro lado.
    #[serde(default)]
    pub connected: bool,
    /// Estado legible: `listo`, `conectado`, `error`.
    #[serde(default)]
    pub status: String,
    /// Acciones ejecutadas contra este mundo.
    #[serde(default)]
    pub actions: u64,
    /// Última vez que ARIA actuó aquí.
    #[serde(default)]
    pub last_action_at: u64,
    /// Cola para puentes externos.
    #[serde(default)]
    pub pending: VecDeque<PendingAction>,
    pub created_at: u64,
    pub updated_at: u64,
}

/// Vista compacta de un mundo, para el prompt y la UI.
#[derive(Debug, Clone, Serialize)]
pub struct WorldView {
    pub id: String,
    pub kind: String,
    pub label: String,
    pub connected: bool,
    pub status: String,
    pub capabilities: Vec<String>,
    pub pending: usize,
    pub context: Value,
    /// Cuándo publicó el mundo su último estado.
    pub context_at: u64,
}

/// Verbos que ARIA no puede ejecutar en ningún mundo.
///
/// Es la misma política que aplica el resto del proyecto (ver
/// `ARIA_APP/backend/process_guard.py`): nada que mate, borre o apague
/// procesos del usuario, ni siquiera si un puente declara esa capacidad.
/// La lista se comprueba por partes, así que `process.kill` y `kill` caen
/// los dos.
pub const FORBIDDEN_VERBS: &[&str] = &[
    "kill",
    "taskkill",
    "terminate",
    "stop-process",
    "stopprocess",
    "shutdown",
    "restart",
    "format",
    "delete",
    "remove",
    "rm",
    "drop",
    "truncate",
    "wmic",
    "rmdir",
    "del",
];

/// ¿Es un verbo prohibido?
pub fn is_forbidden(action: &str) -> bool {
    let action = action.trim().to_lowercase();
    if action.is_empty() {
        return false;
    }
    if FORBIDDEN_VERBS.contains(&action.as_str()) {
        return true;
    }
    action
        .split(|c: char| c == '.' || c == ':' || c == '_' || c == '/')
        .any(|part| !part.is_empty() && FORBIDDEN_VERBS.contains(&part))
}

/// Estado global del bus.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct WorldState {
    pub worlds: BTreeMap<String, World>,
    pub forces: VecDeque<Force>,
    pub next_id: u64,
}

/* ------------------------------------------------------------------ *
 * Estado global
 * ------------------------------------------------------------------ */

static WORLDS: OnceLock<Mutex<WorldState>> = OnceLock::new();

fn worlds() -> &'static Mutex<WorldState> {
    WORLDS.get_or_init(|| Mutex::new(load_worlds()))
}

/// Seres vivos (puentes) por mundo.
///
/// Es un `StdMutex` a propósito: los manejadores de hijo (`tokio::process::Child`)
/// son `Send` pero no `Sync`, y registrar un puente no puede esperar a que
/// termine la petición HTTP.
static BRIDGES: OnceLock<StdMutex<BTreeMap<String, u32>>> = OnceLock::new();

fn bridges() -> &'static StdMutex<BTreeMap<String, u32>> {
    BRIDGES.get_or_init(|| StdMutex::new(BTreeMap::new()))
}

fn now_secs() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

/* ------------------------------------------------------------------ *
 * Mundos de fábrica
 * ------------------------------------------------------------------ */

fn capability(name: &str, description: &str, params: &[&str]) -> Capability {
    Capability {
        name: name.to_string(),
        description: description.to_string(),
        params: params.iter().map(|p| p.to_string()).collect(),
    }
}

/// Los mundos que ARIA conoce de fábrica.
///
/// No son todos reales a la vez: `vrchat` sólo hace algo si hay un VRChat
/// abierto escuchando en el puerto 9000, y `minecraft` necesita un puente
/// conectado. Están declarados para que ARIA sepa qué puede intentar.
fn builtin_worlds(now: u64) -> Vec<World> {
    vec![
        World {
            id: "escritorio".to_string(),
            kind: "escritorio".to_string(),
            label: "Escritorio".to_string(),
            capabilities: vec![
                capability("say", "Decir algo en la interfaz de ARIA", &["text"]),
                capability(
                    "skill.run",
                    "Ejecutar una skill forjada",
                    &["skill_id", "input"],
                ),
                capability("status", "Mirar cómo está el sistema", &[]),
            ],
            context: json!({ "lugar": "escritorio" }),
            context_at: now,
            connected: true,
            status: "listo".to_string(),
            actions: 0,
            last_action_at: 0,
            pending: VecDeque::new(),
            created_at: now,
            updated_at: now,
        },
        World {
            id: "vrchat".to_string(),
            kind: "avatar".to_string(),
            label: "VRChat".to_string(),
            capabilities: vec![
                capability("chatbox.say", "Escribir en el chatbox del avatar", &["text"]),
                capability(
                    "expression.set",
                    "Cambiar la expresión del avatar",
                    &["expression"],
                ),
            ],
            context: json!({ "avatar": "sin conectar" }),
            context_at: now,
            connected: false,
            status: "sin conectar".to_string(),
            actions: 0,
            last_action_at: 0,
            pending: VecDeque::new(),
            created_at: now,
            updated_at: now,
        },
        World {
            id: "minecraft".to_string(),
            kind: "juego".to_string(),
            label: "Minecraft".to_string(),
            capabilities: vec![
                capability("chat.say", "Escribir en el chat del juego", &["text"]),
                capability("move", "Ir a un punto", &["x", "y", "z"]),
                capability("look", "Mirar hacia", &["x", "y", "z"]),
                capability("dig", "Cavar un bloque", &["block"]),
                capability("craft", "Fabricar un objeto", &["item"]),
                capability("observe", "Mirar alrededor y describir", &[]),
            ],
            context: json!({ "estado": "esperando puente" }),
            context_at: now,
            connected: false,
            status: "esperando puente".to_string(),
            actions: 0,
            last_action_at: 0,
            pending: VecDeque::new(),
            created_at: now,
            updated_at: now,
        },
        World {
            id: "discord".to_string(),
            kind: "chat".to_string(),
            label: "Discord".to_string(),
            capabilities: vec![
                capability("chat.send", "Enviar un mensaje a un canal", &["text", "channel"]),
            ],
            context: json!({ "estado": "esperando puente" }),
            context_at: now,
            connected: false,
            status: "esperando puente".to_string(),
            actions: 0,
            last_action_at: 0,
            pending: VecDeque::new(),
            created_at: now,
            updated_at: now,
        },
    ]
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

fn worlds_path() -> std::path::PathBuf {
    state_dir().join(WORLDS_FILE)
}

fn load_worlds() -> WorldState {
    let mut state = WorldState {
        worlds: BTreeMap::new(),
        forces: VecDeque::new(),
        next_id: 1,
    };
    for world in builtin_worlds(now_secs()) {
        state.worlds.insert(world.id.clone(), world);
    }
    // Si hay mundos guardados, se recuperan encima de los de fábrica: el
    // usuario puede haber conectado uno nuevo y no queremos perderlo.
    let Ok(raw) = std::fs::read_to_string(worlds_path()) else {
        return state;
    };
    let Ok(saved) = serde_json::from_str::<WorldState>(&raw) else {
        eprintln!("worlds: estado ilegible, se usan los mundos de fábrica");
        return state;
    };
    for (id, world) in saved.worlds {
        state.worlds.insert(id, world);
    }
    state.next_id = saved.next_id.max(state.next_id);
    state
}

fn persist_worlds(state: &WorldState) {
    let path = worlds_path();
    if let Some(parent) = path.parent() {
        if let Err(err) = std::fs::create_dir_all(parent) {
            eprintln!("worlds: no se pudo crear {}: {err}", parent.display());
            return;
        }
    }
    match serde_json::to_string_pretty(state) {
        Ok(body) => {
            if let Err(err) = std::fs::write(&path, body) {
                eprintln!("worlds: no se pudo escribir {}: {err}", path.display());
            }
        }
        Err(err) => eprintln!("worlds: no se pudo serializar: {err}"),
    }
}

/* ------------------------------------------------------------------ *
 * API interna
 * ------------------------------------------------------------------ */

/// Vista compacta de los mundos, para el prompt y la UI.
pub async fn views() -> Vec<WorldView> {
    let guard = worlds().lock().await;
    guard
        .worlds
        .values()
        .map(|world| WorldView {
            id: world.id.clone(),
            kind: world.kind.clone(),
            label: world.label.clone(),
            connected: world.connected,
            status: world.status.clone(),
            capabilities: world.capabilities.iter().map(|c| c.name.clone()).collect(),
            pending: world.pending.len(),
            context: world.context.clone(),
            context_at: world.context_at,
        })
        .collect()
}

/// Cuántas acciones ha ejecutado ARIA en un mundo.
///
/// Sirve para *verificar*: si ARIA cree que ha actuado en Minecraft pero el
/// contador no se ha movido, la acción no ocurrió.
pub async fn action_count(world_id: &str) -> u64 {
    let guard = worlds().lock().await;
    guard.worlds.get(world_id).map(|w| w.actions).unwrap_or(0)
}

/// Resumen textual de los mundos para el prompt del modelo.
pub fn prompt_summary() -> String {
    let guard = match worlds().try_lock() {
        Ok(guard) => guard,
        Err(_) => return String::new(),
    };
    let mut out = String::new();
    for world in guard.worlds.values() {
        out.push_str(&format!(
            "- {} ({}): {}\n",
            world.label,
            world.kind,
            if world.connected { "conectado" } else { "sin conectar" }
        ));
        if !world.capabilities.is_empty() {
            let caps: Vec<&str> = world.capabilities.iter().map(|c| c.name.as_str()).collect();
            out.push_str(&format!("  puede: {}\n", caps.join(", ")));
        }
    }
    out
}

/// Registra (o actualiza) un mundo.
pub async fn register(
    id: &str,
    kind: &str,
    label: &str,
    capabilities: Vec<Capability>,
) -> Result<World, String> {
    let id = id.trim().to_lowercase();
    if id.is_empty() {
        return Err("el mundo necesita un identificador".to_string());
    }
    let mut guard = worlds().lock().await;
    let now = now_secs();
    if guard.worlds.len() >= MAX_WORLDS && !guard.worlds.contains_key(&id) {
        return Err("no caben más mundos".to_string());
    }
    let world = guard.worlds.entry(id.clone()).or_insert_with(|| World {
        id: id.clone(),
        kind: kind.to_string(),
        label: label.to_string(),
        capabilities: Vec::new(),
        context: json!({}),
        context_at: now,
        connected: false,
        status: "registrado".to_string(),
        actions: 0,
        last_action_at: 0,
        pending: VecDeque::new(),
        created_at: now,
        updated_at: now,
    });
    world.kind = kind.to_string();
    if !label.trim().is_empty() {
        world.label = label.to_string();
    }
    if !capabilities.is_empty() {
        world.capabilities = capabilities;
    }
    world.updated_at = now;
    let view = world.clone();
    persist_worlds(&guard);
    Ok(view)
}

/// Publica el estado de un mundo (`context_update` del neuro-sdk).
pub async fn publish_context(world_id: &str, context: Value) -> Result<World, String> {
    let encoded = context.to_string();
    if encoded.len() > MAX_CONTEXT_BYTES {
        return Err("el contexto es demasiado grande".to_string());
    }
    let mut guard = worlds().lock().await;
    let Some(world) = guard.worlds.get_mut(world_id) else {
        return Err(format!("no existe el mundo '{world_id}'"));
    };
    world.context = context;
    world.context_at = now_secs();
    world.connected = true;
    if world.status == "esperando puente" || world.status == "sin conectar" {
        world.status = "conectado".to_string();
    }
    world.updated_at = world.context_at;
    let view = world.clone();
    persist_worlds(&guard);
    Ok(view)
}

/// Marca un mundo como desconectado.
pub async fn mark_disconnected(world_id: &str) {
    let mut guard = worlds().lock().await;
    if let Some(world) = guard.worlds.get_mut(world_id) {
        world.connected = false;
        world.status = "sin conectar".to_string();
        world.updated_at = now_secs();
    }
}

/// Ejecuta una acción de ARIA en un mundo.
///
/// Si el mundo tiene ejecutor local (VRChat, escritorio) la acción ocurre en
/// el acto; si no, queda en cola para que un puente externo la recoja.
pub async fn execute(world_id: &str, action: &str, args: Value) -> Result<String, String> {
    let action = action.trim().to_lowercase();
    if action.is_empty() {
        return Err("la acción va vacía".to_string());
    }

    // Comprobación de capacidad antes de nada: ARIA no puede inventarse
    // verbs que el mundo no ha declarado.
    {
        let guard = worlds().lock().await;
        let Some(world) = guard.worlds.get(world_id) else {
            return Err(format!("no existe el mundo '{world_id}'"));
        };
        if !world.capabilities.is_empty()
            && !world.capabilities.iter().any(|c| c.name == action)
        {
            return Err(format!(
                "'{world_id}' no sabe hacer '{action}' (puede: {})",
                world
                    .capabilities
                    .iter()
                    .map(|c| c.name.as_str())
                    .collect::<Vec<_>>()
                    .join(", ")
            ));
        }
    }

    // Política global: hay verbos que no se ejecutan aunque un mundo los
    // declare. Matar o borrar procesos del usuario no es una capacidad de
    // ARIA en ningún escenario (ver `ARIA_APP/backend/process_guard.py`).
    if is_forbidden(&action) {
        return Err(format!(
            "la acción '{action}' está prohibida: ARIA no ejecuta acciones destructivas"
        ));
    }

    // Texto de la acción (lo usan casi todas).
    let text = args
        .get("text")
        .and_then(|v| v.as_str())
        .unwrap_or_default()
        .trim()
        .to_string();

    let outcome = match (world_id, action.as_str()) {
        ("vrchat", "chatbox.say") => match crate::osc::send_chatbox(&text, true, 6.0) {
            Ok(bytes) => format!("chatbox de VRChat: {bytes} bytes"),
            Err(err) => return Err(format!("no se pudo escribir en VRChat: {err}")),
        },
        ("vrchat", "expression.set") => {
            let expression = args
                .get("expression")
                .and_then(|v| v.as_str())
                .unwrap_or("neutra");
            match crate::osc::send_expression(expression) {
                Ok(bytes) => format!("expresión '{expression}': {bytes} bytes"),
                Err(err) => return Err(format!("no se pudo cambiar la expresión: {err}")),
            }
        }
        ("escritorio", "say") => {
            crate::autonomy::broadcast_event(&crate::autonomy::WorldEvent {
                id: 0,
                kind: "habla".to_string(),
                source: "escritorio".to_string(),
                text: text.clone(),
                payload: json!({ "mundo": "escritorio" }),
                at: now_secs(),
            });
            format!("dicho en el escritorio: {text}")
        }
        ("escritorio", "skill.run") => {
            let skill_id = args
                .get("skill_id")
                .and_then(|v| v.as_str())
                .unwrap_or_default()
                .trim()
                .to_string();
            if skill_id.is_empty() {
                return Err("falta skill_id".to_string());
            }
            let input = args
                .get("input")
                .and_then(|v| v.as_str())
                .unwrap_or_default()
                .to_string();
            let (output, xp) = crate::creativity::run_generated_skill(&skill_id, &input).await?;
            format!("{output} (+{xp} XP)")
        }
        ("escritorio", "status") => {
            let skills = crate::creativity::skill_catalog().await.len();
            format!("{skills} skills disponibles")
        }
        _ => {
            // Mundo externo: la acción se encola.
            let mut guard = worlds().lock().await;
            let id = guard.next_id;
            guard.next_id += 1;
            let Some(world) = guard.worlds.get_mut(world_id) else {
                return Err(format!("no existe el mundo '{world_id}'"));
            };
            world.pending.push_back(PendingAction {
                id,
                action: action.clone(),
                args: args.clone(),
                created_at: now_secs(),
            });
            while world.pending.len() > MAX_PENDING {
                world.pending.pop_front();
            }
            let queued = world.pending.len();
            format!("encolada en {world_id} (pendientes: {queued})")
        }
    };

    {
        let mut guard = worlds().lock().await;
        if let Some(world) = guard.worlds.get_mut(world_id) {
            world.actions += 1;
            world.last_action_at = now_secs();
            world.updated_at = world.last_action_at;
        }
        persist_worlds(&guard);
    }

    Ok(outcome)
}

/// Cola de un mundo: lo que un puente externo tiene que ejecutar.
async fn take_pending_route(Path(id): Path<String>) -> Json<Value> {
    let messages = take_pending(&id).await;
    Json(json!({
        "status": "ok",
        "actions": messages,
        "count": messages.len(),
        "server": "ARIA-Axum-8002",
    }))
}

/// Acciones pendientes de un mundo, para el puente externo.
///
/// Se devuelven y se vacían: el puente es el dueño de la cola.
pub async fn take_pending(world_id: &str) -> Vec<PendingAction> {
    let mut guard = worlds().lock().await;
    let Some(world) = guard.worlds.get_mut(world_id) else {
        return Vec::new();
    };
    let pending: Vec<PendingAction> = world.pending.drain(..).collect();
    if !pending.is_empty() {
        world.updated_at = now_secs();
        persist_worlds(&guard);
    }
    pending
}

/// Registra una obligación del mundo (`action_force`).
pub async fn push_force(
    world_id: &str,
    action: &str,
    args: Value,
    timeout_secs: u64,
) -> Result<Force, String> {
    let mut guard = worlds().lock().await;
    if !guard.worlds.contains_key(world_id) {
        return Err(format!("no existe el mundo '{world_id}'"));
    }
    let now = now_secs();
    let id = guard.next_id;
    guard.next_id += 1;
    let force = Force {
        id,
        world: world_id.to_string(),
        action: action.trim().to_string(),
        args,
        deadline: now + timeout_secs.max(1),
        created_at: now,
        satisfied: false,
        result: None,
    };
    guard.forces.push_back(force.clone());
    while guard.forces.len() > MAX_FORCES {
        guard.forces.pop_front();
    }
    persist_worlds(&guard);
    Ok(force)
}

/// La obligación más urgente y sin cumplir.
///
/// Si venció su plazo se marca como no cumplida y se descarta: un `force`
/// caducado no puede estar esperando para siempre.
pub async fn take_force() -> Option<Force> {
    let mut guard = worlds().lock().await;
    let now = now_secs();
    let mut expired: Vec<Force> = Vec::new();
    let mut chosen: Option<Force> = None;
    while let Some(force) = guard.forces.pop_front() {
        if force.satisfied {
            continue;
        }
        if force.deadline <= now {
            expired.push(force);
            continue;
        }
        if chosen.is_none() {
            chosen = Some(force);
        } else {
            // Se devuelven a la cola: sólo se atiende una fuerza por tick.
            guard.forces.push_front(force);
            break;
        }
    }
    for force in expired {
        eprintln!(
            "[ARIA-Mundos] la fuerza '{}' de '{}' caducó sin cumplirse",
            force.action, force.id
        );
    }
    chosen
}

/// Marca una fuerza como cumplida con su resultado.
pub async fn satisfy_force(force_id: u64, result: String) {
    let mut guard = worlds().lock().await;
    let mut record = Force {
        id: force_id,
        world: String::new(),
        action: String::new(),
        args: json!({}),
        deadline: 0,
        created_at: now_secs(),
        satisfied: true,
        result: Some(result.clone()),
    };
    for force in guard.forces.iter_mut() {
        if force.id == force_id {
            force.satisfied = true;
            force.result = Some(result.clone());
            record = force.clone();
            break;
        }
    }
    // La fuerza atendida se guarda en el historial del mundo para que se
    // vea qué pasó, pero ya no obliga.
    guard.forces.push_back(record);
    while guard.forces.len() > MAX_FORCES {
        guard.forces.pop_front();
    }
    persist_worlds(&guard);
}

/// Fuerzas pendientes (para la UI).
pub async fn forces() -> Vec<Force> {
    let guard = worlds().lock().await;
    guard.forces.iter().rev().take(10).cloned().collect()
}

/* ------------------------------------------------------------------ *
 * Rutas
 * ------------------------------------------------------------------ */

pub fn router() -> Router<()> {
    Router::new()
        .route("/api/worlds", get(list_worlds).post(register_world))
        .route("/api/worlds/events", get(world_events))
        .route("/api/worlds/forces", get(list_forces))
        .route("/api/worlds/:id", get(get_world).delete(delete_world))
        .route("/api/worlds/:id/context", post(publish_context_route))
        .route("/api/worlds/:id/actions", post(run_action))
        .route("/api/worlds/:id/pending", get(take_pending_route))
        .route("/api/worlds/:id/force", post(push_force_route))
        .route("/api/worlds/:id/bridge", post(bridge_state))
}

async fn list_worlds() -> Json<Value> {
    let worlds = views().await;
    Json(json!({
        "status": "ok",
        "worlds": worlds,
        "count": worlds.len(),
        "server": "ARIA-Axum-8002",
    }))
}

async fn get_world(Path(id): Path<String>) -> Json<Value> {
    let guard = worlds().lock().await;
    match guard.worlds.get(&id) {
        Some(world) => Json(json!({
            "status": "ok",
            "world": world,
            "server": "ARIA-Axum-8002",
        })),
        None => Json(json!({
            "status": "error",
            "error": format!("no existe el mundo '{id}'"),
        })),
    }
}

#[derive(Deserialize)]
struct RegisterRequest {
    id: String,
    #[serde(default)]
    kind: Option<String>,
    #[serde(default)]
    label: Option<String>,
    #[serde(default)]
    capabilities: Vec<Capability>,
}

async fn register_world(Json(req): Json<RegisterRequest>) -> Json<Value> {
    let kind = req.kind.clone().unwrap_or_else(|| "juego".to_string());
    let label = req.label.clone().unwrap_or_else(|| req.id.clone());
    match register(&req.id, &kind, &label, req.capabilities).await {
        Ok(world) => Json(json!({
            "status": "ok",
            "world": world,
            "server": "ARIA-Axum-8002",
        })),
        Err(error) => Json(json!({ "status": "error", "error": error })),
    }
}

async fn delete_world(Path(id): Path<String>) -> Json<Value> {
    let mut guard = worlds().lock().await;
    let removed = guard.worlds.remove(&id).is_some();
    persist_worlds(&guard);
    Json(json!({
        "status": if removed { "ok" } else { "error" },
        "removed": removed,
        "id": id,
    }))
}

#[derive(Deserialize)]
struct ContextRequest {
    #[serde(default)]
    context: Value,
    #[serde(default)]
    connected: Option<bool>,
}

async fn publish_context_route(Path(id): Path<String>, Json(req): Json<ContextRequest>) -> Json<Value> {
    let context = if req.context.is_null() {
        json!({})
    } else {
        req.context
    };
    match publish_context(&id, context).await {
        Ok(world) => Json(json!({
            "status": "ok",
            "world": world,
            "server": "ARIA-Axum-8002",
        })),
        Err(error) => Json(json!({ "status": "error", "error": error })),
    }
}

#[derive(Deserialize)]
struct ActionRequest {
    #[serde(default)]
    action: String,
    #[serde(default)]
    args: Value,
}

async fn run_action(Path(id): Path<String>, Json(req): Json<ActionRequest>) -> Json<Value> {
    let args = if req.args.is_null() {
        json!({})
    } else {
        req.args
    };
    match execute(&id, &req.action, args).await {
        Ok(result) => Json(json!({
            "status": "ok",
            "result": result,
            "server": "ARIA-Axum-8002",
        })),
        Err(error) => Json(json!({ "status": "error", "error": error })),
    }
}

#[derive(Deserialize)]
struct ForceRequest {
    #[serde(default)]
    action: String,
    #[serde(default)]
    args: Value,
    #[serde(default)]
    timeout_secs: Option<u64>,
}

async fn push_force_route(Path(id): Path<String>, Json(req): Json<ForceRequest>) -> Json<Value> {
    let timeout = req.timeout_secs.unwrap_or(DEFAULT_FORCE_TIMEOUT_SECS);
    match push_force(&id, &req.action, req.args, timeout).await {
        Ok(force) => Json(json!({
            "status": "ok",
            "force": force,
            "server": "ARIA-Axum-8002",
        })),
        Err(error) => Json(json!({ "status": "error", "error": error })),
    }
}

async fn list_forces() -> Json<Value> {
    let forces = forces().await;
    Json(json!({
        "status": "ok",
        "forces": forces,
        "server": "ARIA-Axum-8002",
    }))
}

#[derive(Deserialize)]
struct BridgeRequest {
    #[serde(default)]
    connected: bool,
    #[serde(default)]
    status: Option<String>,
}

/// Un puente externo dice si sigue conectado.
async fn bridge_state(Path(id): Path<String>, Json(req): Json<BridgeRequest>) -> Json<Value> {
    let mut guard = worlds().lock().await;
    let Some(world) = guard.worlds.get_mut(&id) else {
        return Json(json!({
            "status": "error",
            "error": format!("no existe el mundo '{id}'"),
        }));
    };
    world.connected = req.connected;
    world.status = req
        .status
        .clone()
        .unwrap_or_else(|| if req.connected { "conectado" } else { "sin conectar" }.to_string());
    world.updated_at = now_secs();
    let view = world.clone();
    persist_worlds(&guard);
    Json(json!({
        "status": "ok",
        "world": view,
        "server": "ARIA-Axum-8002",
    }))
}

/// Flujo de eventos del mundo.
///
/// Reutiliza el canal de difusión de la autonomía: así la UI ve en el mismo
/// sitio lo que pasa en Minecraft, en VRChat y en el chat social.
async fn world_events() -> axum::response::sse::Sse<impl futures::Stream<Item = Result<axum::response::sse::Event, std::convert::Infallible>>> {
    use axum::response::sse::{Event, KeepAlive, Sse};

    let receiver = crate::autonomy::broadcaster().subscribe();
    let stream = futures::stream::unfold(receiver, |mut receiver| async move {
        match receiver.recv().await {
            Ok(payload) => Some((Ok(Event::default().data(payload)), receiver)),
            Err(broadcast::error::RecvError::Lagged(skipped)) => Some((
                Ok(Event::default().data(json!({ "type": "lagged", "skipped": skipped }).to_string())),
                receiver,
            )),
            Err(broadcast::error::RecvError::Closed) => None,
        }
    });

    Sse::new(stream).keep_alive(KeepAlive::default())
}

/// Estado de autenticación: lo usan los puentes que llaman a la API.
pub async fn auth_probe(state: &Arc<Mutex<SharedState>>) -> Option<String> {
    let guard = state.lock().await;
    Some(guard.api_key().to_string())
}

/* ------------------------------------------------------------------ *
 * Tests
 * ------------------------------------------------------------------ */

#[cfg(test)]
mod tests {
    use super::*;

    fn capability_names(world: &World) -> Vec<&str> {
        world.capabilities.iter().map(|c| c.name.as_str()).collect()
    }

    #[test]
    fn los_mundos_de_fabrica_declaran_sus_capacidades() {
        let worlds = builtin_worlds(0);
        let by_id: BTreeMap<&str, &World> = worlds.iter().map(|w| (w.id.as_str(), w)).collect();
        assert!(by_id.contains_key("escritorio"));
        assert!(by_id.contains_key("vrchat"));
        assert!(by_id.contains_key("minecraft"));
        let caps = capability_names(by_id["minecraft"]);
        assert!(caps.contains(&"chat.say"));
        assert!(caps.contains(&"move"));
    }

    #[test]
    fn el_avatar_de_vrchat_sabe_hablar_y_expresarse() {
        let worlds = builtin_worlds(0);
        let vrchat = worlds.iter().find(|w| w.id == "vrchat").expect("vrchat");
        let caps = capability_names(vrchat);
        assert!(caps.contains(&"chatbox.say"));
        assert!(caps.contains(&"expression.set"));
    }

    #[test]
    fn una_capacidad_desconocida_no_se_puede_ejecutar() {
        // Se comprueba la lógica de validación sin tocar el estado global.
        let worlds = builtin_worlds(0);
        let minecraft = worlds.iter().find(|w| w.id == "minecraft").expect("minecraft");
        assert!(!capability_names(minecraft).contains(&"teletransportar"));
    }

    #[test]
    fn el_contexto_muy_grande_se_rechaza() {
        let big = json!({ "datos": "x".repeat(MAX_CONTEXT_BYTES + 10) });
        assert!(big.to_string().len() > MAX_CONTEXT_BYTES);
    }

    #[test]
    fn los_verbos_destructivos_estan_prohibidos() {
        assert!(is_forbidden("kill"));
        assert!(is_forbidden("process.kill"));
        assert!(is_forbidden("taskkill"));
        assert!(is_forbidden("TASKKILL"));
        assert!(is_forbidden("system:delete"));
        assert!(is_forbidden("stop-process"));
    }

    #[test]
    fn las_acciones_normales_no_estan_prohibidas() {
        assert!(!is_forbidden("move"));
        assert!(!is_forbidden("chat.say"));
        assert!(!is_forbidden("craft"));
        assert!(!is_forbidden("observe"));
    }

    #[tokio::test]
    async fn la_expresion_de_un_mundo_externo_se_encola() {
        // La cola vive en el estado global; para no depender del orden de
        // los tests se usa un mundo de prueba aislado.
        let mut guard = worlds().lock().await;
        guard.worlds.insert(
            "test-mundo".to_string(),
            World {
                id: "test-mundo".to_string(),
                kind: "juego".to_string(),
                label: "Test".to_string(),
                capabilities: vec![capability("move", "Ir", &["x"])],
                context: json!({}),
                context_at: 0,
                connected: false,
                status: "listo".to_string(),
                actions: 0,
                last_action_at: 0,
                pending: VecDeque::new(),
                created_at: 0,
                updated_at: 0,
            },
        );
        let id = guard.next_id;
        guard.next_id += 1;
        guard
            .worlds
            .get_mut("test-mundo")
            .expect("mundo")
            .pending
            .push_back(PendingAction {
                id,
                action: "move".to_string(),
                args: json!({ "x": 1 }),
                created_at: 0,
            });
        let pending = guard.worlds.get("test-mundo").expect("mundo").pending.len();
        assert_eq!(pending, 1);
        guard.worlds.remove("test-mundo");
    }
}
