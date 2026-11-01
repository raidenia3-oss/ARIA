//! Árbol de habilidades de ARIA — progresión tipo videojuego.
//!
//! El árbol no es decorativo: cada nodo es una capacidad real de ARIA y cada
//! uso real de esa capacidad devuelve XP. Desbloquear un nodo cuesta puntos
//! de habilidad, exige prerrequisitos ya desbloqueados y, al hacerlo,
//! registra la habilidad como *equipada* para que los agentes la propongan
//! primero.
//!
//! Modelo de progresión:
//!   - `xp` global sube al usar nodos desbloqueados.
//!   - `level` se deriva del XP acumulado con una curva cuadrática.
//!   - Cada nivel da 1 punto de habilidad (+ el bonus de clase inicial).
//!   - Los nodos *activos* se equipan (máx. 3 a la vez); los *pasivos* no.
//!
//! Persistencia: JSON en el directorio de estado por usuario, el mismo que usa
//! `control` para su config, para que el progreso sobreviva a reinicios y no
//! dependa del cwd desde el que se lanzó el servidor.

use axum::{
    routing::{get, post},
    Json, Router,
};
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::collections::{BTreeMap, BTreeSet};
use std::path::PathBuf;
use std::sync::OnceLock;

/// Nombre del archivo de estado dentro del directorio de estado.
const SKILL_TREE_FILE: &str = "skill_tree.json";
/// Override del directorio donde vive el estado del árbol.
const SKILL_TREE_STATE_DIR_ENV: &str = "ARIA_SKILL_TREE_STATE_DIR";
/// Máximo de habilidades activas equipadas a la vez.
pub const MAX_EQUIPPED: usize = 3;
/// Puntos de habilidad que se ganan por cada nivel alcanzado.
pub const POINTS_PER_LEVEL: u32 = 3;

/* ------------------------------------------------------------------ *
 * Catálogo
 * ------------------------------------------------------------------ */

/// Si el nodo se equipa (habilidad activa) o si es pasivo (siempre activo
/// mientras esté desbloqueado).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum NodeKind {
    Passive,
    Active,
}

/// Un nodo del árbol: una capacidad de ARIA con su coste y sus prerrequisitos.
#[derive(Debug, Clone, Copy)]
pub struct SkillNode {
    pub id: &'static str,
    pub name: &'static str,
    pub description: &'static str,
    pub branch: &'static str,
    /// Columna del grafo (1 = raíz). El layout del renderer usa esto como X.
    pub tier: u8,
    /// Fila dentro de la columna. El layout del renderer usa esto como Y.
    pub slot: u8,
    /// Puntos de habilidad para desbloquear.
    pub cost: u32,
    /// Ids que deben estar desbloqueados antes que éste.
    pub requires: &'static [&'static str],
    pub icon: &'static str,
    pub kind: NodeKind,
    /// Skill real del backend que este nodo represents.
    pub command: &'static str,
    /// XP que otorga al desbloquearlo.
    pub xp_reward: u64,
}

/// Ramas del árbol. La clave es el identificador de rama.
pub const BRANCHES: &[(&str, &str, &str, &str)] = &[
    ("nucleo", "Núcleo", "La mente de ARIA: inferencia, contexto y diálogo.", "#38bdf8"),
    ("percepcion", "Percepción", "Ojo, oído y cuerpo: cámara, voz y gestos.", "#f472b6"),
    ("autonomia", "Autonomía", "ARIA trabajando sola mientras tú no estás.", "#a78bfa"),
    ("conocimiento", "Conocimiento", "Memoria, wiki y aprendizaje que no se borran.", "#34d399"),
    ("guardian", "Guardián", "Protección del sistema, de tus datos y de ti.", "#fb923c"),
];

