/**
 * Nucleus renderer: the Raphael core and its element cores.
 *
 * Canvas 2D on purpose: no bundler, no vendored WebGL runtime, works from
 * `file://` and from a static host. What it imitates is the brahma-evo
 * "Quantum Core Resonator" (three.js + UnrealBloom), read at
 * https://brahma-evo.netlify.app/web_background/index.html: a standing-wave
 * lattice, 36 vortex tendrils, three gyroscopic rings, starburst nodes, a
 * white singularity and a bloom pass. Everything WebGL does there with a bloom
 * pass is done here with a radial gradient plus `lighter`, and every colour
 * there compiles into a texture once is compiled into a sprite once.
 *
 * Second pass over that page, which is what this revision adds. The reactor's
 * own builder list was read rather than guessed, so the scene now has all six
 * of its layers:
 *   buildStandingWaveManifold  -> drawStandingWave()   four lobes, the signature
 *   buildCentralVortexSingularity -> drawTendrils()    three-armed vortex
 *   buildGyroscopicOrbitalRings   -> drawRings()        four rings, own axis + precess
 *   buildStarburstNodes           -> drawNodes()        eight nodes bound to cores
 *   buildReferenceMoonBokeh       -> drawBokeh()        five fixed soft discs
 *   buildAmbientDust              -> drawDust()         three depth layers
 * and the same page publishes a control surface (`window.setBrahmaState`,
 * `window.setPageCamera`, `window.losePower`, ...) which is reproduced on
 * `window.ARIA.nucleus` by `NUCLEUS_CONTROLS` in lore.js.
 *
 * On the Tensura art the user asked for: the searches only return third-party
 * anime stills (Steam Workshop, Pixiv, Pinterest, ZEDGE, wallpaper farms) with
 * no redistributable licence, so none of it is embedded. What is taken from
 * the series is described instead of copied, and drawn procedurally: the
 * four-lobed standing wave, the halo, the starburst nodes and the
 * white-hot centre. Everything on screen here is original canvas work.
 *
 * Two additions on top of the reference, both grounded in lore.js:
 *   - the geometry is re-keyed to Raphael's six sub-skills, so each visual
 *     element has a name and a readable measurement behind it;
 *   - the palette is a state machine driven by real probe results, exactly as
 *     the reference's `setBrahmaState` drives its `STATE_COLORS` table.
 *
 * Honesty rule: a core never glows on its own. It glows only when a probe in
 * api.js reports a measured value for the subsystem it is bound to.
 */

import { GEOMETRY, NUCLEUS_CONTROLS, NUCLEUS_STATES, stageFor, stageInfo } from "./lore.js";

const TAU = Math.PI * 2;

const ELEMENT_CORES = [
  { id: "fire", label: "FUEGO", system: "Nucleo vivo", endpoint: "/health", hue: 18 },
  { id: "water", label: "AGUA", system: "Dependencias", endpoint: "/health/detailed", hue: 192 },
  { id: "earth", label: "TIERRA", system: "Enjambre APEX", endpoint: "/api/swarm/agents/status", hue: 96 },
  { id: "wind", label: "VIENTO", system: "Despacho", endpoint: "/api/swarm/metrics", hue: 158 },
  { id: "light", label: "LUZ", system: "Catalogo de roles", endpoint: "/api/swarm/roles", hue: 44 },
  { id: "shadow", label: "SOMBRA", system: "Estado del enjambre", endpoint: "/api/swarm/status", hue: 282 },
];

const SPRITE = 128;
const SPRITE_CACHE = new Map();

const reducedMotion =
  typeof matchMedia === "function" &&
  matchMedia("(prefers-reduced-motion: reduce)").matches;

function hsl(h, s, l, a = 1) {
  return `hsla(${h}, ${s}%, ${l}%, ${a})`;
}

function hexToRgb(hex) {
  const value = String(hex).replace("#", "");
  return [
    parseInt(value.slice(0, 2), 16),
    parseInt(value.slice(2, 4), 16),
    parseInt(value.slice(4, 6), 16),
  ];
}

function rgbToHex([r, g, b]) {
  return `#${[r, g, b].map((v) => Math.round(v).toString(16).padStart(2, "0")).join("")}`;
}

function rgba(hex, alpha) {
  const [r, g, b] = hexToRgb(hex);
  return `rgba(${r},${g},${b},${alpha})`;
}

/**
 * Bloom lives here. The reference runs UnrealBloomPass with strength 0.75,
 * radius 0.35, threshold 0.75; in 2D the equivalent is a radial gradient that
 * stays empty until 75% of the radius, so only the hottest centre survives.
 * Compiled once per colour and cached, like the reference's starburst texture.
 */
