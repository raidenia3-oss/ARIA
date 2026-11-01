//! Percepción: el mundo tal y como ARIA lo ve ahora.
//!
//! ## De dónde sale el diseño
//!
//! Neuro-sama no decide leyendo un chat. El juego le manda lo que pasa por
//! pantalla, un modelo de visión lo convierte en texto estructurado, y
//! *eso* es lo que entra al modelo. Sin esa capa, el modelo decide a ciegas
//! y se inventa el contexto.
//!
//! Airi resuelve el mismo problema separando "Stage" (dónde se ve) de
//! "Core" (quién es): el core es uno y los escenarios son muchos.
//!
//! Aquí la percepción es exactamente eso: un agregador que junta en un
//! único sitio lo que ARIA puede saber de este momento — los mundos
//! conectados y su estado, la audiencia que la está esperando, las skills
//! que puede usar, sus pulsiones, su presencia, su agenda y lo que ha
//! aprendido. El runtime lee de ahí antes de decidir, y la UI puede leer
//! lo mismo para explicar qué está viendo ARIA.

use axum::{routing::get, Json, Router};
use serde::Serialize;
use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::time::{SystemTime, UNIX_EPOCH};

use crate::affect::AffectState;
use crate::autonomy::{Initiative, Persona, Presence, SkillOption, WorldEvent};
use crate::lessons::Lesson;
use crate::social_live::SocialPrompt;

/* ------------------------------------------------------------------ *
 * Tipos
 * ------------------------------------------------------------------ */

/// Lo que ARIA ve de un mundo.
#[derive(Debug, Clone, Serialize)]
pub struct WorldPerception {
    pub id: String,
    pub label: String,
    pub kind: String,
    pub connected: bool,
    pub status: String,
    /// Qué sabe hacer ese mundo.
    pub capabilities: Vec<String>,
    /// Lo que el mundo acaba de publicar de sí mismo.
    pub context: Value,
    /// Cuántos segundos lleva el mundo sin publicar nada.
    pub context_age_secs: u64,
    /// Acciones que esperan a que un puente las recoja.
    pub pending: usize,
}

/// Vista completa de lo que ARIA percibe en este momento.
#[derive(Debug, Clone, Serialize)]
pub struct PerceptionSnapshot {
    /// Epoch en segundos.
    pub at: u64,
    /// Los mundos que ve.
    pub worlds: Vec<WorldPerception>,
    /// Alguien en un canal social esperando respuesta.
    pub audience: Option<SocialPrompt>,
    /// Las skills que puede usar.
    pub skills: Vec<SkillOption>,
    /// Sus pulsiones.
    pub drives: BTreeMap<String, f32>,
    /// Dónde está y qué cara pone.
    pub presence: Presence,
    /// Cómo está de ánimo.
    pub affect: AffectState,
    /// Lo último que ha pasado, de más reciente a más antiguo.
    pub events: Vec<WorldEvent>,
    /// Lo que tiene entre manos.
    pub agenda: Vec<Initiative>,
    /// Lo que ha aprendido.
    pub lessons: Vec<Lesson>,
    /// Quién es.
    pub persona: Persona,
}

fn now_secs() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

/* ------------------------------------------------------------------ *
 * Construcción
 * ------------------------------------------------------------------ */

/// Toma la foto de lo que ARIA perceives ahora.
///
/// Es una lectura, no una decisión: no toca nada y no bloquea al runtime.
pub async fn snapshot() -> PerceptionSnapshot {
    let view = crate::autonomy::view().await;
    let worlds = crate::world::views().await;
    let now = now_secs();

    let worlds: Vec<WorldPerception> = worlds
        .into_iter()
        .map(|world| WorldPerception {
            context_age_secs: now.saturating_sub(world.context_at),
            id: world.id,
            label: world.label,
            kind: world.kind,
            connected: world.connected,
            status: world.status,
            capabilities: world.capabilities,
            context: world.context,
            pending: world.pending,
        })
        .collect();

    let skills: Vec<SkillOption> = crate::creativity::skill_catalog()
        .await
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

    PerceptionSnapshot {
        at: now,
        worlds,
        audience: crate::social_live::pending_prompt().await,
        skills,
        drives: view.drives,
        presence: view.presence,
        affect: crate::affect::snapshot().await,
        events: view.events,
        agenda: view.agenda,
        lessons: crate::lessons::top(crate::lessons::PROMPT_LESSONS).await,
        persona: view.persona,
    }
}

/* ------------------------------------------------------------------ *
 * Texto para el prompt
 * ------------------------------------------------------------------ */

