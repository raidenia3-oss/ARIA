/**
 * Detección de audífonos con micrófono.
 *
 * `enumerateDevices()` sólo revela las etiquetas de los dispositivos tras
 * conceder permiso de micrófono. Windows reporta el nombre del fabricante
 * tal cual ("Headset Microphone", "Auriculares (Jabra EVO)", "AirPods Pro"),
 * así que la detección es por patrón de texto sobre la etiqueta.
 */

/**
 * Patrones de etiqueta que delatan un auricular o casco con micrófono.
 *
 * Se incluyen términos en inglés y en español porque el nombre del
 * dispositivo depende de cómo lo haya instalado el usuario.
 */
export const HEADSET_PATTERNS: readonly string[] = [
  'headset',
  'head phone',
  'headphone',
  'earphone',
  'earbud',
  'earbuds',
  'auricular',
  'auriculares',
  'casco',
  'cascos',
  'hands-free',
  'handsfree',
  'airpods',
  'buds',
  'tws',
  'gaming',
  'wireless',
]

/** `true` si la etiqueta del dispositivo delata un auricular con micrófono. */
export function looksLikeHeadset(label: string): boolean {
  if (!label) return false
  const lower = label.toLowerCase()
  return HEADSET_PATTERNS.some((pattern) => lower.includes(pattern))
}

/**
 * Limpia la etiqueta que reporta el sistema.
 *
 * Windows antepone el número de puerto de audio ("2- Headset Microphone"),
 * que no aporta nada y desordena la lista.
 */
export function cleanDeviceLabel(label: string): string {
  return label.replace(/^\d+\s*-\s*/, '').trim()
}
