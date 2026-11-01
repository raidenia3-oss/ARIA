//! Estado afectivo y evolución de la persona.
//!
//! ## De dónde sale el diseño
//!
//! Neuro-sama no es "un modelo con un prompt de personaje": tiene estado
//! interno. El marco de referencia (`o9nn/neuro-sama`, que replica el
//! genoma arquitectónico de Vedal) separa tres cosas que aquí también:
//!
//! * **Rasgos** (`traits`): lo estable. Cómo es ARIA por dentro. Cambian
//!   poco, y cuando cambian, cambian poco.
//! * **Estado afectivo** (`affectiveState`): lo que siente ahora. Cambia con
//!   cada episodio y se calma sola.
//! * **Proyección** (`expression`): lo que se ve. La cara, la voz, el avatar.
//!
//! Y una regla que sí se copia tal cual: la evolución de los rasgos está
//! **acotada**. El marco de Neuro-sama habla de "±15% trait changes": la
//! personalidad puede cambiar, pero despacio y sin perder la coherencia del
//! personaje. Aquí el límite es el mismo: ningún rasgo se mueve más de 0.15
//! en una reflexión, y la reflexión sólo ocurre tras un episodio, no cada
//! mensaje.
//!
//! ## Para qué sirve
//!
//! Sin estado afectivo ARIA dice siempre lo mismo con la misma cara. Con él,
//! el humor se ve (en la UI, en el orbe, en la expresión de VRChat) y las
//! decisiones dependen de cómo está: no es lo mismo responder al mismo
//! mensaje con curiosidad que con enfado.

use axum::{routing::{get, post}, Json, Router};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::{BTreeMap, VecDeque};
use std::sync::OnceLock;
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::sync::Mutex;

use crate::autonomy::{Episode, Persona};

/// Cuánto baja cada emoción por tick.
pub const AFFECT_DECAY: f32 = 0.03;

/// Cuánto puede moverse un rasgo en una reflexión (límit de Neuro-sama).
pub const MAX_TRAIT_DELTA: f32 = 0.15;

/// Límite de un rasgo.
pub const MAX_TRAIT: f32 = 1.0;

/// Emociones que ARIA puede tener.
pub const EMOTIONS: &[&str] = &[
    "alegria",
    "curiosidad",
    "calma",
    "enfado",
    "aburrimiento",
    "sorpresa",
    "determinacion",
];

/// Rasgos de carácter con valor numérico.
pub const TRAITS: &[&str] = &["curiosidad", "calidez", "humor", "audacia", "disciplina"];

/// Archivo donde se guarda el estado afectivo.
const AFFECT_FILE: &str = "affect.json";

/* ------------------------------------------------------------------ *
 * Tipos
 * ------------------------------------------------------------------ */

/// Cómo está ARIA ahora mismo.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AffectState {
    /// Emoción -> intensidad (0..1).
    pub emotions: BTreeMap<String, f32>,
    /// La emoción dominante.
    pub dominant: String,
    /// Expresión que se ve.
    pub expression: String,
    /// Ánimo global (0..1).
    pub mood: f32,
    /// Historial breve: (epoch, emoción, intensidad).
    #[serde(default)]
    pub history: VecDeque<Impact>,
    pub updated_at: u64,
}

/// Un cambio de estado emocional.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Impact {
    pub at: u64,
    /// Qué pasó: el nombre del episodio o del evento.
    pub cause: String,
    /// Emoción que se movió.
    pub emotion: String,
    /// Cuánto se movió (positivo o negativo).
    pub delta: f32,
}

impl Default for AffectState {
    fn default() -> Self {
        let mut emotions = BTreeMap::new();
        for emotion in EMOTIONS {
            emotions.insert((*emotion).to_string(), 0.2);
        }
        emotions.insert("calma".to_string(), 0.6);
        AffectState {
            emotions,
            dominant: "calma".to_string(),
            expression: "neutra".to_string(),
            mood: 0.6,
            history: VecDeque::new(),
            updated_at: 0,
        }
    }
}

