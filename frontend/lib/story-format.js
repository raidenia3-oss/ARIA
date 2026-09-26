/**
 * Utilidades puras de la base literaria (sin DOM ni red).
 * JS plano + JSDoc para poder testearlas con node --test.
 */

/**
 * Ordena eventos por timestamp ascendente (cronología).
 * @param {Array<{timestamp?: number}>} events
 * @returns {Array<{timestamp?: number}>} copia ordenada
 */
export function sortEventsByTimestamp(events) {
  return [...(events || [])].sort(
    (a, b) => (a.timestamp || 0) - (b.timestamp || 0)
  );
}

/**
 * Formatea un timestamp (epoch seconds) como fecha legible.
 * @param {number} ts
 * @returns {string}
 */
export function formatEventTime(ts) {
  if (!ts) return "—";
  try {
    return new Date(ts * 1000).toLocaleString();
  } catch {
    return "—";
  }
}

const CHAPTER_STATUS_LABELS = {
  planned: "Planificado",
  in_progress: "En progreso",
  drafted: "Borrador",
  revised: "Revisado",
  completed: "Completado",
};

/**
 * Etiqueta legible del estado de un capítulo.
 * @param {string} status
 * @returns {string}
 */
export function chapterStatusLabel(status) {
  return CHAPTER_STATUS_LABELS[status] || status || "—";
}

/**
 * Separa texto multilínea/coma en lista limpia (para formularios).
 * @param {string} raw
 * @returns {string[]}
 */
export function parseListInput(raw) {
  return (raw || "")
    .split(/\n|,/)
    .map((s) => s.trim())
    .filter(Boolean);
}

/**
 * Slug simple para ids de obra/personaje.
 * @param {string} text
 * @returns {string}
 */
export function slugify(text) {
  return (text || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}
