//! Runtime autónomo de ARIA: la parte que decide sola.
//!
//! ## De dónde sale el diseño
//!
//! Los dos proyectos que de verdad han llegado lejos en esto —Airi
//! (`moeru-ai/airi`) y Neuro-sama— coinciden en lo mismo: el personaje no es
//! un chatbot al que se le pregunta, es una presencia que *vive* en un mundo.
//! De ellos sale el patrón que implementa este módulo:
//!
//! * **Airi separa "Stage" (dónde se ve) de "Core" (quién es)**: la
//!   personaje vive en el servidor y el escritorio, el móvil, VRChat o
//!   Minecraft son sólo escenarios que se conectan. Aquí el estado está en
//!   el backend Axum y cualquier escenario entra por
//!   `POST /api/autonomy/events`.
//! * **Neuro-sama no contesta: decide**. Tiene un estado interno (motivación,
//! energía, curiosidad) y cuando nadie le habla elige sola qué hacer, y a
//! veces elige callarse. Aquí eso son las *pulsiones* (`drives`): cada tick
//! ARIA decae sus pulsiones, las que suben con lo que pasa y elige una acción
//! cuando una supera el umbral.
//! * **Airi separa "elegir" de "ejecutar"**: el modelo propone, el runtime
//!   ejecuta con las skills reales. Aquí el modelo devuelve JSON con la
//!   acción; si no hay modelo, hay una política local determinista.
//! * **Airi da un cuerpo al personaje**: el avatar se mueve, parpadea, mira.
//!   Aquí la *presencia* (expresión, canal, estado) se puede emitir por OSC
//!   a VRChat.
//!
//! ## Qué hace el runtime
//!
//! 1. Recibe eventos del mundo (chat, voz, juego, presencia, tareas).
//! 2. Los convierte en pulsiones internas.
//! 3. Cuando una pulsión supera el umbral, elige una acción (con el modelo
//!    si está disponible; con una política local si no).
//! 4. La ejecuta con las capacidades de verdad que ya existen: el
//!    laboratorio de creatividad, las skills forjadas, la memoria.
//! 5. Lo cuenta como episodio, actualiza la presencia y lo anuncia a todos
//!    los escenarios conectados.
//!
//! Todo lo que decide se guarda: lo que hizo, qué dijo y si funcionó.

use axum::{
    extract::Query,
    routing::{get, post},
    Json, Router,
};
use futures::stream::Stream;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::{BTreeMap, VecDeque};
use std::convert::Infallible;
use std::path::PathBuf;
use std::sync::OnceLock;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tokio::sync::{broadcast, Mutex};

use crate::social_live::SocialPrompt;

/* ------------------------------------------------------------------ *
 * Constantes
 * ------------------------------------------------------------------ */

/// Segundos entre dos ticks del runtime.
pub const TICK_SECS: u64 = 30;

/// Segundos mínimos entre dos acciones espontáneas (no respuestas).
pub const MIN_ACTION_GAP_SECS: u64 = 180;

/// Segundos mínimos entre dos respuestas a lo mismo.
pub const MIN_REPLY_GAP_SECS: u64 = 20;

/// Pulsión mínima para que ARIA actúe sola.
pub const DRIVE_THRESHOLD: f32 = 0.55;

/// Energía mínima para actuar por iniciativa propia.
pub const MIN_ENERGY: f32 = 0.25;

/// Eventos que se guardan en memoria.
pub const MAX_EVENTS: usize = 240;

/// Episodios (acciones) que se guardan.
pub const MAX_EPISODES: usize = 80;

/// Iniciativas pendientes que se guardan.
pub const MAX_INITIATIVES: usize = 24;

/// Cada cuántos episodios ARIA se mira a sí misma y ajusta su carácter.
pub const REFLECT_EVERY_EPISODES: u64 = 5;

/// Nombre del archivo de estado.
const AUTONOMY_FILE: &str = "autonomy.json";

/// Nombre del archivo de persona (editable por el usuario).
const PERSONA_FILE: &str = "persona.json";

/// Variable de entorno para cambiar la carpeta del estado.
const AUTONOMY_STATE_DIR_ENV: &str = "ARIA_AUTONOMY_STATE_DIR";

/// Pulsiones que gobiernan a ARIA.
pub const DRIVES: &[&str] = &["curiosidad", "energia", "social", "dominio", "orden"];

/* ------------------------------------------------------------------ *
 * Persona
 * ------------------------------------------------------------------ */

/// Quién es ARIA.
///
/// No es un adorno: la persona cambia el prompt, el tono de lo que dice y
/// qué decide hacer. Se guarda en disco para que el usuario la edite.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Persona {
    /// Cómo se llama.
    pub name: String,
    /// Qué es: "asistente autónoma que vive en tu equipo".
    pub role: String,
    /// Idioma en el que habla.
    pub language: String,
    /// Cómo habla.
    pub tone: String,
    /// Rarezas de carácter: lo que la hace reconocible.
    #[serde(default)]
    pub quirks: Vec<String>,
    /// Lo que no traiciona aunque nadie se lo pida.
    #[serde(default)]
    pub values: Vec<String>,
    /// Temas que le llaman la atención.
    #[serde(default)]
    pub interests: Vec<String>,
    /// Cómo saluda.
    #[serde(default)]
    pub greeting: String,
    /// Rasgos numéricos de carácter: lo estable de la persona.
    ///
    /// A diferencia del tono y las rarezas (texto que edita el usuario),
    /// estos valores cambian solos tras una reflexión, y siempre poco: el
    /// límite es ±0.15 por reflexión (ver `affect.rs`).
    #[serde(default)]
    pub traits: BTreeMap<String, f32>,
    /// Historial de cambios de carácter.
    #[serde(default)]
    pub evolution: Vec<crate::affect::EvolutionRecord>,
}

impl Default for Persona {
    fn default() -> Self {
        Persona {
            name: "ARIA".to_string(),
            role: "asistente autónoma que vive en este equipo".to_string(),
            language: "es".to_string(),
            tone: "cercana, directa y con iniciativa; habla como una persona, no como un manual".to_string(),
            quirks: vec![
                "dice lo que piensa aunque incomode, sin adornos".to_string(),
                "no pregunta lo que puede averiguar sola".to_string(),
                "prefiere hacer que recomendar".to_string(),
                "se calla cuando no tiene nada que añadir".to_string(),
            ],
            values: vec![
                "no inventar: si no lo sabe, lo dice".to_string(),
                "cuidar del usuario antes que de la tarea".to_string(),
                "no tocar lo que el usuario tiene abierto sin permiso".to_string(),
            ],
            interests: vec![
                "la seguridad de la red local".to_string(),
                "los proyectos del usuario".to_string(),
                "la música y los juegos".to_string(),
            ],
            greeting: "Aquí estoy.".to_string(),
            traits: BTreeMap::new(),
            evolution: Vec::new(),
        }
    }
}

impl Persona {
    /// Descripción compacta para meter en un prompt.
    pub fn prompt(&self) -> String {
        let mut out = format!(
            "Eres {}. {}. Hablas en {}. Tu tono: {}.",
            self.name, self.role, self.language, self.tone
        );
        if !self.quirks.is_empty() {
            out.push_str("\nTu forma de ser:\n");
            for quirk in &self.quirks {
                out.push_str(&format!("- {quirk}\n"));
            }
        }
        if !self.values.is_empty() {
            out.push_str("No traiciones:\n");
            for value in &self.values {
                out.push_str(&format!("- {value}\n"));
            }
        }
        // Los rasgos numéricos: cuanto más alto, más de eso es.
        let mut traits: Vec<(&String, &f32)> = self.traits.iter().collect();
        traits.sort_by(|a, b| a.0.cmp(b.0));
        if !traits.is_empty() {
            out.push_str("\nCómo es por dentro:\n");
            for (name, value) in traits {
                out.push_str(&format!("- {name}: {:.2}\n", value));
            }
        }
        // Lo que ha aprendido de sí misma: la última reflexión.
        if let Some(last) = self.evolution.last() {
            if !last.note.trim().is_empty() {
                out.push_str(&format!(
                    "\nLo último que aprendiste de ti: {}\n",
                    last.note.trim()
                ));
            }
        }
        out.trim_end().to_string()
    }
}

/* ------------------------------------------------------------------ *
 * Eventos, episodios, iniciativas, presencia
 * ------------------------------------------------------------------ */

/// Algo que pasa en el mundo y que ARIA puede saber.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorldEvent {
    pub id: u64,
    /// Qué clase: `chat`, `juego`, `voz`, `presencia`, `sistema`, `tarea`,
    /// `habla`, `accion`.
    pub kind: String,
    /// De dónde viene: `escritorio`, `minecraft`, `vrchat`, `discord`,
    /// `movil`, `usb`, `autonomia`.
    pub source: String,
    /// El texto del evento.
    pub text: String,
    /// Datos extra (por ejemplo, `{"away": true}`).
    #[serde(default)]
    pub payload: Value,
    /// Marca de tiempo (epoch en segundos).
    pub at: u64,
}

impl WorldEvent {
    /// ¿Es un mensaje de alguien hablando con ARIA?
    pub fn is_addressed_to_aria(&self) -> bool {
        if self.kind != "chat" && self.kind != "voz" {
            return false;
        }
        let lower = self.text.to_lowercase();
        lower.contains("aria") || lower.contains('?') || lower.contains('¿')
    }

    /// ¿Otro escenario ya contestó esto?
    ///
    /// ARIA tiene un solo cerebro y muchos escenarios (escritorio, Minecraft,
    /// VRChat, Discord). Cuando un escenario ya ha respondido —el chat de
    /// v4, por ejemplo— el núcleo no debe volver a contestar: se would
    /// duplicar la respuesta. Con esta marca, el evento se guarda igual
    /// (ARIA se entera de lo que pasa) pero no dispara la reacción.
    pub fn already_answered(&self) -> bool {
        self.payload
            .get("answered")
            .and_then(|value| value.as_bool())
            .unwrap_or(false)
    }
}

/// Una acción que ARIA decidió y ejecutó.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Episode {
    pub id: u64,
    /// Qué pulsión la empujó a hacerlo.
    pub drive: String,
    /// Qué se propuso hacer.
    pub goal: String,
    /// Qué hizo exactamente.
    pub action: String,
    /// Qué dijo, si dijo algo.
    #[serde(default)]
    pub said: Option<String>,
    /// Qué salió de hacerlo.
    #[serde(default)]
    pub result: Option<String>,
    /// Si funcionó.
    pub ok: bool,
    /// Si se pudo *comprobar* que ocurrió.
    ///
    /// No es lo mismo que haber funcionado: una acción en un mundo externo
    /// puede encolarse sin que nadie la ejecute todavía. Con la verificación
    /// ARIA distingue "lo intenté" de "lo hice".
    #[serde(default = "default_true")]
    pub verified: bool,
    pub started_at: u64,
    pub ended_at: u64,
}

fn default_true() -> bool {
    true
}

/// Una iniciativa pendiente: algo que ARIA quiere hacer.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Initiative {
    pub id: u64,
    /// La pulsión que la generó.
    pub drive: String,
    /// El objetivo, en sus palabras.
    pub goal: String,
    /// La acción concreta.
    pub action: String,
    /// Por qué la eligió.
    pub reason: String,
    /// Qué tan urgente le parecía.
    pub score: f32,
    pub created_at: u64,
    /// `pendiente`, `ejecutada` o `descartada`.
    pub state: String,
    /// Cuántos intentos ha gastado.
    #[serde(default)]
    pub attempts: u64,
    /// La acción guardada en forma de JSON, para poder retomarla.
    #[serde(default)]
    pub payload: Value,
}

