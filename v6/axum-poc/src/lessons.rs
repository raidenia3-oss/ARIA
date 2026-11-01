//! Lecciones: lo que ARIA aprende de lo que hace.
//!
//! ## De dónde sale el diseño
//!
//! Neuro-sama no "aprende" en vivo. Lo que hace es acumular transcripciones
//! de sus streams, curarlas a mano y reentrenar el modelo por lotes. El
//! resultado es que su carácter y su forma de jugar cambian poco a poco,
//! pero siempre a partir de material real: lo que dijo, lo que le pasó y
//! lo que la gente respondió.
//!
//! Aquí el equivalente honesto es más pequeño pero **real**: cada episodio
//! deja una lección, las lecciones que fallaron pesan más que las que
//! funcionaron, y ARIA las lee **antes** de decidir. No hay reentrenamiento
//! (no hay pesos que tocar), pero sí hay memoria de la experiencia y esa
//! memoria cambia lo que hace después.
//!
//! Nada aquí se inventa: las lecciones se derivan de episodios reales, se
//! pueden borrar a mano y se pueden desactivar (`suppressed`).

use axum::{
    routing::{get, post},
    Json, Router,
};
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::collections::VecDeque;
use std::path::PathBuf;
use std::sync::OnceLock;
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::sync::Mutex;

use crate::autonomy::Episode;

/// Lecciones que se guardan como máximo.
pub const MAX_LESSONS: usize = 120;

/// Cuántas lecciones entran en el prompt de decisión.
pub const PROMPT_LESSONS: usize = 6;

/// Peso máximo de una lección.
const MAX_WEIGHT: f32 = 1.0;

/// Archivo donde se guardan las lecciones.
const LESSONS_FILE: &str = "lessons.json";

/* ------------------------------------------------------------------ *
 * Tipos
 * ------------------------------------------------------------------ */

/// Una lección aprendida.
///
/// No es texto decorativo: cada lección tiene un peso, y el peso decide si
/// entra en el prompt de decisión.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Lesson {
    pub id: u64,
    /// `regla` (puesta a mano), `exito` o `fallo`.
    pub kind: String,
    /// La lección, en una frase.
    pub text: String,
    /// Cuánto pesa (0..1). Un fallo pesa más que un acierto.
    pub weight: f32,
    /// De dónde sale: `episodio`, `usuario` o `curacion`.
    pub source: String,
    /// Cuántas veces se ha reforzado.
    #[serde(default)]
    pub uses: u64,
    /// Si está desactivada (no entra en el prompt).
    #[serde(default)]
    pub suppressed: bool,
    pub created_at: u64,
}

impl Lesson {
    /// Una lección de fallo.
    pub fn failure(text: String) -> Self {
        Lesson {
            id: 0,
            kind: "fallo".to_string(),
            text,
            weight: 0.9,
            source: "episodio".to_string(),
            uses: 1,
            suppressed: false,
            created_at: now_secs(),
        }
    }

    /// Una lección de acierto.
    pub fn success(text: String) -> Self {
        Lesson {
            id: 0,
            kind: "exito".to_string(),
            text,
            weight: 0.5,
            source: "episodio".to_string(),
            uses: 1,
            suppressed: false,
            created_at: now_secs(),
        }
    }

    /// Una lección puesta a mano por el usuario o por el modelo.
    pub fn rule(text: String, weight: f32) -> Self {
        Lesson {
            id: 0,
            kind: "regla".to_string(),
            text,
            weight: weight.clamp(0.0, MAX_WEIGHT),
            source: "usuario".to_string(),
            uses: 1,
            suppressed: false,
            created_at: now_secs(),
        }
    }

    /// Clave de agrupación: dos lecciones con la misma clave son la misma.
    fn key(&self) -> String {
        normalize(&self.text)
    }
}

/// Normaliza una frase para poder compararla.
fn normalize(text: &str) -> String {
    text.trim()
        .to_lowercase()
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
}

/// Estado global de las lecciones.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct LessonStore {
    pub lessons: VecDeque<Lesson>,
    pub next_id: u64,
}

/* ------------------------------------------------------------------ *
 * Estado global
 * ------------------------------------------------------------------ */

static LESSONS: OnceLock<Mutex<LessonStore>> = OnceLock::new();

fn lessons() -> &'static Mutex<LessonStore> {
    LESSONS.get_or_init(|| Mutex::new(load()))
}

fn now_secs() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

fn state_dir() -> PathBuf {
    std::env::var("ARIA_AUTONOMY_STATE_DIR")
        .ok()
        .filter(|v| !v.trim().is_empty())
        .map(PathBuf::from)
        .unwrap_or_else(crate::control::default_state_dir)
}

fn lessons_path() -> PathBuf {
    state_dir().join(LESSONS_FILE)
}