/// Un cambio en los rasgos de la persona.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvolutionRecord {
    pub at: u64,
    /// Por qué cambió (el episodio que lo provocó).
    pub reason: String,
    /// Rasgo -> cuánto se movió.
    pub changes: BTreeMap<String, f32>,
    /// Lo que ARIA aprendió, en una frase.
    #[serde(default)]
    pub note: String,
}

/* ------------------------------------------------------------------ *
 * Estado global
 * ------------------------------------------------------------------ */

static AFFECT: OnceLock<Mutex<AffectState>> = OnceLock::new();

fn affect() -> &'static Mutex<AffectState> {
    AFFECT.get_or_init(|| Mutex::new(load_affect()))
}

fn now_secs() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

fn state_dir() -> std::path::PathBuf {
    std::env::var("ARIA_AUTONOMY_STATE_DIR")
        .ok()
        .filter(|v| !v.trim().is_empty())
        .map(std::path::PathBuf::from)
        .unwrap_or_else(crate::control::default_state_dir)
}

fn affect_path() -> std::path::PathBuf {
    state_dir().join(AFFECT_FILE)
}

fn load_affect() -> AffectState {
    let Ok(raw) = std::fs::read_to_string(affect_path()) else {
        return AffectState::default();
    };
    serde_json::from_str::<AffectState>(&raw).unwrap_or_default()
}

fn persist_affect(state: &AffectState) {
    let path = affect_path();
    if let Some(parent) = path.parent() {
        if let Err(err) = std::fs::create_dir_all(parent) {
            eprintln!("affect: no se pudo crear {}: {err}", parent.display());
            return;
        }
    }
    match serde_json::to_string_pretty(state) {
        Ok(body) => {
            if let Err(err) = std::fs::write(&path, body) {
                eprintln!("affect: no se pudo escribir {}: {err}", path.display());
            }
        }
        Err(err) => eprintln!("affect: no se pudo serializar: {err}"),
    }
}

/* ------------------------------------------------------------------ *
 * Emociones
 * ------------------------------------------------------------------ */

/// La expresión que corresponde a una emoción.
///
/// Los nombres son los que entiende el OSC de VRChat (`osc.rs`), para que el
/// avatar y el backend hablen el mismo idioma.
pub fn expression_for(emotion: &str) -> &'static str {
    match emotion {
        "alegria" => "alegre",
        "curiosidad" => "curiosa",
        "enfado" => "enfadada",
        "aburrimiento" => "aburrida",
        "sorpresa" => "sorprendida",
        "determinacion" => "concentrada",
        "calma" => "neutra",
        _ => "neutra",
    }
}

/// Sube una emoción.
pub fn stimulate(state: &mut AffectState, emotion: &str, delta: f32) {
    let entry = state
        .emotions
        .entry(emotion.to_string())
        .or_insert(0.0);
    *entry = (*entry + delta).clamp(0.0, 1.0);
    state.history.push_back(Impact {
        at: now_secs(),
        cause: emotion.to_string(),
        emotion: emotion.to_string(),
        delta,
    });
    while state.history.len() > 40 {
        state.history.pop_front();
    }
}

/// Baja todas las emociones poco a poco y recalcula la dominante.
pub fn decay(state: &mut AffectState) {
    for level in state.emotions.values_mut() {
        *level = (*level - AFFECT_DECAY).clamp(0.0, 1.0);
    }
    recompute(state);
}

/// Recalcula emoción dominante, expresión y ánimo.
pub fn recompute(state: &mut AffectState) {
    let (dominant, level) = state
        .emotions
        .iter()
        .max_by(|a, b| a.1.partial_cmp(b.1).unwrap_or(std::cmp::Ordering::Equal))
        .map(|(name, level)| (name.clone(), *level))
        .unwrap_or_else(|| ("calma".to_string(), 0.0));
    state.expression = expression_for(&dominant).to_string();
    state.dominant = dominant;
    // El ánimo es una mezcla de cómo está de bien (alegria, calma) y de
    // cuánto la fuerza contraria (enfado, aburrimiento) arrastra hacia abajo.
    let positive = state
        .emotions
        .get("alegria")
        .copied()
        .unwrap_or(0.0)
        + state.emotions.get("calma").copied().unwrap_or(0.0)
        + state.emotions.get("curiosidad").copied().unwrap_or(0.0);
    let negative = state
        .emotions
        .get("enfado")
        .copied()
        .unwrap_or(0.0)
        + state.emotions.get("aburrimiento").copied().unwrap_or(0.0);
    state.mood = ((positive / 3.0) - (negative / 2.0)).clamp(0.0, 1.0);
    let _ = level;
    state.updated_at = now_secs();
}