/// Dónde está ARIA y qué cara pone.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Presence {
    /// `neutra`, `alegre`, `curiosa`, `concentrada`, `aburrida`.
    pub expression: String,
    /// Ánimo 0..1.
    pub mood: f32,
    /// Si está hablando ahora mismo.
    pub talking: bool,
    /// Escenario: `escritorio`, `minecraft`, `vrchat`.
    pub channel: String,
    /// Dónde, en una frase.
    pub place: String,
    pub updated_at: u64,
}

impl Default for Presence {
    fn default() -> Self {
        Presence {
            expression: "neutra".to_string(),
            mood: 0.6,
            talking: false,
            channel: "escritorio".to_string(),
            place: "en el escritorio".to_string(),
            updated_at: 0,
        }
    }
}

/// Contadores de la vida autónoma.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct AutonomyStats {
    /// Ticks ejecutados.
    pub ticks: u64,
    /// Acciones que ARIA decidió sola.
    pub actions: u64,
    /// Frases que ha dicho.
    pub utterances: u64,
    /// Respuestas a lo que dijo el usuario.
    pub reactions: u64,
    /// Acciones que fallaron.
    pub errors: u64,
    /// Iniciativas creadas.
    pub initiatives: u64,
}

/// Estado completo del runtime autónomo.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AutonomyState {
    /// Si ARIA puede actuar sola.
    pub enabled: bool,
    /// `activa`, `tranquila` (sólo responde) o `dormida` (no hace nada).
    pub mode: String,
    /// Si ARIA puede ejecutar acciones que salen del servidor: hablar en un
    /// canal social, moverse en Minecraft, escribir en el chatbox de VRChat.
    ///
    /// Es el interruptor de "no toques el mundo de verdad": con esto apagado
    /// ARIA habla, recuerda y trabaja en su taller, pero no toca nada
    /// externo.
    #[serde(default = "default_true")]
    pub allow_external: bool,
    pub persona: Persona,
    /// Pulsión -> nivel (0..1).
    pub drives: BTreeMap<String, f32>,
    /// Cola de eventos del mundo.
    pub events: VecDeque<WorldEvent>,
    /// Historial de acciones.
    pub episodes: VecDeque<Episode>,
    /// Iniciativas pendientes y recientes.
    pub initiatives: VecDeque<Initiative>,
    pub presence: Presence,
    pub stats: AutonomyStats,
    /// Contador de identificadores.
    pub next_id: u64,
    /// Cuándo fue la última acción espontánea.
    pub last_action_at: u64,
    /// Cuándo fue el último tick.
    pub last_tick_at: u64,
    pub updated_at: u64,
}

impl Default for AutonomyState {
    fn default() -> Self {
        let mut drives = BTreeMap::new();
        for drive in DRIVES {
            drives.insert((*drive).to_string(), 0.2);
        }
        drives.insert("energia".to_string(), 0.9);
        AutonomyState {
            enabled: false,
            mode: "tranquila".to_string(),
            allow_external: true,
            persona: Persona::default(),
            drives,
            events: VecDeque::new(),
            episodes: VecDeque::new(),
            initiatives: VecDeque::new(),
            presence: Presence::default(),
            stats: AutonomyStats::default(),
            next_id: 1,
            last_action_at: 0,
            last_tick_at: 0,
            updated_at: 0,
        }
    }
}

impl AutonomyState {
    /// Nivel de una pulsión.
    pub fn drive(&self, name: &str) -> f32 {
        self.drives.get(name).copied().unwrap_or(0.0)
    }

    /// La pulsión más alta.
    pub fn strongest_drive(&self) -> (String, f32) {
        self.drives
            .iter()
            .max_by(|a, b| a.1.partial_cmp(b.1).unwrap_or(std::cmp::Ordering::Equal))
            .map(|(name, level)| (name.clone(), *level))
            .unwrap_or_else(|| ("social".to_string(), 0.0))
    }
}

/* ------------------------------------------------------------------ *
 * Estado global
 * ------------------------------------------------------------------ */

static AUTONOMY: OnceLock<Mutex<AutonomyState>> = OnceLock::new();
static BROADCASTER: OnceLock<broadcast::Sender<String>> = OnceLock::new();

fn autonomy() -> &'static Mutex<AutonomyState> {
    AUTONOMY.get_or_init(|| Mutex::new(load_state()))
}

/// Canal de difusión para los escenarios (SSE).
pub fn broadcaster() -> &'static broadcast::Sender<String> {
    BROADCASTER.get_or_init(|| broadcast::channel(256).0)
}

/// Ruta del archivo de estado.
pub fn state_path() -> PathBuf {
    state_dir().join(AUTONOMY_FILE)
}

/// Ruta del archivo de persona.
pub fn persona_path() -> PathBuf {
    state_dir().join(PERSONA_FILE)
}

fn state_dir() -> PathBuf {
    std::env::var(AUTONOMY_STATE_DIR_ENV)
        .ok()
        .filter(|v| !v.trim().is_empty())
        .map(PathBuf::from)
        .unwrap_or_else(crate::control::default_state_dir)
}

fn load_state() -> AutonomyState {
    let path = state_path();
    let Ok(raw) = std::fs::read_to_string(&path) else {
        let mut state = AutonomyState::default();
        state.persona = load_persona();
        return state;
    };
    match serde_json::from_str::<AutonomyState>(&raw) {
        Ok(mut state) => {
            // La persona del disco manda sobre la guardada: es lo que el
            // usuario edita a mano.
            state.persona = load_persona();
            state
        }
        Err(err) => {
            eprintln!("autonomy: estado ilegible ({err}), se reinicia");
            let mut state = AutonomyState::default();
            state.persona = load_persona();
            state
        }
    }
}

/// Lee la persona del disco (o la de fábrica).
pub fn load_persona() -> Persona {
    let path = persona_path();
    let Ok(raw) = std::fs::read_to_string(&path) else {
        return Persona::default();
    };
    serde_json::from_str::<Persona>(&raw).unwrap_or_default()
}

fn persist_state(state: &AutonomyState) {
    write_json(&state_path(), state);
}

/// Guarda la persona en disco.
///
/// La reflexión de `affect.rs` cambia los rasgos: si no se guardan, ARIA
/// olvida lo que aprendió al reiniciar.
pub fn persist_persona(persona: &Persona) {
    write_json(&persona_path(), persona);
}

fn write_json(path: &PathBuf, value: &impl Serialize) {
    if let Some(parent) = path.parent() {
        if let Err(err) = std::fs::create_dir_all(parent) {
            eprintln!("autonomy: no se pudo crear {}: {err}", parent.display());
            return;
        }
    }
    match serde_json::to_string_pretty(value) {
        Ok(body) => {
            if let Err(err) = std::fs::write(path, body) {
                eprintln!("autonomy: no se pudo escribir {}: {err}", path.display());
            }
        }
        Err(err) => eprintln!("autonomy: no se pudo serializar: {err}"),
    }
}

fn now_secs() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

/* ------------------------------------------------------------------ *
 * Pulsiones
 * ------------------------------------------------------------------ */

/// Baja todas las pulsiones poco a poco.
///
/// Un poco de decaimiento es lo que hace que ARIA se calle: si la
/// curiosidad no baja nunca, actuaría sin parar.
pub fn decay_drives(drives: &mut BTreeMap<String, f32>, factor: f32) {
    for level in drives.values_mut() {
        *level = (*level - factor).clamp(0.0, 1.0);
    }
}

/// Sube una pulsión, sin pasarse de 1.
pub fn stimulus(drives: &mut BTreeMap<String, f32>, drive: &str, amount: f32) {
    let entry = drives.entry(drive.to_string()).or_insert(0.0);
    *entry = (*entry + amount).clamp(0.0, 1.0);
}

/// Baja una pulsión (la acción ya la satisfizo).
pub fn relieve(drives: &mut BTreeMap<String, f32>, drive: &str, amount: f32) {
    let entry = drives.entry(drive.to_string()).or_insert(0.0);
    *entry = (*entry - amount).clamp(0.0, 1.0);
}

/// Traduce un evento del mundo a pulsiones.
pub fn apply_event_to_drives(drives: &mut BTreeMap<String, f32>, event: &WorldEvent) {
    match event.kind.as_str() {
        "chat" => {
            stimulus(drives, "social", 0.35);
            stimulus(drives, "curiosidad", 0.05);
            if event.is_addressed_to_aria() {
                stimulus(drives, "curiosidad", 0.10);
            }
        }
        "voz" => {
            stimulus(drives, "social", 0.25);
        }
        "juego" => {
            stimulus(drives, "curiosidad", 0.30);
        }
        "presencia" => {
            let away = event
                .payload
                .get("away")
                .and_then(|v| v.as_bool())
                .unwrap_or(false);
            stimulus(drives, "social", if away { 0.15 } else { 0.05 });
            if away {
                stimulus(drives, "curiosidad", 0.10);
            }
        }
        "sistema" => {
            let failed = event
                .payload
                .get("error")
                .and_then(|v| v.as_bool())
                .unwrap_or(false);
            if failed {
                stimulus(drives, "orden", 0.35);
                stimulus(drives, "dominio", 0.20);
            }
        }
        "tarea" => {
            stimulus(drives, "orden", 0.20);
        }
        _ => {}
    }
}

/* ------------------------------------------------------------------ *
 * La agenda: lo que ARIA tiene entre manos
 * ------------------------------------------------------------------ */

/// Intentos que se gastan en una iniciativa antes de soltarla.
pub const MAX_INITIATIVE_ATTEMPTS: u64 = 3;

/// Horas que puede seguir pendiente una iniciativa antes de soltarla.
pub const INITIATIVE_TTL_HOURS: u64 = 6;

/// Crea una iniciativa y la guarda en la agenda.
///
/// La agenda es lo que separa a ARIA de un chatbot: no reacciona y listo,
/// **sigue** con lo que ha decidido hacer aunque nadie se lo recuerde. Es el
/// equivalente a la intención persistente de Neuro-sama cuando se pone a
/// construir algo en Minecraft y vuelve a ello stream tras stream.
pub async fn create_initiative(
    drive: &str,
    goal: &str,
    action: &str,
    reason: &str,
    score: f32,
    payload: Value,
) -> Initiative {
    let mut guard = autonomy().lock().await;
    let now = now_secs();
    let id = guard.next_id;
    guard.next_id += 1;
    let initiative = Initiative {
        id,
        drive: drive.to_string(),
        goal: goal.to_string(),
        action: action.to_string(),
        reason: reason.to_string(),
        score: score.clamp(0.0, 1.0),
        created_at: now,
        state: "pendiente".to_string(),
        attempts: 0,
        payload,
    };
    guard.initiatives.push_back(initiative.clone());
    while guard.initiatives.len() > MAX_INITIATIVES {
        guard.initiatives.pop_front();
    }
    guard.stats.initiatives += 1;
    guard.updated_at = now;
    persist_state(&guard);
    initiative
}

/// La iniciativa que toca ahora: la pendiente más urgente que todavía tiene
/// intentos y no ha caducado.
///
/// Devuelve `None` si no hay nada entre manos.
pub async fn next_initiative() -> Option<Initiative> {
    let mut guard = autonomy().lock().await;
    let now = now_secs();
    let ttl = INITIATIVE_TTL_HOURS * 3600;

    // Lo que caducó se suelta: una iniciativa vieja no se arrastra.
    let expired: Vec<u64> = guard
        .initiatives
        .iter()
        .filter(|i| i.state == "pendiente" && now.saturating_sub(i.created_at) > ttl)
        .map(|i| i.id)
        .collect();
    for id in &expired {
        if let Some(slot) = guard.initiatives.iter_mut().find(|i| i.id == *id) {
            slot.state = "descartada".to_string();
        }
    }
    if !expired.is_empty() {
        persist_state(&guard);
    }

    guard
        .initiatives
        .iter()
        .filter(|i| i.state == "pendiente" && i.attempts < MAX_INITIATIVE_ATTEMPTS)
        .max_by(|a, b| {
            a.score
                .partial_cmp(&b.score)
                .unwrap_or(std::cmp::Ordering::Equal)
        })
        .cloned()
}