fn load() -> LessonStore {
    let Ok(raw) = std::fs::read_to_string(lessons_path()) else {
        return LessonStore {
            lessons: VecDeque::new(),
            next_id: 1,
        };
    };
    match serde_json::from_str::<LessonStore>(&raw) {
        Ok(store) => LessonStore {
            next_id: store.next_id.max(1),
            ..store
        },
        Err(err) => {
            eprintln!("lessons: estado ilegible ({err}), se reinicia");
            LessonStore {
                lessons: VecDeque::new(),
                next_id: 1,
            }
        }
    }
}

fn persist(store: &LessonStore) {
    let path = lessons_path();
    if let Some(parent) = path.parent() {
        if let Err(err) = std::fs::create_dir_all(parent) {
            eprintln!("lessons: no se pudo crear {}: {err}", parent.display());
            return;
        }
    }
    match serde_json::to_string_pretty(store) {
        Ok(body) => {
            if let Err(err) = std::fs::write(&path, body) {
                eprintln!("lessons: no se pudo escribir {}: {err}", path.display());
            }
        }
        Err(err) => eprintln!("lessons: no se pudo serializar: {err}"),
    }
}

/* ------------------------------------------------------------------ *
 * Extracción
 * ------------------------------------------------------------------ */

/// Saca las lecciones de un conjunto de episodios.
///
/// Es una función pura y determinista: los mismos episodios dan siempre las
/// mismas lecciones. Nada aquí depende de un modelo, así que funciona igual
/// sin Ollama.
pub fn extract(episodes: &[Episode]) -> Vec<Lesson> {
    let mut out: Vec<Lesson> = Vec::new();

    for episode in episodes {
        let result = episode
            .result
            .as_deref()
            .unwrap_or_default()
            .trim()
            .to_string();

        if !episode.ok {
            // Un fallo sin resultado no dice nada: no se inventa el motivo.
            if result.is_empty() {
                continue;
            }
            out.push(Lesson::failure(format!(
                "Falló «{}»: {}",
                episode.goal, result
            )));
            continue;
        }

        // Los aciertos sólo cuentan cuando el resultado dice algo: si no,
        // la lección sería ruido.
        if result.is_empty() {
            continue;
        }
        if episode.action.starts_with("ejecutar skill")
            || episode.action.starts_with("mejorar skill")
            || episode.action.starts_with("solucionar")
        {
            out.push(Lesson::success(format!(
                "«{}» funcionó: {}",
                episode.goal, result
            )));
        }
    }

    out
}

/// Fusiona lecciones repetidas: una sola lección, con el peso más alto y
/// las repeticiones sumadas.
///
/// Devuelve cuántas se fusionaron.
pub fn curate(lessons: &mut Vec<Lesson>) -> usize {
    let mut merged: Vec<Lesson> = Vec::new();
    let mut merged_count = 0usize;

    for lesson in lessons.drain(..) {
        let key = lesson.key();
        match merged.iter_mut().find(|existing| existing.key() == key) {
            Some(existing) => {
                existing.weight = existing.weight.max(lesson.weight).min(MAX_WEIGHT);
                existing.uses += lesson.uses;
                existing.suppressed = existing.suppressed && lesson.suppressed;
                existing.created_at = existing.created_at.max(lesson.created_at);
                merged_count += 1;
            }
            None => merged.push(lesson),
        }
    }

    *lessons = merged;
    merged_count
}

/* ------------------------------------------------------------------ *
 * API interna
 * ------------------------------------------------------------------ */

/// Añade lecciones nuevas al almacén, fusionando con las que ya existen.
pub async fn ingest(new_lessons: Vec<Lesson>) -> usize {
    if new_lessons.is_empty() {
        return 0;
    }
    let mut guard = lessons().lock().await;
    let mut added = 0usize;

    for lesson in new_lessons {
        let key = lesson.key();
        if let Some(existing) = guard.lessons.iter_mut().find(|e| e.key() == key) {
            existing.weight = existing.weight.max(lesson.weight).min(MAX_WEIGHT);
            existing.uses += 1;
            existing.suppressed = false;
            continue;
        }
        let mut lesson = lesson;
        lesson.id = guard.next_id;
        guard.next_id += 1;
        guard.lessons.push_back(lesson);
        added += 1;
    }

    while guard.lessons.len() > MAX_LESSONS {
        guard.lessons.pop_front();
    }
    persist(&guard);
    added
}

/// Aprende de los episodios: extrae, fusiona y guarda.
pub async fn learn_from(episodes: &[Episode]) -> usize {
    let mut extracted = extract(episodes);
    if extracted.is_empty() {
        return 0;
    }
    curate(&mut extracted);
    ingest(extracted).await
}

