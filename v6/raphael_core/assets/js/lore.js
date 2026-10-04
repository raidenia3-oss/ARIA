/**
 * Raphael: the verified layer.
 *
 * Two separate sources live here and they are kept apart on purpose.
 *
 * 1. LORE — names, kanji and the evolution chain of "Raphael, Lord of Wisdom"
 *    from *That Time I Got Reincarnated as a Slime* (転生したらスライムだった件).
 *    Every string was read off the series wiki, not remembered:
 *      https://tensura.fandom.com/wiki/Raphael
 *      https://tensura.fandom.com/wiki/Ciel
 *    The wiki lists exactly six sub-skills for Raphael, and they are listed
 *    here in that order with no additions. The chain is
 *      Great Sage + Degenerate -> Raphael -> Azathoth
 *    and Ciel is the Manas that later separated from Raphael.
 *    This is fan reference material. It says nothing about ARIA.
 *
 * 2. MACHINE — the palette and geometry vocabulary, which is *ours*. The ramps
 *    are lifted from the brahma-evo "Quantum Core Resonator" state table
 *    (`STATE_COLORS`, read from
 *    https://brahma-evo.netlify.app/web_background/index.html) because that
 *    orb is the thing we are imitating, but the states are re-keyed to what
 *    ARIA's probes can actually report. Nothing here is a measurement.
 *
 * Rule that survives every edit: this file declares names and geometry only.
 * Every number the HUD prints comes from a probe in api.js.
 */

/** The six sub-skills the wiki attributes to Raphael, in wiki order. */
export const RAPHAEL_SUB_SKILLS = [
  {
    id: "thought-acceleration",
    kanji: "思考加速",
    romaji: "shikō kasoku",
    label: "Aceleración de pensamiento",
    geometry: "core-pulse",
    readout: "latencia de las seis sondas",
  },
  {
    id: "analytical-appraisal",
    kanji: "解析鑑定",
    romaji: "kaiseki kantei",
    label: "Peritación analítica",
    geometry: "reticle",
    readout: "clasificación ok / degraded / unavailable",
  },
  {
    id: "parallel-calculation",
    kanji: "並列演算",
    romaji: "heiretsu enzan",
    label: "Cálculo paralelo",
    geometry: "rings",
    readout: "las seis sondas en vuelo a la vez",
  },
  {
    id: "chant-annulment",
    kanji: "詠唱破棄",
    romaji: "eishō haki",
    label: "Anulación del canto",
    geometry: "silence",
    readout: "lo que no responde se apaga en vez de inventarse",
  },
  {
    id: "all-of-creation",
    kanji: "森羅万象",
    romaji: "shinrabanshō",
    label: "Creación de todas las cosas",
    geometry: "tendrils",
    readout: "polvo y tentáculos del núcleo",
  },
  {
    id: "alteration",
    kanji: "能力改変",
    romaji: "nōryoku kaihen",
    label: "Alteración de capacidad",
    geometry: "vitality",
    readout: "cuántas sondas dicen data_source measured",
  },
];

/**
 * The evolution chain, names only. Which rung the HUD shows is decided by
 * `stageFor()` below from measured counts, which is our rule, not the canon.
 */
export const EVOLUTION_CHAIN = [
  { id: "great-sage", label: "GRAN SABIO", kanji: "大賢者", state: "analyzing" },
  { id: "raphael", label: "RAPHAEL", kanji: "智慧之王", state: "online" },
  { id: "ciel", label: "CIEL", kanji: "シエル", state: "measured" },
];

/**
 * Our own stage rule, stated here so the README and the tests can point at it.
 * Counted by what the backend itself measured (`data_source === "measured"`),
 * never by what merely answered 200.
 */
export function stageFor(measured, total) {
  if (!total || measured <= 0) return "great-sage";
  if (measured < total) return "raphael";
  return "ciel";
}

export function stageInfo(id) {
  return EVOLUTION_CHAIN.find((s) => s.id === id) ?? EVOLUTION_CHAIN[0];
}

/**
 * Nucleus states, keyed to what api.js can report. Each ramp is three stops:
 * hot (core), mid (rings), dim (dust and lattice). Copied from brahma-evo's
 * STATE_COLORS for the shades, re-keyed to ARIA for the states.
 */
export const NUCLEUS_STATES = {
  /* 0/6 measured: nothing answers. Crimson, taken from brahma's MUTED. */
  unavailable: { hot: "#ff9999", mid: "#ff3b30", dim: "#881111", speed: 0.55, scale: 0.86 },
  /* first cycle in flight and nothing measured yet. Cyber cyan matrix. */
  scanning: { hot: "#a0ffea", mid: "#00f0ff", dim: "#0088aa", speed: 1.35, scale: 1.02 },
  /* some measured, some not. Sunset amber, as brahma's THINKING. */
  degraded: { hot: "#ffc080", mid: "#ff9100", dim: "#cc6600", speed: 0.9, scale: 0.95 },
  /* all six answered, at least one dependency unhappy. Cyber blue. */
  working: { hot: "#00f0ff", mid: "#0090ff", dim: "#0040aa", speed: 1.15, scale: 1.06 },
  /* all six measured. Quantum white and cyber cyan: brahma's ONLINE. */
  online: { hot: "#ffffff", mid: "#ebf5ff", dim: "#00f0ff", speed: 1, scale: 1.1 },
};