/// Traduce un episodio al cambio emocional que provoca.
pub fn impact_of_episode(episode: &Episode) -> Vec<(&'static str, f32)> {
    let mut out = Vec::new();
    if episode.ok {
        out.push(("alegria", 0.10));
        out.push(("determinacion", 0.05));
    } else {
        out.push(("enfado", 0.12));
        out.push(("determinacion", 0.08));
    }
    if episode.said.is_some() {
        out.push(("alegria", 0.06));
    }
    match episode.drive.as_str() {
        "curiosidad" => out.push(("curiosidad", 0.14)),
        "social" => out.push(("curiosidad", 0.05)),
        "dominio" => out.push(("determinacion", 0.10)),
        "orden" => out.push(("determinacion", 0.06)),
        "energia" => out.push(("aburrimiento", 0.08)),
        _ => {}
    }
    out
}

/// Anota un episodio en el estado afectivo.
pub async fn note_episode(episode: &Episode) {
    let mut guard = affect().lock().await;
    for (emotion, delta) in impact_of_episode(episode) {
        stimulate(&mut guard, emotion, delta);
    }
    recompute(&mut guard);
    persist_affect(&guard);
}

/// Estado afectivo actual.
pub async fn snapshot() -> AffectState {
    affect().lock().await.clone()
}

/// Estado afectivo en JSON para la API.
pub async fn view() -> Value {
    let guard = affect().lock().await;
    let view = guard.clone();
    json!({
        "status": "ok",
        "affect": view,
        "dominant": guard.dominant,
        "expression": guard.expression,
        "mood": guard.mood,
        "emotions": guard.emotions,
        "server": "ARIA-Axum-8002",
    })
}

/// Empuja una emoción a mano (desde la UI o desde un puente).
pub async fn stimulate_now(emotion: &str, delta: f32) -> Result<Value, String> {
    if !EMOTIONS.contains(&emotion) {
        return Err(format!(
            "emoción desconocida '{emotion}' (conocidas: {})",
            EMOTIONS.join(", ")
        ));
    }
    let mut guard = affect().lock().await;
    stimulate(&mut guard, emotion, delta);
    recompute(&mut guard);
    persist_affect(&guard);
    let view = guard.clone();
    Ok(json!({
        "status": "ok",
        "affect": view,
    }))
}

/// Decaimiento: lo llama el tick del runtime.
pub async fn tick_decay() {
    let mut guard = affect().lock().await;
    decay(&mut guard);
    persist_affect(&guard);
}

/* ------------------------------------------------------------------ *
 * Evolución de la persona
 * ------------------------------------------------------------------ */

/// Aplica unos cambios de rasgos respetando el límite de ±0.15.
///
/// Devuelve el registro de evolución con los cambios *ya acotados*: lo que
/// se guarda es lo que realmente se aplicó, no lo que pidió el modelo.
pub fn apply_trait_changes(
    persona: &mut Persona,
    changes: &BTreeMap<String, f32>,
    reason: &str,
    note: &str,
) -> EvolutionRecord {
    let mut applied = BTreeMap::new();
    for (trait_name, raw_delta) in changes {
        if !TRAITS.contains(&trait_name.as_str()) {
            continue;
        }
        let delta = raw_delta.clamp(-MAX_TRAIT_DELTA, MAX_TRAIT_DELTA);
        if delta.abs() < 0.001 {
            continue;
        }
        let current = persona.traits.get(trait_name).copied().unwrap_or(0.5);
        let next = (current + delta).clamp(0.0, MAX_TRAIT);
        persona.traits.insert(trait_name.clone(), next);
        applied.insert(trait_name.clone(), next - current);
    }
    let record = EvolutionRecord {
        at: now_secs(),
        reason: reason.to_string(),
        changes: applied,
        note: note.trim().to_string(),
    };
    persona.evolution.push(record.clone());
    // El historial de evolución también está acotado: no crece sin fin.
    while persona.evolution.len() > 40 {
        persona.evolution.remove(0);
    }
    record
}