/// El bloque "ahora mismo" que entra en el prompt de decisión.
///
/// Se construye a partir de la instantánea interna del runtime (la misma
/// que usa para decidir), para no abrir un segundo cerrojo a mitad del
/// tick.
pub fn render(
    worlds: &[crate::world::WorldView],
    audience: &Option<SocialPrompt>,
    agenda: &[Initiative],
    lessons: &[Lesson],
    events: &[WorldEvent],
    now: u64,
) -> String {
    let mut out = String::new();

    /* ── Dónde está y qué hay alrededor ─────────────────────────── */
    if !worlds.is_empty() {
        out.push_str("Mundos donde puedes estar:\n");
        for world in worlds {
            out.push_str(&format!(
                "- {} ({}): {}\n",
                world.label,
                world.kind,
                if world.connected { "conectado" } else { "sin conectar" }
            ));
            if !world.capabilities.is_empty() {
                out.push_str(&format!("  puede: {}\n", world.capabilities.join(", ")));
            }
            // El estado real del mundo: esto es lo que Neuro-sama recibe del
            // juego antes de decidir. Sin esto, decide a ciegas.
            let context = world.context.to_string();
            let context = context.trim();
            if !context.is_empty() && context != "{}" && context != "null" {
                out.push_str(&format!("  ahora: {context}\n"));
            }
        }
    } else {
        out.push_str("Mundos donde puedes estar: (ninguno)\n");
    }

    /* ── La audiencia ───────────────────────────────────────────── */
    match audience {
        Some(prompt) => {
            out.push_str(&format!(
                "\nEn el canal {} ({}), {} ha dicho: \"{}\"\n",
                prompt.channel, prompt.kind, prompt.author, prompt.text
            ));
        }
        None => out.push_str("\nNadie te está esperando ahora mismo.\n"),
    }

    /* ── Lo que tiene entre manos ───────────────────────────────── */
    let pending: Vec<&Initiative> = agenda
        .iter()
        .filter(|initiative| initiative.state == "pendiente")
        .collect();
    if !pending.is_empty() {
        out.push_str("\nLo que tienes entre manos:\n");
        for initiative in pending.iter().take(3) {
            out.push_str(&format!(
                "- {} (por qué: {})\n",
                initiative.goal, initiative.reason
            ));
        }
    }

    /* ── Lo último que ha pasado ────────────────────────────────── */
    let recent: Vec<&WorldEvent> = events.iter().rev().take(6).rev().collect();
    if !recent.is_empty() {
        out.push_str("\nLo último que ha pasado:\n");
        for event in recent {
            out.push_str(&format!(
                "- [{}] {}: {}\n",
                event.kind, event.source, event.text
            ));
        }
    }

    /* ── Lo que ha aprendido ────────────────────────────────────── */
    out.push('\n');
    out.push_str(&crate::lessons::prompt(lessons));
    let _ = now;

    out.trim_end().to_string()
}

/* ------------------------------------------------------------------ *
 * Rutas
 * ------------------------------------------------------------------ */

pub fn router() -> Router<()> {
    Router::new().route("/api/perception", get(view))
}

async fn view() -> Json<Value> {
    let snapshot = snapshot().await;
    Json(json!({
        "status": "ok",
        "perception": snapshot,
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

    fn world(id: &str, connected: bool, context: Value) -> crate::world::WorldView {
        crate::world::WorldView {
            id: id.to_string(),
            kind: "juego".to_string(),
            label: id.to_string(),
            connected,
            status: if connected { "conectado" } else { "sin conectar" }.to_string(),
            capabilities: vec!["move".to_string(), "say".to_string()],
            context,
            context_at: 0,
            pending: 0,
        }
    }

    #[test]
    fn el_texto_de_percepcion_muestra_el_estado_del_mundo() {
        let worlds = vec![world(
            "minecraft",
            true,
            json!({"inventario": "pico de diamante", "salud": 18}),
        )];
        let text = render(&worlds, &None, &[], &[], &[], 0);
        assert!(text.contains("minecraft"));
        assert!(text.contains("pico de diamante"));
        assert!(text.contains("puede: move, say"));
    }

    #[test]
    fn sin_mundos_el_texto_lo_dice() {
        let text = render(&[], &None, &[], &[], &[], 0);
        assert!(text.contains("(ninguno)"));
    }

    #[test]
    fn la_audiencia_gana_a_los_mundos() {
        let worlds = vec![world("minecraft", true, json!({}))];
        let audience = Some(SocialPrompt {
            channel: "discord:general".to_string(),
            kind: "mensaje".to_string(),
            author: "user".to_string(),
            text: "hola".to_string(),
            at: 0,
        });
        let text = render(&worlds, &audience, &[], &[], &[], 0);
        assert!(text.contains("discord:general"));
        assert!(text.contains("user ha dicho"));
    }
}