/// Las lecciones que entran en el prompt: las de más peso, sin las
/// desactivadas.
pub async fn top(count: usize) -> Vec<Lesson> {
    let guard = lessons().lock().await;
    let mut active: Vec<Lesson> = guard
        .lessons
        .iter()
        .filter(|lesson| !lesson.suppressed)
        .cloned()
        .collect();
    active.sort_by(|a, b| {
        b.weight
            .partial_cmp(&a.weight)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then(b.uses.cmp(&a.uses))
    });
    active.truncate(count);
    active
}

/// Todas las lecciones, de la más reciente a la más antigua.
pub async fn all() -> Vec<Lesson> {
    let guard = lessons().lock().await;
    guard.lessons.iter().rev().cloned().collect()
}

/// Registra una lección a mano.
pub async fn record(kind: &str, text: &str, source: &str, weight: f32) -> Result<Lesson, String> {
    let text = text.trim().to_string();
    if text.is_empty() {
        return Err("la lección está vacía".to_string());
    }
    let mut lesson = match kind {
        "regla" => Lesson::rule(text, weight),
        "exito" => Lesson::success(text),
        "fallo" => Lesson::failure(text),
        other => return Err(format!("tipo desconocido: {other}")),
    };
    lesson.source = source.to_string();

    let mut guard = lessons().lock().await;
    lesson.id = guard.next_id;
    guard.next_id += 1;
    guard.lessons.push_back(lesson.clone());
    while guard.lessons.len() > MAX_LESSONS {
        guard.lessons.pop_front();
    }
    persist(&guard);
    Ok(lesson)
}

/// Activa o desactiva una lección.
pub async fn set_suppressed(id: u64, suppressed: bool) -> bool {
    let mut guard = lessons().lock().await;
    let Some(lesson) = guard.lessons.iter_mut().find(|lesson| lesson.id == id) else {
        return false;
    };
    lesson.suppressed = suppressed;
    persist(&guard);
    true
}

/// Borra una lección.
pub async fn remove(id: u64) -> bool {
    let mut guard = lessons().lock().await;
    let before = guard.lessons.len();
    guard.lessons.retain(|lesson| lesson.id != id);
    let removed = guard.lessons.len() != before;
    if removed {
        persist(&guard);
    }
    removed
}

/// Consolida las lecciones repetidas.
pub async fn consolidate() -> usize {
    let mut guard = lessons().lock().await;
    let mut list: Vec<Lesson> = guard.lessons.drain(..).collect();
    let merged = curate(&mut list);
    guard.lessons = list.into();
    persist(&guard);
    merged
}

/// Vacía el almacén (para empezar de cero).
pub async fn clear() {
    let mut guard = lessons().lock().await;
    guard.lessons.clear();
    persist(&guard);
}

/// El bloque de texto que se mete en el prompt de decisión.
///
/// Las lecciones desactivadas no entran nunca: el filtro está aquí y no
/// sólo en `top()`, para que ningún camino se cugele una lección apagada.
pub fn prompt(lessons: &[Lesson]) -> String {
    let active: Vec<&Lesson> = lessons.iter().filter(|lesson| !lesson.suppressed).collect();
    if active.is_empty() {
        return String::new();
    }
    let mut out = String::from("Lo que has aprendido:\n");
    for lesson in active {
        out.push_str(&format!("- {}\n", lesson.text.trim()));
    }
    out
}

/* ------------------------------------------------------------------ *
 * Rutas
 * ------------------------------------------------------------------ */

pub fn router() -> Router<()> {
    Router::new()
        .route("/api/lessons", get(list).post(create))
        .route("/api/lessons/curate", post(curate_route))
        .route("/api/lessons/clear", post(clear_route))
        .route(
            "/api/lessons/:id",
            axum::routing::delete(remove_route).patch(suppress_route),
        )
}

async fn list() -> Json<serde_json::Value> {
    let all = all().await;
    Json(json!({
        "status": "ok",
        "lessons": all,
        "count": all.len(),
        "server": "ARIA-Axum-8002",
    }))
}

#[derive(Deserialize)]
struct CreateRequest {
    #[serde(default)]
    text: String,
    /// `regla`, `exito` o `fallo`.
    #[serde(default = "default_kind")]
    kind: String,
    #[serde(default)]
    weight: Option<f32>,
}

fn default_kind() -> String {
    "regla".to_string()
}

async fn create(Json(req): Json<CreateRequest>) -> Json<serde_json::Value> {
    match record(&req.kind, &req.text, "usuario", req.weight.unwrap_or(0.8)).await {
        Ok(lesson) => Json(json!({
            "status": "ok",
            "lesson": lesson,
            "server": "ARIA-Axum-8002",
        })),
        Err(error) => Json(json!({ "status": "error", "error": error })),
    }
}