/// Catálogo completo del árbol.
///
/// El orden de声明 es el orden de lectura del renderer: el grafo se dibuja
/// rama por rama, de la raíz a la cima.
pub const NODES: &[SkillNode] = &[
    /* ── Núcleo ─────────────────────────────────────────────────────── */
    SkillNode {
        id: "chat",
        name: "Diálogo",
        description: "Conversación completa con el modelo local.",
        branch: "nucleo",
        tier: 1,
        slot: 0,
        cost: 0,
        requires: &[],
        icon: "💬",
        kind: NodeKind::Passive,
        command: "chat",
        xp_reward: 10,
    },
    SkillNode {
        id: "inferencia",
        name: "Inferencia Local",
        description: "Ejecuta modelos en tu máquina, sin nube.",
        branch: "nucleo",
        tier: 2,
        slot: 0,
        cost: 1,
        requires: &["chat"],
        icon: "🧠",
        kind: NodeKind::Passive,
        command: "chat",
        xp_reward: 20,
    },
    SkillNode {
        id: "streaming",
        name: "Flujo Continuo",
        description: "Respuestas token a token, sin esperar al final.",
        branch: "nucleo",
        tier: 2,
        slot: 1,
        cost: 1,
        requires: &["chat"],
        icon: "🌊",
        kind: NodeKind::Passive,
        command: "chat",
        xp_reward: 20,
    },
    SkillNode {
        id: "contexto",
        name: "Memoria de Contexto",
        description: "Mantiene el hilo de una sesión larga sin perderlo.",
        branch: "nucleo",
        tier: 3,
        slot: 0,
        cost: 2,
        requires: &["inferencia"],
        icon: "🧩",
        kind: NodeKind::Passive,
        command: "chat",
        xp_reward: 40,
    },
    SkillNode {
        id: "orquestacion",
        name: "Orquestación",
        description: "Reparte cada tarea al modelo más adecuado.",
        branch: "nucleo",
        tier: 4,
        slot: 0,
        cost: 3,
        requires: &["contexto"],
        icon: "🎼",
        kind: NodeKind::Active,
        command: "chat",
        xp_reward: 60,
    },
    SkillNode {
        id: "autoreflexion",
        name: "Autorreferencia",
        description: "ARIA relee su propio trabajo y lo mejora.",
        branch: "nucleo",
        tier: 5,
        slot: 0,
        cost: 5,
        requires: &["orquestacion"],
        icon: "🔁",
        kind: NodeKind::Active,
        command: "self-improvement",
        xp_reward: 120,
    },
    /* ── Percepción ─────────────────────────────────────────────────── */
    SkillNode {
        id: "microfono",
        name: "Oído",
        description: "Escucha por el micrófono del sistema.",
        branch: "percepcion",
        tier: 1,
        slot: 0,
        cost: 0,
        requires: &[],
        icon: "🎤",
        kind: NodeKind::Passive,
        command: "voice",
        xp_reward: 10,
    },
    SkillNode {
        id: "auricular",
        name: "Auricular con Micro",
        description: "Detecta audífonos con micrófono y los usa como canal principal.",
        branch: "percepcion",
        tier: 2,
        slot: 0,
        cost: 1,
        requires: &["microfono"],
        icon: "🎧",
        kind: NodeKind::Passive,
        command: "voice",
        xp_reward: 25,
    },
    SkillNode {
        id: "voz_tts",
        name: "Voz Propia",
        description: "ARIA habla con su propia voz en vez de imprimir texto.",
        branch: "percepcion",
        tier: 2,
        slot: 1,
        cost: 1,
        requires: &["microfono"],
        icon: "🔊",
        kind: NodeKind::Active,
        command: "voice",
        xp_reward: 25,
    },
    SkillNode {
        id: "camara",
        name: "Ojo de Cámara",
        description: "Captura de vídeo en tiempo real.",
        branch: "percepcion",
        tier: 1,
        slot: 1,
        cost: 0,
        requires: &[],
        icon: "📷",
        kind: NodeKind::Passive,
        command: "vision",
        xp_reward: 10,
    },
    SkillNode {
        id: "gestos",
        name: "Lectura de Gestos",
        description: "Interpreta manos: puño, índice, paz, palma, pulgar.",
        branch: "percepcion",
        tier: 3,
        slot: 0,
        cost: 2,
        requires: &["camara"],
        icon: "🖐️",
        kind: NodeKind::Active,
        command: "gestures",
        xp_reward: 45,
    },
    SkillNode {
        id: "identidad",
        name: "Verificar Identidad",
        description: "Reconoce tu rostro antes de obedecer una orden sensible.",
        branch: "percepcion",
        tier: 4,
        slot: 0,
        cost: 3,
        requires: &["gestos"],
        icon: "🔐",
        kind: NodeKind::Passive,
        command: "identity",
        xp_reward: 70,
    },
    SkillNode {
        id: "vision_pantalla",
        name: "Visión de Pantalla",
        description: "Lee lo que hay en tu pantalla y lo entiende.",
        branch: "percepcion",
        tier: 2,
        slot: 2,
        cost: 1,
        requires: &["camara"],
        icon: "🖥️",
        kind: NodeKind::Passive,
        command: "vision",
        xp_reward: 25,
    },
    SkillNode {
        id: "vision_pro",
        name: "Percepción Pro",
        description: "Fusiona cámara, voz y pantalla en un mismo instante.",
        branch: "percepcion",
        tier: 4,
        slot: 1,
        cost: 4,
        requires: &["vision_pantalla", "voz_tts"],
        icon: "🌟",
        kind: NodeKind::Active,
        command: "vision",
        xp_reward: 90,
    },
    /* ── Autonomía ──────────────────────────────────────────────────── */
    SkillNode {
        id: "daemon",
        name: "Daemon Persistente",
        description: "ARIA sigue viva aunque cierres la ventana.",
        branch: "autonomia",
        tier: 1,
        slot: 0,
        cost: 0,
        requires: &[],
        icon: "🛡️",
        kind: NodeKind::Passive,
        command: "daemon",
        xp_reward: 10,
    },
    SkillNode {
        id: "heartbeat",
        name: "Latido",
        description: "ARIA sabe que sigues ahí y te espera.",
        branch: "autonomia",
        tier: 2,
        slot: 0,
        cost: 1,
        requires: &["daemon"],
        icon: "💓",
        kind: NodeKind::Passive,
        command: "daemon",
        xp_reward: 20,
    },
    SkillNode {
        id: "bots_fondo",
        name: "Bots en Segundo Plano",
        description: "Tareas en paralelo mientras tú haces otra cosa.",
        branch: "autonomia",
        tier: 3,
        slot: 0,
        cost: 3,
        requires: &["daemon"],
        icon: "🤖",
        kind: NodeKind::Active,
        command: "self-improvement",
        xp_reward: 50,
    },
    SkillNode {
        id: "proactividad",
        name: "Proactividad",
        description: "ARIA propone antes de que se lo pidas.",
        branch: "autonomia",
        tier: 3,
        slot: 1,
        cost: 2,
        requires: &["heartbeat"],
        icon: "💡",
        kind: NodeKind::Passive,
        command: "proactive",
        xp_reward: 45,
    },
    SkillNode {
        id: "usb_aria",
        name: "Puente USB-ARIA",
        description: "Habla con el hardware conectado por USB.",
        branch: "autonomia",
        tier: 2,
        slot: 1,
        cost: 1,
        requires: &["daemon"],
        icon: "🔌",
        kind: NodeKind::Passive,
        command: "daemon",
        xp_reward: 20,
    },
    SkillNode {
        id: "auto_mejora",
        name: "Auto-mejora",
        description: "Cada error se convierte en una regla permanente.",
        branch: "autonomia",
        tier: 4,
        slot: 0,
        cost: 4,
        requires: &["bots_fondo"],
        icon: "🧬",
        kind: NodeKind::Passive,
        command: "self-improvement",
        xp_reward: 80,
    },
    SkillNode {
        id: "enjambre",
        name: "Enjambre",
        description: "Varios agentes coordinados en el mismo problema.",
        branch: "autonomia",
        tier: 5,
        slot: 0,
        cost: 6,
        requires: &["auto_mejora", "proactividad"],
        icon: "🐝",
        kind: NodeKind::Active,
        command: "agents",
        xp_reward: 150,
    },
    /* ── Conocimiento ───────────────────────────────────────────────── */
    SkillNode {
        id: "memoria_corto",
        name: "Memoria de Sesión",
        description: "Lo que acaba de pasar, todavía caliente.",
        branch: "conocimiento",
        tier: 1,
        slot: 0,
        cost: 0,
        requires: &[],
        icon: "📝",
        kind: NodeKind::Passive,
        command: "memory",
        xp_reward: 10,
    },
    SkillNode {
        id: "memoria_largo",
        name: "Memoria de Largo Plazo",
        description: "Recuerdos que sobreviven a los reinicios.",
        branch: "conocimiento",
        tier: 2,
        slot: 0,
        cost: 1,
        requires: &["memoria_corto"],
        icon: "🗄️",
        kind: NodeKind::Passive,
        command: "memory",
        xp_reward: 20,
    },
    SkillNode {
        id: "mnemosyne",
        name: "Mnemosyne",
        description: "Buffer instantáneo, sin dependencias externas.",
        branch: "conocimiento",
        tier: 2,
        slot: 2,
        cost: 1,
        requires: &["memoria_corto"],
        icon: "🧠",
        kind: NodeKind::Passive,
        command: "memory",
        xp_reward: 30,
    },
    SkillNode {
        id: "hindsight",
        name: "Hindsight",
        description: "Reflexiona sobre lo que hizo y aprende de ello.",
        branch: "conocimiento",
        tier: 3,
        slot: 1,
        cost: 2,
        requires: &["mnemosyne"],
        icon: "🔮",
        kind: NodeKind::Active,
        command: "memory",
        xp_reward: 45,
    },
    SkillNode {
        id: "wiki",
        name: "Obsidian Wiki",
        description: "Conocimiento permanente escrito en Markdown.",
        branch: "conocimiento",
        tier: 2,
        slot: 1,
        cost: 1,
        requires: &["memoria_corto"],
        icon: "📚",
        kind: NodeKind::Passive,
        command: "memory",
        xp_reward: 25,
    },
    SkillNode {
        id: "rag",
        name: "Recuperación Vectorial",
        description: "Busca por significado, no por palabra exacta.",
        branch: "conocimiento",
        tier: 3,
        slot: 0,
        cost: 2,
        requires: &["memoria_largo"],
        icon: "🔎",
        kind: NodeKind::Passive,
        command: "memory",
        xp_reward: 40,
    },
    SkillNode {
        id: "aprendizaje",
        name: "Aprendizaje Compuesto",
        description: "Cada lección compone la siguiente.",
        branch: "conocimiento",
        tier: 4,
        slot: 1,
        cost: 3,
        requires: &["wiki"],
        icon: "🌱",
        kind: NodeKind::Passive,
        command: "learning",
        xp_reward: 65,
    },
    SkillNode {
        id: "busqueda_global",
        name: "Búsqueda Global",
        description: "Un solo gesto alcanza a toda la memoria de ARIA.",
        branch: "conocimiento",
        tier: 4,
        slot: 0,
        cost: 4,
        requires: &["rag", "hindsight"],
        icon: "🛰️",
        kind: NodeKind::Active,
        command: "memory",
        xp_reward: 80,
    },
    SkillNode {
        id: "sintesis",
        name: "Síntesis",
        description: "Convierte todo lo aprendido en una sola respuesta.",
        branch: "conocimiento",
        tier: 5,
        slot: 0,
        cost: 6,
        requires: &["busqueda_global", "aprendizaje"],
        icon: "⚗️",
        kind: NodeKind::Active,
        command: "learning",
        xp_reward: 150,
    },
    /* ── Guardián ───────────────────────────────────────────────────── */
    SkillNode {
        id: "process_guard",
        name: "Guardián de Procesos",
        description: "ARIA nunca cierra las ventanas que tú abriste.",
        branch: "guardian",
        tier: 1,
        slot: 0,
        cost: 0,
        requires: &[],
        icon: "🚧",
        kind: NodeKind::Passive,
        command: "system",
        xp_reward: 10,
    },
    SkillNode {
        id: "filtro_shell",
        name: "Filtro de Comandos",
        description: "Filtra lo que ARIA ejecuta en tu equipo.",
        branch: "guardian",
        tier: 2,
        slot: 0,
        cost: 1,
        requires: &["process_guard"],
        icon: "🧱",
        kind: NodeKind::Passive,
        command: "system",
        xp_reward: 20,
    },
    SkillNode {
        id: "boveda",
        name: "Bóveda de Secretos",
        description: "Credenciales fuera del código y fuera del chat.",
        branch: "guardian",
        tier: 2,
        slot: 1,
        cost: 1,
        requires: &["process_guard"],
        icon: "🗝️",
        kind: NodeKind::Passive,
        command: "system",
        xp_reward: 20,
    },
    SkillNode {
        id: "stealth",
        name: "Modo Oculto",
        description: "ARIA trabaja sin dejar rastro visible.",
        branch: "guardian",
        tier: 3,
        slot: 0,
        cost: 2,
        requires: &["boveda"],
        icon: "🌫️",
        kind: NodeKind::Active,
        command: "system",
        xp_reward: 45,
    },
    SkillNode {
        id: "red_guard",
        name: "Guardián de Red",
        description: "Vigila las salidas de ARIA a internet.",
        branch: "guardian",
        tier: 3,
        slot: 1,
        cost: 2,
        requires: &["boveda"],
        icon: "🕸️",
        kind: NodeKind::Passive,
        command: "system",
        xp_reward: 45,
    },
    SkillNode {
        id: "sandbox",
        name: "Sandbox",
        description: "Todo lo dudoso se ejecuta aislado.",
        branch: "guardian",
        tier: 4,
        slot: 0,
        cost: 3,
        requires: &["filtro_shell"],
        icon: "🧿",
        kind: NodeKind::Active,
        command: "sandbox",
        xp_reward: 70,
    },
    SkillNode {
        id: "ciber_guardia",
        name: "Cyber Guardia",
        description: "Todo a la vez: red, procesos, bóveda y aislamiento.",
        branch: "guardian",
        tier: 5,
        slot: 0,
        cost: 6,
        requires: &["stealth", "sandbox"],
        icon: "🛡️",
        kind: NodeKind::Active,
        command: "system",
        xp_reward: 150,
    },
];