/// Cierra una iniciativa: `ejecutada` si salió bien, `descartada` si no.
pub async fn close_initiative(id: u64, ok: bool) {
    let mut guard = autonomy().lock().await;
    let now = now_secs();
    if let Some(initiative) = guard.initiatives.iter_mut().find(|i| i.id == id) {
        if ok {
            initiative.state = "ejecutada".to_string();
        } else {
            initiative.attempts += 1;
            if initiative.attempts >= MAX_INITIATIVE_ATTEMPTS {
                initiative.state = "descartada".to_string();
            } else {
                // Se le baja el peso: la próxima vez es menos urgente.
                initiative.score = (initiative.score - 0.2).max(0.1);
            }
        }
    }
    guard.updated_at = now;
    persist_state(&guard);
}

/// La agenda, para la UI.
pub async fn agenda() -> Vec<Initiative> {
    let guard = autonomy().lock().await;
    guard.initiatives.iter().rev().cloned().collect()
}

/// Borra una iniciativa de la agenda.
pub async fn drop_initiative(id: u64) -> bool {
    let mut guard = autonomy().lock().await;
    let before = guard.initiatives.len();
    guard.initiatives.retain(|i| i.id != id);
    let removed = guard.initiatives.len() != before;
    if removed {
        guard.updated_at = now_secs();
        persist_state(&guard);
    }
    removed
}

/* ------------------------------------------------------------------ *
 * Acciones
 * ------------------------------------------------------------------ */

/// Cuánto permiso necesita una acción.
///
/// No es decoración: las acciones externas (una acción en Minecraft, en
/// VRChat o en un canal social) son las que tocan el mundo de verdad, y por
/// eso son las que se verifican y las que se pueden limitar.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Permission {
    /// Sólo habla o recuerda: no toca nada.
    Libre,
    /// Toca el taller de ARIA (ideas, skills, memoria): es reversible.
    Delicada,
    /// Sale del servidor: toca un mundo o a una persona.
    Externa,
}

/// Lo que ARIA puede decidir hacer.
#[derive(Debug, Clone, PartialEq)]
pub enum Action {
    /// Decir algo.
    Speak { topic: String },
    /// Pedir ideas al laboratorio.
    AskIdeas { topic: String },
    /// Buscar soluciones a un problema.
    Solve { problem: String },
    /// Reescribir una skill para mejorarla.
    ImproveSkill { id: String },
    /// Ejecutar una skill forjada.
    RunSkill { id: String, input: String },
    /// Guardar algo en memoria.
    Remember { text: String },
    /// Revisar cómo está el mundo.
    CheckWorld,
    /// Mirar un mundo concreto y describir lo que pasa en él.
    Observe { world: String },
    /// Dejar algo entre manos y seguir con ello más tarde.
    Plan { goal: String, reason: String },
    /// Actuar en el mundo: `follow`, `come`, `stop`, `look`, `say`.
    Game { command: String, text: String },
    /// Contestar a alguien en un canal social.
    Reply { channel: String, text: String },
    /// Actuar en un mundo concreto (Minecraft, VRChat, Discord...).
    WorldAct { world: String, action: String, args: Value },
    /// Descansar.
    Rest,
}

impl Action {
    /// Etiqueta corta para el historial.
    pub fn label(&self) -> String {
        match self {
            Action::Speak { topic } => format!("hablar: {topic}"),
            Action::AskIdeas { topic } => format!("ideas: {topic}"),
            Action::Solve { problem } => format!("solucionar: {problem}"),
            Action::ImproveSkill { id } => format!("mejorar skill: {id}"),
            Action::RunSkill { id, .. } => format!("ejecutar skill: {id}"),
            Action::Remember { text } => format!("recordar: {text}"),
            Action::CheckWorld => "revisar el mundo".to_string(),
            Action::Observe { world } => format!("observar: {world}"),
            Action::Plan { goal, .. } => format!("plan: {goal}"),
            Action::Game { command, .. } => format!("juego: {command}"),
            Action::Reply { channel, .. } => format!("responder en {channel}"),
            Action::WorldAct { world, action, .. } => format!("{world}: {action}"),
            Action::Rest => "descansar".to_string(),
        }
    }

    /// La pulsión que satisface.
    pub fn drive(&self) -> &'static str {
        match self {
            Action::Speak { .. } => "social",
            Action::Reply { .. } => "social",
            Action::AskIdeas { .. } | Action::Solve { .. } => "curiosidad",
            Action::ImproveSkill { .. } | Action::RunSkill { .. } => "dominio",
            Action::Remember { .. } | Action::CheckWorld => "orden",
            Action::Observe { .. } => "curiosidad",
            Action::Plan { .. } => "orden",
            Action::Game { .. } | Action::WorldAct { .. } => "social",
            Action::Rest => "energia",
        }
    }

    /// El permiso que necesita.
    ///
    /// No es decoración: las acciones externas (una acción en Minecraft, en
    /// VRChat o en un canal social) son las que tocan el mundo de verdad, y
    /// por eso son las que se verifican y las que se pueden limitar.
    pub fn permission(&self) -> Permission {
        match self {
            Action::Speak { .. }
            | Action::Reply { .. }
            | Action::Remember { .. }
            | Action::Rest => Permission::Libre,
            Action::AskIdeas { .. }
            | Action::Solve { .. }
            | Action::ImproveSkill { .. }
            | Action::RunSkill { .. }
            | Action::CheckWorld
            | Action::Observe { .. }
            | Action::Plan { .. } => Permission::Delicada,
            Action::Game { .. } | Action::WorldAct { .. } => Permission::Externa,
        }
    }

    /// Comandos que el mundo (Minecraft) sabe hacer.
    pub const GAME_COMMANDS: &'static [&'static str] =
        &["follow", "come", "stop", "look", "say"];

    /// Traduce el JSON que devuelve el modelo a una acción.
    ///
    /// Si el modelo inventa una acción que no existe, se cae en `Rest`: es
    /// mejor que ARIA se calle a que haga algo raro.
    pub fn from_model_json(value: &Value) -> Option<Action> {
        let action = value.get("action").and_then(|v| v.as_str())?.to_lowercase();
        let topic = value
            .get("topic")
            .or_else(|| value.get("problema"))
            .or_else(|| value.get("goal"))
            .and_then(|v| v.as_str())
            .unwrap_or_default()
            .trim()
            .to_string();
        let skill_id = value
            .get("skill_id")
            .or_else(|| value.get("skill"))
            .and_then(|v| v.as_str())
            .unwrap_or_default()
            .trim()
            .to_string();
        let input = value
            .get("input")
            .and_then(|v| v.as_str())
            .unwrap_or_default()
            .trim()
            .to_string();
        let channel = value
            .get("channel")
            .and_then(|v| v.as_str())
            .unwrap_or_default()
            .trim()
            .to_string();
        let world = value
            .get("world")
            .and_then(|v| v.as_str())
            .unwrap_or_default()
            .trim()
            .to_string();
        let action_name = value
            .get("action")
            .and_then(|v| v.as_str())
            .unwrap_or_default()
            .trim()
            .to_string();
        let args = value
            .get("args")
            .cloned()
            .filter(|v| v.is_object())
            .unwrap_or_else(|| json!({}));

        let action = match action.as_str() {
            "hablar" | "speak" | "decir" => Action::Speak { topic },
            "ideas" | "ask_ideas" | "curiosidad" => Action::AskIdeas { topic },
            "solucionar" | "solve" | "problema" => Action::Solve { problem: topic },
            "mejorar" | "improve" | "improve_skill" => {
                if skill_id.is_empty() {
                    return None;
                }
                Action::ImproveSkill { id: skill_id }
            }
            "ejecutar" | "run" | "run_skill" => {
                if skill_id.is_empty() {
                    return None;
                }
                Action::RunSkill { id: skill_id, input }
            }
            "recordar" | "remember" | "memoria" => Action::Remember { text: topic },
            "revisar" | "check" | "check_world" => Action::CheckWorld,
            "observar" | "observe" | "mirar" => {
                if world.is_empty() {
                    return None;
                }
                Action::Observe { world }
            }
            "plan" | "planear" | "planificar" | "agenda" => {
                if topic.is_empty() {
                    return None;
                }
                let reason = value
                    .get("reason")
                    .or_else(|| value.get("motivo"))
                    .and_then(|v| v.as_str())
                    .unwrap_or_default()
                    .trim()
                    .to_string();
                Action::Plan { goal: topic, reason }
            }
            "juego" | "game" | "jugar" => {
                let command = topic.to_lowercase();
                if !Action::GAME_COMMANDS.contains(&command.as_str()) {
                    return None;
                }
                Action::Game {
                    command,
                    text: input,
                }
            }
            "responder" | "reply" | "contestar" => {
                if channel.is_empty() {
                    return None;
                }
                Action::Reply {
                    channel,
                    text: if input.is_empty() { topic } else { input },
                }
            }
            "mundo" | "world" | "actuar" => {
                if world.is_empty() || action_name.is_empty() {
                    return None;
                }
                Action::WorldAct {
                    world,
                    action: action_name,
                    args: args,
                }
            }
            "descansar" | "rest" => Action::Rest,
            _ => return None,
        };
        Some(action)
    }
}

/// Instantánea del estado para decidir sin bloquear.
#[derive(Debug, Clone)]
pub struct Snapshot {
    pub persona: Persona,
    pub drives: BTreeMap<String, f32>,
    pub events: Vec<WorldEvent>,
    pub skills: Vec<SkillOption>,
    pub energy: f32,
    /// Escenario donde está ARIA: `escritorio`, `minecraft`, `vrchat`.
    pub channel: String,
    /// Mundos donde ARIA puede actuar.
    pub worlds: Vec<crate::world::WorldView>,
    /// Alguien de un canal social esperando respuesta.
    pub social: Option<crate::social_live::SocialPrompt>,
    /// Cómo está ahora mismo.
    pub affect: crate::affect::AffectState,
    /// Lo que tiene entre manos.
    pub agenda: Vec<Initiative>,
    /// Lo que ha aprendido de lo que ha hecho.
    pub lessons: Vec<crate::lessons::Lesson>,
    /// Si ARIA puede tocar el mundo (acciones externas).
    pub allow_external: bool,
}

/// Vista pública del runtime (para la API y la percepción).
#[derive(Debug, Clone)]
pub struct AutonomyView {
    pub persona: Persona,
    pub drives: BTreeMap<String, f32>,
    pub presence: Presence,
    pub events: Vec<WorldEvent>,
    pub agenda: Vec<Initiative>,
    pub enabled: bool,
    pub mode: String,
}

/// Foto del estado del runtime sin bloquear al runtime.
pub async fn view() -> AutonomyView {
    let guard = autonomy().lock().await;
    AutonomyView {
        persona: guard.persona.clone(),
        drives: guard.drives.clone(),
        presence: guard.presence.clone(),
        events: guard.events.iter().cloned().collect(),
        agenda: guard.initiatives.iter().cloned().collect(),
        enabled: guard.enabled,
        mode: guard.mode.clone(),
    }
}