/// Prompt de reflexión: qué hizo ARIA y qué debería cambiar de ella.
///
/// Es el momento "transformativo" del que habla el marco de referencia: tras
/// una acción, ARIA mira lo que hizo y ajusta su forma de ser. Los cambios
/// van acotados para que no se convierta en otra persona de un día para otro.
fn reflect_prompt(persona: &Persona, episodes: &[Episode]) -> String {
    let mut recent = String::new();
    for episode in episodes.iter().rev().take(6).rev() {
        recent.push_str(&format!(
            "- {} (pulso {}, {}): {}\n",
            episode.goal,
            episode.drive,
            if episode.ok { "salió bien" } else { "falló" },
            episode.result.clone().unwrap_or_else(|| "sin resultado".to_string())
        ));
    }
    if recent.is_empty() {
        recent.push_str("- (todavía no ha hecho nada)\n");
    }

    let mut traits = String::new();
    for trait_name in TRAITS {
        traits.push_str(&format!(
            "- {trait_name}: {:.2}\n",
            persona.traits.get(*trait_name).copied().unwrap_or(0.5)
        ));
    }

    format!(
        "{}\n\nQué ha hecho ARIA últimamente:\n{recent}\n\nSus rasgos ahora:\n{traits}\n\n\
         Piensa como ARIA: ¿qué debería cambiar en su forma de ser a partir de lo que acaba de \
         pasar? Un rasgo puede moverse como máximo 0.15 y sólo si de verdad hay una razón.\n\n\
         Responde sólo con JSON: {{\"trait_changes\": {{\"curiosidad\": 0.05, \"calidez\": -0.02}}, \
         \"note\": \"una frase con lo que ha aprendido\"}}",
        persona.prompt()
    )
}

/// Refelexión de verdad: el modelo propone, el límite manda.
///
/// Si no hay modelo o no devuelve JSON utilizable, no se cambia nada: es
/// preferible que ARIA no cambie a que cambie por un error de parseo.
pub async fn reflect(persona: &mut Persona, episodes: &[Episode]) -> Option<EvolutionRecord> {
    if episodes.is_empty() {
        return None;
    }
    let client = reqwest::Client::new();
    let model = crate::chat::resolve_model(&client, None).await;
    let value = crate::chat::call_ollama_json(&client, &reflect_prompt(persona, episodes), &model).await?;
    let changes = value.get("trait_changes").and_then(|v| v.as_object())?;
    let mut parsed: BTreeMap<String, f32> = BTreeMap::new();
    for (name, raw) in changes {
        let Some(delta) = raw.as_f64() else { continue };
        parsed.insert(name.clone(), delta as f32);
    }
    if parsed.is_empty() {
        return None;
    }
    let note = value
        .get("note")
        .and_then(|v| v.as_str())
        .unwrap_or_default()
        .to_string();
    let reason = episodes
        .last()
        .map(|e| e.goal.clone())
        .unwrap_or_else(|| "reflexión".to_string());
    let record = apply_trait_changes(persona, &parsed, &reason, &note);
    crate::autonomy::persist_persona(persona);
    Some(record)
}

/// Los rasgos con su valor, para la UI.
pub fn trait_view(persona: &Persona) -> Value {
    let mut out = serde_json::Map::new();
    for trait_name in TRAITS {
        out.insert(
            (*trait_name).to_string(),
            json!(persona.traits.get(*trait_name).copied().unwrap_or(0.5)),
        );
    }
    Value::Object(out)
}

/* ------------------------------------------------------------------ *
 * Rutas
 * ------------------------------------------------------------------ */

pub fn router() -> Router<()> {
    Router::new()
        .route("/api/affect", get(affect_status))
        .route("/api/affect/stimulus", post(stimulus_route))
        .route("/api/affect/evolution", get(evolution))
}

async fn affect_status() -> Json<Value> {
    Json(view().await)
}

#[derive(Deserialize)]
struct StimulusRequest {
    #[serde(default)]
    emotion: String,
    #[serde(default)]
    delta: Option<f32>,
}