/// Clases jugables. Cada una da un punto de habilidad extra y desbloquea
/// desde el principio la habilidad con la que empieza tu recorrido.
///
/// La tupla es `(id, nombre, descripción, icono, rama, nodo_inicial)`.
pub const CLASSES: &[(&str, &str, &str, &str, &str, &str)] = &[
    (
        "origen",
        "Origen",
        "El equilibrio: sin atajos, sin favoritos.",
        "◈",
        "nucleo",
        "chat",
    ),
    (
        "vidente",
        "Vidente",
        "Percepción máxima: cámara, voz y rostro primero.",
        "◎",
        "percepcion",
        "camara",
    ),
    (
        "automata",
        "Autómata",
        "ARIA trabaja sola antes que tú se lo pidas.",
        "⚙",
        "autonomia",
        "daemon",
    ),
    (
        "sabio",
        "Sabio",
        "Memoria profunda y conocimiento encadenado.",
        "📖",
        "conocimiento",
        "memoria_corto",
    ),
    (
        "guardian",
        "Guardián",
        "Protección: procesos, red y bóveda.",
        "🛡",
        "guardian",
        "process_guard",
    ),
];

/// Busca un nodo por id.
pub fn node(id: &str) -> Option<&'static SkillNode> {
    NODES.iter().find(|n| n.id == id)
}