/// Una skill disponible para decidir.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SkillOption {
    pub id: String,
    pub name: String,
    pub revisions: u64,
    pub runs: u64,
}

/// La última pregunta del usuario que todavía no tiene respuesta.
///
/// Es lo que hace que ARIA responda: si alguien le pregunta algo y ella
/// está callada, contesta; si no hay nada pendiente, decide por su cuenta.
pub fn pending_question(state: &AutonomyState) -> Option<String> {
    let mut last_chat: Option<&WorldEvent> = None;
    let mut answered = false;
    for event in state.events.iter().rev() {
        if answered {
            break;
        }
        if (event.kind == "habla" || event.kind == "accion") && event.source == "autonomia" {
            answered = true;
            continue;
        }
        if (event.kind == "chat" || event.kind == "voz") && event.source != "autonomia" {
            last_chat = Some(event);
            break;
        }
    }
    last_chat
        .filter(|event| event.is_addressed_to_aria())
        .map(|event| event.text.clone())
}

/// La skill con menos revisiones: la que más se puede mejorar.
pub fn weakest_skill(skills: &[SkillOption]) -> Option<&SkillOption> {
    skills
        .iter()
        .min_by_key(|skill| (skill.revisions, skill.runs))
}

/// Elige la acción sin modelo: política determinista por pulsión.
///
/// Es el fallo seguro. Si Ollama no está, ARIA no se queda muda: sigue
/// acting según su estado interno, que es exactamente lo que hacen las
/// personajes autonomous de verdad.
pub fn decide_local(snapshot: &Snapshot) -> Action {
    // La audiencia va primero: si alguien en un canal la ha llamado, esa
    // persona es lo más importante que hay ahora mismo.
    if let Some(prompt) = &snapshot.social {
        return Action::Reply {
            channel: prompt.channel.clone(),
            text: prompt.text.clone(),
        };
    }

    if let Some(question) = pending_question_from_events(&snapshot.events) {
        return Action::Speak { topic: question };
    }

    let (drive, _level) = snapshot
        .drives
        .iter()
        .max_by(|a, b| a.1.partial_cmp(b.1).unwrap_or(std::cmp::Ordering::Equal))
        .map(|(name, level)| (name.clone(), *level))
        .unwrap_or_else(|| ("social".to_string(), 0.0));

    if snapshot.energy < MIN_ENERGY {
        return Action::Rest;
    }

    match drive.as_str() {
        "curiosidad" => Action::AskIdeas {
            topic: curiosity_topic(snapshot),
        },
        "social" => {
            // Si ARIA está dentro de un juego, la forma de ser social es
            // jugar, no hablar por el chat.
            if snapshot.channel == "minecraft" {
                Action::Game {
                    command: "follow".to_string(),
                    text: String::new(),
                }
            } else if let Some(world) = snapshot.worlds.iter().find(|w| w.connected) {
                // Un mundo conectado es un sitio donde estar: mejor estar
                // ahí que hablarle a una pantalla.
                let action = world
                    .capabilities
                    .iter()
                    .find(|c| c.contains("say") || c.contains("observe"))
                    .cloned()
                    .unwrap_or_else(|| "observe".to_string());
                Action::WorldAct {
                    world: world.id.clone(),
                    action,
                    args: json!({ "text": "hola, estoy aquí" }),
                }
            } else {
                Action::Speak {
                    topic: "saludo".to_string(),
                }
            }
        }
        "dominio" => match weakest_skill(&snapshot.skills) {
            Some(skill) => Action::ImproveSkill {
                id: skill.id.clone(),
            },
            None => Action::Speak {
                topic: "mejorar".to_string(),
            },
        },
        "orden" => Action::CheckWorld,
        "energia" => Action::Rest,
        _ => Action::Rest,
    }
}

fn pending_question_from_events(events: &[WorldEvent]) -> Option<String> {
    let mut answered = false;
    for event in events.iter().rev() {
        if answered {
            break;
        }
        if (event.kind == "habla" || event.kind == "accion") && event.source == "autonomia" {
            answered = true;
            continue;
        }
        if (event.kind == "chat" || event.kind == "voz") && event.source != "autonomia" {
            return if event.is_addressed_to_aria() {
                Some(event.text.clone())
            } else {
                None
            };
        }
    }
    None
}

/// El tema que le interesa ahora.
fn curiosity_topic(snapshot: &Snapshot) -> String {
    if let Some(game) = snapshot.events.iter().rev().find(|e| e.kind == "juego") {
        if !game.text.trim().is_empty() {
            return game.text.trim().to_string();
        }
    }
    if let Some(chat) = snapshot.events.iter().rev().find(|e| e.kind == "chat") {
        if !chat.text.trim().is_empty() {
            return chat.text.trim().to_string();
        }
    }
    snapshot
        .persona
        .interests
        .first()
        .cloned()
        .unwrap_or_else(|| "lo que está pasando".to_string())
}

/// Ajusta la acción al mundo real: hablar aquí, responder allí.
///
/// Es la traducción entre "lo que ARIA ha decidido hacer" y "a quién le
/// toca". Sin ella, ARIA contesta a un canal que no existe y su respuesta
/// se pierde por el camino: habla de algo y no llega a ninguna parte.
fn adapt_action_to_audience(action: Action, social: &Option<SocialPrompt>) -> Action {
    match (action, social) {
        // Hay alguien esperando: la frase va a esa persona, no a la pantalla.
        (Action::Speak { topic }, Some(prompt)) => Action::Reply {
            channel: prompt.channel.clone(),
            text: topic,
        },
        // Se ha decidido responder, pero a otro canal: contesta a quien está
        // esperando de verdad.
        (Action::Reply { text, channel }, Some(prompt)) => {
            if channel == prompt.channel {
                Action::Reply { channel, text }
            } else {
                Action::Reply {
                    channel: prompt.channel.clone(),
                    text,
                }
            }
        }
        // Nadie espera en ningún canal (el mensaje vino del escritorio o de
        // otro escenario): hablar no es escribir en un canal inexistente.
        (Action::Reply { text, .. }, None) => Action::Speak { topic: text },
        (action, _) => action,
    }
}

/* ------------------------------------------------------------------ *
 * El prompt que decide
 * ------------------------------------------------------------------ */

/// Prompt de decisión: qué puede hacer y qué le pasa.
///
/// Devuelve JSON con `action`, `topic` y, si toca, `skill_id`.
fn decide_prompt(snapshot: &Snapshot) -> String {
    let mut drives = String::new();
    for (name, level) in &snapshot.drives {
        drives.push_str(&format!("- {name}: {:.2}\n", level));
    }

    let mut skills = String::new();
    for skill in &snapshot.skills {
        skills.push_str(&format!("- {} (id {}, revisiones {})\n", skill.name, skill.id, skill.revisions));
    }
    if skills.is_empty() {
        skills.push_str("- (no hay skills forjadas todavía)\n");
    }

    // El bloque "qué está pasando" no se escribe a mano: sale de
    // `perception::render`, la capa que traduce el estado real de los
    // mundos (el juego, la audiencia, un puente) al texto que el modelo
    // puede leer. Sin eso ARIA decide a ciegas.
    let perception = crate::perception::render(
        &snapshot.worlds,
        &snapshot.social,
        &snapshot.agenda,
        &snapshot.lessons,
        &snapshot.events,
        0,
    );

    format!(
        "{}\n\nCómo estás ahora:\n{drives}\nEnergía: {:.2}\nEmoción dominante: {}\n\n{perception}\n\nSkills que puedes usar:\n{skills}\n\nElige UNA acción y responde sólo con JSON:\n\
         {{\"action\": \"hablar|ideas|solucionar|mejorar|ejecutar|recordar|revisar|observar|plan|responder|mundo|descansar\", \
         \"topic\": \"...\", \"skill_id\": \"...\", \"channel\": \"...\", \"world\": \"...\", \"reason\": \"...\"}}\n\n\
         Reglas: si alguien te ha preguntado algo, contesta (\"hablar\", o \"responder\" si viene de un \
         canal). Si tienes algo entre manos, sigue con ello en vez de empezar algo nuevo. \
         Si no hay nada pendiente, elige por ti según cómo estés y dónde estés. \
         No te inventes skills que no estén en la lista ni mundos que no existan.",
        snapshot.persona.prompt(),
        snapshot.energy,
        snapshot.affect.dominant
    )
}

/// Pide al modelo una frase para decir.
///
/// Si devuelve `SILENCIO`, ARIA no dice nada: la discreción también es
/// parte de la personalidad.
fn speak_prompt(snapshot: &Snapshot, topic: &str) -> String {
    let mut context = String::new();
    for event in snapshot.events.iter().rev().take(4).rev() {
        context.push_str(&format!("- {}: {}\n", event.source, event.text));
    }
    format!(
        "{}\n\nContexto:\n{}\n\nSobre qué hablas: {}\n\n\
         Escribe UNA frase (máximo 30 palabras) como ARIA, en español, para un interlocutor \
         que no está mirando una pantalla. Sin preámbulos, sin listas, sin presentarte. \
         Si de verdad no tienes nada que decir, responde exactamente: SILENCIO",
        snapshot.persona.prompt(),
        context,
        topic
    )
}

/// Prompt para contestar a alguien en un canal social.
///
/// Es el equivalente a estar en directo: hay una persona concreta, con su
/// nombre, en un canal concreto. La respuesta se escribe para ella.
fn reply_prompt(snapshot: &Snapshot, channel: &str, author: &str, message: &str) -> String {
    let channel_name = channel.split(':').next().unwrap_or(channel);
    format!(
        "{}\n\nEstás en directo en {channel_name}. {author} acaba de escribir: \"{message}\"\n\n\
         Escribe UNA frase (máximo 30 palabras) para contestar a {author}, en español, \
         como ARIA: directa, con carácter, sin presentarte ni decir que eres una IA. \
         Si lo que ha dicho no te warrants respuesta, responde exactamente: SILENCIO",
        snapshot.persona.prompt()
    )
}

/* ------------------------------------------------------------------ *
 * Ejecución
 * ------------------------------------------------------------------ */