async fn stimulus_route(Json(req): Json<StimulusRequest>) -> Json<Value> {
    let delta = req.delta.unwrap_or(0.1);
    match stimulate_now(&req.emotion, delta).await {
        Ok(payload) => Json(payload),
        Err(error) => Json(json!({ "status": "error", "error": error })),
    }
}

async fn evolution() -> Json<Value> {
    let persona = crate::autonomy::load_persona();
    Json(json!({
        "status": "ok",
        "traits": trait_view(&persona),
        "history": persona.evolution,
        "limit_per_reflection": MAX_TRAIT_DELTA,
        "server": "ARIA-Axum-8002",
    }))
}

/* ------------------------------------------------------------------ *
 * Tests
 * ------------------------------------------------------------------ */

#[cfg(test)]
mod tests {
    use super::*;

    fn persona() -> Persona {
        Persona::default()
    }

    #[test]
    fn cada_emocion_tiene_su_expresion() {
        assert_eq!(expression_for("alegria"), "alegre");
        assert_eq!(expression_for("curiosidad"), "curiosa");
        assert_eq!(expression_for("enfado"), "enfadada");
        assert_eq!(expression_for("sorpresa"), "sorprendida");
        assert_eq!(expression_for("desconocida"), "neutra");
    }

    #[test]
    fn la_expresion_se_puede_mandar_a_vrchat() {
        // Las expresiones del backend tienen que existir en el catálogo OSC.
        for emotion in EMOTIONS {
            let expression = expression_for(emotion);
            assert!(
                crate::osc::expression_index(expression).is_some(),
                "'{expression}' no existe en VRChat"
            );
        }
    }

    #[test]
    fn la_emocion_dominante_manda_en_la_expresion() {
        let mut state = AffectState::default();
        stimulate(&mut state, "alegria", 0.6);
        recompute(&mut state);
        assert_eq!(state.dominant, "alegria");
        assert_eq!(state.expression, "alegre");
    }

    #[test]
    fn las_emociones_se_calman_solas() {
        let mut state = AffectState::default();
        stimulate(&mut state, "enfado", 0.5);
        let before = state.emotions.get("enfado").copied().unwrap_or(0.0);
        decay(&mut state);
        let after = state.emotions.get("enfado").copied().unwrap_or(0.0);
        assert!(after < before, "el enfado tiene que bajar: {before} -> {after}");
    }

    #[test]
    fn un_rasgo_no_se_mueve_mas_de_015() {
        let mut persona = persona();
        let mut changes = BTreeMap::new();
        changes.insert("curiosidad".to_string(), 0.9);
        let record = apply_trait_changes(&mut persona, &changes, "test", "");
        let delta = record.changes.get("curiosidad").copied().unwrap_or(0.0);
        assert!(delta <= MAX_TRAIT_DELTA, "el cambio fue {delta}");
        assert!((delta - MAX_TRAIT_DELTA).abs() < 0.001);
    }

    #[test]
    fn un_rasgo_desconocido_no_se_toca() {
        let mut persona = persona();
        let mut changes = BTreeMap::new();
        changes.insert("poder".to_string(), 0.5);
        let record = apply_trait_changes(&mut persona, &changes, "test", "");
        assert!(record.changes.is_empty());
        assert!(!persona.traits.contains_key("poder"));
    }

    #[test]
    fn los_rasgos_se_quedan_entre_cero_y_uno() {
        let mut persona = persona();
        let mut changes = BTreeMap::new();
        changes.insert("humor".to_string(), 1.0);
        apply_trait_changes(&mut persona, &changes, "test", "");
        let humor = persona.traits.get("humor").copied().unwrap_or(0.5);
        assert!(humor <= MAX_TRAIT, "el humor se pasó: {humor}");
    }

    #[test]
    fn el_historial_de_evolucion_no_crece_sin_limite() {
        let mut persona = persona();
        let changes: BTreeMap<String, f32> = [("calidez".to_string(), 0.05)].into_iter().collect();
        for _ in 0..60 {
            apply_trait_changes(&mut persona, &changes, "test", "");
        }
        assert!(persona.evolution.len() <= 40);
    }
}
