/**
 * Utilidades puras de la "encarnación" de ARIA: su cuerpo y su público.
 *
 * Son tres cosas las que hacen que ARIA sea una presencia y no un chat:
 *
 * - los **mundos** (Minecraft, VRChat, el escritorio): dónde está y qué
 *   puede hacer allí,
 * - los **canales** (Twitch, YouTube, Discord): quién le está hablando,
 * - el **estado afectivo**: cómo está, y qué cara pone con eso.
 *
 * Todo lo que se puede decidir sin servidor vive aquí, para poder probarlo
 * sin navegador ni red.
 */

/** Etiqueta legible de cada tipo de mundo. */
export const WORLD_KIND_LABELS: Record<string, string> = {
  escritorio: 'Escritorio',
  avatar: 'Avatar',
  juego: 'Juego',
  chat: 'Chat',
}

/** Etiqueta de un tipo de mundo, o el propio si no se conoce. */
export function worldKindLabel(kind: string): string {
  return WORLD_KIND_LABELS[kind] ?? kind
}

/** Icono del tipo de mundo, para leer la lista de un vistazo. */
export function worldKindIcon(kind: string): string {
  switch (kind) {
    case 'escritorio':
      return '🖥️'
    case 'avatar':
      return '🎭'
    case 'juego':
      return '⛏️'
    case 'chat':
      return '💬'
    default:
      return '🌐'
  }
}

/** Estado de la conexión de un mundo. */
export function worldStatusLabel(world: { connected: boolean; status: string }): string {
  if (world.connected) return 'Conectado'
  if (!world.status || world.status === 'listo') return 'Preparado'
  return world.status
}

/** Si un mundo puede recibir acciones ahora mismo. */
export function worldIsUsable(world: { connected: boolean }): boolean {
  return world.connected
}

/**
 * Cuántas capacidades declara un mundo.
 *
 * Un mundo sin capacidades es un adorno: no se puede hacer nada en él.
 */
export function worldCapabilityCount(world: { capabilities?: string[] }): number {
  return world.capabilities?.length ?? 0
}

/** Etiqueta legible de cada tipo de canal. */
export const CHANNEL_KIND_LABELS: Record<string, string> = {
  twitch: 'Twitch',
  youtube: 'YouTube',
  discord: 'Discord',
  telegram: 'Telegram',
  http: 'Web',
  simulador: 'Simulador',
}

/** Etiqueta de un tipo de canal, o el propio si no se conoce. */
export function channelKindLabel(kind: string): string {
  return CHANNEL_KIND_LABELS[kind] ?? kind
}

/** Icono del tipo de canal. */
export function channelKindIcon(kind: string): string {
  switch (kind) {
    case 'twitch':
      return '🟣'
    case 'youtube':
      return '🔴'
    case 'discord':
      return '🔵'
    case 'telegram':
      return '✈️'
    case 'simulador':
      return '🧪'
    default:
      return '🌐'
  }
}

/** Cuántas personas le han hablado a ARIA por ese canal. */
export function channelAudience(channel: { messages: number }): string {
  const count = channel.messages ?? 0
  if (count === 0) return 'nadie ha hablado todavía'
  if (count === 1) return '1 mensaje'
  return `${count} mensajes`
}

/** Si el canal está listo para escuchar. */
export function channelIsListening(channel: { enabled: boolean; connected: boolean }): boolean {
  return channel.enabled && channel.connected
}

/** Etiqueta legible de cada emoción. */
export const EMOTION_LABELS: Record<string, string> = {
  alegria: 'Alegría',
  curiosidad: 'Curiosidad',
  calma: 'Calma',
  enfado: 'Enfado',
  aburrimiento: 'Aburrimiento',
  sorpresa: 'Sorpresa',
  determinacion: 'Determinación',
}

/** Etiqueta de una emoción, o la propia si no se conoce. */
export function emotionLabel(emotion: string): string {
  return EMOTION_LABELS[emotion] ?? emotion
}

/**
 * Qué tan fuerte está una emoción (0..1) en texto.
 *
 * Por encima de 0.6 la emoción domina; por debajo de 0.25 apenas se nota.
 */
export function emotionStrength(level: number): string {
  if (!Number.isFinite(level)) return '—'
  if (level >= 0.6) return 'muy marcada'
  if (level >= 0.35) return 'notable'
  if (level >= 0.15) return 'sutil'
  return 'apenas'
}

/** Etiqueta legible de cada rasgo de carácter. */
export const TRAIT_LABELS: Record<string, string> = {
  curiosidad: 'Curiosidad',
  calidez: 'Calidez',
  humor: 'Humor',
  audacia: 'Audacia',
  disciplina: 'Disciplina',
}

/** Etiqueta de un rasgo, o el propio si no se conoce. */
export function traitLabel(name: string): string {
  return TRAIT_LABELS[name] ?? name
}

/**
 * Si un cambio de rasgo merece la pena enseñarse.
 *
 * Los cambios son pequeños (±0.15) y ARIA no debe quejarse de cada uno.
 */
export function traitChangeIsVisible(delta: number): boolean {
  return Number.isFinite(delta) && Math.abs(delta) >= 0.01
}

/**
 * Formatea el cambio de un rasgo con su signo.
 *
 * `+0.05` es "un poco más", `-0.12` es "bastante menos".
 */
export function formatTraitChange(delta: number): string {
  if (!Number.isFinite(delta)) return '—'
  const sign = delta >= 0 ? '+' : ''
  return `${sign}${delta.toFixed(2)}`
}

/** Si un mensaje del canal va dirigido a ARIA. */
export function messageIsAddressed(message: { addressed: boolean }): boolean {
  return message.addressed
}

/** Si ARIA ya contestó a ese mensaje. */
export function messageIsAnswered(message: { replied: boolean }): boolean {
  return message.replied
}