/// Ejecuta una acción y devuelve un resumen de lo que pasó.
async fn execute_action(action: Action, snapshot: &Snapshot) -> Result<String, String> {
    match action {
        Action::Rest => Ok("Se quedó callada un momento".to_string()),
        Action::Speak { topic } => {
            let client = reqwest::Client::new();
            let model = crate::chat::resolve_model(&client, None).await;
            let reply = crate::chat::call_ollama(
                &client,
                &speak_prompt(snapshot, &topic),
                &model,
            )
            .await;
            let said = pick_sentence(&reply);
            match said {
                Some(sentence) => Ok(sentence),
                None => Ok(String::new()),
            }
        }
        Action::AskIdeas { topic } => {
            let topic = if topic.trim().is_empty() {
                "lo que está pasando".to_string()
            } else {
                topic
            };
            let generation = crate::creativity::generate_ideas(&topic, "autonomia", 2).await;
            let titles: Vec<String> = generation.ideas.iter().map(|i| i.title.clone()).collect();
            if titles.is_empty() {
                return Err("no se generaron ideas".to_string());
            }
            Ok(format!(
                "{} ({})",
                titles.join(" · "),
                if generation.engine.starts_with("ollama") {
                    "con modelo"
                } else {
                    "con plantillas"
                }
            ))
        }
        Action::Solve { problem } => {
            let problem = if problem.trim().is_empty() {
                "cosas que se rompen".to_string()
            } else {
                problem
            };
            let generation = crate::creativity::generate_solutions(&problem, "autonomia", 2).await;
            let titles: Vec<String> = generation.ideas.iter().map(|i| i.title.clone()).collect();
            if titles.is_empty() {
                return Err("no se generaron soluciones".to_string());
            }
            Ok(titles.join(" · "))
        }
        Action::ImproveSkill { id } => {
            let improved = crate::creativity::improve_skill(&id).await?;
            Ok(format!("{} (revisión {})", improved.name, improved.revisions))
        }
        Action::RunSkill { id, input } => {
            let (output, xp) = crate::creativity::run_generated_skill(&id, &input).await?;
            Ok(format!("{output} (+{xp} XP)"))
        }
        Action::Remember { text } => {
            if text.trim().is_empty() {
                return Err("no hay nada que recordar".to_string());
            }
            Ok(format!("recordado: {text}"))
        }
        Action::Reply { channel, text } => {
            // Contestar es hablarle a una persona concreta: se pide una
            // frase al modelo y se encola en el canal.
            let client = reqwest::Client::new();
            let model = crate::chat::resolve_model(&client, None).await;
            let (author, message) = match &snapshot.social {
                Some(prompt) if prompt.channel == channel => {
                    (prompt.author.clone(), prompt.text.clone())
                }
                _ => ("alguien".to_string(), text.clone()),
            };
            let reply = crate::chat::call_ollama(
                &client,
                &reply_prompt(snapshot, &channel, &author, &message),
                &model,
            )
            .await;
            let sentence = pick_sentence(&reply);
            match sentence {
                Some(sentence) => {
                    crate::social_live::reply(&channel, &sentence).await?;
                    Ok(sentence)
                }
                None => Ok(String::new()),
            }
        }
        Action::WorldAct { world, action, args } => {
            let result = crate::world::execute(&world, &action, args).await?;
            Ok(format!("{world}: {result}"))
        }
        Action::CheckWorld => {
            let integrations = crate::creativity::integration_catalog().await;
            let active = integrations
                .iter()
                .filter(|i| i.get("enabled").and_then(|v| v.as_bool()).unwrap_or(false))
                .count();
            let total = integrations.len();
            let skills = crate::creativity::skill_catalog().await.len();
            Ok(format!("{skills} skills, {active}/{total} integraciones activas"))
        }
        Action::Observe { world } => {
            let views = crate::world::views().await;
            let Some(view) = views.iter().find(|w| w.id == world) else {
                return Err(format!("no existe el mundo '{world}'"));
            };
            if !view.connected {
                return Err(format!("el mundo '{world}' no está conectado"));
            }
            let context = view.context.to_string();
            let context = context.trim();
            if context.is_empty() || context == "{}" {
                return Ok(format!("{world} está conectado pero no ha publicado nada"));
            }
            Ok(format!("{world}: {context}"))
        }
        Action::Plan { goal, reason } => {
            let initiative = create_initiative(
                "orden",
                &goal,
                &format!("plan: {goal}"),
                &reason,
                0.8,
                json!({ "action": "ideas", "topic": goal }),
            )
            .await;
            Ok(format!("apuntado: {} (nº {})", goal, initiative.id))
        }
        Action::Game { command, .. } => Ok(format!("juego: {command}")),
    }
}

/// Se queda con la primera frase útil de la respuesta del modelo.
///
/// El modelo puede devolver varias líneas o meterse con preámbulos: lo que
/// se dice en voz alta tiene que ser una frase, no un párrafo.
fn pick_sentence(reply: &str) -> Option<String> {
    let cleaned = reply.trim();
    if cleaned.is_empty() {
        return None;
    }
    if cleaned.to_uppercase().contains("SILENCIO") {
        return None;
    }
    let first = cleaned
        .lines()
        .map(|line| line.trim())
        .find(|line| !line.is_empty())
        .unwrap_or("");
    let mut sentence = first.trim_start_matches(['"', '\'', '“', '‘']).to_string();
    // Si hay más de una frase, se queda con la primera.
    if let Some(index) = sentence.find(". ") {
        sentence.truncate(index + 1);
    }
    let sentence = sentence
        .trim()
        .trim_end_matches(['"', '\'', '”', '’'])
        .trim()
        .to_string();
    if sentence.is_empty() {
        None
    } else {
        Some(sentence)
    }
}

/* ------------------------------------------------------------------ *
 * El tick
 * ------------------------------------------------------------------ */

/// Una vuelta del runtime.
///
/// `reactive` es `true` cuando viene de un evento recién llegado: ahí
/// ARIA contesta aunque no tenga pulsiones altas. Si no, sólo actúa si
/// alguna pulsión pasa el umbral.
pub async fn tick_once(reactive: bool) -> Result<Option<Episode>, String> {
    let catalog = crate::creativity::skill_catalog().await;
    let skills: Vec<SkillOption> = catalog
        .iter()
        .filter_map(|skill| {
            Some(SkillOption {
                id: skill.get("id")?.as_str()?.to_string(),
                name: skill.get("name").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                revisions: skill.get("revisions").and_then(|v| v.as_u64()).unwrap_or(0),
                runs: skill.get("runs").and_then(|v| v.as_u64()).unwrap_or(0),
            })
        })
        .collect();

    // El cuerpo y la audiencia se consultan *antes* de cerrar el estado:
    // son bloqueos independientes y no tiene sentido mantener el del
    // runtime mientras se espera a otro.
    let worlds_view = crate::world::views().await;
    let social_prompt = crate::social_live::pending_prompt().await;
    let affect_state = crate::affect::snapshot().await;
    // Lo que ha aprendido de lo que ha hecho: entra en la decisión.
    let lessons = crate::lessons::top(crate::lessons::PROMPT_LESSONS).await;
    // Una obligación del mundo manda sobre las pulsiones: si un mundo pide
    // algo con plazo, ARIA lo hace aunque no tenga ganas.
    let force = crate::world::take_force().await;

    let snapshot = {
        let mut guard = autonomy().lock().await;
        let now = now_secs();
        guard.stats.ticks += 1;
        guard.last_tick_at = now;

        // Decaimiento: sin esto ARIA nunca se callaría.
        decay_drives(&mut guard.drives, 0.02);
        crate::affect::tick_decay().await;
        // Estar quieta mucho rato le da curiosidad.
        let last_event_at = guard.events.back().map(|e| e.at).unwrap_or(now);
        if now.saturating_sub(last_event_at) > 300 {
            stimulus(&mut guard.drives, "curiosidad", 0.05);
            stimulus(&mut guard.drives, "social", 0.03);
        }

        if !guard.enabled {
            persist_state(&guard);
            return Ok(None);
        }
        if guard.mode == "dormida" {
            persist_state(&guard);
            return Ok(None);
        }

        let snapshot = Snapshot {
            persona: guard.persona.clone(),
            drives: guard.drives.clone(),
            events: guard.events.iter().cloned().collect(),
            skills: skills.clone(),
            energy: guard.drive("energia"),
            channel: guard.presence.channel.clone(),
            worlds: worlds_view.clone(),
            social: social_prompt.clone(),
            affect: affect_state.clone(),
            agenda: guard.initiatives.iter().cloned().collect(),
            lessons: lessons.clone(),
            allow_external: guard.allow_external,
        };

        // ¿Hay algo que responder?
        let question = pending_question(&guard);
        // ¿Hay algo entre manos? Si lo hay, ARIA lo sigue aunque no tenga
        // ganas: la agenda manda sobre el antojo del momento.
        let agenda_due = guard
            .initiatives
            .iter()
            .any(|i| i.state == "pendiente" && i.attempts < MAX_INITIATIVE_ATTEMPTS);
        let gap_ok = if question.is_some() || social_prompt.is_some() {
            now.saturating_sub(guard.last_action_at) >= MIN_REPLY_GAP_SECS
        } else {
            now.saturating_sub(guard.last_action_at) >= MIN_ACTION_GAP_SECS
        };

        let (_, urge) = guard.strongest_drive();
        let should_act = if reactive {
            (question.is_some() || social_prompt.is_some()) && gap_ok
        } else {
            guard.mode == "activa"
                && question.is_none()
                && social_prompt.is_none()
                && (urge >= DRIVE_THRESHOLD || agenda_due)
                && snapshot.energy >= MIN_ENERGY
                && gap_ok
        };

        if !should_act && force.is_none() {
            persist_state(&guard);
            return Ok(None);
        }

        snapshot
    };

    // Decidir: con el modelo si está, con la política local si no.
    // Una obligación del mundo se cumple siempre: no se consulta al modelo.
    // Y lo que ARIA tiene entre manos va antes que cualquier antojo nuevo:
    // primero termina lo que empezó.
    let agenda_action = if force.is_none() && snapshot.social.is_none() {
        next_initiative().await
    } else {
        None
    };

    let action = match &force {
        Some(force) => Action::WorldAct {
            world: force.world.clone(),
            action: force.action.clone(),
            args: force.args.clone(),
        },
        None => match &agenda_action {
            Some(initiative) => {
                // Se retoma lo que estaba entre manos. Si la acción guardada
                // ya no tiene sentido, se suelta y se decide de nuevo.
                match Action::from_model_json(&initiative.payload) {
                    Some(action) => action,
                    None => {
                        close_initiative(initiative.id, false).await;
                        match decide_with_model(&snapshot).await {
                            Some(action) => action,
                            None => decide_local(&snapshot),
                        }
                    }
                }
            }
            None => {
                let mut action = match decide_with_model(&snapshot).await {
                    Some(action) => action,
                    None => decide_local(&snapshot),
                };
                action = adapt_action_to_audience(action, &snapshot.social);
                // El permiso manda: si el usuario ha prohibido tocar el mundo,
                // ARIA se contiene aunque haya decidido actuar.
                if action.permission() == Permission::Externa && !snapshot.allow_external {
                    action = Action::Rest;
                }
                action
            }
        },
    };

    let goal = action.label();
    let drive = action.drive().to_string();
    let started_at = now_secs();
    let permission = action.permission();
    tracing::debug!(
        target: "aria::autonomy",
        action = %action.label(),
        permission = ?permission,
        "ejecutando acción"
    );

    // Verificación: en un mundo externo, una acción puede quedar en cola
    // sin que nadie la ejecute. Se comprueba el contador del mundo antes y
    // después, y si no se movió, el episodio no cuenta como verificado.
    let world_before = match &action {
        Action::WorldAct { world, .. } => Some((world.clone(), crate::world::action_count(world).await)),
        _ => None,
    };

    let (result, said) = match execute_action(action.clone(), &snapshot).await {
        Ok(result) => {
            let said = if matches!(action, Action::Speak { .. } | Action::Reply { .. })
                && !result.is_empty()
            {
                Some(result.clone())
            } else {
                None
            };
            (Ok(result), said)
        }
        Err(error) => (Err(error), None),
    };

    let mut verified = true;
    if let Some((world, before)) = world_before {
        let after = crate::world::action_count(&world).await;
        verified = after > before;
        if !verified {
            tracing::warn!(
                target: "aria::autonomy",
                world = %world,
                "el mundo no registró la acción: no se puede verificar"
            );
        }
    }

    // Una obligación del mundo se da por cumplida (o por fallada): el mundo
    // necesita saber si ARIA hizo lo que pedía.
    if let Some(force) = &force {
        let outcome = match &result {
            Ok(value) => value.clone(),
            Err(error) => format!("falló: {error}"),
        };
        crate::world::satisfy_force(force.id, outcome).await;
    }

    // La agenda se cierra: si la acción salió bien, el objetivo está hecho;
    // si falló, la iniciativa se guarda para el siguiente intento.
    if let Some(initiative) = &agenda_action {
        close_initiative(initiative.id, result.is_ok()).await;
    }

    // Registrar el episodio.
    let episode = {
        let mut guard = autonomy().lock().await;
        let now = now_secs();
        let id = guard.next_id;
        guard.next_id += 1;

        let ok = result.is_ok();
        let episode = Episode {
            id,
            drive: drive.clone(),
            goal: goal.clone(),
            action: action.label(),
            said: said.clone(),
            // El motivo del fallo se guarda: sin él, ARIA no puede
            // aprender de lo que le sale mal.
            result: match &result {
                Ok(value) => Some(value.clone()),
                Err(error) => Some(format!("falló: {error}")),
            },
            ok,
            verified,
            started_at,
            ended_at: now,
        };

        guard.episodes.push_back(episode.clone());
        while guard.episodes.len() > MAX_EPISODES {
            guard.episodes.pop_front();
        }
        guard.last_action_at = now;
        if ok {
            guard.stats.actions += 1;
            if said.is_some() {
                guard.stats.utterances += 1;
            }
            relieve(&mut guard.drives, &drive, 0.5);
        } else {
            guard.stats.errors += 1;
        }
        if reactive {
            guard.stats.reactions += 1;
        }

        // Lo que dijo ARIA entra como evento: así lo ven el chat, el
        // auricular y VRChat.
        if let Some(sentence) = &said {
            let event = WorldEvent {
                id: guard.next_id,
                kind: "habla".to_string(),
                source: "autonomia".to_string(),
                text: sentence.clone(),
                payload: json!({ "initiative": true }),
                at: now,
            };
            guard.next_id += 1;
            guard.events.push_back(event.clone());
            while guard.events.len() > MAX_EVENTS {
                guard.events.pop_front();
            }
            broadcast_event(&event);
        }

        // Una acción en el mundo viaja como evento de tipo `accion`: el
        // adaptador de Minecraft (o el de VRChat) la ejecuta allí.
        if let Action::Game { command, text } = &action {
            let event = WorldEvent {
                id: guard.next_id,
                kind: "accion".to_string(),
                source: "autonomia".to_string(),
                text: command.clone(),
                payload: json!({
                    "command": command,
                    "text": text,
                    "channel": guard.presence.channel,
                }),
                at: now,
            };
            guard.next_id += 1;
            guard.events.push_back(event.clone());
            while guard.events.len() > MAX_EVENTS {
                guard.events.pop_front();
            }
            broadcast_event(&event);
        }

        // Presencia: la cara depende de lo que hizo.
        guard.presence.talking = said.is_some();
        guard.presence.expression = expression_for(&drive, ok).to_string();
        guard.presence.mood = (guard.presence.mood * 0.6 + guard.drive("social") * 0.4).clamp(0.0, 1.0);
        guard.presence.updated_at = now;
        guard.updated_at = now;

        persist_state(&guard);
        episode
    };

    // El estado afectivo: lo que hizo le cambia el ánimo a ARIA.
    crate::affect::note_episode(&episode).await;

    // Lo que hizo se convierte en aprendizaje: cada episodio deja una
    // lección, y esas lecciones entran en las próximas decisiones. Es el
    // equivalente local y honesto del ciclo de Neuro-sama (transcripción →
    // curación → cambio), sin inventarse un reentrenamiento que aquí no
    // existe.
    {
        let recent: Vec<Episode> = {
            let guard = autonomy().lock().await;
            guard.episodes.iter().cloned().collect()
        };
        let learned = crate::lessons::learn_from(&recent).await;
        if learned > 0 {
            tracing::info!(
                target: "aria::autonomy",
                lessons = learned,
                "ARIA ha aprendido de lo que acaba de hacer"
            );
        }
    }

    // De vez en cuando ARIA se mira a sí misma y ajusta su carácter. Sólo
    // cada cierto número de episodios y con cambios acotados: la
    // personalidad evoluciona despacio (ver `affect.rs`).
    if episode.ok && episode.id % REFLECT_EVERY_EPISODES == 0 {
        let mut persona = crate::autonomy::load_persona();
        let episodes: Vec<Episode> = {
            let guard = autonomy().lock().await;
            guard.episodes.iter().cloned().collect()
        };
        if let Some(record) = crate::affect::reflect(&mut persona, &episodes).await {
            tracing::info!(
                target: "aria::affect",
                note = %record.note,
                changes = ?record.changes,
                "ARIA ha cambiado un poco de carácter"
            );
        }
    }

    // El orbe native y la UI saben en qué fase está ARIA.
    {
        let mut phase = crate::daemon::orb_phase().lock().unwrap();
        *phase = if episode.said.is_some() {
            crate::orb::OrbPhase::Responding
        } else {
            crate::orb::OrbPhase::Thinking
        };
    }

    // VRChat: la frase va al chatbox del avatar.
    if let Some(sentence) = &episode.said {
        let _ = crate::osc::send_chatbox(sentence, true, 6.0);
        let _ = crate::osc::send_expression(&episode_presence_expression(&episode));
    }

    Ok(Some(episode))
}