/* ------------------------------------------------------------------ *
 * Progresión
 * ------------------------------------------------------------------ */

/// XP total acumulado necesario para alcanzar `level`.
///
/// Curva cuadrática: `50 * n * (n - 1)`. Nivel 1 = 0 XP, nivel 2 = 100,
/// nivel 3 = 300, nivel 4 = 600, nivel 5 = 1000.
pub fn xp_for_level(level: u32) -> u64 {
    if level <= 1 {
        return 0;
    }
    let n = level as u64;
    50 * n * (n - 1)
}

/// Nivel correspondente a un XP acumulado.
pub fn level_for_xp(xp: u64) -> u32 {
    let mut level = 1u32;
    while level < 99 && xp >= xp_for_level(level + 1) {
        level += 1;
    }
    level
}

/// Progreso guardado del jugador.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Progression {
    /// Clase elegida. Vacía hasta que se elige una.
    #[serde(default)]
    pub class: String,
    #[serde(default)]
    pub xp: u64,
    #[serde(default)]
    pub points: u32,
    #[serde(default)]
    pub unlocked: Vec<String>,
    #[serde(default)]
    pub equipped: Vec<String>,
    /// XP acumulado por nodo.
    #[serde(default)]
    pub node_xp: BTreeMap<String, u64>,
    /// Veces que se usó cada nodo desbloqueado.
    #[serde(default)]
    pub uses: BTreeMap<String, u64>,
    /// Skills que ARIA se forjó y están equipadas.
    ///
    /// Son habilidades de verdad: entran en el prompt del chat igual que
    /// las del catálogo, y por eso viven en la progresión y no en el
    /// laboratorio.
    #[serde(default)]
    pub generated_equipped: Vec<String>,
}

impl Default for Progression {
    fn default() -> Self {
        Self {
            class: String::new(),
            xp: 0,
            points: 0,
            unlocked: Vec::new(),
            equipped: Vec::new(),
            node_xp: BTreeMap::new(),
            uses: BTreeMap::new(),
            generated_equipped: Vec::new(),
        }
    }
}

impl Progression {
    /// Nivel actual derivado del XP.
    pub fn level(&self) -> u32 {
        level_for_xp(self.xp)
    }

    /// XP que falta para el siguiente nivel.
    pub fn xp_to_next(&self) -> u64 {
        let next = xp_for_level(self.level() + 1);
        next.saturating_sub(self.xp)
    }

    /// XP total del nivel actual (para la barra de progreso).
    pub fn xp_into_level(&self) -> u64 {
        let level = self.level();
        self.xp.saturating_sub(xp_for_level(level))
    }

    /// ¿Está desbloqueado este nodo?
    pub fn is_unlocked(&self, id: &str) -> bool {
        self.unlocked.iter().any(|u| u == id)
    }

    /// ¿Está equipado este nodo?
    pub fn is_equipped(&self, id: &str) -> bool {
        self.equipped.iter().any(|e| e == id)
    }

    /// Motivo por el que un nodo no se puede desbloquear todavía, si lo hay.
    ///
    /// Devuelve `None` cuando sí se puede desbloquear.
    pub fn block_reason(&self, id: &str) -> Option<String> {
        let Some(n) = node(id) else {
            return Some(format!("Nodo desconocido: {id}"));
        };
        if self.is_unlocked(id) {
            return Some("Ya está desbloqueado".to_string());
        }
        if self.class.is_empty() {
            return Some("Elige una clase primero".to_string());
        }
        for req in n.requires {
            if !self.is_unlocked(req) {
                let name = node(req).map(|r| r.name).unwrap_or(req);
                return Some(format!("Requiere «{name}»"));
            }
        }
        if self.points < n.cost {
            let missing = n.cost - self.points;
            return Some(if missing == 1 {
                "Falta 1 punto de habilidad".to_string()
            } else {
                format!("Faltan {missing} puntos de habilidad")
            });
        }
        None
    }

    /// Suma XP y reparte los puntos de habilidad de los niveles ganados.
    ///
    /// Los puntos de nivel son la recompensa principal por usar las
    /// habilidades; los puntos por nodo desbloqueado (en [`Progression::unlock`])
    /// son el segundo motor, para que desbloquear siempre devuelva algo.
    fn add_xp(&mut self, amount: u64) {
        if amount == 0 {
            return;
        }
        let before = self.level();
        self.xp = self.xp.saturating_add(amount);
        let gained_levels = self.level().saturating_sub(before);
        if gained_levels > 0 {
            self.points = self.points.saturating_add(gained_levels * POINTS_PER_LEVEL);
        }
    }

    /// Aplica el desbloqueo de un nodo, si es legal.
    ///
    /// Devuelve `Err` con el motivo cuando la operación no es válida. En caso
    /// de éxito, consume los puntos y otorga el XP del nodo.
    pub fn unlock(&mut self, id: &str) -> Result<(), String> {
        if let Some(reason) = self.block_reason(id) {
            return Err(reason);
        }
        let Some(n) = node(id) else {
            return Err(format!("Nodo desconocido: {id}"));
        };
        self.points = self.points.saturating_sub(n.cost);
        self.unlocked.push(n.id.to_string());
        self.unlocked.sort();
        self.add_xp(n.xp_reward);
        *self.node_xp.entry(n.id.to_string()).or_insert(0) += n.xp_reward;
        // Desbloquear siempre devuelve algo: el árbol nunca se estanca.
        self.points += 1;
        Ok(())
    }

