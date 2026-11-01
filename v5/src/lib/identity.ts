/**
 * Verificación de identidad por rostro.
 *
 * MediaPipe Face Landmarker devuelve 468 puntos 3D del malla facial. De ahí
 * se deriva un descriptor que compara caras:
 *
 *   1. Se centra la malla en su propio origen (media de todos los puntos).
 *   2. Se escala por la distancia entre las comisuras de los ojos, de modo
 *      que la distancia a la cámara o el tamaño de la cara no importen.
 *   3. Se submuestrea la malla (1 de cada 6 puntos) para que el descriptor sea
 *      pequeño y para que un punto mal detectado no mueva todo el vector.
 *   4. Se normaliza a longitud 1, con lo que el producto escalar ES el
 *      coseno del ángulo entre los dos descriptores.
 *
 * NO es un embedding de reconocimiento facial de nivel industrial: es una
 * comprobación de "es la misma persona" reasonable, sin dependencias
 * adicionales y con todo el cálculo en local. El umbral se ajusta a mano
 * con la puntuación mostrada en pantalla.
 */

/** Punto 3D de la malla facial, en coordenadas normalizadas de la imagen. */
export interface FacePoint {
  x: number
  y: number
  z: number
}

/** Descriptor de rostro: vector de reales normalizado a longitud 1. */
export type FaceDescriptor = number[]

/** Índices de las comisuras externas de los ojos en la malla de MediaPipe. */
const LEFT_EYE_OUTER = 33
const RIGHT_EYE_OUTER = 263

/** Cada cuántos puntos de la malla se conserva uno. */
const SAMPLE_STRIDE = 6

/** Longitud mínima de malla aceptable: menos de esto no se compara. */
const MIN_LANDMARKS = 100

/**
 * Construye el descriptor de una malla facial.
 *
 * Devuelve `null` si la malla es demasiado corta o degenerada (todos los
 * puntos en el mismo sitio), porque un descriptor inválido compararía bien
 * con cualquier otra cosa y daría un falso positivo de identidad.
 */
export function faceDescriptor(points: FacePoint[]): FaceDescriptor | null {
  if (!points || points.length < MIN_LANDMARKS) return null

  const left = points[LEFT_EYE_OUTER]
  const right = points[RIGHT_EYE_OUTER]
  if (!left || !right) return null

  const dx = left.x - right.x
  const dy = left.y - right.y
  const dz = left.z - right.z
  const scale = Math.sqrt(dx * dx + dy * dy + dz * dz)
  // Un tamaño de cara menor que 0.01 significa que la malla está colapsada.
  if (!Number.isFinite(scale) || scale < 0.01) return null

  let cx = 0
  let cy = 0
  let cz = 0
  for (const p of points) {
    cx += p.x
    cy += p.y
    cz += p.z
  }
  const n = points.length
  cx /= n
  cy /= n
  cz /= n

  const out: number[] = []
  for (let i = 0; i < n; i += SAMPLE_STRIDE) {
    const p = points[i]
    out.push((p.x - cx) / scale, (p.y - cy) / scale, (p.z - cz) / scale)
  }

  const norm = Math.sqrt(out.reduce((acc, v) => acc + v * v, 0))
  if (!Number.isFinite(norm) || norm < 1e-8) return null
  for (let i = 0; i < out.length; i++) out[i] /= norm

  return out
}

/**
 * Similitud coseno entre dos descriptores.
 *
 * Devuelve 0 si las longitudes no coinciden: compararlos sería comparar
 * vets de dimensiones distintas y daría un número sin sentido.
 */
export function cosineSimilarity(a: FaceDescriptor, b: FaceDescriptor): number {
  if (!a || !b || a.length !== b.length || a.length === 0) return 0
  let dot = 0
  for (let i = 0; i < a.length; i++) dot += a[i] * b[i]
  return dot
}

/**
 * Promedia varios descriptores de la misma persona y vuelve a normalizar.
 *
 * Promediar reduce el ruido de una captura puntual: un solo frame puede
 * tener un punto mal detectado.
 */
export function averageDescriptors(list: FaceDescriptor[]): FaceDescriptor | null {
  const valid = list.filter((d) => Array.isArray(d) && d.length > 0)
  if (valid.length === 0) return null
  const size = valid[0].length
  if (!valid.every((d) => d.length === size)) return null

  const out = new Array<number>(size).fill(0)
  for (const d of valid) {
    for (let i = 0; i < size; i++) out[i] += d[i]
  }
  for (let i = 0; i < size; i++) out[i] /= valid.length

  const norm = Math.sqrt(out.reduce((acc, v) => acc + v * v, 0))
  if (!Number.isFinite(norm) || norm < 1e-8) return null
  for (let i = 0; i < size; i++) out[i] /= norm
  return out
}

/** Umbral por debajo del cual se considera que es OTRA persona. */
export const IDENTITY_THRESHOLD = 0.72
/** Umbral a partir del cual la identidad se considera confirmada. */
export const IDENTITY_STRONG_THRESHOLD = 0.85

export type IdentityVerdict = 'desconocido' | 'probable' | 'confirmado'

/**
 * Verdict sobre una comparación de identidad.
 *
 * - `desconocido`: no hay perfil enrolmentado, o la similitud es baja.
 * - `probable`: por encima del umbral, pero sin confianza plena.
 * - `confirmado`: por encima del umbral fuerte.
 */
export function identityVerdict(score: number): IdentityVerdict {
  if (score >= IDENTITY_STRONG_THRESHOLD) return 'confirmado'
  if (score >= IDENTITY_THRESHOLD) return 'probable'
  return 'desconocido'
}

/* ------------------------------------------------------------------ *
 * Persistencia
 * ------------------------------------------------------------------ */

const STORAGE_KEY = 'aria.identity.v1'

/** Perfil de identidad enrolmentado. */
export interface IdentityProfile {
  name: string
  descriptor: FaceDescriptor
  samples: number
  enrolledAt: number
}

/**
 * Guarda el perfil en `localStorage`.
 *
 * El descriptor es una geometría de la cara, no una imagen: no permite
 * reconstruir la fotografía, pero sigue siendo información biométrica. Por
 * eso en la app de escritorio se usa el IPC de Electron (fichero en
 * `userData`) y este es sólo el respaldo del navegador.
 */
export function saveIdentityProfile(profile: IdentityProfile): boolean {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(profile))
    return true
  } catch {
    return false
  }
}

/** Carga el perfil enrolmentado, o `null` si no hay o está corrupto. */
export function loadIdentityProfile(): IdentityProfile | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<IdentityProfile>
    if (
      typeof parsed?.name !== 'string' ||
      !Array.isArray(parsed?.descriptor) ||
      parsed.descriptor.length === 0
    ) {
      return null
    }
    return {
      name: parsed.name,
      descriptor: parsed.descriptor,
      samples: typeof parsed.samples === 'number' ? parsed.samples : 1,
      enrolledAt: typeof parsed.enrolledAt === 'number' ? parsed.enrolledAt : Date.now(),
    }
  } catch {
    return null
  }
}

/** Borra el perfil enrolmentado. */
export function clearIdentityProfile(): void {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    /* sin storage disponible */
  }
}