function glowSprite(key, stops) {
  const cached = SPRITE_CACHE.get(key);
  if (cached) return cached;
  const canvas = document.createElement("canvas");
  canvas.width = SPRITE;
  canvas.height = SPRITE;
  const ctx = canvas.getContext("2d");
  const r = SPRITE / 2;
  const grad = ctx.createRadialGradient(r, r, 0, r, r, r);
  for (const [offset, color] of stops) grad.addColorStop(offset, color);
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, SPRITE, SPRITE);
  SPRITE_CACHE.set(key, canvas);
  return canvas;
}

function coreSprite(hue, sat, light) {
  return glowSprite(`core:${hue}:${sat}:${light}`, [
    [0, hsl(hue, sat, 96, 0.95)],
    [0.12, hsl(hue, sat, light, 0.7)],
    [0.34, hsl(hue, sat, light, 0.26)],
    [1, hsl(hue, sat, light, 0)],
  ]);
}

function haloSprite(hot, mid) {
  return glowSprite(`halo:${hot}:${mid}`, [
    [0, rgba("#ffffff", 0.9)],
    [GEOMETRY.bloom.threshold, rgba(mid, 0.34)],
    [1, "rgba(0,0,0,0)"],
  ]);
}

/** Which half of the tendril fan takes the hot colour, so the fan reads as woven. */
function tendrilHeat(index, count) {
  return Math.sin((index / count) * Math.PI * 6) * 0.5 + 0.5;
}