    /// Equipa o desequipa una habilidad activa.
    pub fn equip(&mut self, id: &str, equipped: bool) -> Result<(), String> {
        let Some(n) = node(id) else {
            return Err(format!("Nodo desconocido: {id}"));
        };
        if !self.is_unlocked(id) {
            return Err("Desbloquea la habilidad antes de equiparla".to_string());
        }
        if n.kind == NodeKind::Passive {
            return Err("Las habilidades pasivas no se equipan".to_string());
        }
        if equipped {
            if self.is_equipped(id) {
                return Ok(());
            }
            if self.equipped.len() >= MAX_EQUIPPED {
                return Err(format!(
                    "Máximo {MAX_EQUIPPED} habilidades equipadas a la vez"
                ));
            }
            self.equipped.push(n.id.to_string());
        } else {
            self.equipped.retain(|e| e != id);
        }
        Ok(())
    }

    /// Elige clase: reparte el punto inicial y desbloquea la habilidad de
    /// arranque de esa clase.
    pub fn choose_class(&mut self, class: &str) -> Result<(), String> {
        let Some((id, _, _, _, _, start_node)) = CLASSES.iter().find(|c| c.0 == class)
        else {
            return Err(format!("Clase desconocida: {class}"));
        };
        if !self.class.is_empty() && self.class != *id {
            return Err("La clase se elige una sola vez".to_string());
        }
        self.class = id.to_string();
        self.points += 1;
        if node(start_node).is_some() && !self.is_unlocked(start_node) {
            self.unlocked.push(start_node.to_string());
            self.unlocked.sort();
        }
        Ok(())
    }

    /// Registra el uso de una habilidad y devuelve el XP ganado.
    ///
    /// Sólo cuenta si el nodo está desbloqueado: usar algo que no tienes
    /// desbloqueado no progresa el árbol.
    pub fn award_use(&mut self, id: &str) -> u64 {
        if !self.is_unlocked(id) {
            return 0;
        }
        let gain = 5u64;
        self.add_xp(gain);
        *self.node_xp.entry(id.to_string()).or_insert(0) += gain;
        *self.uses.entry(id.to_string()).or_insert(0) += 1;
        gain
    }

    /// Equipa o desequipa una skill creada por ARIA.
    ///
    /// La existencia de la skill la comprueba quien llama (el laboratorio es
    /// el dueño de la lista); aquí sólo se aplica la regla de juego: hay un
    /// tope de skills generadas equipadas y no se repite la misma.
    pub fn equip_generated(&mut self, id: &str, equipped: bool) -> Result<(), String> {
        let id = id.trim();
        if id.is_empty() {
            return Err("Falta el id de la skill".to_string());
        }
        if equipped {
            if self.generated_equipped.iter().any(|e| e == id) {
                return Ok(());
            }
            if self.generated_equipped.len() >= crate::creativity::MAX_GENERATED_EQUIPPED {
                return Err(format!(
                    "Máximo {} habilidades creadas equipadas a la vez",
                    crate::creativity::MAX_GENERATED_EQUIPPED
                ));
            }
            self.generated_equipped.push(id.to_string());
        } else {
            self.generated_equipped.retain(|e| e != id);
        }
        Ok(())
    }
}

/* ------------------------------------------------------------------ *
 * Estado global y persistencia
 * ------------------------------------------------------------------ */

static PROGRESSION: OnceLock<tokio::sync::Mutex<Progression>> = OnceLock::new();

fn progression() -> &'static tokio::sync::Mutex<Progression> {
    PROGRESSION.get_or_init(|| tokio::sync::Mutex::new(load_progression()))
}

/// Ruta del archivo de estado del árbol.
pub fn state_path() -> PathBuf {
    let dir = std::env::var(SKILL_TREE_STATE_DIR_ENV)
        .ok()
        .filter(|v| !v.trim().is_empty())
        .map(PathBuf::from)
        .unwrap_or_else(crate::control::default_state_dir);
    dir.join(SKILL_TREE_FILE)
}

/// Lee el estado del disco. Un archivo corrupto no debe tumbar el servidor:
/// se descarta y se empieza de cero.
fn load_progression() -> Progression {
    let path = state_path();
    let Ok(raw) = std::fs::read_to_string(&path) else {
        return Progression::default();
    };
    match serde_json::from_str::<Progression>(&raw) {
        Ok(p) => p,
        Err(err) => {
            eprintln!("skill_tree: estado ilegible ({}), se reinicia", err);
            Progression::default()
        }
    }
}

/// Escribe el estado en disco.
fn persist_progression(progression: &Progression) {
    let path = state_path();
    if let Some(parent) = path.parent() {
        if let Err(err) = std::fs::create_dir_all(parent) {
            eprintln!("skill_tree: no se pudo crear {}: {err}", parent.display());
            return;
        }
    }
    match serde_json::to_string_pretty(progression) {
        Ok(body) => {
            if let Err(err) = std::fs::write(&path, body) {
                eprintln!("skill_tree: no se pudo escribir {}: {err}", path.display());
            }
        }
        Err(err) => eprintln!("skill_tree: no se pudo serializar: {err}"),
    }
}

/// Otorga XP por usar una skill real del backend.
///
/// Varios nodos pueden compartir comando (`camara`, `vision_pantalla` y
/// `vision_pro` son todos `"vision"`), así que se acredita XP a todos los
/// nodos desbloqueados que lo implementan: usar una capacidad ejercita todas
/// las habilidades que ya has desbloqueado de ella.
///
/// Devuelve el XP ganado (0 si esa skill no corresponde a ningún nodo
/// desbloqueado).
pub async fn award_skill_usage(skill_name: &str) -> u64 {
    let mut guard = progression().lock().await;
    let mut total = 0u64;
    for n in NODES.iter().filter(|n| n.command == skill_name) {
        total += guard.award_use(n.id);
    }
    if total > 0 {
        persist_progression(&guard);
    }
    total
}

/// Ids de las skills creadas por ARIA que están equipadas.
pub async fn generated_equipped() -> Vec<String> {
    let guard = progression().lock().await;
    guard.generated_equipped.clone()
}

/// Equipa (o desequipa) una skill creada por ARIA.
///
/// La validación de existencia la hace el laboratorio —que es el dueño de
/// la lista de skills forjadas— y después se aplica la regla de juego
/// sobre la progresión.
pub async fn equip_generated_skill(id: &str, equipped: bool) -> Result<(), String> {
    if equipped && !crate::creativity::skill_exists(id) {
        return Err(format!("Skill desconocida: {id}"));
    }
    let mut guard = progression().lock().await;
    guard.equip_generated(id, equipped)?;
    persist_progression(&guard);
    Ok(())
}