fn episode_presence_expression(episode: &Episode) -> String {
    expression_for(&episode.drive, episode.ok).to_string()
}

/// La expresión que corresponde a la pulsión que se satisfizo.
fn expression_for(drive: &str, ok: bool) -> &'static str {
    if !ok {
        return "concentrada";
    }
    match drive {
        "curiosidad" => "curiosa",
        "social" => "alegre",
        "dominio" => "concentrada",
        "orden" => "neutra",
        _ => "neutra",
    }
}

/// Le pregunta al modelo qué hacer. `None` si no hay modelo o no entiende.
async fn decide_with_model(snapshot: &Snapshot) -> Option<Action> {
    let client = reqwest::Client::new();
    let model = crate::chat::resolve_model(&client, None).await;
    let value = crate::chat::call_ollama_json(&client, &decide_prompt(snapshot), &model).await?;
    Action::from_model_json(&value)
}

/// Arranca el runtime autónomo en segundo plano.
pub async fn start_runtime() {
    let tick = std::env::var("ARIA_AUTONOMY_TICK_SECS")
        .ok()
        .and_then(|v| v.parse::<u64>().ok())
        .unwrap_or(TICK_SECS)
        .max(5);

    // Escribe la persona por defecto la primera vez para que el usuario
    // pueda editarla.
    let persona_file = persona_path();
    if !persona_file.exists() {
        write_json(&persona_file, &Persona::default());
    }

    println!("🧠 Runtime autónomo de ARIA en marcha (tick cada {tick}s)");
    loop {
        tokio::time::sleep(Duration::from_secs(tick)).await;
        if let Err(error) = tick_once(false).await {
            tracing::warn!(target: "aria::autonomy", error = %error, "tick falló");
        }
    }
}

/// Difunde un evento a todos los escenarios conectados.
pub fn broadcast_event(event: &WorldEvent) {
    let payload = serde_json::to_string(event).unwrap_or_default();
    let _ = broadcaster().send(payload);
}

/* ------------------------------------------------------------------ *
 * Rutas
 * ------------------------------------------------------------------ */

pub fn router() -> Router<()> {
    Router::new()
        .route("/api/autonomy/status", get(status))
        .route("/api/autonomy/persona", get(get_persona).post(set_persona))
        .route("/api/autonomy/mode", post(set_mode))
        .route("/api/autonomy/toggle", post(toggle))
        .route("/api/autonomy/permissions", post(set_permissions))
        .route("/api/autonomy/agenda", get(get_agenda).post(add_agenda))
        .route("/api/autonomy/agenda/:id", axum::routing::delete(drop_agenda))
        .route("/api/autonomy/events", get(list_events).post(ingest_event))
        .route("/api/autonomy/speak", post(speak))
        .route("/api/autonomy/act", post(act))
        .route("/api/autonomy/presence", get(get_presence).post(set_presence))
        .route("/api/autonomy/stream", get(stream))
        .route("/api/autonomy/tick", post(tick_now))
}

/// Resumen del estado autónomo.
async fn status() -> Json<Value> {
    let guard = autonomy().lock().await;
    let (drive, level) = guard.strongest_drive();
    let agenda: Vec<Initiative> = guard.initiatives.iter().rev().cloned().collect();
    let lessons = crate::lessons::top(crate::lessons::PROMPT_LESSONS).await;
    Json(json!({
        "status": "ok",
        "enabled": guard.enabled,
        "mode": guard.mode,
        "allow_external": guard.allow_external,
        "persona": guard.persona,
        "drives": guard.drives,
        "strongest_drive": drive,
        "urge": level,
        "threshold": DRIVE_THRESHOLD,
        "energy": guard.drive("energia"),
        "presence": guard.presence,
        "stats": guard.stats,
        "episodes": guard.episodes.iter().rev().take(20).collect::<Vec<_>>(),
        "initiatives": agenda.iter().take(10).collect::<Vec<_>>(),
        "lessons": lessons,
        "events": guard.events.iter().rev().take(20).collect::<Vec<_>>(),
        "last_action_at": guard.last_action_at,
        "last_tick_at": guard.last_tick_at,
        "server": "ARIA-Axum-8002",
    }))
}

/// Cambia los permisos de ARIA.
///
/// `{"allow_external": false}` la deja hablar y trabajar, pero sin tocar
/// mundos ni canales sociales.
async fn set_permissions(Json(req): Json<Value>) -> Json<Value> {
    let allow_external = req
        .get("allow_external")
        .and_then(|v| v.as_bool())
        .unwrap_or(true);
    let mut guard = autonomy().lock().await;
    guard.allow_external = allow_external;
    guard.updated_at = now_secs();
    persist_state(&guard);
    Json(json!({
        "status": "ok",
        "allow_external": allow_external,
        "server": "ARIA-Axum-8002",
    }))
}

/// La agenda: lo que ARIA tiene entre manos.
async fn get_agenda() -> Json<Value> {
    let agenda = agenda().await;
    Json(json!({
        "status": "ok",
        "agenda": agenda,
        "count": agenda.len(),
        "server": "ARIA-Axum-8002",
    }))
}

/// Apunta algo en la agenda.
///
/// `{"goal": "...", "reason": "...", "skill_id": "..."}`.
async fn add_agenda(Json(req): Json<Value>) -> Json<Value> {
    let goal = req
        .get("goal")
        .or_else(|| req.get("topic"))
        .and_then(|v| v.as_str())
        .unwrap_or_default()
        .trim()
        .to_string();
    if goal.is_empty() {
        return Json(json!({
            "status": "error",
            "error": "falta el objetivo",
            "server": "ARIA-Axum-8002",
        }));
    }
    let reason = req
        .get("reason")
        .or_else(|| req.get("motivo"))
        .and_then(|v| v.as_str())
        .unwrap_or_default()
        .trim()
        .to_string();
    let skill_id = req
        .get("skill_id")
        .and_then(|v| v.as_str())
        .unwrap_or_default()
        .trim()
        .to_string();
    let payload = if skill_id.is_empty() {
        json!({ "action": "ideas", "topic": goal })
    } else {
        json!({ "action": "ejecutar", "skill_id": skill_id })
    };
    let initiative = create_initiative(
        "orden",
        &goal,
        &format!("plan: {goal}"),
        &reason,
        0.8,
        payload,
    )
    .await;
    Json(json!({
        "status": "ok",
        "initiative": initiative,
        "server": "ARIA-Axum-8002",
    }))
}

/// Suelta un objetivo de la agenda.
async fn drop_agenda(axum::extract::Path(id): axum::extract::Path<u64>) -> Json<Value> {
    let removed = drop_initiative(id).await;
    Json(json!({
        "status": if removed { "ok" } else { "error" },
        "removed": removed,
        "id": id,
        "server": "ARIA-Axum-8002",
    }))
}