class NucleusRenderer {
  constructor(canvas, cores) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.cores = cores;
    this.dust = [];
    this.t = 0;
    this.running = false;
    this.breath = { phase: 0, level: 0, target: 0 };
    this.pointer = { x: 0, y: 0, tx: 0, ty: 0, active: false };
    /*
     * `setPageCamera` in the reference: the pointer dollies the camera instead of
     * only leaning the orb. Kept as a dolly distance so the projection maths stay
     * identical in 2D: closer camera, bigger scene.
     */
    this.camera = { z: GEOMETRY.cameraZ, tz: GEOMETRY.cameraZ, x: 0, tx: 0, y: 0, ty: 0 };
    /* window.losePower / window.restorePower / window.dissolveReactor.
     * Field names are deliberately not the control names: an instance field would
     * shadow the prototype method of the same name and quietly drop it off
     * `controls()`, which is exactly what happened the first time. */
    this.charge = { level: 1, target: 1 };
    this.fracture = { level: 0, target: 0 };
    /* window.triggerPulse / window.accelerateReactor / window.setReactorSpeed. */
    this.pulse = 0;
    this.boost = 1;
    this.compact = false;
    this.state = "scanning";
    this.stage = "great-sage";
    this.ramp = {
      hot: hexToRgb(NUCLEUS_STATES.scanning.hot),
      mid: hexToRgb(NUCLEUS_STATES.scanning.mid),
      dim: hexToRgb(NUCLEUS_STATES.scanning.dim),
    };
    this.target = NUCLEUS_STATES.scanning;
    this.speed = NUCLEUS_STATES.scanning.speed;
    this.scale = NUCLEUS_STATES.scanning.scale;
    this.resize = this.resize.bind(this);
    this.loop = this.loop.bind(this);
  }

  mount() {
    this.resize();
    if (typeof ResizeObserver === "function") {
      this.resizeObserver = new ResizeObserver(this.resize);
      this.resizeObserver.observe(this.canvas);
    } else {
      addEventListener("resize", this.resize);
    }
    if (typeof document !== "undefined") {
      document.addEventListener("visibilitychange", () => {
        if (document.hidden) this.stop();
        else this.start();
      });
    }
    if (reducedMotion) {
      this.draw();
      return;
    }
    this.start();
  }

  destroy() {
    this.stop();
    if (this.resizeObserver) this.resizeObserver.disconnect();
    else removeEventListener("resize", this.resize);
  }

  start() {
    if (this.running) return;
    this.running = true;
    this.last = performance.now();
    requestAnimationFrame(this.loop);
  }

  stop() {
    this.running = false;
  }

  resize() {
    const dpr = Math.min(globalThis.devicePixelRatio || 1, 2);
    const w = this.canvas.clientWidth || innerWidth;
    const h = this.canvas.clientHeight || innerHeight;
    this.canvas.width = Math.max(1, Math.round(w * dpr));
    this.canvas.height = Math.max(1, Math.round(h * dpr));
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.w = w;
    this.h = h;
    this.cx = w / 2;
    this.cy = h / 2;
    this.unit = Math.min(w, h);
    this.dust = Array.from({ length: GEOMETRY.dust }, () => ({
      a: Math.random() * TAU,
      r: 0.18 + Math.random() * 0.82,
      size: 0.4 + Math.random() * 1.4,
      drift: (Math.random() - 0.5) * 0.0004,
      alpha: 0.1 + Math.random() * 0.45,
      layer: Math.floor(Math.random() * GEOMETRY.dustLayers),
    }));
    // Fixed tables, not randomness: the bokeh and the node field are the same on
    // every load, so a change in what they look like is always a change in code.
    this.bokeh = GEOMETRY.bokeh.map((b) => ({ ...b }));
    this.nodes = GEOMETRY.nodes.map((n) => ({ ...n }));
    if (reducedMotion) this.draw();
  }

  /** Level 0..1: how much of the core is alive. Driven by real probe results. */
  setVitality(level) {
    this.breath.target = Math.max(0, Math.min(1, level));
    // Without animation the ramp never runs, so the nucleus would stay at its
    // dim birth level forever and read as dead even when everything answers.
    if (reducedMotion) {
      this.breath.level = this.breath.target;
      this.draw();
    }
  }

  setCoreState(id, state) {
    const core = this.cores.find((c) => c.id === id);
    if (!core) return;
    const wasAnswering = core.state === "ok" || core.state === "degraded";
    const isAnswering = state === "ok" || state === "degraded";
    core.state = state;
    // A probe that has just started answering throws that core's starburst.
    // This is the only motion in the nucleus not derived from the clock.
    if (isAnswering && !wasAnswering) core.flash = 1;
  }

  /**
   * The whole nucleus takes one state, keyed to the same counts the pill uses.
   * The direct analogue of the reference's `setBrahmaState(state)`.
   */
  setState(state) {
    if (!NUCLEUS_STATES[state] || state === this.state) return;
    this.state = state;
    this.target = NUCLEUS_STATES[state];
    if (reducedMotion) {
      this.ramp = {
        hot: hexToRgb(this.target.hot),
        mid: hexToRgb(this.target.mid),
        dim: hexToRgb(this.target.dim),
      };
      this.speed = this.target.speed;
      this.scale = this.target.scale;
      this.draw();
    }
  }

  /** Rung of the evolution chain that the measured data earns. */
  setStage(measured, total) {
    this.stage = stageFor(measured, total);
  }

  stageLabel() {
    return stageInfo(this.stage).label;
  }

  /** nx, ny in [-1, 1]. The nucleus leans toward the pointer, like the reference. */
  setPointer(nx, ny) {
    this.pointer.tx = Math.max(-1, Math.min(1, nx));
    this.pointer.ty = Math.max(-1, Math.min(1, ny));
    this.pointer.active = true;
    if (this.camera.tz === GEOMETRY.cameraZ) this.setCamera(this.pointer.tx, this.pointer.ty);
  }

  /**
   * Camera dolly, the analogue of the reference's `setPageCamera`. ny above 0
   * pulls the camera closer (the scene grows); the shift is capped at a couple of
   * per cent so the HUD never swims under the pointer.
   */
  setCamera(nx, ny) {
    const x = Math.max(-1, Math.min(1, nx));
    const y = Math.max(-1, Math.min(1, ny));
    this.camera.tx = GEOMETRY.cameraZ - y * 5;
    this.camera.x = x * this.unit * 0.012;
    this.camera.y = -y * this.unit * 0.008;
  }

  /** window.setReactorSpeed: multiplies the clock without touching the state table. */
  setSpeed(multiplier) {
    const value = Number(multiplier);
    if (!Number.isFinite(value)) return;
    this.boost = Math.max(0, Math.min(4, value));
  }

  /** window.accelerateReactor: a one-shot speed kick that decays back to 1. */
  accelerate(amount = 1.8) {
    this.boost = Math.max(this.boost, Math.max(1, Math.min(4, amount)));
  }

  /** window.triggerPulse: one extra breath, decaying. Never sets a measurement. */
  triggerPulse(amount = 1) {
    this.pulse = Math.min(1.6, this.pulse + Math.max(0.1, amount));
  }

  /** window.setCompactMode: fewer samples, so small screens stay smooth. */
  setCompactMode(on) {
    this.compact = Boolean(on);
    if (reducedMotion) this.draw();
  }

  /** window.losePower / window.restorePower. */
  losePower() {
    this.charge.target = 0.28;
    if (reducedMotion) {
      this.charge.level = this.charge.target;
      this.draw();
    }
  }

  restorePower() {
    this.charge.target = 1;
    if (reducedMotion) {
      this.charge.level = this.charge.target;
      this.draw();
    }
  }

  /** window.dissolveReactor: scatters the wave, then restores it. */
  dissolve(on = true) {
    this.fracture.target = on ? 1 : 0;
    if (reducedMotion) {
      this.fracture.level = this.fracture.target;
      this.draw();
    }
  }

  /** The public surface, shaped like the reference's `window.*` reactor API. */
  controls() {
    return Object.fromEntries(
      NUCLEUS_CONTROLS.filter((name) => typeof this[name] === "function").map((name) => [
        name,
        this[name].bind(this),
      ]),
    );
  }

  loop(now) {
    if (!this.running) return;
    const dt = Math.min(64, now - this.last);
    this.last = now;
    this.t += dt * this.speed * this.boost;
    this.breath.phase += dt * 0.0009;
    const ease = Math.min(1, dt * 0.0016);
    this.breath.level += (this.breath.target - this.breath.level) * ease;
    this.pointer.x += (this.pointer.tx - this.pointer.x) * Math.min(1, dt * 0.004);
    this.pointer.y += (this.pointer.ty - this.pointer.y) * Math.min(1, dt * 0.004);
    this.camera.z += (this.camera.tz - this.camera.z) * Math.min(1, dt * 0.003);
    this.charge.level += (this.charge.target - this.charge.level) * Math.min(1, dt * 0.0025);
    this.fracture.level += (this.fracture.target - this.fracture.level) * Math.min(1, dt * 0.0018);
    if (this.pulse > 0) this.pulse = Math.max(0, this.pulse - dt * 0.0012);
    this.boost += (1 - this.boost) * Math.min(1, dt * 0.0012);
    this.speed += (this.target.speed - this.speed) * Math.min(1, dt * 0.0008);
    this.scale += (this.target.scale - this.scale) * Math.min(1, dt * 0.0008);
    this.lerpRamp(Math.min(1, dt * 0.0009));
    for (const core of this.cores) {
      if (core.flash) core.flash = Math.max(0, core.flash - dt * 0.0012);
    }
    this.draw();
    requestAnimationFrame(this.loop);
  }

  lerpRamp(amount) {
    const goal = {
      hot: hexToRgb(this.target.hot),
      mid: hexToRgb(this.target.mid),
      dim: hexToRgb(this.target.dim),
    };
    for (const stop of ["hot", "mid", "dim"]) {
      const from = this.ramp[stop];
      const to = goal[stop];
      from[0] += (to[0] - from[0]) * amount;
      from[1] += (to[1] - from[1]) * amount;
      from[2] += (to[2] - from[2]) * amount;
    }
  }

  get hot() {
    return rgbToHex(this.ramp.hot);
  }

  get mid() {
    return rgbToHex(this.ramp.mid);
  }

  get dim() {
    return rgbToHex(this.ramp.dim);
  }

  draw() {
    const { ctx, w, h } = this;
    ctx.clearRect(0, 0, w, h);
    // Camera dolly expressed as a scale: closer camera, bigger scene. The camera
    // itself never moves off-centre by more than the pointer shift set above.
    const dolly = GEOMETRY.cameraZ / this.camera.z;
    const base = this.unit * 0.15 * this.scale * dolly;
    const power = this.charge.level;
    const ox = (this.pointer.active ? this.pointer.x * this.unit * 0.022 : 0) + this.camera.x;
    const oy = (this.pointer.active ? this.pointer.y * this.unit * 0.016 : 0) + this.camera.y;
    const vitality = this.breath.level * power;
    const pulse = this.pulse;
    this.drawBokeh(ox, oy, power);
    this.drawDust(ox, oy);
    this.drawLattice(ox, oy, base);
    this.drawStandingWave(ox, oy, base, vitality);
    this.drawTendrils(ox, oy, base, vitality);
    this.drawRings(ox, oy, base, vitality);
    this.drawNodes(ox, oy, base, vitality, pulse);
    this.drawCores(ox, oy, base, vitality, pulse);
    this.drawNucleus(ox, oy, base, vitality, pulse);
    this.drawReticle(ox, oy, base, vitality);
  }

  /**
   * buildReferenceMoonBokeh. Five large defocused discs behind everything, so the
   * core sits in a depth field instead of on flat black. Positions and sizes come
   * from a table in lore.js; `depth` below 0.5 is closer and drifts faster.
   */
  drawBokeh(ox, oy, power) {
    const { ctx, cx, cy, unit } = this;
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    for (const b of this.bokeh) {
      const drift = this.t * (0.00004 + b.depth * 0.00006);
      const x = cx + ox + Math.cos(b.a + drift) * b.r * unit * 0.62;
      const y = cy + oy + Math.sin(b.a + drift) * b.r * unit * 0.44;
      const size = b.size * unit;
      const grad = ctx.createRadialGradient(x, y, 0, x, y, size);
      grad.addColorStop(0, rgba(this.dim, b.alpha * power * (0.5 + b.depth)));
      grad.addColorStop(0.55, rgba(this.mid, b.alpha * power * 0.28));
      grad.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(x, y, size, 0, TAU);
      ctx.fill();
    }
    ctx.restore();
  }

  /**
   * buildAmbientDust, in three depth layers. The far layer is slower, smaller and
   * dimmer than the near one, which is what sells the depth. The only random
   * numbers in this file live here and in this pass there is nothing measured,
   * so nothing on screen can be a fabricated reading.
   */
  drawDust(ox, oy) {
    const { ctx, cx, cy, unit } = this;
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    ctx.fillStyle = rgba(this.dim, 0.18);
    for (const p of this.dust) {
      p.a += p.drift * (1 - p.layer * 0.28);
      const depth = 1 - p.layer * 0.26;
      const x = cx + ox + Math.cos(p.a) * p.r * unit * 0.62 * depth;
      const y = cy + oy + Math.sin(p.a) * p.r * unit * 0.44 * depth;
      ctx.globalAlpha = p.alpha * depth;
      ctx.beginPath();
      ctx.arc(x, y, p.size * depth, 0, TAU);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
    ctx.restore();
  }

  /**
   * 解析鑑定 / Analytical Appraisal: the standing-wave manifold it sweeps.
   *
   * The reference builds its manifold from `LOBES = 4` with `AMPLITUDE = 0.75`,
   * and so does this: each curve is `r + A*cos(lobes*theta)`, so the wave has four
   * lobes and four saddles, and the saddles rotate against the rings. On small
   * screens the sample count drops instead of the lobe count, because four lobes
   * is the shape and the sample count is not.
   */
  drawStandingWave(ox, oy, base, vitality) {
    const { ctx, cx, cy } = this;
    const lobes = GEOMETRY.lobes;
    const amplitude = GEOMETRY.lobeAmplitude;
    const samples = this.compact ? Math.round(GEOMETRY.waveSamples / 2) : GEOMETRY.waveSamples;
    const spread = this.fracture.level;
    ctx.save();
    ctx.translate(cx + ox, cy + oy);
    ctx.globalCompositeOperation = "lighter";
    ctx.lineWidth = 1;

    for (let i = 0; i < GEOMETRY.waveRings; i += 1) {
      const parity = i % 2 === 0 ? 1 : -1;
      const falloff = 1 - i / (GEOMETRY.waveRings + 1);
      const r0 = base * (0.5 + i * 0.34);
      const spin = this.t * 0.00021 * parity * GEOMETRY.vortexSpeed;
      ctx.beginPath();
      for (let s = 0; s < samples; s += 1) {
        const theta = (s / samples) * TAU;
        // The dissolve term scatters the lobes outward instead of fading them,
        // which is what makes `dissolve()` read as a shock and not a dimmer.
        const scatter = spread * Math.sin(theta * lobes * 2 + i * 1.7 + this.t * 0.001) * base * 0.22;
        const wave = Math.cos(theta * lobes + spin + i * 0.42) * amplitude * falloff * base * 0.24;
        const r = r0 + wave + scatter;
        const x = Math.cos(theta) * r;
        const y = Math.sin(theta) * r * 0.6;
        if (s === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.strokeStyle = i % 2 === 0 ? this.mid : this.hot;
      ctx.globalAlpha = (0.05 + falloff * 0.12) * (0.25 + vitality * 0.75);
      ctx.stroke();
    }

    // The hairlines the reference draws across the manifold: one per lobe axis.
    ctx.strokeStyle = this.dim;
    ctx.globalAlpha = 0.05 * (0.2 + vitality * 0.8);
    const reach = base * (0.5 + (GEOMETRY.waveRings - 1) * 0.34) * 1.2;
    for (let a = 0; a < lobes * 2; a += 1) {
      const theta = (a / (lobes * 2)) * TAU + this.t * 0.00012;
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.lineTo(Math.cos(theta) * reach, Math.sin(theta) * reach * 0.6);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
    ctx.restore();
  }

  /** 解析鑑定 / Analytical Appraisal: the standing-wave manifold it sweeps. */
  drawLattice(ox, oy, base) {
    const { ctx, cx, cy, unit } = this;
    const span = unit * 0.66 * (base / (unit * 0.15));
    const step = unit * 0.0125;
    const drift = this.t * 0.00004;
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    ctx.lineWidth = 1;
    ctx.strokeStyle = this.dim;
    for (let i = 0; i < GEOMETRY.latticeLines; i += 1) {
      const v = (i / (GEOMETRY.latticeLines - 1)) * 2 - 1;
      const falloff = Math.sin(Math.acos(Math.abs(v))) * 0.42 + 0.06;
      const y0 = cy + oy + v * span * 0.5;
      ctx.beginPath();
      for (let s = 0; s < GEOMETRY.latticeSamples; s += 1) {
        const u = (s / (GEOMETRY.latticeSamples - 1)) * 2 - 1;
        const x = cx + ox + u * span * 0.5;
        const taper = Math.sin(Math.acos(Math.abs(u)));
        const wave =
          Math.sin(u * 5.4 + this.t * 0.00042 + drift * 40) *
          Math.cos(v * 3.1 - this.t * 0.00027) *
          taper *
          falloff *
          step *
          2.6;
        const y = y0 + wave;
        if (s === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.globalAlpha = 0.06 + falloff * 0.1;
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
    ctx.restore();
  }

  /**
   * 森羅万象 / All of Creation. The reference builds 36 tendrils of 80 points
   * spiralling out of the singularity. Every point here is clock-driven: no
   * randomness in this pass, so nothing on screen can be a fabricated reading.
   */
  drawTendrils(ox, oy, base, vitality) {
    const { ctx, cx, cy } = this;
    const count = GEOMETRY.tendrils;
    const points = Math.min(GEOMETRY.tendrilPoints, this.compact ? 30 : 44);
    const hot = this.hot;
    const mid = this.mid;
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    ctx.lineWidth = 1;
    for (let i = 0; i < count; i += 1) {
      const phi = (i / count) * TAU;
      const heat = tendrilHeat(i, count);
      const reach = base * (1.5 + Math.sin(phi * 3 + this.t * 0.0004) * 0.35);
      const direction = i % 2 === 0 ? 1 : -1;
      ctx.beginPath();
      for (let p = 0; p < points; p += 1) {
        const frac = p / (points - 1);
        const spin = phi + frac * 2.4 + this.t * 0.00055 * direction * GEOMETRY.vortexSpeed * 1.4;
        const r = base * 0.42 + frac * reach;
        const x = cx + ox + Math.cos(spin) * r;
        const y = cy + oy + Math.sin(spin) * r * 0.62;
        if (p === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.strokeStyle = heat > 0.5 ? hot : mid;
      ctx.globalAlpha = (0.03 + heat * 0.06) * (0.25 + vitality * 0.75);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
    ctx.restore();
  }

  /**
   * 並列演算 / Parallel Calculation: rings turning at once, each on its own plane.
   *
   * `buildGyroscopicOrbitalRings` in the reference gives every ring its own
   * inclination axis and its own precession rate, so the set behaves like a
   * gyroscope instead of three circles squashed by different amounts. That is
   * what `axis` and `precess` are for, and it is the reason this is not just a
   * `scale(1, squash)`.
   */
  drawRings(ox, oy, base, vitality) {
    const { ctx, cx, cy } = this;
    const lean = this.pointer.active ? this.pointer.x * 0.12 : 0;
    ctx.save();
    ctx.translate(cx + ox, cy + oy);
    ctx.globalCompositeOperation = "lighter";
    for (const ring of GEOMETRY.rings) {
      const r = base * ring.scale;
      // Precession: the ring's own spin plus a slow wobble of its axis.
      const precess = this.t * ring.precess * 0.001;
      const squash = Math.cos(ring.tilt + Math.sin(precess) * 0.18) * 0.55 + 0.45;
      ctx.save();
      ctx.rotate(ring.axis + precess * 0.5 + lean);
      ctx.scale(1, squash);
      ctx.rotate(this.t * ring.speed * 0.001);
      ctx.beginPath();
      ctx.arc(0, 0, r, 0, TAU);
      ctx.strokeStyle = this.mid;
      ctx.globalAlpha = ring.alpha * (0.5 + vitality * 0.5);
      ctx.lineWidth = 1;
      ctx.stroke();

      ctx.setLineDash([2, 10]);
      ctx.beginPath();
      ctx.arc(0, 0, r * 1.06, 0, TAU);
      ctx.globalAlpha = ring.alpha * 0.5 * (0.5 + vitality * 0.5);
      ctx.stroke();
      ctx.setLineDash([]);

      const sweep = this.t * 0.0006;
      ctx.beginPath();
      ctx.arc(0, 0, r, sweep, sweep + 0.9);
      ctx.strokeStyle = this.hot;
      ctx.globalAlpha = 0.5 * (0.4 + vitality * 0.6);
      ctx.lineWidth = 1.6;
      ctx.stroke();
      ctx.restore();
    }
    ctx.globalAlpha = 1;
    ctx.restore();
  }

  /**
   * buildStarburstNodes. The reference glints these off a generated sprite; here
   * each node is bound to one element core (`node.core`) and only burns as bright
   * as that core's own probe allows, so eight lit nodes is a statement about the
   * backend and not decoration.
   */
  drawNodes(ox, oy, base, vitality, pulse) {
    const { ctx, cx, cy } = this;
    const lean = this.pointer.active ? this.pointer.x * 0.12 : 0;
    ctx.save();
    ctx.translate(cx + ox, cy + oy);
    ctx.globalCompositeOperation = "lighter";
    for (const node of this.nodes) {
      const ring = GEOMETRY.rings[node.ring % GEOMETRY.rings.length];
      const core = this.cores[node.core % this.cores.length];
      if (!ring || !core) continue;
      const state = core.state || "unknown";
      const alive = state === "ok";
      const degraded = state === "degraded";
      const lit = alive ? 1 : degraded ? 0.5 : 0.12;
      if (lit <= 0.12 && pulse <= 0.02) continue;

      const precess = this.t * ring.precess * 0.001;
      const squash = Math.cos(ring.tilt + Math.sin(precess) * 0.18) * 0.55 + 0.45;
      const angle =
        (node.at + ring.axis + precess * 0.5 + lean) + this.t * ring.speed * 0.001;
      const r = base * ring.scale;
      const x = Math.cos(angle) * r;
      const y = Math.sin(angle) * r * squash;
      const size = node.size * (1 + pulse * 0.5) * (alive ? 1 : degraded ? 0.8 : 0.5);
      const strength = (lit + pulse * 0.3) * (0.4 + vitality * 0.6);

      const reach = size * 7;
      ctx.globalAlpha = strength * 0.5;
      ctx.drawImage(
        haloSprite(this.hot, this.mid),
        x - reach,
        y - reach,
        reach * 2,
        reach * 2,
      );

      ctx.globalAlpha = Math.min(1, strength);
      ctx.strokeStyle = core.flash > 0 ? "#ffffff" : hsl(core.hue, 100, 78);
      ctx.lineWidth = 1;
      for (let arm = 0; arm < 4; arm += 1) {
        const a = (arm / 4) * TAU + node.at * 3;
        const len = size * (2 + Math.sin(this.t * 0.002 + node.at * 6) * 0.6);
        ctx.beginPath();
        ctx.moveTo(x + Math.cos(a) * size * 0.4, y + Math.sin(a) * size * 0.4);
        ctx.lineTo(x + Math.cos(a) * len, y + Math.sin(a) * len);
        ctx.stroke();
      }

      ctx.beginPath();
      ctx.arc(x, y, size * 0.5, 0, TAU);
      ctx.fillStyle = `rgba(255,255,255,${0.35 + strength * 0.5})`;
      ctx.fill();
    }
    ctx.globalAlpha = 1;
    ctx.restore();
  }

  coreOrbit(index, base) {
    const radius = base * (1.05 + (index % 3) * 0.29);
    const speed = 0.00016 * (index % 2 === 0 ? 1 : -0.78) * (1 + index * 0.06);
    const tilt = -0.5 + index * 0.2;
    return { radius, speed, tilt, angle: this.t * speed + (index / this.cores.length) * TAU };
  }

  drawCores(ox, oy, base, vitality, pulse) {
    const { ctx, cx, cy, unit } = this;
    ctx.save();
    ctx.translate(cx + ox, cy + oy);
    ctx.globalCompositeOperation = "lighter";

    this.cores.forEach((core, index) => {
      const orbit = this.coreOrbit(index, base);
      const squash = Math.cos(orbit.tilt) * 0.5 + 0.5;
      const x = Math.cos(orbit.angle) * orbit.radius;
      const y = Math.sin(orbit.angle) * orbit.radius * squash;
      const state = core.state || "unknown";
      const alive = state === "ok";
      const degraded = state === "degraded";
      const sat = alive ? 100 : degraded ? 85 : 12;
      const light = alive ? 68 : degraded ? 58 : 22;
      const size = unit * (alive ? 0.011 : 0.008) * (1 + pulse * 0.18);
      const throb = 1 + Math.sin(this.t * 0.004 + index) * 0.12;
      const reach = size * 9 * throb * (alive ? 1 : degraded ? 0.72 : 0.4);

      ctx.save();
      ctx.globalAlpha = alive ? 1 : degraded ? 0.72 : 0.3;
      ctx.drawImage(coreSprite(core.hue, sat, light), x - reach, y - reach, reach * 2, reach * 2);

      ctx.beginPath();
      ctx.arc(x, y, size, 0, TAU);
      ctx.fillStyle = hsl(core.hue, sat, alive ? 92 : 70, 0.95);
      ctx.fill();

      const link = ctx.createLinearGradient(0, 0, x, y);
      link.addColorStop(0, hsl(190, 100, 70, 0.22 * (0.4 + vitality * 0.6)));
      link.addColorStop(1, hsl(core.hue, sat, light, alive ? 0.5 : 0.12));
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.lineTo(x, y);
      ctx.strokeStyle = link;
      ctx.lineWidth = 1;
      ctx.stroke();

      // Starburst: the reference glints these off a generated canvas texture.
      // Here it fires only when the probe feeding this core starts answering,
      // and the size is the flash value, never a random number.
      if (core.flash > 0) {
        const streak = (this.t * 0.0022 + index * 0.4) % 1;
        ctx.strokeStyle = `rgba(255,255,255,${core.flash * (1 - streak)})`;
        ctx.lineWidth = 1;
        for (let arm = 0; arm < 4; arm += 1) {
          const a = (arm / 4) * TAU + index;
          const len = size * (2.4 + streak * 9);
          ctx.beginPath();
          ctx.moveTo(x + Math.cos(a) * size, y + Math.sin(a) * size);
          ctx.lineTo(x + Math.cos(a) * len, y + Math.sin(a) * len);
          ctx.stroke();
        }
      }
      ctx.restore();

      if (alive) {
        const beacon = (this.t * 0.0009 + index * 0.17) % 1;
        ctx.beginPath();
        ctx.arc(x * beacon, y * beacon, 2, 0, TAU);
        ctx.fillStyle = hsl(core.hue, 100, 80, 0.8 * (1 - beacon));
        ctx.fill();
      }
    });
    ctx.globalAlpha = 1;
    ctx.restore();
  }

  /**
   * The singularity, plus the geometric form the anime reflects in Rimuru's
   * eyes when the skill takes over: an eight-point mandala that gains one
   * ring per answering probe. 思考加速 / Thought Acceleration lives in the pulse
   * rate, which is this.speed, and that is a function of the state table.
   */
  drawNucleus(ox, oy, base, vitality, pulse) {
    const { ctx, cx, cy } = this;
    const breath = 1 + Math.sin(this.breath.phase * TAU) * 0.05 + pulse * 0.12;
    const r = base * breath;
    ctx.save();
    ctx.translate(cx + ox, cy + oy);
    ctx.globalCompositeOperation = "lighter";

    // UnrealBloomPass at strength 0.75 does not wash the scene out because it
    // only sees pixels already above threshold. In 2D the whole gradient is the
    // bloom, so it has to stay weak or the nucleus becomes a white blob.
    const haloR = r * 2.8;
    ctx.globalAlpha = 0.14 + vitality * 0.4;
    ctx.drawImage(haloSprite(this.hot, this.mid), -haloR, -haloR, haloR * 2, haloR * 2);
    ctx.globalAlpha = 1;

    const core = ctx.createRadialGradient(0, 0, 0, 0, 0, r);
    const lit = 0.35 + vitality * 0.65;
    core.addColorStop(0, `rgba(255,255,255,${0.75 * lit + 0.15})`);
    core.addColorStop(0.28, this.hot);
    core.addColorStop(0.7, this.mid);
    core.addColorStop(1, "rgba(0,0,0,0)");
    ctx.fillStyle = core;
    ctx.beginPath();
    ctx.arc(0, 0, r, 0, TAU);
    ctx.fill();

    this.drawMandala(r, vitality);

    ctx.beginPath();
    ctx.arc(0, 0, r * 0.42, 0, TAU);
    ctx.fillStyle = `rgba(255,255,255,${0.28 + vitality * 0.5})`;
    ctx.fill();
    ctx.restore();
  }

  drawMandala(r, vitality) {
    const { ctx } = this;
    const spokes = GEOMETRY.mandalaPoints;
    const measured = this.cores.filter((c) => c.state === "ok" || c.state === "degraded").length;
    ctx.save();
    ctx.rotate(this.t * 0.00023);
    ctx.lineWidth = 1;
    this.starPath(ctx, spokes, r * 0.92, r * 0.46, 0);
    ctx.strokeStyle = this.mid;
    ctx.globalAlpha = 0.16 + vitality * 0.3;
    ctx.stroke();

    ctx.rotate(-this.t * 0.00052);
    this.starPath(ctx, spokes, r * 0.78, r * 0.34, 0.19);
    ctx.strokeStyle = this.hot;
    ctx.globalAlpha = 0.1 + vitality * 0.24;
    ctx.stroke();

    // One ring per answering probe. Its absence is the measurement.
    ctx.strokeStyle = this.mid;
    ctx.globalAlpha = 0.14 + vitality * 0.2;
    for (let i = 0; i < measured; i += 1) {
      ctx.beginPath();
      ctx.arc(0, 0, r * (1.12 + i * 0.16), 0, TAU);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
    ctx.restore();
  }

  starPath(ctx, spokes, outer, inner, phase) {
    ctx.beginPath();
    for (let i = 0; i < spokes * 2; i += 1) {
      const a = (i / (spokes * 2)) * TAU + phase;
      const radius = i % 2 === 0 ? outer : inner;
      const x = Math.cos(a) * radius;
      const y = Math.sin(a) * radius;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.closePath();
  }

  /** 詠唱破棄 / Chant Annulment: when nothing is measured, only the ticks stay. */
  drawReticle(ox, oy, base, vitality) {
    const { ctx, cx, cy } = this;
    const r = base * 2.05;
    ctx.save();
    ctx.translate(cx + ox, cy + oy);
    ctx.rotate(this.t * 0.00004);
    ctx.strokeStyle = this.mid;
    ctx.globalAlpha = 0.16 + vitality * 0.2;
    ctx.lineWidth = 1;
    for (let i = 0; i < 48; i += 1) {
      const a = (i / 48) * TAU;
      const long = i % 4 === 0;
      const inner = r * (long ? 0.955 : 0.975);
      ctx.beginPath();
      ctx.moveTo(Math.cos(a) * inner, Math.sin(a) * inner);
      ctx.lineTo(Math.cos(a) * r, Math.sin(a) * r);
      ctx.stroke();
    }
    ctx.setLineDash([1, 6]);
    ctx.beginPath();
    ctx.arc(0, 0, r * 1.08, 0, TAU);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.globalAlpha = 1;
    ctx.restore();
  }
}

export { ELEMENT_CORES, NucleusRenderer, reducedMotion };