/* ------------------------------------------------------------------ *
 * Serialización de la respuesta
 * ------------------------------------------------------------------ */

/// Nodo con su estado actual, listo para el renderer.
#[derive(Debug, Clone, Serialize)]
pub struct NodeView {
    pub id: &'static str,
    pub name: &'static str,
    pub description: &'static str,
    pub branch: &'static str,
    pub tier: u8,
    pub slot: u8,
    pub cost: u32,
    pub requires: &'static [&'static str],
    pub icon: &'static str,
    pub kind: &'static str,
    pub command: &'static str,
    pub xp_reward: u64,
    pub unlocked: bool,
    pub equipped: bool,
    pub available: bool,
    /// Motivo por el que no se puede desbloquear todavía.
    pub blocked_by: Option<String>,
    pub xp: u64,
    pub uses: u64,
}

/// Rama del árbol con su color y descripción.
#[derive(Debug, Clone, Serialize)]
pub struct BranchView {
    pub id: &'static str,
    pub name: &'static str,
    pub description: &'static str,
    pub color: &'static str,
}

/// Clase jugable.
#[derive(Debug, Clone, Serialize)]
pub struct ClassView {
    pub id: &'static str,
    pub name: &'static str,
    pub description: &'static str,
    pub icon: &'static str,
    pub branch: &'static str,
    pub selected: bool,
}

/// Progresión serializada.
#[derive(Debug, Clone, Serialize)]
pub struct ProgressionView {
    pub class: String,
    pub xp: u64,
    pub level: u32,
    pub points: u32,
    pub xp_to_next: u64,
    pub xp_into_level: u64,
    pub xp_for_next_level: u64,
    pub unlocked: Vec<String>,
    pub equipped: Vec<String>,
    pub max_equipped: usize,
    pub node_xp: BTreeMap<String, u64>,
    pub uses: BTreeMap<String, u64>,
    /// Skills creadas por ARIA que están equipadas.
    pub generated_equipped: Vec<String>,
    pub max_generated_equipped: usize,
}

fn progression_view(p: &Progression) -> ProgressionView {
    ProgressionView {
        class: p.class.clone(),
        xp: p.xp,
        level: p.level(),
        points: p.points,
        xp_to_next: p.xp_to_next(),
        xp_into_level: p.xp_into_level(),
        xp_for_next_level: xp_for_level(p.level() + 1) - xp_for_level(p.level()),
        unlocked: p.unlocked.clone(),
        equipped: p.equipped.clone(),
        max_equipped: MAX_EQUIPPED,
        node_xp: p.node_xp.clone(),
        uses: p.uses.clone(),
        generated_equipped: p.generated_equipped.clone(),
        max_generated_equipped: crate::creativity::MAX_GENERATED_EQUIPPED,
    }
}

/// Resumen de la progresión para el prompt del modelo.
///
/// El árbol de habilidades sólo vale algo si ARIA lo usa: este texto es lo
/// que el chat inyecta antes de la petición, de modo que las habilidades
/// equipadas cambian cómo responde el agente.
///
/// Devuelve cadena vacía si todavía no se eligió clase: un ARIA sin clase
/// no tiene identidad que anunciarle al modelo y un prompt vacío se
/// distingue de uno real.
pub async fn equipped_prompt() -> String {
    let guard = progression().lock().await;
    let p = guard.clone();
    drop(guard);
    // Las skills que ARIA se forjó y equipó son habilidades de verdad:
    // entran en el prompt igual que las del catálogo.
    let generated = crate::creativity::generated_summaries(&p.generated_equipped);
    equipped_prompt_with(&p, &generated)
}

/// Versión pura del prompt: recibe la progresión y devuelve el texto.
///
/// Separarla de la versión async permite probarla sin tocar el estado
/// global que vive en disco.
pub fn equipped_prompt_from(p: &Progression) -> String {
    equipped_prompt_with(p, &[])
}

/// Prompt con las skills generadas que se le pasan.
///
/// `generated` son pares `(nombre, descripción)` de las skills que ARIA se
/// forjó y equipó.
pub fn equipped_prompt_with(p: &Progression, generated: &[(String, String)]) -> String {
    let Some((_, class_name, class_desc, class_icon, _, _)) =
        CLASSES.iter().find(|c| c.0 == p.class)
    else {
        return String::new();
    };

    let mut lines = vec![format!(
        "Eres ARIA, clase {class_icon} {class_name} (nivel {level}). {class_desc}",
        level = p.level(),
    )];

    if p.equipped.is_empty() {
        lines.push("Todavía no has equipado ninguna habilidad.".to_string());
    } else {
        lines.push("Habilidades activas:".to_string());
        for id in &p.equipped {
            if let Some(n) = node(id) {
                lines.push(format!(
                    "- {icon} {name}: {desc}",
                    icon = n.icon,
                    name = n.name,
                    desc = n.description
                ));
            }
        }
    }

    if !generated.is_empty() {
        lines.push("Habilidades que tú creaste y equipaste:".to_string());
        for (name, description) in generated {
            lines.push(format!("- {name}: {description}"));
        }
    }

    lines.join("\n")
}

/* ------------------------------------------------------------------ *
 * Handlers
 * ------------------------------------------------------------------ */

pub fn router() -> Router<()> {
    Router::new()
        .route("/api/skill-tree", get(get_tree))
        .route("/api/skill-tree/state", get(get_state))
        .route("/api/skill-tree/unlock", post(post_unlock))
        .route("/api/skill-tree/equip", post(post_equip))
        .route("/api/skill-tree/equip-generated", post(post_equip_generated))
        .route("/api/skill-tree/class", post(post_class))
        .route("/api/skill-tree/reset", post(post_reset))
}

