//! Laboratorio de creatividad de ARIA.
//!
//! Tres cosas que viven en un mismo sitio:
//!
//! * **Ideas** — ARIA propone ideas nuevas y las puntúa en novedad,
//!   viabilidad e impacto.
//! * **Aprendizaje** — cada veredicto del usuario (acepta, rechaza, pide
//!   mejora) ajusta el peso de un tema. Ese peso entra en el prompt de
//!   generación —ARIA sabe qué temas le gustan— y en el orden final de las
//!   ideas. No es decorativo: es el mecanismo por el que ARIA "aprende a
//!   sugerir".
//! * **Forja** — una idea aceptada se convierte en una skill real, que se
//!   puede equipar (y entonces entra en el prompt del chat) y ejecutar.
//! * **Solución** — un problema concreto se convierte en soluciones
//!   accionables; cada una se puede aceptar y forjar igual que una idea.
//! * **Creación directa** — una skill se puede pedir por su cuenta
//!   («una skill que mire el clima»), sin pasar por una idea.
//! * **Integraciones** — capacidades externas (herramientas, servicios,
//!   módulos) que se registran y quedan disponibles para ARIA.
//!
//! El estado vive en disco (`creativity.json`, en el directorio de estado) y
//! se cruza con el árbol de habilidades: una skill forjada aparece en
//! `GET /api/skills` como cualquier otra capacidad y se equipa con
//! `POST /api/skill-tree/equip-generated`.

use axum::{
    extract::Path,
    routing::{get, post},
    Extension, Json, Router,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::path::PathBuf;
use std::sync::{Arc, OnceLock};
use tokio::sync::Mutex;

use crate::state::SharedState;

/// Archivo de estado dentro del directorio de estado.
const CREATIVITY_FILE: &str = "creativity.json";
/// Override del directorio donde vive el estado del laboratorio.
const CREATIVITY_STATE_DIR_ENV: &str = "ARIA_CREATIVITY_STATE_DIR";

/// Ideas guardadas como máximo. El laboratorio no es un archivo infinito.
const MAX_IDEAS: usize = 240;
/// Skills forjadas guardadas como máximo.
const MAX_SKILLS: usize = 80;
/// Integraciones registradas como máximo.
const MAX_INTEGRATIONS: usize = 40;
/// Cuántas ideas se piden por defecto.
///
/// Dos es el punto dulce en esta máquina: Ollama va por CPU (no hay GPU
/// dedicada) y cada idea extra son minutos de espera. El usuario puede
/// pedir más cuando quiera, y las ideas de reserva son inmediatas.
const DEFAULT_COUNT: usize = 2;
/// Tope de ideas por petición.
const MAX_COUNT: usize = 12;
/// Longitud máxima del nombre de un tema.
const THEME_MAX_LEN: usize = 32;
/// Skills creadas por ARIA que se pueden equipar a la vez.
pub const MAX_GENERATED_EQUIPPED: usize = 2;

/// Peso máximo (en valor absoluto) de un tema aprendido.
const MAX_THEME_WEIGHT: f32 = 1.0;
/// Peso que suma un veredicto «me gusta».
const ACCEPT_DELTA: f32 = 0.30;
/// Peso que resta un veredicto «no me gusta».
const REJECT_DELTA: f32 = 0.30;
/// Peso que suma un veredicto «mejórala» (es unaacceptance con matiz).
const IMPROVE_DELTA: f32 = 0.05;
/// Cuánto pesa el tema aprendido en el orden final de las ideas.
const THEME_RANK_BONUS: f32 = 0.15;
/// Peso que suma usar una skill: lo que se usa es un tema que interesa.
const USAGE_DELTA: f32 = 0.05;

/* ------------------------------------------------------------------ *
 * Modelo de datos
 * ------------------------------------------------------------------ */

/// Una idea propuesta (por ARIA o por el propio usuario).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Idea {
    pub id: String,
    pub title: String,
    #[serde(default)]
    pub summary: String,
    #[serde(default)]
    pub detail: String,
    /// Tema del que trata. El aprendizaje agrupa por tema.
    #[serde(default = "default_theme")]
    pub theme: String,
    /// De dónde salió: `idea`, `mejora` o `manual`.
    #[serde(default)]
    pub origin: String,
    /// Novedad (0..1).
    pub novelty: f32,
    /// Viabilidad (0..1).
    pub feasibility: f32,
    /// Impacto (0..1).
    pub impact: f32,
    /// Puntuación global (0..1).
    pub score: f32,
    /// `new`, `refining`, `accepted`, `rejected` o `built`.
    pub status: String,
    /// Nota del usuario (por ejemplo, qué le faltaba).
    #[serde(default)]
    pub note: Option<String>,
    #[serde(default)]
    pub created_at: String,
    /// Skill forjada a partir de esta idea, si ya existe.
    #[serde(default)]
    pub skill_id: Option<String>,
}

fn default_theme() -> String {
    "general".to_string()
}

/// Una skill escrita por ARIA a partir de una idea.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GeneratedSkill {
    pub id: String,
    /// Nombre corto y legible: `resumir_chat`.
    pub name: String,
    pub description: String,
    /// Qué tiene que hacer la skill (las instrucciones que se le dan).
    #[serde(default)]
    pub instruction: String,
    #[serde(default)]
    pub theme: String,
    #[serde(default)]
    pub params: Vec<String>,
    #[serde(default)]
    pub source_idea: Option<String>,
    #[serde(default)]
    pub created_at: String,
    #[serde(default)]
    pub runs: u64,
    /// Cuántas veces ARIA ha reescrito esta skill para mejorarla.
    #[serde(default)]
    pub revisions: u64,
}

/// Una capacidad externa que se integra en ARIA.
///
/// No es una skill: es algo que ya existe fuera (un binario, un servicio, un
/// módulo) y que ARIA declara para poder usarla y nombrarla. Queda
/// registrada, se puede activar y desactivar, y las activas entran en el
/// prompt del chat.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Integration {
    pub id: String,
    /// Nombre legible: `nmap`, `discord`, `kafka`.
    pub name: String,
    /// Qué clase de integración es: `herramienta`, `servicio` o `módulo`.
    #[serde(default)]
    pub kind: String,
    /// Dónde vive: comando, URL o ruta.
    #[serde(default)]
    pub target: String,
    /// Para qué sirve, en una frase.
    #[serde(default)]
    pub description: String,
    /// Si está activa, ARIA la puede usar.
    #[serde(default = "default_enabled")]
    pub enabled: bool,
    #[serde(default)]
    pub created_at: String,
    /// Cuántas veces se ha probado.
    #[serde(default)]
    pub calls: u64,
}

fn default_enabled() -> bool {
    true
}

/// Estado completo del laboratorio.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreativeState {
    #[serde(default)]
    pub ideas: Vec<Idea>,
    #[serde(default)]
    pub skills: Vec<GeneratedSkill>,
    /// Integraciones registradas (herramientas, servicios, módulos).
    #[serde(default)]
    pub integrations: Vec<Integration>,
    /// Peso aprendido por tema (-1..1).
    #[serde(default)]
    pub weights: BTreeMap<String, f32>,
    /// Contador de ids.
    #[serde(default)]
    pub seq: u64,
    /// Ciclos de generación completados.
    #[serde(default)]
    pub cycles: u64,
    #[serde(default)]
    pub accepted: u64,
    #[serde(default)]
    pub rejected: u64,
    #[serde(default)]
    pub built: u64,
    /// De dónde salieron las últimas ideas: `ollama:<modelo>` o `local`.
    #[serde(default)]
    pub last_engine: String,
    #[serde(default)]
    pub updated_at: String,
}

impl Default for CreativeState {
    fn default() -> Self {
        Self {
            ideas: Vec::new(),
            skills: Vec::new(),
            integrations: Vec::new(),
            weights: BTreeMap::new(),
            seq: 0,
            cycles: 0,
            accepted: 0,
            rejected: 0,
            built: 0,
            last_engine: String::new(),
            updated_at: String::new(),
        }
    }
}

/* ------------------------------------------------------------------ *
 * Veredictos y aprendizaje
 * ------------------------------------------------------------------ */

/// Lo que el usuario dice de una idea.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Verdict {
    /// La idea sirve: ARIA la tiene en cuenta.
    Accept,
    /// La idea no sirve: ARIA deja de proponer cosas así.
    Reject,
    /// La idea sirve pero hay que refinarla: se guarda la nota.
    Improve,
}

impl Verdict {
    /// Interpreta el texto que llega por HTTP.
    pub fn parse(raw: &str) -> Option<Verdict> {
        let normalized = raw.trim().to_lowercase().replace([' ', '-'], "_");
        match normalized.as_str() {
            "accept" | "aceptar" | "aceptada" | "like" | "me_gusta" | "si" => Some(Verdict::Accept),
            "reject" | "rechazar" | "rechazada" | "dislike" | "no" => Some(Verdict::Reject),
            "improve" | "mejorar" | "mejorada" | "refine" => Some(Verdict::Improve),
            _ => None,
        }
    }

    /// Cuánto mueve el peso del tema.
    pub fn delta(self) -> f32 {
        match self {
            Verdict::Accept => ACCEPT_DELTA,
            Verdict::Reject => -REJECT_DELTA,
            Verdict::Improve => IMPROVE_DELTA,
        }
    }
}

/// Peso aprendido de un tema.
#[derive(Debug, Clone, Serialize)]
pub struct ThemeProfile {
    pub theme: String,
    pub weight: f32,
}

impl CreativeState {
    /// Normaliza un tema: minúsculas, sin espacios raro, con tope de largo.
    pub fn normalize_theme(raw: &str) -> String {
        let cleaned: String = raw
            .trim()
            .to_lowercase()
            .chars()
            .map(|c| if c.is_alphanumeric() { c } else { '-' })
            .collect();
        let trimmed = cleaned.trim_matches('-').to_string();
        if trimmed.is_empty() {
            default_theme()
        } else {
            trimmed.chars().take(THEME_MAX_LEN).collect()
        }
    }

    /// Peso aprendido de un tema (0 si nunca se juzgó).
    pub fn theme_weight(&self, theme: &str) -> f32 {
        self.weights.get(theme).copied().unwrap_or(0.0)
    }

    /// Ajusta el peso de un tema, sin salirse de `-1..1`.
    fn bump_theme(&mut self, theme: &str, delta: f32) {
        let current = self.theme_weight(theme);
        let next = (current + delta).clamp(-MAX_THEME_WEIGHT, MAX_THEME_WEIGHT);
        if next.abs() < f32::EPSILON {
            self.weights.remove(theme);
        } else {
            self.weights.insert(theme.to_string(), next);
        }
    }