/**
 * Geometry constants, taken from the Quantum Core Resonator build.
 *
 * The second pass over https://brahma-evo.netlify.app/web_background/index.html
 * read five more numbers off the reactor instead of guessing them: `LOBES = 4`,
 * `AMPLITUDE = 0.75`, `SPEED = 0.7` and `targetCameraZ = 46`, plus the names of
 * the six builders that make the scene read (`buildStandingWaveManifold`,
 * `buildCentralVortexSingularity`, `buildGyroscopicOrbitalRings`,
 * `buildStarburstNodes`, `buildReferenceMoonBokeh`, `buildAmbientDust`). Each
 * one is now a layer here. Four lobes is not decoration: it is the shape the
 * series draws around Rimuru when the skill takes over, and it is the number
 * the reference itself settled on.
 */
export const GEOMETRY = {
  cameraFov: 38,
  cameraZ: 46,
  bloom: { strength: 0.75, radius: 0.35, threshold: 0.75 },
  /* Standing wave: LOBES = 4, AMPLITUDE = 0.75 in the reference. */
  lobes: 4,
  lobeAmplitude: 0.75,
  vortexSpeed: 0.7,
  waveRings: 6,
  waveSamples: 190,
  /* Central vortex singularity: buildCentralVortexSingularity + tendrils. */
  tendrils: 36,
  tendrilPoints: 80,
  vortexArms: 3,
  /*
   * buildGyroscopicOrbitalRings: each ring gets its own inclination `axis` and
   * its own `precess`, so the set behaves like a gyroscope rather than three
   * circles squashed by different amounts.
   */
  rings: [
    { scale: 1.0, tilt: -0.22, speed: 0.12, alpha: 0.3, axis: 0.0, precess: 0.07 },
    { scale: 1.32, tilt: 0.34, speed: -0.08, alpha: 0.22, axis: 1.1, precess: -0.05 },
    { scale: 1.66, tilt: -0.08, speed: 0.05, alpha: 0.16, axis: 2.2, precess: 0.035 },
    { scale: 1.98, tilt: 0.5, speed: -0.035, alpha: 0.11, axis: 3.3, precess: -0.022 },
  ],
  /*
   * buildStarburstNodes: fixed points riding the outer rings. Positions are a
   * table, not random, so the node field is identical on every load and can be
   * reasoned about. Brightness still comes from the probes.
   */
  nodes: [
    { ring: 0, at: 0.0, size: 1.5, core: 0 },
    { ring: 1, at: 0.24, size: 1.2, core: 3 },
    { ring: 2, at: 0.51, size: 1.35, core: 1 },
    { ring: 3, at: 0.72, size: 1.05, core: 5 },
    { ring: 0, at: 0.62, size: 0.95, core: 2 },
    { ring: 2, at: 0.88, size: 1.1, core: 4 },
    { ring: 1, at: 0.79, size: 0.8, core: 0 },
    { ring: 3, at: 0.33, size: 0.9, core: 3 },
  ],
  /*
   * buildReferenceMoonBokeh: big out-of-focus discs behind everything. Also a
   * table. `depth` below 0.5 drifts slower and reads as further away.
   */
  bokeh: [
    { r: 0.46, a: 0.42, size: 0.34, depth: 0.22, alpha: 0.05 },
    { r: 0.72, a: 2.31, size: 0.26, depth: 0.48, alpha: 0.045 },
    { r: 0.3, a: 4.1, size: 0.44, depth: 0.34, alpha: 0.04 },
    { r: 0.86, a: 5.4, size: 0.2, depth: 0.66, alpha: 0.035 },
    { r: 0.58, a: 1.2, size: 0.3, depth: 0.15, alpha: 0.03 },
  ],
  latticeLines: 54,
  latticeSamples: 120,
  /* buildAmbientDust: three depth layers instead of one flat sheet. */
  dust: 150,
  dustLayers: 3,
  mandalaPoints: 8,
};

/**
 * The reactor control surface, mirroring the reference's global API
 * (`window.setBrahmaState`, `window.setPointerNorm`, `window.setPageCamera`,
 * `window.losePower`, `window.dissolveReactor`, `window.setCompactMode`,
 * `window.accelerateReactor`, `window.triggerPulse`, `window.setReactorSpeed`).
 * Read off the published page so the HUD can be driven from outside the same way
 * the orb it imitates can be.
 */
export const NUCLEUS_CONTROLS = [
  "setState",
  "setVitality",
  "setCoreState",
  "setStage",
  "setPointer",
  "setCamera",
  "setSpeed",
  "setCompactMode",
  "accelerate",
  "triggerPulse",
  "losePower",
  "restorePower",
  "dissolve",
];

/**
 * Snow-white ramp used where the state colour must not fight the element hue.
 * These are the exact RGB values the reference orb compiles its white end with.
 */
export const QUANTUM_WHITE = { hot: "#ffffff", mid: "#ebf5ff", dim: "#90b5d8", particle: "#d9f0ff" };