/// `GET /api/skill-tree` — catálogo completo + progresión.
async fn get_tree() -> Json<serde_json::Value> {
    let guard = progression().lock().await;
    let p = guard.clone();
    drop(guard);

    let nodes: Vec<NodeView> = NODES
        .iter()
        .map(|n| NodeView {
            id: n.id,
            name: n.name,
            description: n.description,
            branch: n.branch,
            tier: n.tier,
            slot: n.slot,
            cost: n.cost,
            requires: n.requires,
            icon: n.icon,
            kind: match n.kind {
                NodeKind::Passive => "passive",
                NodeKind::Active => "active",
            },
            command: n.command,
            xp_reward: n.xp_reward,
            unlocked: p.is_unlocked(n.id),
            equipped: p.is_equipped(n.id),
            available: p.block_reason(n.id).is_none(),
            blocked_by: p.block_reason(n.id),
            xp: p.node_xp.get(n.id).copied().unwrap_or(0),
            uses: p.uses.get(n.id).copied().unwrap_or(0),
        })
        .collect();

    let branches: Vec<BranchView> = BRANCHES
        .iter()
        .map(|(id, name, description, color)| BranchView {
            id,
            name,
            description,
            color,
        })
        .collect();

    let classes: Vec<ClassView> = CLASSES
        .iter()
        .map(|(id, name, description, icon, branch, _)| ClassView {
            id,
            name,
            description,
            icon,
            branch,
            selected: p.class == *id,
        })
        .collect();

    Json(json!({
        "status": "ok",
        "nodes": nodes,
        "branches": branches,
        "classes": classes,
        "progression": progression_view(&p),
        "server": "ARIA-Axum-8002",
    }))
}

/// `GET /api/skill-tree/state` — sólo la progresión.
async fn get_state() -> Json<serde_json::Value> {
    let guard = progression().lock().await;
    Json(json!({
        "status": "ok",
        "progression": progression_view(&guard),
        "server": "ARIA-Axum-8002",
    }))
}

/// `POST /api/skill-tree/unlock` — `{ "node_id": "..." }`.
async fn post_unlock(Json(req): Json<serde_json::Value>) -> Json<serde_json::Value> {
    let Some(id) = req.get("node_id").and_then(|v| v.as_str()) else {
        return Json(json!({ "status": "error", "error": "Falta 'node_id'" }));
    };
    let mut guard = progression().lock().await;
    match guard.unlock(id) {
        Ok(()) => {
            persist_progression(&guard);
            Json(json!({
                "status": "ok",
                "unlocked": id,
                "progression": progression_view(&guard),
            }))
        }
        Err(error) => Json(json!({ "status": "error", "error": error })),
    }
}

/// `POST /api/skill-tree/equip` — `{ "node_id": "...", "equipped": true }`.
async fn post_equip(Json(req): Json<serde_json::Value>) -> Json<serde_json::Value> {
    let Some(id) = req.get("node_id").and_then(|v| v.as_str()) else {
        return Json(json!({ "status": "error", "error": "Falta 'node_id'" }));
    };
    let equipped = req
        .get("equipped")
        .and_then(|v| v.as_bool())
        .unwrap_or(true);
    let mut guard = progression().lock().await;
    match guard.equip(id, equipped) {
        Ok(()) => {
            persist_progression(&guard);
            Json(json!({
                "status": "ok",
                "equipped": id,
                "progression": progression_view(&guard),
            }))
        }
        Err(error) => Json(json!({ "status": "error", "error": error })),
    }
}

/// `POST /api/skill-tree/equip-generated` — `{ "skill_id": "gen_001", "equipped": true }`.
///
/// Equipa una skill que ARIA se forjó en el laboratorio de creatividad.
async fn post_equip_generated(Json(req): Json<serde_json::Value>) -> Json<serde_json::Value> {
    let Some(id) = req.get("skill_id").and_then(|v| v.as_str()) else {
        return Json(json!({ "status": "error", "error": "Falta 'skill_id'" }));
    };
    let equipped = req
        .get("equipped")
        .and_then(|v| v.as_bool())
        .unwrap_or(true);
    match equip_generated_skill(id, equipped).await {
        Ok(()) => {
            let guard = progression().lock().await;
            Json(json!({
                "status": "ok",
                "equipped": id,
                "progression": progression_view(&guard),
            }))
        }
        Err(error) => Json(json!({ "status": "error", "error": error })),
    }
}

/// `POST /api/skill-tree/class` — `{ "class": "vidente" }`.
async fn post_class(Json(req): Json<serde_json::Value>) -> Json<serde_json::Value> {
    let Some(class) = req.get("class").and_then(|v| v.as_str()) else {
        return Json(json!({ "status": "error", "error": "Falta 'class'" }));
    };
    let mut guard = progression().lock().await;
    match guard.choose_class(class) {
        Ok(()) => {
            persist_progression(&guard);
            Json(json!({
                "status": "ok",
                "class": class,
                "progression": progression_view(&guard),
            }))
        }
        Err(error) => Json(json!({ "status": "error", "error": error })),
    }
}

/// `POST /api/skill-tree/reset` — empieza de cero.
async fn post_reset() -> Json<serde_json::Value> {
    let mut guard = progression().lock().await;
    *guard = Progression::default();
    persist_progression(&guard);
    Json(json!({
        "status": "ok",
        "progression": progression_view(&guard),
    }))
}

/* ------------------------------------------------------------------ *
 * Tests
 * ------------------------------------------------------------------ */

#[cfg(test)]
mod tests {
    use super::*;

    fn fresh() -> Progression {
        Progression::default()
    }

    #[test]
    fn catalog_is_acyclic_and_references_exist() {
        for n in NODES {
            for req in n.requires {
                assert!(
                    node(req).is_some(),
                    "{} requiere {} que no existe",
                    n.id,
                    req
                );
                assert_ne!(*req, n.id, "{} se requiere a sí mismo", n.id);
            }
        }
        // Un nodo no puede depender (directamente) de un nodo de tier superior.
        for n in NODES {
            for req in n.requires {
                let r = node(req).expect("prerrequisito existe");
                assert!(
                    r.tier < n.tier,
                    "{} (tier {}) requiere {} (tier {})",
                    n.id,
                    n.tier,
                    r.id,
                    r.tier
                );
            }
        }
    }

    #[test]
    fn every_branch_has_a_tier_one_node() {
        for (branch, _, _, _) in BRANCHES {
            assert!(
                NODES.iter().any(|n| n.branch == *branch && n.tier == 1),
                "la rama {branch} no tiene nodo raíz"
            );
        }
    }

    #[test]
    fn node_ids_are_unique() {
        let mut seen = BTreeSet::new();
        for n in NODES {
            assert!(seen.insert(n.id), "id duplicado: {}", n.id);
        }
    }

    #[test]
    fn level_curve_is_monotonic() {
        assert_eq!(level_for_xp(0), 1);
        assert_eq!(level_for_xp(100), 2);
        assert_eq!(level_for_xp(299), 2);
        assert_eq!(level_for_xp(300), 3);
        for l in 1..40u32 {
            assert!(xp_for_level(l) < xp_for_level(l + 1));
        }
    }