    /// Puntuación global de una idea: la del modelo con el sesgo del tema
    /// aprendido encima.
    pub fn effective_score(&self, idea: &Idea) -> f32 {
        (idea.score + self.theme_weight(&idea.theme) * THEME_RANK_BONUS).clamp(0.0, 1.0)
    }

    /// Ideas ordenadas por puntuación efectiva (mejor primero).
    pub fn ranked(&self) -> Vec<Idea> {
        let mut ideas = self.ideas.clone();
        ideas.sort_by(|a, b| {
            self.effective_score(b)
                .partial_cmp(&self.effective_score(a))
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        ideas
    }

    /// Perfil aprendido: temas ordenados de más a menos peso.
    pub fn profile(&self) -> Vec<ThemeProfile> {
        let mut themes: Vec<ThemeProfile> = self
            .weights
            .iter()
            .map(|(theme, weight)| ThemeProfile {
                theme: theme.clone(),
                weight: *weight,
            })
            .collect();
        themes.sort_by(|a, b| {
            b.weight
                .partial_cmp(&a.weight)
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        themes
    }

    /// Busca una idea por id.
    pub fn find_idea(&self, id: &str) -> Option<&Idea> {
        self.ideas.iter().find(|idea| idea.id == id)
    }

    /// Busca una skill por id.
    pub fn find_skill(&self, id: &str) -> Option<&GeneratedSkill> {
        self.skills.iter().find(|skill| skill.id == id)
    }

    /// Guarda una skill escrita (a mano o por ARIA) y le asigna id.
    ///
    /// Es el camino corto para crear una skill: no hace falta una idea por
    /// medio, pero la skill entra en el mismo catálogo y se equipa igual.
    pub fn add_skill(&mut self, mut skill: GeneratedSkill) -> GeneratedSkill {
        self.seq += 1;
        skill.id = format!("gen_{:03}", self.seq);
        if skill.created_at.is_empty() {
            skill.created_at = now();
        }
        self.built += 1;
        self.skills.push(skill.clone());
        if self.skills.len() > MAX_SKILLS {
            let excess = self.skills.len() - MAX_SKILLS;
            self.skills.drain(0..excess);
        }
        skill
    }

    /// Reescribe las instrucciones de una skill para mejorarla.
    ///
    /// Devuelve la skill actualizada. Sólo se llama cuando el modelo ha
    /// dado una instrucción nueva: una «mejora» inventada sería ruido.
    pub fn apply_skill_revision(
        &mut self,
        id: &str,
        instruction: String,
        description: Option<String>,
    ) -> Result<GeneratedSkill, String> {
        let Some(entry) = self.skills.iter_mut().find(|skill| skill.id == id) else {
            return Err(format!("Skill desconocida: {id}"));
        };
        entry.instruction = instruction;
        if let Some(description) = description {
            let description = description.trim().to_string();
            if !description.is_empty() {
                entry.description = description;
            }
        }
        entry.revisions += 1;
        Ok(entry.clone())
    }

    /// Registra una integración nueva.
    ///
    /// Dos integraciones con el mismo nombre no se pueden registrar: sería
    /// la misma capacidad escrita de dos formas y ARIA no sabría cuál
    /// usar.
    pub fn push_integration(&mut self, mut integration: Integration) -> Result<Integration, String> {
        let name = integration.name.trim().to_string();
        if name.is_empty() {
            return Err("La integración necesita un nombre".to_string());
        }
        let key = slugify(&name);
        if self
            .integrations
            .iter()
            .any(|existing| slugify(&existing.name) == key)
        {
            return Err(format!("Ya existe una integración llamada «{name}»"));
        }

        integration.name = name;
        if integration.kind.trim().is_empty() {
            integration.kind = "herramienta".to_string();
        }
        if integration.description.trim().is_empty() {
            integration.description = integration.target.clone();
        }

        self.seq += 1;
        integration.id = format!("int_{:03}", self.seq);
        integration.created_at = now();
        self.integrations.push(integration.clone());
        if self.integrations.len() > MAX_INTEGRATIONS {
            let excess = self.integrations.len() - MAX_INTEGRATIONS;
            self.integrations.drain(0..excess);
        }
        Ok(integration)
    }

    /// Busca una integración por id.
    pub fn find_integration(&self, id: &str) -> Option<&Integration> {
        self.integrations.iter().find(|entry| entry.id == id)
    }

    /// Activa o desactiva una integración.
    pub fn toggle_integration(&mut self, id: &str, enabled: bool) -> Result<Integration, String> {
        let Some(entry) = self
            .integrations
            .iter_mut()
            .find(|integration| integration.id == id)
        else {
            return Err(format!("Integración desconocida: {id}"));
        };
        entry.enabled = enabled;
        Ok(entry.clone())
    }

    /// Integraciones activas: las que ARIA puede usar ahora mismo.
    pub fn enabled_integrations(&self) -> Vec<Integration> {
        self.integrations
            .iter()
            .filter(|entry| entry.enabled)
            .cloned()
            .collect()
    }

    /// Registra un veredicto del usuario y devuelve la idea actualizada.
    ///
    /// Aquí está el aprendizaje: el veredicto mueve el peso del tema, y ese
    /// peso luego ordena las ideas y se le cuenta al modelo para que no
    /// repita lo que el usuario rechazó.
    pub fn apply_verdict(
        &mut self,
        idea_id: &str,
        verdict: Verdict,
        note: Option<String>,
    ) -> Result<Idea, String> {
        let Some(index) = self.ideas.iter().position(|idea| idea.id == idea_id) else {
            return Err(format!("Idea desconocida: {idea_id}"));
        };
        let theme = self.ideas[index].theme.clone();

        match verdict {
            Verdict::Accept => {
                self.ideas[index].status = "accepted".to_string();
                self.accepted += 1;
            }
            Verdict::Reject => {
                self.ideas[index].status = "rejected".to_string();
                self.rejected += 1;
            }
            Verdict::Improve => {
                if self.ideas[index].status == "new" {
                    self.ideas[index].status = "refining".to_string();
                }
            }
        }

        if let Some(text) = note {
            let text = text.trim().to_string();
            if !text.is_empty() {
                self.ideas[index].note = Some(text);
            }
        }

        self.bump_theme(&theme, verdict.delta());
        Ok(self.ideas[index].clone())
    }

    /// Guarda una idea y le asigna id.
    pub fn push_idea(&mut self, mut idea: Idea) -> Idea {
        self.seq += 1;
        idea.id = format!("idea_{:03}", self.seq);
        if idea.created_at.is_empty() {
            idea.created_at = now();
        }
        if idea.score <= 0.0 {
            idea.score = score_of(idea.novelty, idea.feasibility, idea.impact);
        }
        self.ideas.push(idea.clone());
        if self.ideas.len() > MAX_IDEAS {
            let excess = self.ideas.len() - MAX_IDEAS;
            self.ideas.drain(0..excess);
        }
        idea
    }

    /// Convierte una idea en una skill ejecutable.
    pub fn forge(&mut self, idea_id: &str) -> Result<GeneratedSkill, String> {
        let Some(index) = self.ideas.iter().position(|idea| idea.id == idea_id) else {
            return Err(format!("Idea desconocida: {idea_id}"));
        };
        if self.ideas[index].status == "built" {
            return Err("Esta idea ya tiene una skill forjada".to_string());
        }

        let title = self.ideas[index].title.clone();
        let summary = self.ideas[index].summary.clone();
        let detail = self.ideas[index].detail.clone();
        let theme = self.ideas[index].theme.clone();

        self.seq += 1;
        let id = format!("gen_{:03}", self.seq);
        let name = slugify(&title);
        let instruction = if detail.trim().is_empty() {
            format!("Realiza esta tarea: {title}. {summary}")
        } else {
            detail.trim().to_string()
        };

        let skill = GeneratedSkill {
            id: id.clone(),
            name,
            description: if summary.trim().is_empty() {
                title.clone()
            } else {
                summary.clone()
            },
            instruction,
            theme: theme.clone(),
            params: vec!["input".to_string()],
            source_idea: Some(idea_id.to_string()),
            created_at: now(),
            runs: 0,
            revisions: 0,
        };

        self.ideas[index].status = "built".to_string();
        self.ideas[index].skill_id = Some(id);
        self.built += 1;
        self.skills.push(skill.clone());
        if self.skills.len() > MAX_SKILLS {
            let excess = self.skills.len() - MAX_SKILLS;
            self.skills.drain(0..excess);
        }
        Ok(skill)
    }
}

/// Puntuación global a partir de los tres ejes.
pub fn score_of(novelty: f32, feasibility: f32, impact: f32) -> f32 {
    (novelty * 0.35 + feasibility * 0.35 + impact * 0.30).clamp(0.0, 1.0)
}

/// Convierte un título en un nombre de skill: minúsculas, sin acentos,
/// con guiones bajos.
///
/// Sin acentos porque el nombre acaba siendo un identificador que se
/// teclea y se compara: «resumir_la_sesion» se busca mucho mejor que
/// «resumir_la_sesión».
pub fn slugify(text: &str) -> String {
    let mut slug = String::new();
    let mut pending_separator = false;
    for ch in fold_accents(&text.trim().to_lowercase()).chars() {
        if ch.is_ascii_alphanumeric() {
            if pending_separator && !slug.is_empty() {
                slug.push('_');
            }
            pending_separator = false;
            slug.push(ch);
        } else {
            pending_separator = true;
        }
    }
    let slug: String = slug.chars().take(48).collect();
    if slug.is_empty() {
        "skill_sin_nombre".to_string()
    } else {
        slug
    }
}

/// Quita las tildes de las letras que ARIA usa en español.
///
/// `ñ` se convierte en `n` (no es una tilde) y `ü` en `u`.
fn fold_accents(text: &str) -> String {
    text.chars()
        .map(|ch| match ch {
            'á' => 'a',
            'é' => 'e',
            'í' => 'i',
            'ó' => 'o',
            'ú' => 'u',
            'ü' => 'u',
            'ñ' => 'n',
            'Á' => 'a',
            'É' => 'e',
            'Í' => 'i',
            'Ó' => 'o',
            'Ú' => 'u',
            'Ü' => 'u',
            'Ñ' => 'n',
            other => other,
        })
        .collect()
}

fn now() -> String {
    chrono::Utc::now().to_rfc3339()
}

/* ------------------------------------------------------------------ *
 * Estado global y persistencia
 * ------------------------------------------------------------------ */

static CREATIVE: OnceLock<Mutex<CreativeState>> = OnceLock::new();

fn creative() -> &'static Mutex<CreativeState> {
    CREATIVE.get_or_init(|| Mutex::new(load_state()))
}

/// Ruta del archivo de estado del laboratorio.
pub fn state_path() -> PathBuf {
    let dir = std::env::var(CREATIVITY_STATE_DIR_ENV)
        .ok()
        .filter(|v| !v.trim().is_empty())
        .map(PathBuf::from)
        .unwrap_or_else(crate::control::default_state_dir);
    dir.join(CREATIVITY_FILE)
}

fn load_state() -> CreativeState {
    let path = state_path();
    let Ok(raw) = std::fs::read_to_string(&path) else {
        return CreativeState::default();
    };
    match serde_json::from_str::<CreativeState>(&raw) {
        Ok(state) => state,
        Err(err) => {
            eprintln!("creativity: estado ilegible ({err}), se reinicia");
            CreativeState::default()
        }
    }
}

fn persist_state(state: &CreativeState) {
    let path = state_path();
    if let Some(parent) = path.parent() {
        if let Err(err) = std::fs::create_dir_all(parent) {
            eprintln!("creativity: no se pudo crear {}: {err}", parent.display());
            return;
        }
    }
    match serde_json::to_string_pretty(state) {
        Ok(body) => {
            if let Err(err) = std::fs::write(&path, body) {
                eprintln!("creativity: no se pudo escribir {}: {err}", path.display());
            }
        }
        Err(err) => eprintln!("creativity: no se pudo serializar: {err}"),
    }
}

/* ------------------------------------------------------------------ *
 * Generación de ideas
 * ------------------------------------------------------------------ */

/// Plantillas de ideas cuando no hay modelo disponible.
///
/// El laboratorio no puede quedarse mudo: sin Ollama (o con el modelo
/// devolviendo basura) sigue habiendo ideas; la diferencia con el modelo es
/// la calidad, no la existencia.
const IDEA_TEMPLATES: &[(&str, &str)] = &[
    (
        "Un resumen automático de {t} al final de cada sesión",
        "ARIA lee lo que pasó y deja un resumen corto, para no perder el hilo.",
    ),
    (
        "Una alerta cuando {t} se desvía de lo esperado",
        "Compara {t} contra su valor normal y avisa sólo cuando hay algo raro.",
    ),
    (
        "Un historial visual de {t}",
        "Guarda cada cambio de {t} con su fecha para poder comparar y volver atrás.",
    ),
    (
        "Un atajo de voz para {t}",
        "Un gesto o una frase corta que dispare {t} sin tocar el teclado.",
    ),
    (
        "Una skill que detecte el error repetido en {t}",
        "Guarda los fallos de {t} y avisa cuando el mismo error vuelve a pasar.",
    ),
    (
        "Un modo de prueba para {t} antes de aplicarlo",
        "Ensaya {t} en un entorno aparte y sólo lo aplica si el resultado convence.",
    ),
    (
        "Comparar {t} contra la semana anterior",
        "Un informe corto con la diferencia y qué la causó.",
    ),
    (
        "Documentar {t} con ejemplos que se ejecutan",
        "Cada capacidad de {t} documentada con un caso real y reproducible.",
    ),
];

/// Propuestas de mejora de ARIA cuando no hay modelo disponible.
const IMPROVEMENT_TEMPLATES: &[(&str, &str)] = &[
    (
        "Acordar las ideas aceptadas con la memoria de largo plazo",
        "Lo que ARIA acepta no debería volver a proponerlo en seis meses.",
    ),
    (
        "Conectar el laboratorio con el árbol de habilidades",
        "Cada skill forjada debería poder equiparse y cambiar cómo responde ARIA.",
    ),
    (
        "Dejar que la voz abra el laboratorio",
        "Pedir ideas por el auricular, sin teclado, como el resto del chat.",
    ),
    (
        "Revisar cada semana las ideas rechazadas",
        "El veredicto de ayer puede estar equivocado hoy: una relectura periódica.",
    ),
    (
        "Puntuar las ideas con dos modelos distintos",
        "Un modelo propone y otro califica: la diversidad encuentra mejores ideas.",
    ),
    (
        "Guardar el historial de veredictos por tema",
        "Saber qué temas agradan y cuáles no, con números y no con intuiciones.",
    ),
];

/// Soluciones de reserva cuando no hay modelo disponible.
///
/// Un problema siempre tiene un camino: aunque sea el de siempre. El
/// laboratorio no puede responder «no sé».
const SOLUTION_TEMPLATES: &[(&str, &str)] = &[
    (
        "Dividir el problema en partes verificables",
        "Cada parte con su propio criterio de éxito: lo que no se puede medir no se arregla.",
    ),
    (
        "Buscar la causa raíz antes de parchear",
        "Un ejemplo mínimo que reproduce el fallo suele explicar más que diez horas de lectura.",
    ),
    (
        "Escribir primero la prueba que falla",
        "La prueba manda: cuando pasa, el problema está resuelto y no hay forma de discutirlo.",
    ),
    (
        "Instrumentar y medir antes de cambiar",
        "Saber qué pasa es más barato que adivinarlo, y siempre es más rápido que rehacerlo.",
    ),
    (
        "Convertir el paso que más se repite en una skill",
        "Cada repetición manual es una invitación a que ARIA lo haga sola la próxima vez.",
    ),
    (
        "Acotar el problema a una sola sesión",
        "Lo que se resuelve hoy vale más que el plan perfecto que nunca se aplica.",
    ),
];

/// Resultado de una generación.
pub struct Generation {
    pub ideas: Vec<Idea>,
    /// De dónde salieron: `ollama:<modelo>` o `local`.
    pub engine: String,
}

/// Construye el prompt de ideas.
///
/// El prompt pide frases cortas a propósito: la máquina de ARIA no tiene GPU
/// y el modelo va a CPU, así que cada token de más son segundos de espera.
/// Además, un modelo con «max 25 palabras» por campo responde ideas
/// utilizables, no párrafos.
fn idea_prompt(
    topic: &str,
    theme: &str,
    count: usize,
    profile: &[ThemeProfile],
    context: &str,
) -> String {
    let liked: Vec<String> = profile
        .iter()
        .filter(|p| p.weight > 0.0)
        .map(|p| format!("{} ({:+.2})", p.theme, p.weight))
        .collect();
    let disliked: Vec<String> = profile
        .iter()
        .filter(|p| p.weight < 0.0)
        .map(|p| format!("{} ({:+.2})", p.theme, p.weight))
        .collect();

    format!(
        "Eres el laboratorio de ideas de ARIA.\n\
         Tema: {topic}\n\
         Categoría: {theme}\n\
         Propón {count} ideas nuevas, distintas de lo que ya existe.\n\
         Cada idea: un título de 8 palabras, un resumen de 20 palabras y un detalle de 25 \
         palabras con cómo se implementa y cómo se prueba.\n\
         Puntúa novelty, feasibility e impact de 0 a 1.\n\
         Contexto de ARIA: {context}\n\
         Le gusta: {liked}\n\
         No le gusta: {disliked}\n\
         Responde SOLO con JSON: \
         {{\"ideas\":[{{\"title\":\"...\",\"summary\":\"...\",\"detail\":\"...\",\"theme\":\"...\",\
         \"novelty\":0.0,\"feasibility\":0.0,\"impact\":0.0}}]}}",
        liked = if liked.is_empty() { "ninguno".to_string() } else { liked.join(", ") },
        disliked = if disliked.is_empty() { "ninguno".to_string() } else { disliked.join(", ") },
    )
}

/// Construye el prompt de mejora de ARIA.
fn improvement_prompt(focus: &str, count: usize, profile: &[ThemeProfile], context: &str) -> String {
    let liked: Vec<String> = profile
        .iter()
        .filter(|p| p.weight > 0.0)
        .map(|p| p.theme.clone())
        .collect();
    let focus_line = if focus.trim().is_empty() {
        String::new()
    } else {
        format!(" orientadas a: {}", focus.trim())
    };
    format!(
        "Eres ARIA revisando su propio sistema.\n\
         Propón {count} mejoras concretas para ARIA{focus_line}.\n\
         Cada mejora: un título de 8 palabras, un resumen de 20 palabras y un detalle de 25 \
         palabras con qué toca cambiar.\n\
         Puntúa novelty, feasibility e impact de 0 a 1.\n\
         Contexto de ARIA: {context}\n\
         Temas que el usuario valora: {liked}\n\
         Responde SOLO con JSON: \
         {{\"ideas\":[{{\"title\":\"...\",\"summary\":\"...\",\"detail\":\"...\",\"theme\":\"mejora\",\
         \"novelty\":0.0,\"feasibility\":0.0,\"impact\":0.0}}]}}",
        liked = if liked.is_empty() { "ninguno".to_string() } else { liked.join(", ") },
    )
}

/// Normaliza un número de puntuación que puede venir en 0..1 o en 0..10.
fn normalize_score(raw: Option<&Value>) -> f32 {
    let value = match raw {
        Some(Value::Number(n)) => n.as_f64().unwrap_or(0.0),
        Some(Value::String(s)) => s.parse::<f64>().unwrap_or(0.0),
        _ => 0.0,
    };
    let clamped = if value > 1.0 { value / 10.0 } else { value };
    clamped.clamp(0.0, 1.0) as f32
}

/// Convierte la respuesta del modelo en ideas.
pub fn parse_ideas(raw: &Value, topic: &str, theme: &str) -> Vec<Idea> {
    let array = raw
        .get("ideas")
        .and_then(|v| v.as_array())
        .or_else(|| raw.as_array());
    let Some(array) = array else {
        return Vec::new();
    };

    let mut ideas = Vec::new();
    for item in array.iter().take(MAX_COUNT) {
        let Some(object) = item.as_object() else {
            continue;
        };
        let title = object
            .get("title")
            .and_then(|v| v.as_str())
            .map(str::trim)
            .filter(|t| !t.is_empty())
            .unwrap_or_default();
        if title.is_empty() {
            continue;
        }
        let novelty = normalize_score(object.get("novelty"));
        let feasibility = normalize_score(object.get("feasibility"));
        let impact = normalize_score(object.get("impact"));
        let idea_theme = match object.get("theme").and_then(|v| v.as_str()) {
            Some(value) if !value.trim().is_empty() => CreativeState::normalize_theme(value),
            _ => CreativeState::normalize_theme(theme),
        };
        ideas.push(Idea {
            id: String::new(),
            title: title.to_string(),
            summary: object
                .get("summary")
                .and_then(|v| v.as_str())
                .unwrap_or_default()
                .trim()
                .to_string(),
            detail: object
                .get("detail")
                .and_then(|v| v.as_str())
                .unwrap_or_default()
                .trim()
                .to_string(),
            theme: idea_theme,
            origin: "idea".to_string(),
            novelty,
            feasibility,
            impact,
            score: score_of(novelty, feasibility, impact),
            status: "new".to_string(),
            note: None,
            created_at: now(),
            skill_id: None,
        });
    }

    if ideas.is_empty() {
        // El modelo respondió con algo irreconocible: mejor una idea
        // local que un laboratorio mudo.
        return local_ideas(topic, theme, 1);
    }
    ideas
}

/// Ideas de reserva cuando el modelo no está o no devuelve JSON válido.
pub fn local_ideas(topic: &str, theme: &str, count: usize) -> Vec<Idea> {
    let topic = if topic.trim().is_empty() { "ARIA" } else { topic.trim() };
    let mut ideas = Vec::new();
    for (index, (title, summary)) in IDEA_TEMPLATES.iter().enumerate() {
        if ideas.len() >= count.min(MAX_COUNT) {
            break;
        }
        let title = title.replace("{t}", topic);
        let summary = summary.replace("{t}", topic);
        let (novelty, feasibility, impact) = local_scores(&format!("{title}:{index}"));
        ideas.push(Idea {
            id: String::new(),
            title,
            summary,
            detail: String::new(),
            theme: CreativeState::normalize_theme(theme),
            origin: "idea".to_string(),
            novelty,
            feasibility,
            impact,
            score: score_of(novelty, feasibility, impact),
            status: "new".to_string(),
            note: None,
            created_at: now(),
            skill_id: None,
        });
    }
    ideas
}

/// Propuestas de mejora de reserva.
pub fn local_improvements(count: usize) -> Vec<Idea> {
    let mut ideas = Vec::new();
    for (index, (title, summary)) in IMPROVEMENT_TEMPLATES.iter().enumerate() {
        if ideas.len() >= count.min(MAX_COUNT) {
            break;
        }
        let (novelty, feasibility, impact) = local_scores(&format!("mejora:{title}:{index}"));
        ideas.push(Idea {
            id: String::new(),
            title: title.to_string(),
            summary: summary.to_string(),
            detail: String::new(),
            theme: "mejora".to_string(),
            origin: "mejora".to_string(),
            novelty,
            feasibility,
            impact,
            score: score_of(novelty, feasibility, impact),
            status: "new".to_string(),
            note: None,
            created_at: now(),
            skill_id: None,
        });
    }
    ideas
}

/// Soluciones de reserva para un problema concreto.
///
/// Se guardan como ideas con origen `solucion`: el veredicto del usuario
/// y la forja funcionan igual que con el resto de ideas.
pub fn local_solutions(problem: &str, count: usize) -> Vec<Idea> {
    let problem = if problem.trim().is_empty() {
        "el problema".to_string()
    } else {
        problem.trim().to_string()
    };
    let mut ideas = Vec::new();
    for (index, (title, summary)) in SOLUTION_TEMPLATES.iter().enumerate() {
        if ideas.len() >= count.min(MAX_COUNT) {
            break;
        }
        let (novelty, feasibility, impact) = local_scores(&format!("solucion:{problem}:{index}"));
        ideas.push(Idea {
            id: String::new(),
            title: title.to_string(),
            summary: summary.to_string(),
            detail: format!("Aplicado a: {problem}."),
            theme: "solucion".to_string(),
            origin: "solucion".to_string(),
            novelty,
            feasibility,
            impact,
            score: score_of(novelty, feasibility, impact),
            status: "new".to_string(),
            note: None,
            created_at: now(),
            skill_id: None,
        });
    }
    ideas
}

/// Puntuaciones deterministas para las ideas de reserva.
///
/// Deterministas a propósito: las mismas ideas tienen las mismas notas en
/// cada ejecución, y los tests pueden comprobarlo.
fn local_scores(seed: &str) -> (f32, f32, f32) {
    let hash = hash32(seed);
    let novelty = 0.30 + ((hash % 45) as f32) / 100.0;
    let feasibility = 0.35 + (((hash >> 8) % 45) as f32) / 100.0;
    let impact = 0.30 + (((hash >> 16) % 45) as f32) / 100.0;
    (novelty, feasibility, impact)
}

/// FNV-1a: hash barato y estable entre ejecuciones.
fn hash32(text: &str) -> u32 {
    let mut hash: u32 = 2166136261;
    for byte in text.as_bytes() {
        hash ^= *byte as u32;
        hash = hash.wrapping_mul(16777619);
    }
    hash
}

/// Contexto que se le pasa al modelo: quién es ARIA y qué tiene encima.
///
/// Va recortado: el prompt va al modelo entero y cada token de contexto es
/// tiempo de espera en una máquina sin GPU.
async fn aria_context() -> String {
    let equipped = crate::skill_tree::equipped_prompt().await;
    let mut context = if equipped.trim().is_empty() {
        "ARIA todavía no tiene clase elegida.".to_string()
    } else {
        equipped
    };
    // Las integraciones activas también son contexto: ARIA tiene que saber
    // qué herramientas tiene a mano antes de prometer nada.
    let integrations = integrations_prompt();
    if !integrations.trim().is_empty() {
        context.push_str("\n\n");
        context.push_str(&integrations);
    }
    let max = 400;
    if context.chars().count() <= max {
        return context;
    }
    let mut cut: String = context.chars().take(max).collect();
    cut.push('…');
    cut
}

/// Genera ideas sobre un tema.
pub async fn generate_ideas(topic: &str, theme: &str, count: usize) -> Generation {
    let count = count.clamp(1, MAX_COUNT);
    let profile = {
        let guard = creative().lock().await;
        guard.profile()
    };
    let context = aria_context().await;
    let prompt = idea_prompt(topic, theme, count, &profile, &context);

    let client = reqwest::Client::new();
    let model = crate::chat::resolve_model(&client, None).await;
    let parsed = crate::chat::call_ollama_json(&client, &prompt, &model).await;

    let (ideas, engine) = match parsed {
        Some(raw) => {
            let ideas = parse_ideas(&raw, topic, theme);
            if ideas.is_empty() {
                (local_ideas(topic, theme, count), "local".to_string())
            } else {
                (ideas, format!("ollama:{model}"))
            }
        }
        None => (local_ideas(topic, theme, count), "local".to_string()),
    };

    Generation { ideas, engine }
}

/// Genera propuestas de mejora de ARIA.
pub async fn generate_improvements(focus: &str, count: usize) -> Generation {
    let count = count.clamp(1, MAX_COUNT);
    let profile = {
        let guard = creative().lock().await;
        guard.profile()
    };
    let context = aria_context().await;
    let prompt = improvement_prompt(focus, count, &profile, &context);

    let client = reqwest::Client::new();
    let model = crate::chat::resolve_model(&client, None).await;
    let parsed = crate::chat::call_ollama_json(&client, &prompt, &model).await;

    let (ideas, engine) = match parsed {
        Some(raw) => {
            let mut ideas = parse_ideas(&raw, "mejora de ARIA", "mejora");
            for idea in ideas.iter_mut() {
                idea.origin = "mejora".to_string();
                idea.theme = "mejora".to_string();
            }
            if ideas.is_empty() {
                (local_improvements(count), "local".to_string())
            } else {
                (ideas, format!("ollama:{model}"))
            }
        }
        None => (local_improvements(count), "local".to_string()),
    };

    Generation { ideas, engine }
}

/// Construye el prompt para escribir una skill.
///
/// Se le da el objetivo tal cual lo escribió el usuario: la skill nace de
/// lo que la persona quiere, no de lo que ARIA suponer.
fn skill_prompt(goal: &str, theme: &str, context: &str) -> String {
    format!(
        "Eres el taller de skills de ARIA.\n\
         Objetivo de la skill: {goal}\n\
         Categoría: {theme}\n\
         Escribe una skill que ARIA pueda ejecutar cuando se la pida.\n\
         Responde SOLO con JSON: \
         {{\"name\":\"nombre_en_palabras_snake_case\",\"description\":\"una frase de 15 palabras\",\
         \"instruction\":\"las instrucciones paso a paso, 40 palabras\",\
         \"params\":[\"input\"]}}\n\
         Contexto de ARIA: {context}",
    )
}

/// Construye el prompt para resolver un problema.
///
/// Se pide lo que el usuario pidió: soluciones que se puedan aplicar, no
/// philosophy. Cada solución es una idea más: se acepta, se nota y se
/// forja como cualquier otra.
fn solution_prompt(problem: &str, count: usize, profile: &[ThemeProfile], context: &str) -> String {
    let liked: Vec<String> = profile
        .iter()
        .filter(|p| p.weight > 0.0)
        .map(|p| p.theme.clone())
        .collect();
    format!(
        "Eres el solucionador de ARIA.\n\
         Problema: {problem}\n\
         Propón {count} soluciones concretas para resolverlo.\n\
         Cada solución: un título de 8 palabras, un resumen de 20 palabras y un detalle de 25 \
         palabras con los pasos para aplicarla.\n\
         Puntúa novelty, feasibility e impact de 0 a 1.\n\
         Contexto de ARIA: {context}\n\
         Temas que el usuario valora: {liked}\n\
         Responde SOLO con JSON: \
         {{\"ideas\":[{{\"title\":\"...\",\"summary\":\"...\",\"detail\":\"...\",\"theme\":\"solucion\",\
         \"novelty\":0.0,\"feasibility\":0.0,\"impact\":0.0}}]}}",
        liked = if liked.is_empty() { "ninguno".to_string() } else { liked.join(", ") },
    )
}

/// Escribe una skill a partir de lo que el usuario pide.
///
/// Si el modelo no está, la skill se escribe aquí: una skill es una
/// instrucción, y una instrucción honesta vale más que un error.
pub async fn compose_skill(goal: &str, name_hint: Option<&str>, theme: &str) -> GeneratedSkill {
    let context = aria_context().await;
    let client = reqwest::Client::new();
    let model = crate::chat::resolve_model(&client, None).await;
    let prompt = skill_prompt(goal, theme, &context);
    let parsed = crate::chat::call_ollama_json(&client, &prompt, &model).await;

    let (name, description, instruction) = match parsed {
        Some(raw) => {
            let name = raw
                .get("name")
                .and_then(|v| v.as_str())
                .map(str::trim)
                .filter(|value| !value.is_empty())
                .map(slugify)
                .unwrap_or_default();
            let description = raw
                .get("description")
                .and_then(|v| v.as_str())
                .unwrap_or_default()
                .trim()
                .to_string();
            let instruction = raw
                .get("instruction")
                .and_then(|v| v.as_str())
                .unwrap_or_default()
                .trim()
                .to_string();
            (name, description, instruction)
        }
        None => (String::new(), String::new(), String::new()),
    };

    let name = if name.is_empty() {
        name_hint
            .map(slugify)
            .filter(|value| !value.is_empty())
            .unwrap_or_else(|| slugify(goal))
    } else {
        name
    };
    let description = if description.is_empty() {
        format!("Skill para: {}", goal.trim())
    } else {
        description
    };
    let instruction = if instruction.is_empty() {
        format!(
            "Realiza esta tarea: {}. Antes de responder, comprueba que la información sea \
             suficiente; si no lo es, dilo y pregunta lo que falte.",
            goal.trim()
        )
    } else {
        instruction
    };

    GeneratedSkill {
        id: String::new(),
        name,
        description,
        instruction,
        theme: CreativeState::normalize_theme(theme),
        params: vec!["input".to_string()],
        source_idea: None,
        created_at: String::new(),
        runs: 0,
        revisions: 0,
    }
}

/// Propone soluciones para un problema concreto.
pub async fn generate_solutions(problem: &str, theme: &str, count: usize) -> Generation {
    let count = count.clamp(1, MAX_COUNT);
    let profile = {
        let guard = creative().lock().await;
        guard.profile()
    };
    let context = aria_context().await;
    let prompt = solution_prompt(problem, count, &profile, &context);

    let client = reqwest::Client::new();
    let model = crate::chat::resolve_model(&client, None).await;
    let parsed = crate::chat::call_ollama_json(&client, &prompt, &model).await;

    let theme = CreativeState::normalize_theme(theme);
    let (ideas, engine) = match parsed {
        Some(raw) => {
            let mut ideas = parse_ideas(&raw, problem, &theme);
            for idea in ideas.iter_mut() {
                idea.origin = "solucion".to_string();
                if idea.theme == "general" {
                    idea.theme = theme.clone();
                }
            }
            if ideas.is_empty() {
                (local_solutions(problem, count), "local".to_string())
            } else {
                (ideas, format!("ollama:{model}"))
            }
        }
        None => (local_solutions(problem, count), "local".to_string()),
    };

    Generation { ideas, engine }
}

/// Reescribe las instrucciones de una skill para mejorarla.
///
/// A diferencia de `compose_skill`, aquí no hay red de seguridad: si el
/// modelo no responde, se dice que no. Una «mejora» inventada ensuciaría
/// la skill.
pub async fn improve_skill(id: &str) -> Result<GeneratedSkill, String> {
    let skill = {
        let guard = creative().lock().await;
        guard.find_skill(id).cloned()
    };
    let Some(skill) = skill else {
        return Err(format!("Skill desconocida: {id}"));
    };

    let profile = {
        let guard = creative().lock().await;
        guard.profile()
    };
    let liked: Vec<String> = profile
        .iter()
        .filter(|entry| entry.weight > 0.0)
        .map(|entry| entry.theme.clone())
        .collect();

    let prompt = format!(
        "Eres ARIA improving una skill que ella misma escribió.\n\
         Nombre: {name}\n\
         Qué hace: {description}\n\
         Instrucciones actuales: {instruction}\n\
         Temas que el usuario valora: {liked}\n\
         Reescribe las instrucciones para que la skill funcione mejor: más concreta, con \
         pasos verificables y con lo que hay que devolver.\n\
         Responde SOLO con JSON: \
         {{\"description\":\"una frase de 15 palabras\",\"instruction\":\"las instrucciones nuevas, \
         50 palabras\"}}",
        name = skill.name,
        description = skill.description,
        instruction = skill.instruction,
        liked = if liked.is_empty() { "ninguno".to_string() } else { liked.join(", ") },
    );

    let client = reqwest::Client::new();
    let model = crate::chat::resolve_model(&client, None).await;
    let Some(raw) = crate::chat::call_ollama_json(&client, &prompt, &model).await else {
        return Err(
            "El modelo no está disponible ahora mismo: no se puede mejorar la skill sin él."
                .to_string(),
        );
    };
    let instruction = raw
        .get("instruction")
        .and_then(|v| v.as_str())
        .unwrap_or_default()
        .trim()
        .to_string();
    if instruction.is_empty() {
        return Err("El modelo no propuso instrucciones nuevas para la skill.".to_string());
    }
    let description = raw
        .get("description")
        .and_then(|v| v.as_str())
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(String::from);

    let mut guard = creative().lock().await;
    let updated = guard.apply_skill_revision(id, instruction, description)?;
    guard.bump_theme(&updated.theme, USAGE_DELTA);
    guard.updated_at = now();
    persist_state(&guard);
    Ok(updated)
}

/// Guarda ideas en el estado y persiste.
async fn store_ideas(ideas: Vec<Idea>, engine: &str) -> Vec<Idea> {
    let mut guard = creative().lock().await;
    let mut stored = Vec::new();
    for idea in ideas {
        stored.push(guard.push_idea(idea));
    }
    guard.cycles += 1;
    guard.last_engine = engine.to_string();
    guard.updated_at = now();
    persist_state(&guard);
    stored
}

/* ------------------------------------------------------------------ *
 * Integración con las demás piezas
 * ------------------------------------------------------------------ */

/// Resumen (nombre, descripción) de las skills indicadas.
///
/// Lo usa el árbol de habilidades para meter en el prompt del chat las
/// skills que ARIA se ha forjado y ha equipado.
pub fn generated_summaries(ids: &[String]) -> Vec<(String, String)> {
    let guard = match creative().try_lock() {
        Ok(guard) => guard,
        // Si el laboratorio está ocupado, se responde sin las skills
        // generadas en vez de bloquear el chat entero.
        Err(_) => return Vec::new(),
    };
    ids.iter()
        .filter_map(|id| {
            guard
                .find_skill(id)
                .map(|skill| (skill.name.clone(), skill.description.clone()))
        })
        .collect()
}

/// ¿Existe una skill forjada con ese id?
pub fn skill_exists(id: &str) -> bool {
    match creative().try_lock() {
        Ok(guard) => guard.find_skill(id).is_some(),
        Err(_) => false,
    }
}

/// Catálogo de skills forjadas, con la marca de equipada.
pub async fn skill_catalog() -> Vec<Value> {
    // Primero el árbol (que suelta el cerrojo antes de devolver) y después
    // el laboratorio: nunca se toma un cerrojo teniendo el otro.
    let equipped = crate::skill_tree::generated_equipped().await;
    let guard = creative().lock().await;
    guard
        .skills
        .iter()
        .map(|skill| {
            json!({
                "id": skill.id,
                "name": skill.name,
                "description": skill.description,
                "theme": skill.theme,
                "runs": skill.runs,
                "created_at": skill.created_at,
                "source_idea": skill.source_idea,
                "equipped": equipped.contains(&skill.id),
                "status": "generated",
            })
        })
        .collect()
}

/// Catálogo de integraciones registradas.
pub async fn integration_catalog() -> Vec<Value> {
    let guard = creative().lock().await;
    guard
        .integrations
        .iter()
        .map(|integration| {
            json!({
                "id": integration.id,
                "name": integration.name,
                "kind": integration.kind,
                "target": integration.target,
                "description": integration.description,
                "enabled": integration.enabled,
                "created_at": integration.created_at,
                "calls": integration.calls,
            })
        })
        .collect()
}

/// Las integraciones activas, escritas para el prompt.
///
/// Es el puente entre «integrar cosas nuevas» y «ARIA usándolas»: lo que
/// está aquí es lo que el modelo sabe que tiene a mano.
pub fn integrations_prompt() -> String {
    let guard = match creative().try_lock() {
        Ok(guard) => guard,
        Err(_) => return String::new(),
    };
    format_integrations_prompt(&guard.enabled_integrations())
}

/// Escribe las integraciones para el prompt.
///
/// Función aparte para poder probarla sin tocar el estado global: lo que
/// importa es qué ve el modelo, no dónde vive la lista.
pub fn format_integrations_prompt(integrations: &[Integration]) -> String {
    if integrations.is_empty() {
        return String::new();
    }
    let mut lines = vec!["Integraciones activas de ARIA:".to_string()];
    for integration in integrations {
        lines.push(format!(
            "- {} ({}) en {}: {}",
            integration.name, integration.kind, integration.target, integration.description
        ));
    }
    lines.join("\n")
}

/// Ejecuta una skill forjada.
///
/// La skill es una instrucción escrita por ARIA: el modelo la ejecuta con la
/// entrada que le da el usuario.
pub async fn run_generated_skill(id: &str, input: &str) -> Result<(String, u64), String> {
    let skill = {
        let guard = creative().lock().await;
        guard.find_skill(id).cloned()
    };
    let Some(skill) = skill else {
        return Err(format!("Skill desconocida: {id}"));
    };

    let prompt = format!(
        "Eres ARIA ejecutando una skill que tú misma escribiste.\n\
         Nombre: {name}\n\
         Objetivo: {description}\n\
         Instrucciones: {instruction}\n\
         Entrada: {input}\n\
         Responde con el resultado de la skill, sin explicar la skill.",
        name = skill.name,
        description = skill.description,
        instruction = skill.instruction,
        input = if input.trim().is_empty() { "(sin entrada)" } else { input.trim() },
    );

    let client = reqwest::Client::new();
    let model = crate::chat::resolve_model(&client, None).await;
    let output = crate::chat::call_ollama(&client, &prompt, &model).await;
    if output.starts_with("[ARIA-Axum]") {
        return Err(output);
    }

    {
        let mut guard = creative().lock().await;
        if let Some(entry) = guard.skills.iter_mut().find(|s| s.id == id) {
            entry.runs += 1;
        }
        // Usar una skill enseña: su tema pesa un poco más, así que ARIA
        // propondrá más cosas de ese tipo.
        guard.bump_theme(&skill.theme, USAGE_DELTA);
        guard.updated_at = now();
        persist_state(&guard);
    }

    // Usar una skill que ARIA se escribió cuenta como auto-mejora: el árbol
    // de habilidades lo sabe (`command: "self-improvement"`).
    let xp = crate::skill_tree::award_skill_usage("self-improvement").await;
    Ok((output, xp))
}

/* ------------------------------------------------------------------ *
 * Handlers
 * ------------------------------------------------------------------ */

pub fn router() -> Router<()> {
    Router::new()
        .route("/api/creativity/state", get(get_state))
        .route("/api/creativity/profile", get(get_profile))
        .route("/api/creativity/ideas", post(post_ideas))
        .route("/api/creativity/ideas/:id/feedback", post(post_feedback))
        .route("/api/creativity/ideas/:id/forge", post(post_forge))
        .route("/api/creativity/improve", post(post_improve))
        .route("/api/creativity/solve", post(post_solve))
        .route("/api/creativity/skills", get(get_skills).post(post_create_skill))
        .route("/api/creativity/skills/:id/run", post(post_run_skill))
        .route("/api/creativity/skills/:id/equip", post(post_equip_skill))
        .route("/api/creativity/skills/:id/improve", post(post_improve_skill))
        .route(
            "/api/creativity/integrations",
            get(get_integrations).post(post_register_integration),
        )
        .route(
            "/api/creativity/integrations/:id/toggle",
            post(post_toggle_integration),
        )
        .route(
            "/api/creativity/integrations/:id/probe",
            post(post_probe_integration),
        )
}

#[derive(Deserialize)]
struct GenerateRequest {
    #[serde(default)]
    prompt: String,
    #[serde(default)]
    theme: Option<String>,
    #[serde(default)]
    count: Option<usize>,
}

#[derive(Deserialize)]
struct FeedbackRequest {
    #[serde(default)]
    verdict: String,
    #[serde(default)]
    note: Option<String>,
}

#[derive(Deserialize)]
struct RunRequest {
    #[serde(default)]
    input: String,
}

#[derive(Deserialize)]
struct EquipRequest {
    #[serde(default)]
    equipped: Option<bool>,
}

/// `POST /api/creativity/skills` — crear una skill sin pasar por una idea.
#[derive(Deserialize)]
struct CreateSkillRequest {
    /// Nombre que propone el usuario (opcional: ARIA lo pone).
    #[serde(default)]
    name: Option<String>,
    /// Qué tiene que hacer la skill.
    #[serde(default)]
    goal: String,
    /// Instrucciones escritas a mano (opcional: ARIA las escribe).
    #[serde(default)]
    instruction: Option<String>,
    #[serde(default)]
    theme: Option<String>,
}

/// `POST /api/creativity/integrations` — registrar una capacidad externa.
#[derive(Deserialize)]
struct IntegrationRequest {
    #[serde(default)]
    name: String,
    #[serde(default)]
    kind: Option<String>,
    #[serde(default)]
    target: String,
    #[serde(default)]
    description: Option<String>,
    #[serde(default)]
    enabled: Option<bool>,
}

/// `POST /api/creativity/integrations/:id/toggle` — activar o desactivar.
#[derive(Deserialize)]
struct ToggleRequest {
    #[serde(default)]
    enabled: Option<bool>,
}

/// `GET /api/creativity/state` — ideas ordenadas, skills y perfil aprendido.
async fn get_state(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
) -> Json<serde_json::Value> {
    {
        let guard = state.lock().await;
        guard.increment_requests().await;
    }

    let equipped = crate::skill_tree::generated_equipped().await;
    let guard = creative().lock().await;

    let ideas: Vec<Value> = guard
        .ranked()
        .iter()
        .map(|idea| {
            json!({
                "id": idea.id,
                "title": idea.title,
                "summary": idea.summary,
                "detail": idea.detail,
                "theme": idea.theme,
                "origin": idea.origin,
                "novelty": idea.novelty,
                "feasibility": idea.feasibility,
                "impact": idea.impact,
                "score": guard.effective_score(idea),
                "raw_score": idea.score,
                "status": idea.status,
                "note": idea.note,
                "created_at": idea.created_at,
                "skill_id": idea.skill_id,
            })
        })
        .collect();

    let skills: Vec<Value> = guard
        .skills
        .iter()
        .map(|skill| {
            json!({
                "id": skill.id,
                "name": skill.name,
                "description": skill.description,
                "instruction": skill.instruction,
                "theme": skill.theme,
                "params": skill.params,
                "source_idea": skill.source_idea,
                "created_at": skill.created_at,
                "runs": skill.runs,
                "revisions": skill.revisions,
                "equipped": equipped.contains(&skill.id),
            })
        })
        .collect();

    let integrations: Vec<Value> = guard
        .integrations
        .iter()
        .map(|integration| {
            json!({
                "id": integration.id,
                "name": integration.name,
                "kind": integration.kind,
                "target": integration.target,
                "description": integration.description,
                "enabled": integration.enabled,
                "created_at": integration.created_at,
                "calls": integration.calls,
            })
        })
        .collect();

    let profile: Vec<Value> = guard
        .profile()
        .iter()
        .map(|entry| json!({ "theme": entry.theme, "weight": entry.weight }))
        .collect();

    Json(json!({
        "status": "ok",
        "ideas": ideas,
        "skills": skills,
        "integrations": integrations,
        "profile": profile,
        "stats": {
            "ideas": guard.ideas.len(),
            "accepted": guard.accepted,
            "rejected": guard.rejected,
            "built": guard.built,
            "cycles": guard.cycles,
            "integrations": guard.integrations.len(),
            "active_integrations": guard.enabled_integrations().len(),
        },
        "last_engine": guard.last_engine,
        "max_generated_equipped": MAX_GENERATED_EQUIPPED,
        "server": "ARIA-Axum-8002",
    }))
}

/// `GET /api/creativity/profile` — sólo lo aprendido.
async fn get_profile() -> Json<serde_json::Value> {
    let guard = creative().lock().await;
    let profile: Vec<Value> = guard
        .profile()
        .iter()
        .map(|entry| json!({ "theme": entry.theme, "weight": entry.weight }))
        .collect();
    Json(json!({
        "status": "ok",
        "profile": profile,
        "stats": {
            "ideas": guard.ideas.len(),
            "accepted": guard.accepted,
            "rejected": guard.rejected,
            "built": guard.built,
            "cycles": guard.cycles,
        },
        "server": "ARIA-Axum-8002",
    }))
}

/// `POST /api/creativity/ideas` — pide ideas nuevas.
async fn post_ideas(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<GenerateRequest>,
) -> Json<serde_json::Value> {
    {
        let guard = state.lock().await;
        guard.increment_requests().await;
    }

    let topic = req.prompt.trim();
    if topic.is_empty() {
        return Json(json!({
            "status": "error",
            "error": "Falta 'prompt': ¿sobre qué quieres ideas?",
        }));
    }
    let theme = CreativeState::normalize_theme(req.theme.as_deref().unwrap_or(topic));
    let count = req.count.unwrap_or(DEFAULT_COUNT);

    let generation = generate_ideas(topic, &theme, count).await;
    let stored = store_ideas(generation.ideas, &generation.engine).await;

    Json(json!({
        "status": "ok",
        "ideas": stored,
        "count": stored.len(),
        "engine": generation.engine,
        "server": "ARIA-Axum-8002",
    }))
}

/// `POST /api/creativity/improve` — ARIA propone mejoras de sí misma.
async fn post_improve(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<GenerateRequest>,
) -> Json<serde_json::Value> {
    {
        let guard = state.lock().await;
        guard.increment_requests().await;
    }

    let focus = req.prompt.trim();
    let count = req.count.unwrap_or(DEFAULT_COUNT);
    let generation = generate_improvements(focus, count).await;
    let stored = store_ideas(generation.ideas, &generation.engine).await;

    Json(json!({
        "status": "ok",
        "ideas": stored,
        "count": stored.len(),
        "engine": generation.engine,
        "server": "ARIA-Axum-8002",
    }))
}

/// `POST /api/creativity/solve` — soluciones para un problema concreto.
///
/// Las soluciones se guardan como ideas: el usuario las juzga con el mismo
/// «me gusta / no / mejórala» y las puede forjar en una skill.
async fn post_solve(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<GenerateRequest>,
) -> Json<serde_json::Value> {
    {
        let guard = state.lock().await;
        guard.increment_requests().await;
    }

    let problem = req.prompt.trim();
    if problem.is_empty() {
        return Json(json!({
            "status": "error",
            "error": "Falta 'prompt': ¿qué problema hay que resolver?",
        }));
    }
    let theme = req
        .theme
        .as_deref()
        .map(CreativeState::normalize_theme)
        .unwrap_or_else(|| "solucion".to_string());
    let count = req.count.unwrap_or(DEFAULT_COUNT);

    let generation = generate_solutions(problem, &theme, count).await;
    let stored = store_ideas(generation.ideas, &generation.engine).await;

    Json(json!({
        "status": "ok",
        "ideas": stored,
        "count": stored.len(),
        "engine": generation.engine,
        "server": "ARIA-Axum-8002",
    }))
}

/// `POST /api/creativity/skills` — crea una skill nueva.
///
/// Camino corto: se dice qué quieres que ARIA sepa hacer y queda escrita,
/// equipable y ejecutable. Si el usuario trae las instrucciones, se usan
/// tal cual.
async fn post_create_skill(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<CreateSkillRequest>,
) -> Json<serde_json::Value> {
    {
        let guard = state.lock().await;
        guard.increment_requests().await;
    }

    let goal = req.goal.trim();
    if goal.is_empty() {
        return Json(json!({
            "status": "error",
            "error": "Falta 'goal': ¿qué debe hacer la skill?",
        }));
    }
    let theme = req
        .theme
        .as_deref()
        .map(CreativeState::normalize_theme)
        .unwrap_or_else(|| "general".to_string());

    let mut skill = if let Some(instruction) = req.instruction.as_deref().map(str::trim) {
        if instruction.is_empty() {
            compose_skill(goal, req.name.as_deref(), &theme).await
        } else {
            GeneratedSkill {
                id: String::new(),
                name: req
                    .name
                    .as_deref()
                    .map(slugify)
                    .filter(|value| !value.is_empty())
                    .unwrap_or_else(|| slugify(goal)),
                description: format!("Skill para: {goal}"),
                instruction: instruction.to_string(),
                theme: theme.clone(),
                params: vec!["input".to_string()],
                source_idea: None,
                created_at: String::new(),
                runs: 0,
                revisions: 0,
            }
        }
    } else {
        compose_skill(goal, req.name.as_deref(), &theme).await
    };

    if !skill.theme.is_empty() {
        skill.theme = theme.clone();
    }

    let mut guard = creative().lock().await;
    let stored = guard.add_skill(skill);
    guard.updated_at = now();
    persist_state(&guard);

    Json(json!({
        "status": "ok",
        "skill": stored,
        "server": "ARIA-Axum-8002",
    }))
}

/// `POST /api/creativity/skills/:id/improve` — ARIA reescribe su propia skill.
async fn post_improve_skill(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Path(id): Path<String>,
) -> Json<serde_json::Value> {
    {
        let guard = state.lock().await;
        guard.increment_requests().await;
    }

    match improve_skill(&id).await {
        Ok(skill) => Json(json!({
            "status": "ok",
            "skill": skill,
            "server": "ARIA-Axum-8002",
        })),
        Err(error) => Json(json!({ "status": "error", "error": error })),
    }
}

/// `GET /api/creativity/integrations` — integraciones registradas.
async fn get_integrations(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
) -> Json<serde_json::Value> {
    {
        let guard = state.lock().await;
        guard.increment_requests().await;
    }
    let integrations = integration_catalog().await;
    Json(json!({
        "status": "ok",
        "integrations": integrations,
        "count": integrations.len(),
        "server": "ARIA-Axum-8002",
    }))
}

/// `POST /api/creativity/integrations` — registra una capacidad externa.
async fn post_register_integration(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Json(req): Json<IntegrationRequest>,
) -> Json<serde_json::Value> {
    {
        let guard = state.lock().await;
        guard.increment_requests().await;
    }

    let integration = Integration {
        id: String::new(),
        name: req.name.trim().to_string(),
        kind: req.kind.clone().unwrap_or_default(),
        target: req.target.trim().to_string(),
        description: req.description.clone().unwrap_or_default(),
        enabled: req.enabled.unwrap_or(true),
        created_at: String::new(),
        calls: 0,
    };

    let mut guard = creative().lock().await;
    match guard.push_integration(integration) {
        Ok(stored) => {
            guard.updated_at = now();
            persist_state(&guard);
            let integrations = guard
                .integrations
                .iter()
                .map(|integration| {
                    json!({
                        "id": integration.id,
                        "name": integration.name,
                        "kind": integration.kind,
                        "target": integration.target,
                        "description": integration.description,
                        "enabled": integration.enabled,
                        "created_at": integration.created_at,
                        "calls": integration.calls,
                    })
                })
                .collect::<Vec<Value>>();
            Json(json!({
                "status": "ok",
                "integration": stored,
                "integrations": integrations,
                "server": "ARIA-Axum-8002",
            }))
        }
        Err(error) => Json(json!({ "status": "error", "error": error })),
    }
}

/// `POST /api/creativity/integrations/:id/toggle` — activa o desactiva.
async fn post_toggle_integration(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Path(id): Path<String>,
    Json(req): Json<ToggleRequest>,
) -> Json<serde_json::Value> {
    {
        let guard = state.lock().await;
        guard.increment_requests().await;
    }

    let enabled = req.enabled.unwrap_or(true);
    let mut guard = creative().lock().await;
    match guard.toggle_integration(&id, enabled) {
        Ok(integration) => {
            guard.updated_at = now();
            persist_state(&guard);
            Json(json!({
                "status": "ok",
                "integration": integration,
                "server": "ARIA-Axum-8002",
            }))
        }
        Err(error) => Json(json!({ "status": "error", "error": error })),
    }
}

/// `POST /api/creativity/integrations/:id/probe` — comprueba que la integración responde.
///
/// Sólo se prueban servicios HTTP: un `GET` con tiempo límite. Un comando
/// local no se ejecuta desde aquí —eso lo hacen las skills— para no abrir
/// una puerta a ejecutar lo que sea.
async fn post_probe_integration(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Path(id): Path<String>,
) -> Json<serde_json::Value> {
    {
        let guard = state.lock().await;
        guard.increment_requests().await;
    }

    let integration = {
        let guard = creative().lock().await;
        guard.find_integration(&id).cloned()
    };
    let Some(integration) = integration else {
        return Json(json!({
            "status": "error",
            "error": format!("Integración desconocida: {id}"),
        }));
    };

    let target = integration.target.trim();
    if !(target.starts_with("http://") || target.starts_with("https://")) {
        return Json(json!({
            "status": "error",
            "error": "Sólo se pueden probar servicios HTTP (http:// o https://).",
        }));
    }

    let client = reqwest::Client::new();
    let probe = client
        .get(target)
        .timeout(std::time::Duration::from_secs(15))
        .send()
        .await;

    let (http_status, body) = match probe {
        Ok(response) => {
            let status = response.status().as_u16();
            let text = response.text().await.unwrap_or_default();
            let trimmed: String = text.chars().take(600).collect();
            (Some(status), trimmed)
        }
        Err(error) => (None, error.to_string()),
    };

    {
        let mut guard = creative().lock().await;
        if let Some(entry) = guard.integrations.iter_mut().find(|entry| entry.id == id) {
            entry.calls += 1;
        }
        guard.updated_at = now();
        persist_state(&guard);
    }

    if let Some(status) = http_status {
        Json(json!({
            "status": "ok",
            "integration": integration.name,
            "http_status": status,
            "body": body,
            "server": "ARIA-Axum-8002",
        }))
    } else {
        Json(json!({
            "status": "error",
            "integration": integration.name,
            "error": body,
            "server": "ARIA-Axum-8002",
        }))
    }
}

/// `POST /api/creativity/ideas/:id/feedback` — veredicto del usuario.
async fn post_feedback(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Path(id): Path<String>,
    Json(req): Json<FeedbackRequest>,
) -> Json<serde_json::Value> {
    {
        let guard = state.lock().await;
        guard.increment_requests().await;
    }

    let Some(verdict) = Verdict::parse(&req.verdict) else {
        return Json(json!({
            "status": "error",
            "error": "Veredicto desconocido: usa 'accept', 'reject' o 'improve'",
        }));
    };

    let mut guard = creative().lock().await;
    match guard.apply_verdict(&id, verdict, req.note.clone()) {
        Ok(idea) => {
            guard.updated_at = now();
            persist_state(&guard);
            let profile: Vec<Value> = guard
                .profile()
                .iter()
                .map(|entry| json!({ "theme": entry.theme, "weight": entry.weight }))
                .collect();
            Json(json!({
                "status": "ok",
                "idea": idea,
                "profile": profile,
                "server": "ARIA-Axum-8002",
            }))
        }
        Err(error) => Json(json!({ "status": "error", "error": error })),
    }
}

/// `POST /api/creativity/ideas/:id/forge` — convierte una idea en skill.
async fn post_forge(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Path(id): Path<String>,
) -> Json<serde_json::Value> {
    {
        let guard = state.lock().await;
        guard.increment_requests().await;
    }

    let mut guard = creative().lock().await;
    match guard.forge(&id) {
        Ok(skill) => {
            guard.updated_at = now();
            persist_state(&guard);
            Json(json!({
                "status": "ok",
                "skill": skill,
                "server": "ARIA-Axum-8002",
            }))
        }
        Err(error) => Json(json!({ "status": "error", "error": error })),
    }
}

/// `GET /api/creativity/skills` — skills forjadas.
async fn get_skills(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
) -> Json<serde_json::Value> {
    {
        let guard = state.lock().await;
        guard.increment_requests().await;
    }
    let skills = skill_catalog().await;
    Json(json!({
        "status": "ok",
        "skills": skills,
        "count": skills.len(),
        "server": "ARIA-Axum-8002",
    }))
}

/// `POST /api/creativity/skills/:id/run` — ejecuta una skill forjada.
async fn post_run_skill(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Path(id): Path<String>,
    Json(req): Json<RunRequest>,
) -> Json<serde_json::Value> {
    {
        let guard = state.lock().await;
        guard.increment_requests().await;
    }

    match run_generated_skill(&id, &req.input).await {
        Ok((output, xp)) => Json(json!({
            "status": "ok",
            "output": output,
            "xp_gained": xp,
            "server": "ARIA-Axum-8002",
        })),
        Err(error) => Json(json!({ "status": "error", "error": error })),
    }
}

/// `POST /api/creativity/skills/:id/equip` — equipa o desequipa una skill.
async fn post_equip_skill(
    Extension(state): Extension<Arc<Mutex<SharedState>>>,
    Path(id): Path<String>,
    Json(req): Json<EquipRequest>,
) -> Json<serde_json::Value> {
    {
        let guard = state.lock().await;
        guard.increment_requests().await;
    }

    let equipped = req.equipped.unwrap_or(true);
    match crate::skill_tree::equip_generated_skill(&id, equipped).await {
        Ok(()) => {
            let skills = skill_catalog().await;
            Json(json!({
                "status": "ok",
                "equipped": id,
                "skills": skills,
                "server": "ARIA-Axum-8002",
            }))
        }
        Err(error) => Json(json!({ "status": "error", "error": error })),
    }
}

/* ------------------------------------------------------------------ *
 * Tests
 * ------------------------------------------------------------------ */

#[cfg(test)]
mod tests {
    use super::*;

    fn idea(title: &str, theme: &str, score: f32) -> Idea {
        Idea {
            id: "idea_001".to_string(),
            title: title.to_string(),
            summary: String::new(),
            detail: String::new(),
            theme: theme.to_string(),
            origin: "idea".to_string(),
            novelty: score,
            feasibility: score,
            impact: score,
            score,
            status: "new".to_string(),
            note: None,
            created_at: String::new(),
            skill_id: None,
        }
    }

    #[test]
    fn verdicts_are_parsed_in_spanish_and_english() {
        assert_eq!(Verdict::parse("accept"), Some(Verdict::Accept));
        assert_eq!(Verdict::parse("Aceptar"), Some(Verdict::Accept));
        assert_eq!(Verdict::parse("me gusta"), Some(Verdict::Accept));
        assert_eq!(Verdict::parse("reject"), Some(Verdict::Reject));
        assert_eq!(Verdict::parse("no"), Some(Verdict::Reject));
        assert_eq!(Verdict::parse("improve"), Some(Verdict::Improve));
        assert_eq!(Verdict::parse("mejorar"), Some(Verdict::Improve));
        assert_eq!(Verdict::parse("tal cual"), None);
    }

    #[test]
    fn accepting_an_idea_raises_the_weight_of_its_theme() {
        let mut state = CreativeState::default();
        state.push_idea(idea("Idea de voz", "voz", 0.5));
        let id = state.ideas[0].id.clone();
        state.apply_verdict(&id, Verdict::Accept, None).expect("veredicto válido");
        assert!(state.theme_weight("voz") > 0.0);
        assert_eq!(state.accepted, 1);
        assert_eq!(state.ideas[0].status, "accepted");
    }

    #[test]
    fn rejecting_an_idea_lowers_the_weight_and_counts() {
        let mut state = CreativeState::default();
        state.push_idea(idea("Idea de voz", "voz", 0.5));
        let id = state.ideas[0].id.clone();
        state.apply_verdict(&id, Verdict::Reject, None).expect("veredicto válido");
        assert!(state.theme_weight("voz") < 0.0);
        assert_eq!(state.rejected, 1);
        assert_eq!(state.ideas[0].status, "rejected");
    }

    #[test]
    fn the_learned_weight_never_runs_away() {
        let mut state = CreativeState::default();
        state.push_idea(idea("Idea de voz", "voz", 0.5));
        let id = state.ideas[0].id.clone();
        for _ in 0..20 {
            state.apply_verdict(&id, Verdict::Accept, None).expect("veredicto válido");
        }
        assert!(state.theme_weight("voz") <= MAX_THEME_WEIGHT);
        assert!(state.theme_weight("voz") > 0.9);
    }

    #[test]
    fn the_learned_weight_breaks_the_tie_between_ideas() {
        let mut state = CreativeState::default();
        let mut liked = idea("Preferida", "voz", 0.60);
        liked.id = "idea_001".to_string();
        let mut other = idea(" neutra", "memoria", 0.60);
        other.id = "idea_002".to_string();
        state.ideas.push(liked);
        state.ideas.push(other);
        state.weights.insert("voz".to_string(), 0.8);

        let ranked = state.ranked();
        assert_eq!(ranked[0].title, "Preferida", "el tema aprendido manda");
    }

    #[test]
    fn a_note_is_kept_when_the_idea_is_improved() {
        let mut state = CreativeState::default();
        state.push_idea(idea("Idea", "voz", 0.5));
        let id = state.ideas[0].id.clone();
        state
            .apply_verdict(&id, Verdict::Improve, Some("falta la voz".to_string()))
            .expect("veredicto válido");
        assert_eq!(state.ideas[0].note.as_deref(), Some("falta la voz"));
        assert_eq!(state.ideas[0].status, "refining");
    }

    #[test]
    fn an_unknown_idea_is_reported() {
        let mut state = CreativeState::default();
        assert!(state.apply_verdict("idea_999", Verdict::Accept, None).is_err());
    }

    #[test]
    fn forging_an_idea_creates_a_skill_and_marks_the_idea() {
        let mut state = CreativeState::default();
        let mut source = idea("Resumir la sesión", "memoria", 0.8);
        source.summary = "resume lo que pasó".to_string();
        source.detail = "lee la memoria y devuelve un resumen".to_string();
        state.push_idea(source);
        let id = state.ideas[0].id.clone();

        let skill = state.forge(&id).expect("forja posible");
        assert_eq!(skill.name, "resumir_la_sesion");
        assert!(skill.instruction.contains("memoria"));
        assert_eq!(state.built, 1);
        assert_eq!(state.ideas[0].status, "built");
        assert_eq!(state.ideas[0].skill_id.as_deref(), Some(skill.id.as_str()));
    }

    #[test]
    fn an_idea_cannot_be_forged_twice() {
        let mut state = CreativeState::default();
        state.push_idea(idea("Idea", "voz", 0.5));
        let id = state.ideas[0].id.clone();
        state.forge(&id).expect("primera forja");
        assert!(state.forge(&id).is_err(), "segunda forja");
    }

    #[test]
    fn slugs_are_stable_and_safe() {
        assert_eq!(slugify("Resumir la sesión"), "resumir_la_sesion");
        assert_eq!(slugify("  ¿Qué hora es?  "), "que_hora_es");
        assert_eq!(slugify(""), "skill_sin_nombre");
    }

    #[test]
    fn themes_are_normalized() {
        assert_eq!(CreativeState::normalize_theme("  Voz "), "voz");
        assert_eq!(CreativeState::normalize_theme("Skill Tree"), "skill-tree");
        assert_eq!(CreativeState::normalize_theme("   "), "general");
    }

    #[test]
    fn the_model_answer_becomes_ideas() {
        let raw = serde_json::json!({
            "ideas": [
                {
                    "title": "Voz continua",
                    "summary": "hablar sin parar",
                    "detail": "el STT no corta la frase",
                    "theme": "voz",
                    "novelty": 0.8,
                    "feasibility": 0.6,
                    "impact": 0.7
                }
            ]
        });
        let ideas = parse_ideas(&raw, "voz", "voz");
        assert_eq!(ideas.len(), 1);
        assert_eq!(ideas[0].title, "Voz continua");
        assert_eq!(ideas[0].theme, "voz");
        assert!((ideas[0].score - score_of(0.8, 0.6, 0.7)).abs() < 0.0001);
    }

    #[test]
    fn scores_on_a_ten_point_scale_are_normalized() {
        let raw = serde_json::json!({
            "ideas": [{
                "title": "Idea",
                "novelty": 8.0,
                "feasibility": 10.0,
                "impact": 5.0
            }]
        });
        let ideas = parse_ideas(&raw, "x", "x");
        assert!((ideas[0].novelty - 0.8).abs() < 0.0001);
        assert!((ideas[0].feasibility - 1.0).abs() < 0.0001);
        assert!((ideas[0].impact - 0.5).abs() < 0.0001);
    }

    #[test]
    fn a_broken_answer_falls_back_to_local_ideas() {
        let raw = serde_json::json!({ "ideas": [] });
        let ideas = parse_ideas(&raw, "voz", "voz");
        assert_eq!(ideas.len(), 1, "hay al menos una idea de reserva");
        assert!(!ideas[0].title.is_empty());
    }

    #[test]
    fn local_ideas_are_deterministic() {
        let first = local_ideas("voz", "voz", 3);
        let second = local_ideas("voz", "voz", 3);
        assert_eq!(first.len(), 3);
        assert_eq!(first[0].title, second[0].title);
        assert_eq!(first[0].score, second[0].score);
    }

    #[test]
    fn local_ideas_use_the_topic() {
        let ideas = local_ideas("la cámara", "vision", 2);
        assert!(ideas[0].title.contains("la cámara"), "{}", ideas[0].title);
        assert_eq!(ideas[0].theme, "vision");
    }

    #[test]
    fn improvements_are_about_aria() {
        let ideas = local_improvements(3);
        assert_eq!(ideas.len(), 3);
        assert!(ideas.iter().all(|idea| idea.theme == "mejora"));
        assert!(ideas.iter().all(|idea| idea.origin == "mejora"));
    }

    #[test]
    fn the_idea_cap_keeps_the_lab_bounded() {
        let mut state = CreativeState::default();
        for index in 0..(MAX_IDEAS + 5) {
            state.push_idea(idea(&format!("Idea {index}"), "general", 0.5));
        }
        assert_eq!(state.ideas.len(), MAX_IDEAS);
    }

    fn skill(name: &str) -> GeneratedSkill {
        GeneratedSkill {
            id: String::new(),
            name: name.to_string(),
            description: "hace cosas".to_string(),
            instruction: "hazlo".to_string(),
            theme: "general".to_string(),
            params: vec!["input".to_string()],
            source_idea: None,
            created_at: String::new(),
            runs: 0,
            revisions: 0,
        }
    }

    fn integration(name: &str) -> Integration {
        Integration {
            id: String::new(),
            name: name.to_string(),
            kind: "herramienta".to_string(),
            target: format!("/usr/bin/{name}"),
            description: format!("usa {name}"),
            enabled: true,
            created_at: String::new(),
            calls: 0,
        }
    }

    #[test]
    fn a_skill_can_be_created_without_passing_through_an_idea() {
        let mut state = CreativeState::default();
        let stored = state.add_skill(skill("mirar_el_clima"));
        assert_eq!(stored.id, "gen_001");
        assert_eq!(state.skills.len(), 1);
        assert_eq!(state.built, 1);
        assert!(state.find_skill("gen_001").is_some());
    }

    #[test]
    fn a_skill_revision_rewrites_the_instruction() {
        let mut state = CreativeState::default();
        state.add_skill(skill("resumir"));
        let updated = state
            .apply_skill_revision("gen_001", "resume en tres pasos".to_string(), None)
            .expect("revisión posible");
        assert_eq!(updated.instruction, "resume en tres pasos");
        assert_eq!(updated.revisions, 1);
    }

    #[test]
    fn revising_an_unknown_skill_is_reported() {
        let mut state = CreativeState::default();
        assert!(state
            .apply_skill_revision("gen_999", "nada".to_string(), None)
            .is_err());
    }

    #[test]
    fn an_integration_is_registered_with_an_id() {
        let mut state = CreativeState::default();
        let stored = state.push_integration(integration("nmap")).expect("alta válida");
        assert_eq!(stored.id, "int_001");
        assert_eq!(state.integrations.len(), 1);
        assert!(state.enabled_integrations().len() == 1);
    }

    #[test]
    fn the_same_integration_cannot_be_registered_twice() {
        let mut state = CreativeState::default();
        state.push_integration(integration("nmap")).expect("alta válida");
        assert!(state.push_integration(integration("Nmap")).is_err());
        assert_eq!(state.integrations.len(), 1);
    }

    #[test]
    fn an_integration_without_name_is_rejected() {
        let mut state = CreativeState::default();
        assert!(state.push_integration(integration("  ")).is_err());
    }

    #[test]
    fn an_integration_can_be_switched_off_and_on() {
        let mut state = CreativeState::default();
        let stored = state.push_integration(integration("nmap")).expect("alta válida");
        state
            .toggle_integration(&stored.id, false)
            .expect("se puede desactivar");
        assert!(state.enabled_integrations().is_empty());
        state.toggle_integration(&stored.id, true).expect("se puede activar");
        assert_eq!(state.enabled_integrations().len(), 1);
    }

    #[test]
    fn toggling_an_unknown_integration_is_reported() {
        let mut state = CreativeState::default();
        assert!(state.toggle_integration("int_999", true).is_err());
    }

    #[test]
    fn only_active_integrations_reach_the_prompt() {
        let mut state = CreativeState::default();
        let nmap = state.push_integration(integration("nmap")).expect("alta válida");
        state.push_integration(integration("discord")).expect("alta válida");
        state.toggle_integration(&nmap.id, false).expect("se desactiva");

        let prompt = format_integrations_prompt(&state.enabled_integrations());
        assert!(!prompt.contains("nmap"), "{prompt}");
        assert!(prompt.contains("discord"), "{prompt}");
        assert!(prompt.contains("Integraciones activas de ARIA"), "{prompt}");
    }

    #[test]
    fn without_integrations_the_prompt_is_empty() {
        assert!(format_integrations_prompt(&[]).is_empty());
    }

    #[test]
    fn solutions_are_ideas_with_their_own_origin() {
        let ideas = local_solutions("la cámara no arranca", 3);
        assert_eq!(ideas.len(), 3);
        assert!(ideas.iter().all(|idea| idea.origin == "solucion"));
        assert!(ideas.iter().all(|idea| idea.theme == "solucion"));
        assert!(ideas[0].detail.contains("la cámara no arranca"));
    }

    #[test]
    fn local_solutions_are_deterministic() {
        let first = local_solutions("problema", 2);
        let second = local_solutions("problema", 2);
        assert_eq!(first[0].title, second[0].title);
        assert_eq!(first[0].score, second[0].score);
    }
}