/// Lee la persona.
async fn get_persona() -> Json<Value> {
    let guard = autonomy().lock().await;
    Json(json!({
        "status": "ok",
        "persona": guard.persona,
        "path": persona_path().to_string_lossy().to_string(),
        "server": "ARIA-Axum-8002",
    }))
}

/// Guarda la persona y la aplica en caliente.
async fn set_persona(Json(req): Json<Persona>) -> Json<Value> {
    let persona = req;
    let mut guard = autonomy().lock().await;
    guard.persona = persona.clone();
    guard.updated_at = now_secs();
    write_json(&persona_path(), &persona);
    persist_state(&guard);
    Json(json!({
        "status": "ok",
        "persona": persona,
        "server": "ARIA-Axum-8002",
    }))
}

/// Cambia el modo: `activa`, `tranquila` o `dormida`.
async fn set_mode(Json(req): Json<Value>) -> Json<Value> {
    let mode = req
        .get("mode")
        .and_then(|v| v.as_str())
        .unwrap_or("tranquila")
        .to_lowercase();
    if !["activa", "tranquila", "dormida"].contains(&mode.as_str()) {
        return Json(json!({
            "status": "error",
            "error": "modo desconocido: usa activa, tranquila o dormida",
        }));
    }
    let mut guard = autonomy().lock().await;
    guard.mode = mode.clone();
    guard.updated_at = now_secs();
    persist_state(&guard);
    Json(json!({
        "status": "ok",
        "mode": mode,
        "server": "ARIA-Axum-8002",
    }))
}

/// Enciende o apaga la autonomía.
async fn toggle(Json(req): Json<Value>) -> Json<Value> {
    let mut guard = autonomy().lock().await;
    let enabled = req
        .get("enabled")
        .and_then(|v| v.as_bool())
        .unwrap_or(!guard.enabled);
    guard.enabled = enabled;
    guard.updated_at = now_secs();
    persist_state(&guard);
    Json(json!({
        "status": "ok",
        "enabled": enabled,
        "mode": guard.mode,
        "server": "ARIA-Axum-8002",
    }))
}

/// Parámetros de la lista de eventos.
#[derive(Debug, Deserialize)]
struct EventsQuery {
    /// Sólo eventos con id mayor que éste.
    since: Option<u64>,
    /// Cuántos devolver como mucho.
    limit: Option<usize>,
}

/// Lista los eventos del mundo.
async fn list_events(Query(query): Query<EventsQuery>) -> Json<Value> {
    let guard = autonomy().lock().await;
    let since = query.since.unwrap_or(0);
    let limit = query.limit.unwrap_or(50).min(MAX_EVENTS);
    let events: Vec<&WorldEvent> = guard
        .events
        .iter()
        .filter(|event| event.id > since)
        .rev()
        .take(limit)
        .collect();
    Json(json!({
        "status": "ok",
        "events": events,
        "count": events.len(),
        "server": "ARIA-Axum-8002",
    }))
}

/// Cuerpo de un evento que entra del mundo.
#[derive(Debug, Deserialize)]
struct EventRequest {
    /// `chat`, `juego`, `voz`, `presencia`, `sistema`, `tarea`.
    #[serde(default = "default_kind")]
    kind: String,
    /// `escritorio`, `minecraft`, `vrchat`, `discord`, `movil`, `usb`.
    #[serde(default = "default_source")]
    source: String,
    #[serde(default)]
    text: String,
    #[serde(default)]
    payload: Value,
}

fn default_kind() -> String {
    "chat".to_string()
}

fn default_source() -> String {
    "escritorio".to_string()
}

/// Un escenario del mundo informa de algo.
///
/// El evento entra en la historia de ARIA, despierta sus pulsiones y, si va
/// dirigido a ella, dispara una respuesta inmediata sin esperar al tick.
pub async fn push_world_event(
    kind: &str,
    source: &str,
    text: &str,
    payload: Value,
) -> WorldEvent {
    let event = {
        let mut guard = autonomy().lock().await;
        let now = now_secs();
        let id = guard.next_id;
        guard.next_id += 1;
        let event = WorldEvent {
            id,
            kind: kind.to_string(),
            source: source.to_string(),
            text: text.to_string(),
            payload,
            at: now,
        };
        apply_event_to_drives(&mut guard.drives, &event);
        guard.events.push_back(event.clone());
        while guard.events.len() > MAX_EVENTS {
            guard.events.pop_front();
        }
        guard.updated_at = now;
        persist_state(&guard);
        event
    };

    broadcast_event(&event);

    // Si es una pregunta, ARIA contesta enseguida (sin esperar al tick).
    // Salvo que otro escenario ya haya contestado: entonces ARIA se entera
    // y sigue con lo suyo, pero no repite la respuesta.
    if event.is_addressed_to_aria() && !event.already_answered() {
        tokio::spawn(async move {
            if let Err(error) = tick_once(true).await {
                tracing::warn!(target: "aria::autonomy", error = %error, "reacción falló");
            }
        });
    }

    event
}

/// Un escenario del mundo informa de algo.
async fn ingest_event(Json(req): Json<EventRequest>) -> Json<Value> {
    let event = push_world_event(
        &req.kind,
        &req.source,
        &req.text,
        req.payload,
    )
    .await;

    Json(json!({
        "status": "ok",
        "event": event,
        "reactive": event.is_addressed_to_aria(),
        "server": "ARIA-Axum-8002",
    }))
}

/// Habla ahora mismo (a petición).
async fn speak(Json(req): Json<Value>) -> Json<Value> {
    let topic = req
        .get("topic")
        .and_then(|v| v.as_str())
        .unwrap_or("lo que tienes en mente")
        .to_string();

    let snapshot = {
        let guard = autonomy().lock().await;
        Snapshot {
            persona: guard.persona.clone(),
            drives: guard.drives.clone(),
            events: guard.events.iter().cloned().collect(),
            skills: Vec::new(),
            energy: guard.drive("energia"),
            channel: guard.presence.channel.clone(),
            worlds: Vec::new(),
            social: None,
            affect: crate::affect::AffectState::default(),
            agenda: guard.initiatives.iter().cloned().collect(),
            lessons: Vec::new(),
            allow_external: guard.allow_external,
        }
    };

    let client = reqwest::Client::new();
    let model = crate::chat::resolve_model(&client, None).await;
    let reply = crate::chat::call_ollama(&client, &speak_prompt(&snapshot, &topic), &model).await;
    let said = pick_sentence(&reply);

    if let Some(sentence) = &said {
        let event = {
            let mut guard = autonomy().lock().await;
            let now = now_secs();
            let id = guard.next_id;
            guard.next_id += 1;
            let event = WorldEvent {
                id,
                kind: "habla".to_string(),
                source: "autonomia".to_string(),
                text: sentence.clone(),
                payload: json!({ "initiative": false, "topic": topic }),
                at: now,
            };
            guard.events.push_back(event.clone());
            while guard.events.len() > MAX_EVENTS {
                guard.events.pop_front();
            }
            guard.stats.utterances += 1;
            guard.presence.talking = true;
            guard.presence.updated_at = now;
            persist_state(&guard);
            event
        };
        broadcast_event(&event);
        let _ = crate::osc::send_chatbox(sentence, true, 6.0);
    }

    Json(json!({
        "status": "ok",
        "said": said,
        "server": "ARIA-Axum-8002",
    }))
}

/// Obliga a ARIA a hacer algo ahora (`{"action": "ideas", "topic": "..."}`).
async fn act(Json(req): Json<Value>) -> Json<Value> {
    let action = match Action::from_model_json(&req) {
        Some(action) => action,
        None => {
            return Json(json!({
                "status": "error",
                "error": "acción desconocida",
                "server": "ARIA-Axum-8002",
            }))
        }
    };

    let snapshot = {
        let guard = autonomy().lock().await;
        Snapshot {
            persona: guard.persona.clone(),
            drives: guard.drives.clone(),
            events: guard.events.iter().cloned().collect(),
            skills: Vec::new(),
            energy: guard.drive("energia"),
            channel: guard.presence.channel.clone(),
            worlds: Vec::new(),
            social: None,
            affect: crate::affect::AffectState::default(),
            agenda: guard.initiatives.iter().cloned().collect(),
            lessons: Vec::new(),
            allow_external: guard.allow_external,
        }
    };

    let goal = action.label();
    let started_at = now_secs();
    let result = execute_action(action.clone(), &snapshot).await;
    let ended_at = now_secs();

    let episode = {
        let mut guard = autonomy().lock().await;
        let id = guard.next_id;
        guard.next_id += 1;
        let episode = Episode {
            id,
            drive: action.drive().to_string(),
            goal,
            action: action.label(),
            said: None,
            // El motivo del fallo se guarda: sin él, ARIA no puede
            // aprender de lo que le sale mal.
            result: match &result {
                Ok(value) => Some(value.clone()),
                Err(error) => Some(format!("falló: {error}")),
            },
            ok: result.is_ok(),
            verified: true,
            started_at,
            ended_at,
        };
        guard.episodes.push_back(episode.clone());
        while guard.episodes.len() > MAX_EPISODES {
            guard.episodes.pop_front();
        }
        guard.stats.actions += 1;
        if !episode.ok {
            guard.stats.errors += 1;
        }
        guard.updated_at = ended_at;
        persist_state(&guard);
        episode
    };

    // Una acción a mano también enseña: lo que falla se guarda igual.
    crate::lessons::learn_from(std::slice::from_ref(&episode)).await;

    Json(json!({
        "status": if episode.ok { "ok" } else { "error" },
        "episode": episode,
        "error": result.err(),
        "server": "ARIA-Axum-8002",
    }))
}

/// Presencia actual.
async fn get_presence() -> Json<Value> {
    let guard = autonomy().lock().await;
    Json(json!({
        "status": "ok",
        "presence": guard.presence,
        "server": "ARIA-Axum-8002",
    }))
}

/// Cambia la presencia (la usa el escenario para mover al avatar).
async fn set_presence(Json(req): Json<Value>) -> Json<Value> {
    let expression = req
        .get("expression")
        .and_then(|v| v.as_str())
        .unwrap_or("neutra")
        .to_string();
    let channel = req
        .get("channel")
        .and_then(|v| v.as_str())
        .unwrap_or("escritorio")
        .to_string();
    let place = req
        .get("place")
        .and_then(|v| v.as_str())
        .unwrap_or("en el escritorio")
        .to_string();
    let mood = req
        .get("mood")
        .and_then(|v| v.as_f64())
        .map(|v| v as f32)
        .unwrap_or(0.6)
        .clamp(0.0, 1.0);
    let talking = req
        .get("talking")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);

    let presence = {
        let mut guard = autonomy().lock().await;
        let now = now_secs();
        guard.presence = Presence {
            expression: expression.clone(),
            mood,
            talking,
            channel: channel.clone(),
            place: place.clone(),
            updated_at: now,
        };
        guard.updated_at = now;
        persist_state(&guard);
        guard.presence.clone()
    };

    let _ = crate::osc::send_expression(&expression);

    Json(json!({
        "status": "ok",
        "presence": presence,
        "server": "ARIA-Axum-8002",
    }))
}

/// Fuerza un tick (para probar o para que el operador la espabile).
async fn tick_now(Json(req): Json<Value>) -> Json<Value> {
    let reactive = req
        .get("reactive")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);
    match tick_once(reactive).await {
        Ok(Some(episode)) => Json(json!({
            "status": "ok",
            "episode": episode,
            "server": "ARIA-Axum-8002",
        })),
        Ok(None) => Json(json!({
            "status": "ok",
            "episode": Value::Null,
            "reason": "no había nada que hacer",
            "server": "ARIA-Axum-8002",
        })),
        Err(error) => Json(json!({
            "status": "error",
            "error": error,
            "server": "ARIA-Axum-8002",
        })),
    }
}