    #[test]
    fn unlock_requires_prerequisites_and_points() {
        let mut p = fresh();
        assert!(p.unlock("gestos").is_err(), "sin clase ni prerrequisitos");
        p.choose_class("vidente").expect("clase válida");
        // "vidente" otorga "camara", pero no "microfono": "auricular" sigue
        // bloqueada por prerrequisito.
        assert!(p.is_unlocked("camara"));
        assert!(p.unlock("auricular").is_err(), "faltan prerrequisitos");
        p.unlock("microfono").expect("raíz sin coste");
        p.points += 10;
        p.unlock("auricular").expect("con prerrequisito y puntos");
        assert!(p.is_unlocked("auricular"));
    }

    #[test]
    fn cannot_unlock_twice_or_spend_twice() {
        let mut p = fresh();
        p.choose_class("origen").expect("clase válida");
        // "origen" otorga "chat" (coste 0): los puntos no se mueven.
        let before = p.points;
        assert!(p.is_unlocked("chat"));
        assert!(p.unlock("chat").is_err(), "no se desbloquea dos veces");
        assert_eq!(p.points, before, "el coste 0 no gasta puntos");
    }

    #[test]
    fn passive_nodes_cannot_be_equipped() {
        let mut p = fresh();
        p.choose_class("origen").expect("clase válida");
        assert!(p.equip("chat", true).is_err(), "chat es pasiva");
    }

    #[test]
    fn equipped_cap_is_enforced() {
        let mut p = fresh();
        p.choose_class("origen").expect("clase válida");
        p.points += 99;
        for id in ["orquestacion", "voz_tts", "bots_fondo", "stealth"] {
            // Saltamos los prerrequisitos: aquí sólo se prueba el tope.
            p.unlocked.push(id.to_string());
        }
        assert!(p.equip("orquestacion", true).is_ok());
        assert!(p.equip("voz_tts", true).is_ok());
        assert!(p.equip("bots_fondo", true).is_ok());
        assert!(p.equip("stealth", true).is_err(), "cuarto equipado");
    }

    #[test]
    fn class_can_only_be_chosen_once() {
        let mut p = fresh();
        p.choose_class("vidente").unwrap();
        assert!(p.choose_class("sabio").is_err());
    }

    #[test]
    fn award_use_only_counts_unlocked_nodes() {
        let mut p = fresh();
        assert_eq!(p.award_use("chat"), 0, "nodo bloqueado");
        p.choose_class("origen").unwrap();
        assert_eq!(p.award_use("chat"), 5);
        assert_eq!(p.uses.get("chat").copied(), Some(1));
    }

    #[test]
    fn class_grants_its_starting_node_and_a_point() {
        let mut p = fresh();
        p.choose_class("vidente").unwrap();
        assert!(p.is_unlocked("camara"));
        assert_eq!(p.points, 1);
        assert_eq!(p.class, "vidente");
    }

    #[test]
    fn points_are_earned_per_level() {
        let mut p = fresh();
        p.choose_class("origen").unwrap();
        p.xp = 300; // nivel 3
        assert_eq!(p.level(), 3);
        assert_eq!(p.xp_to_next(), xp_for_level(4) - 300);
    }

    #[test]
    fn leveling_up_grants_skill_points() {
        let mut p = fresh();
        p.choose_class("origen").unwrap();
        let before = p.points;
        p.add_xp(xp_for_level(2)); // justo al nivel 2
        assert_eq!(p.level(), 2);
        assert_eq!(p.points, before + POINTS_PER_LEVEL);
    }

    #[test]
    fn unlocking_a_node_always_returns_a_point() {
        let mut p = fresh();
        p.choose_class("origen").unwrap();
        let before = p.points;
        p.unlock("inferencia").expect("coste 1, hay 1 punto");
        // Cuesta 1 y devuelve 1: la diferencia neta es 0.
        assert_eq!(p.points, before);
    }

    #[test]
    fn prompt_is_empty_without_a_class() {
        let p = fresh();
        assert_eq!(equipped_prompt_from(&p), "");
    }

    #[test]
    fn prompt_names_the_class_and_the_equipped_skills() {
        let mut p = fresh();
        p.choose_class("vidente").unwrap();
        p.unlocked.push("camara".to_string());
        p.equipped.push("camara".to_string());

        let prompt = equipped_prompt_from(&p);
        assert!(prompt.contains("Vidente"), "no nombra la clase: {prompt}");
        assert!(prompt.contains("Ojo de Cámara"), "no nombra la habilidad: {prompt}");
        assert!(prompt.contains("nivel 1"), "no dice el nivel: {prompt}");
    }

    #[test]
    fn prompt_says_when_nothing_is_equipped() {
        let mut p = fresh();
        p.choose_class("origen").unwrap();
        let prompt = equipped_prompt_from(&p);
        assert!(prompt.contains("ninguna habilidad"), "{prompt}");
    }

    #[test]
    fn generated_skills_have_their_own_cap() {
        let mut p = fresh();
        p.equip_generated("gen_001", true).expect("primera");
        p.equip_generated("gen_002", true).expect("segunda");
        assert!(
            p.equip_generated("gen_003", true).is_err(),
            "tercera generada"
        );
        assert!(
            p.equip_generated("gen_003", false).is_ok(),
            "desequipar siempre vale"
        );
    }

    #[test]
    fn a_generated_skill_is_equipped_only_once() {
        let mut p = fresh();
        p.equip_generated("gen_001", true).expect("primera vez");
        p.equip_generated("gen_001", true).expect("repetir no falla");
        assert_eq!(p.generated_equipped.len(), 1);
        p.equip_generated("gen_001", false).expect("desequipar");
        assert!(p.generated_equipped.is_empty());
    }

    #[test]
    fn the_prompt_names_the_skills_aria_created() {
        let mut p = fresh();
        p.choose_class("vidente").unwrap();
        p.equipped.push("camara".to_string());
        let generated = vec![(
            "resumir_la_sesion".to_string(),
            "resume lo que pasó".to_string(),
        )];
        let prompt = equipped_prompt_with(&p, &generated);
        assert!(prompt.contains("resumir_la_sesion"), "{prompt}");
        assert!(prompt.contains("resume lo que pasó"), "{prompt}");
    }
}