async fn curate_route() -> Json<serde_json::Value> {
    let merged = consolidate().await;
    Json(json!({
        "status": "ok",
        "merged": merged,
        "server": "ARIA-Axum-8002",
    }))
}

async fn clear_route() -> Json<serde_json::Value> {
    clear().await;
    Json(json!({
        "status": "ok",
        "cleared": true,
        "server": "ARIA-Axum-8002",
    }))
}

async fn remove_route(axum::extract::Path(id): axum::extract::Path<u64>) -> Json<serde_json::Value> {
    let removed = remove(id).await;
    Json(json!({
        "status": if removed { "ok" } else { "error" },
        "removed": removed,
        "id": id,
        "server": "ARIA-Axum-8002",
    }))
}

/// Silencia una lección sin borrarla.
///
/// Desactivar y borrar son cosas distintas: una lección que a ARIA le sale
/// mal una vez no es basura, pero el usuario puede no estar de acuerdo con
/// ella. Al silenciarla deja de entrar en el prompt, pero se conserva para
/// poder volver a activarla.
#[derive(Deserialize)]
struct SuppressRequest {
    #[serde(default)]
    suppressed: bool,
}

async fn suppress_route(
    axum::extract::Path(id): axum::extract::Path<u64>,
    Json(req): Json<SuppressRequest>,
) -> Json<serde_json::Value> {
    let changed = set_suppressed(id, req.suppressed).await;
    Json(json!({
        "status": if changed { "ok" } else { "error" },
        "id": id,
        "suppressed": req.suppressed,
        "server": "ARIA-Axum-8002",
    }))
}

/* ------------------------------------------------------------------ *
 * Tests
 * ------------------------------------------------------------------ */

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn episode(ok: bool, goal: &str, action: &str, result: &str) -> Episode {
        Episode {
            id: 1,
            drive: "curiosidad".to_string(),
            goal: goal.to_string(),
            action: action.to_string(),
            said: None,
            result: Some(result.to_string()),
            ok,
            verified: true,
            started_at: 0,
            ended_at: 0,
        }
    }

    #[test]
    fn un_fallo_produce_una_leccion_de_fallo() {
        let episodes = vec![episode(false, "ejecutar skill: gen_003", "ejecutar skill: gen_003", "timeout")];
        let lessons = extract(&episodes);
        assert_eq!(lessons.len(), 1);
        assert_eq!(lessons[0].kind, "fallo");
        assert!(lessons[0].text.contains("timeout"));
        assert!(lessons[0].weight > 0.5);
    }

    #[test]
    fn un_fallo_sin_resultado_no_inventa_una_leccion() {
        let mut ep = episode(false, "algo", "algo", "");
        ep.result = None;
        assert!(extract(&[ep]).is_empty());
    }

    #[test]
    fn los_aciertos_de_skills_son_lecciones_mas_ligeras() {
        let episodes = vec![episode(
            true,
            "ejecutar skill: gen_008",
            "ejecutar skill: gen_008",
            "reporte listo",
        )];
        let lessons = extract(&episodes);
        assert_eq!(lessons.len(), 1);
        assert_eq!(lessons[0].kind, "exito");
        assert!(lessons[0].weight < 0.9);
    }

    #[test]
    fn un_acio_menor_que_un_fallo_pesa_mas() {
        let failure = Lesson::failure("x".to_string());
        let success = Lesson::success("y".to_string());
        assert!(failure.weight > success.weight);
    }

    #[test]
    fn curar_fusiona_lo_repetido() {
        let mut lessons = vec![
            Lesson::failure("Falló «a»: timeout".to_string()),
            Lesson::failure("Falló «a»: timeout".to_string()),
            Lesson::success("«b» funcionó".to_string()),
        ];
        let merged = curate(&mut lessons);
        assert_eq!(merged, 1);
        assert_eq!(lessons.len(), 2);
        assert_eq!(lessons[0].uses, 2);
    }

    #[test]
    fn las_lecciones_desactivadas_no_entran_en_el_prompt() {
        let mut lesson = Lesson::rule("no tocar procesos del usuario".to_string(), 0.9);
        lesson.suppressed = true;
        assert!(prompt(&[lesson]).is_empty());
    }

    #[test]
    fn el_prompt_empieza_por_lo_aprendido() {
        let lessons = vec![Lesson::rule("pregunta antes de tocar el disco".to_string(), 0.8)];
        let text = prompt(&lessons);
        assert!(text.starts_with("Lo que has aprendido:"));
        assert!(text.contains("pregunta antes de tocar el disco"));
    }

    #[test]
    fn el_prompt_vacio_no_ruina_la_decision() {
        assert_eq!(prompt(&[]), "");
        let _ = json!({});
    }
}