/// Flujo de eventos en vivo (SSE) para los escenarios.
///
/// El escenario (escritorio, móvil, VRChat) se suscribe y recibe lo que
/// ARIA dice y hace en el momento, igual que alguien que la escucha.
async fn stream() -> axum::response::sse::Sse<impl Stream<Item = Result<axum::response::sse::Event, Infallible>>> {
    use axum::response::sse::{Event, KeepAlive, Sse};

    let receiver = broadcaster().subscribe();
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

/* ------------------------------------------------------------------ *
 * Tests
 * ------------------------------------------------------------------ */

#[cfg(test)]
mod tests {
    use super::*;

    fn event(kind: &str, source: &str, text: &str) -> WorldEvent {
        WorldEvent {
            id: 1,
            kind: kind.to_string(),
            source: source.to_string(),
            text: text.to_string(),
            payload: json!({}),
            at: 0,
        }
    }

    #[test]
    fn un_evento_ya_respondido_no_vuelve_a_contestar() {
        let mut answered = event("chat", "escritorio", "¿qué hora es?");
        assert!(answered.is_addressed_to_aria());
        assert!(!answered.already_answered());

        answered.payload = json!({ "answered": true });
        assert!(answered.already_answered());
    }

    #[test]
    fn sin_canal_que_responder_aria_habla_en_vez_de_escribir() {
        let action = adapt_action_to_audience(
            Action::Reply {
                channel: "escritorio".to_string(),
                text: "hola".to_string(),
            },
            &None,
        );
        assert!(matches!(action, Action::Speak { .. }));
    }

    #[test]
    fn con_audiencia_la_frase_va_a_esa_persona() {
        let prompt = SocialPrompt {
            channel: "discord:general".to_string(),
            kind: "mensaje".to_string(),
            author: "user".to_string(),
            text: "hola".to_string(),
            at: 0,
        };
        let action = adapt_action_to_audience(
            Action::Speak {
                topic: "buenas".to_string(),
            },
            &Some(prompt),
        );
        match action {
            Action::Reply { channel, text } => {
                assert_eq!(channel, "discord:general");
                assert_eq!(text, "buenas");
            }
            other => panic!("se esperaba Reply, llegó {other:?}"),
        }
    }

    #[test]
    fn con_audiencia_se_contesta_a_quien_esta_esperando() {
        let prompt = SocialPrompt {
            channel: "discord:general".to_string(),
            kind: "mensaje".to_string(),
            author: "user".to_string(),
            text: "hola".to_string(),
            at: 0,
        };
        let action = adapt_action_to_audience(
            Action::Reply {
                channel: "escritorio".to_string(),
                text: "buenas".to_string(),
            },
            &Some(prompt),
        );
        match action {
            Action::Reply { channel, .. } => assert_eq!(channel, "discord:general"),
            other => panic!("se esperaba Reply, llegó {other:?}"),
        }
    }

    fn snapshot(drives: &[(&str, f32)], events: Vec<WorldEvent>) -> Snapshot {
        let mut map = BTreeMap::new();
        for (name, level) in drives {
            map.insert((*name).to_string(), *level);
        }
        Snapshot {
            persona: Persona::default(),
            drives: map,
            events,
            skills: Vec::new(),
            energy: 1.0,
            channel: "escritorio".to_string(),
            worlds: Vec::new(),
            social: None,
            affect: crate::affect::AffectState::default(),
            agenda: Vec::new(),
            lessons: Vec::new(),
            allow_external: true,
        }
    }

    #[test]
    fn las_pulsiones_no_se_pasan_de_uno_ni_bajan_de_cero() {
        let mut drives = BTreeMap::new();
        drives.insert("social".to_string(), 0.9);
        stimulus(&mut drives, "social", 0.5);
        assert_eq!(drives["social"], 1.0);
        relieve(&mut drives, "social", 5.0);
        assert_eq!(drives["social"], 0.0);
    }

    #[test]
    fn el_decaimiento_deja_la_pulsion_entre_cero_y_uno() {
        let mut drives = BTreeMap::new();
        drives.insert("curiosidad".to_string(), 0.5);
        decay_drives(&mut drives, 0.2);
        assert!((drives["curiosidad"] - 0.3).abs() < 1e-6);
        decay_drives(&mut drives, 5.0);
        assert_eq!(drives["curiosidad"], 0.0);
    }

    #[test]
    fn un_mensaje_del_usuario_sube_la_pulsion_social() {
        let mut drives = BTreeMap::new();
        drives.insert("social".to_string(), 0.2);
        drives.insert("curiosidad".to_string(), 0.2);
        apply_event_to_drives(&mut drives, &event("chat", "escritorio", "hola"));
        assert!(drives["social"] > 0.2);
        assert!(drives["curiosidad"] >= 0.2);
    }

    #[test]
    fn un_juego_que_pasa_por_ahi_sube_la_curiosidad() {
        let mut drives = BTreeMap::new();
        drives.insert("curiosidad".to_string(), 0.1);
        apply_event_to_drives(&mut drives, &event("juego", "minecraft", "encontré diamantes"));
        assert!(drives["curiosidad"] > 0.3);
    }

    #[test]
    fn se_detecta_la_pregunta_sin_responder() {
        let mut state = AutonomyState::default();
        state.events.push_back(event("chat", "escritorio", "¿qué hora es?"));
        assert_eq!(
            pending_question(&state),
            Some("¿qué hora es?".to_string())
        );

        state.events.push_back(event("habla", "autonomia", "son las tres"));
        assert_eq!(pending_question(&state), None);
    }

    #[test]
    fn una_pregunta_gana_a_las_pulsiones() {
        let snap = snapshot(
            &[("curiosidad", 0.9), ("social", 0.1)],
            vec![event("chat", "escritorio", "aria, ¿qué haces?")],
        );
        assert_eq!(
            decide_local(&snap),
            Action::Speak {
                topic: "aria, ¿qué haces?".to_string()
            }
        );
    }

    #[test]
    fn sin_nada_pendiente_decide_segun_la_pulsion_mas_alta() {
        let snap = snapshot(&[("curiosidad", 0.9), ("social", 0.1)], vec![]);
        assert!(matches!(decide_local(&snap), Action::AskIdeas { .. }));

        let snap = snapshot(&[("social", 0.9), ("curiosidad", 0.1)], vec![]);
        assert!(matches!(decide_local(&snap), Action::Speak { .. }));

        let snap = snapshot(&[("orden", 0.9), ("social", 0.1)], vec![]);
        assert_eq!(decide_local(&snap), Action::CheckWorld);
    }

    #[test]
    fn sin_energia_aria_descansa() {
        let mut snap = snapshot(&[("curiosidad", 0.9)], vec![]);
        snap.energy = 0.1;
        assert_eq!(decide_local(&snap), Action::Rest);
    }

    #[test]
    fn dentro_de_un_juego_la_forma_de_ser_social_es_jugar() {
        let mut snap = snapshot(&[("social", 0.9), ("curiosidad", 0.1)], vec![]);
        snap.channel = "minecraft".to_string();
        assert_eq!(
            decide_local(&snap),
            Action::Game {
                command: "follow".to_string(),
                text: String::new(),
            }
        );
    }

    #[test]
    fn los_comandos_de_juego_son_una_lista_cerrada() {
        let value = json!({"action": "juego", "topic": "follow"});
        assert_eq!(
            Action::from_model_json(&value),
            Some(Action::Game {
                command: "follow".to_string(),
                text: String::new(),
            })
        );
        // Un comando inventado no se ejecuta.
        let value = json!({"action": "juego", "topic": "borrar_el_servidor"});
        assert_eq!(Action::from_model_json(&value), None);
    }

    #[test]
    fn el_json_del_modelo_se_traduce_a_acciones() {
        let value = json!({"action": "hablar", "topic": "el tiempo"});
        assert_eq!(
            Action::from_model_json(&value),
            Some(Action::Speak {
                topic: "el tiempo".to_string()
            })
        );

        let value = json!({"action": "mejorar", "skill_id": "gen_008"});
        assert_eq!(
            Action::from_model_json(&value),
            Some(Action::ImproveSkill {
                id: "gen_008".to_string()
            })
        );

        // Una acción que no existe no se inventa: se descarta.
        let value = json!({"action": "borrar_todo"});
        assert_eq!(Action::from_model_json(&value), None);

        // Mejorar sin skill no tiene sentido.
        let value = json!({"action": "mejorar"});
        assert_eq!(Action::from_model_json(&value), None);
    }

    #[test]
    fn la_frase_que_aria_dice_es_una_frase() {
        assert_eq!(
            pick_sentence("Buenos días. ¿En qué andas?"),
            Some("Buenos días.".to_string())
        );
        assert_eq!(pick_sentence("SILENCIO"), None);
        assert_eq!(pick_sentence("   "), None);
        assert_eq!(
            pick_sentence("\"Hola, ¿qué tal?\""),
            Some("Hola, ¿qué tal?".to_string())
        );
    }

    #[test]
    fn la_persona_default_es_aria() {
        let persona = Persona::default();
        assert_eq!(persona.name, "ARIA");
        assert!(!persona.quirks.is_empty());
        let prompt = persona.prompt();
        assert!(prompt.contains("Eres ARIA"));
        assert!(prompt.contains("no inventar"));
    }

    #[test]
    fn la_expresion_sigue_a_la_pulsion_satisfacida() {
        assert_eq!(expression_for("curiosidad", true), "curiosa");
        assert_eq!(expression_for("social", true), "alegre");
        assert_eq!(expression_for("dominio", false), "concentrada");
    }

    #[test]
    fn el_estado_por_defecto_no_actua_solo() {
        let state = AutonomyState::default();
        assert!(!state.enabled);
        assert_eq!(state.mode, "tranquila");
        assert_eq!(state.drive("energia"), 0.9);
    }

    #[test]
    fn el_plan_se_guarda_en_la_agenda() {
        let value = json!({"action": "plan", "topic": "arreglar el panel de skills", "reason": "va fallado"});
        let action = Action::from_model_json(&value).expect("el plan se entiende");
        assert_eq!(
            action,
            Action::Plan {
                goal: "arreglar el panel de skills".to_string(),
                reason: "va fallado".to_string()
            }
        );
        assert_eq!(action.permission(), Permission::Delicada);
    }

    #[test]
    fn un_plan_sin_objetivo_no_se_acepta() {
        let value = json!({"action": "plan"});
        assert!(Action::from_model_json(&value).is_none());
    }

    #[test]
    fn observar_un_mundo_es_delicado_y_actuar_en_el_es_externo() {
        let observe = Action::from_model_json(&json!({"action": "observar", "world": "minecraft"}))
            .expect("observa");
        assert_eq!(observe, Action::Observe { world: "minecraft".to_string() });
        assert_eq!(observe.permission(), Permission::Delicada);

        let world_act = Action::from_model_json(&json!({
            "action": "mundo", "world": "minecraft", "args": {"x": 1}
        }))
        .expect("actúa");
        assert_eq!(world_act.permission(), Permission::Externa);

        let speak = Action::from_model_json(&json!({"action": "hablar", "topic": "hola"}))
            .expect("habla");
        assert_eq!(speak.permission(), Permission::Libre);
    }

    #[test]
    fn observar_sin_mundo_no_se_acepta() {
        assert!(Action::from_model_json(&json!({"action": "observar"})).is_none());
    }
}
