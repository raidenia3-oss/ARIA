/**
 * Nucleus renderer: the Raphael core and its element cores.
 *
 * Canvas 2D on purpose: no bundler, no vendored WebGL runtime, works from
 * `file://` and from a static host. The look is borrowed from two references
 * (brahma-evo "Quantum Core Resonator" standing-wave lattice and blooming
 * lobes, buildonaut "Hangar" dark display type) and re-mapped onto ARIA's
 * real subsystems.
 *
 * Honesty rule: a core never glows on its own. It glows only when a probe in
 * api.js reports a measured value for the subsystem it is bound to.
 */

const TAU = Math.PI * 2;

const ELEMENT_CORES = [
  { id: "fire", label: "FUEGO", system: "Nucleo vivo", endpoint: "/health", hue: 18 },
  { id: "water", label: "AGUA", system: "Dependencias", endpoint: "/health/detailed", hue: 192 },
  { id: "earth", label: "TIERRA", system: "Enjambre APEX", endpoint: "/api/swarm/agents/status", hue: 96 },
  { id: "wind", label: "VIENTO", system: "Despacho", endpoint: "/api/swarm/metrics", hue: 158 },
  { id: "light", label: "LUZ", system: "Catalogo de roles", endpoint: "/api/swarm/roles", hue: 44 },
  { id: "shadow", label: "SOMBRA", system: "Estado del enjambre", endpoint: "/api/swarm/status", hue: 282 },
];

const LATTICE_LINES = 54;
const LATTICE_SAMPLES = 120;
const DUST_COUNT = 150;

const reducedMotion =
  typeof matchMedia === "function" &&
  matchMedia("(prefers-reduced-motion: reduce)").matches;

function hsl(h, s, l, a = 1) {
  return `hsla(${h}, ${s}%, ${l}%, ${a})`;
}

class NucleusRenderer {
  constructor(canvas, cores) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.cores = cores;
    this.dust = [];
    this.t = 0;
    this.frame = 0;
    this.running = false;
    this.breath = { phase: 0, level: 0, target: 0 };
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
    this.dust = Array.from({ length: DUST_COUNT }, () => ({
      a: Math.random() * TAU,
      r: 0.18 + Math.random() * 0.82,
      size: 0.4 + Math.random() * 1.4,
      drift: (Math.random() - 0.5) * 0.0004,
      alpha: 0.1 + Math.random() * 0.45,
    }));
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
    if (core) core.state = state;
  }

  loop(now) {
    if (!this.running) return;
    const dt = Math.min(64, now - this.last);
    this.last = now;
    this.t += dt;
    this.breath.phase += dt * 0.0009;
    const diff = this.breath.target - this.breath.level;
    this.breath.level += diff * Math.min(1, dt * 0.0016);
    this.draw();
    requestAnimationFrame(this.loop);
  }

  draw() {
    const { ctx, cx, cy, unit, t } = this;
    ctx.clearRect(0, 0, this.w, this.h);
    this.drawDust();
    this.drawLattice();
    const vitality = this.breath.level;
    this.drawRings(vitality);
    this.drawCores(vitality);
    this.drawNucleus(vitality);
    this.drawReticle(vitality);
  }

  drawDust() {
    const { ctx, cx, cy, unit } = this;
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    for (const p of this.dust) {
      p.a += p.drift;
      const x = cx + Math.cos(p.a) * p.r * unit * 0.62;
      const y = cy + Math.sin(p.a) * p.r * unit * 0.44;
      ctx.beginPath();
      ctx.arc(x, y, p.size, 0, TAU);
      ctx.fillStyle = `rgba(0, 240, 255, ${p.alpha * 0.5})`;
      ctx.fill();
    }
    ctx.restore();
  }

  /** Standing-wave manifold: polylines whose amplitude falls off at the rim. */
  drawLattice() {
    const { ctx, cx, cy, unit } = this;
    const span = unit * 0.66;
    const step = unit * 0.0125;
    const drift = this.t * 0.00004;
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    ctx.lineWidth = 1;
    for (let i = 0; i < LATTICE_LINES; i += 1) {
      const v = (i / (LATTICE_LINES - 1)) * 2 - 1;
      const falloff = Math.sin(Math.acos(Math.abs(v))) * 0.42 + 0.06;
      const y0 = cy + v * span * 0.5;
      ctx.beginPath();
      for (let s = 0; s < LATTICE_SAMPLES; s += 1) {
        const u = (s / (LATTICE_SAMPLES - 1)) * 2 - 1;
        const x = cx + u * span * 0.5;
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
      ctx.strokeStyle = `rgba(0, 240, 255, ${0.05 + falloff * 0.09})`;
      ctx.stroke();
    }
    ctx.restore();
  }

  drawRings(vitality) {
    const { ctx, cx, cy, unit } = this;
    const base = unit * 0.15;
    const rings = [
      { r: base * 1.0, tilt: -0.22, speed: 0.00012, alpha: 0.3 },
      { r: base * 1.32, tilt: 0.34, speed: -0.00008, alpha: 0.22 },
      { r: base * 1.66, tilt: -0.08, speed: 0.00005, alpha: 0.16 },
    ];
    ctx.save();
    ctx.translate(cx, cy);
    for (const ring of rings) {
      const rot = this.t * ring.speed;
      ctx.save();
      ctx.rotate(rot);
      ctx.scale(1, Math.cos(ring.tilt) * 0.55 + 0.45);
      ctx.beginPath();
      ctx.arc(0, 0, ring.r, 0, TAU);
      ctx.strokeStyle = `rgba(0, 240, 255, ${ring.alpha * (0.5 + vitality * 0.5)})`;
      ctx.lineWidth = 1;
      ctx.stroke();

      ctx.setLineDash([2, 10]);
      ctx.beginPath();
      ctx.arc(0, 0, ring.r * 1.06, 0, TAU);
      ctx.strokeStyle = `rgba(0, 240, 255, ${ring.alpha * 0.5})`;
      ctx.stroke();
      ctx.setLineDash([]);

      const sweep = this.t * 0.0006;
      ctx.beginPath();
      ctx.arc(0, 0, ring.r, sweep, sweep + 0.9);
      ctx.strokeStyle = hsl(190, 100, 70, 0.5 * (0.4 + vitality * 0.6));
      ctx.lineWidth = 1.6;
      ctx.stroke();
      ctx.restore();
    }
    ctx.restore();
  }

  coreOrbit(core, index) {
    const count = this.cores.length;
    const base = this.unit * 0.15;
    const radius = base * (1.05 + (index % 3) * 0.29);
    const speed = 0.00016 * (index % 2 === 0 ? 1 : -0.78) * (1 + index * 0.06);
    const tilt = -0.5 + index * 0.2;
    return { radius, speed, tilt, angle: this.t * speed + (index / count) * TAU };
  }

  corePosition(core, index) {
    const orbit = this.coreOrbit(core, index);
    const squash = Math.cos(orbit.tilt) * 0.5 + 0.5;
    const x = Math.cos(orbit.angle) * orbit.radius;
    const y = Math.sin(orbit.angle) * orbit.radius * squash;
    const depth = (Math.sin(orbit.angle) + 1) / 2;
    return { x, y, squash, depth, orbit };
  }

  drawCores(vitality) {
    const { ctx, cx, cy } = this;
    ctx.save();
    ctx.translate(cx, cy);
    ctx.globalCompositeOperation = "lighter";

    this.cores.forEach((core, index) => {
      const pos = this.corePosition(core, index);
      const state = core.state || "unknown";
      const alive = state === "ok";
      const degraded = state === "degraded";
      const light = alive ? 68 : degraded ? 58 : 22;
      const sat = alive ? 100 : degraded ? 85 : 12;
      const size = this.unit * (alive ? 0.011 : 0.008);
      const pulse = 1 + Math.sin(this.t * 0.004 + index) * 0.12;

      ctx.save();
      ctx.globalCompositeOperation = "lighter";
      const grad = ctx.createRadialGradient(pos.x, pos.y, 0, pos.x, pos.y, size * 9 * pulse);
      grad.addColorStop(0, hsl(core.hue, sat, 92, 0.95));
      grad.addColorStop(0.22, hsl(core.hue, sat, light, 0.55));
      grad.addColorStop(1, hsl(core.hue, sat, light, 0));
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, size * 9 * pulse, 0, TAU);
      ctx.fill();

      ctx.beginPath();
      ctx.arc(pos.x, pos.y, size, 0, TAU);
      ctx.fillStyle = hsl(core.hue, sat, alive ? 92 : 70, 0.95);
      ctx.fill();

      const link = ctx.createLinearGradient(0, 0, pos.x, pos.y);
      link.addColorStop(0, hsl(190, 100, 70, 0.22 * (0.4 + vitality * 0.6)));
      link.addColorStop(1, hsl(core.hue, sat, light, alive ? 0.5 : 0.12));
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.lineTo(pos.x, pos.y);
      ctx.strokeStyle = link;
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.restore();

      if (alive) {
        const beacon = (this.t * 0.0009 + index * 0.17) % 1;
        const bx = pos.x * beacon;
        const by = pos.y * beacon;
        ctx.beginPath();
        ctx.arc(bx, by, 2, 0, TAU);
        ctx.fillStyle = hsl(core.hue, 100, 80, 0.8 * (1 - beacon));
        ctx.fill();
      }
    });
    ctx.restore();
  }

  drawNucleus(vitality) {
    const { ctx, cx, cy, unit } = this;
    const base = unit * 0.15;
    const breath = 1 + Math.sin(this.breath.phase * TAU) * 0.05;
    const r = base * breath;
    ctx.save();
    ctx.translate(cx, cy);
    ctx.globalCompositeOperation = "lighter";

    const halo = ctx.createRadialGradient(0, 0, r * 0.2, 0, 0, r * 3.4);
    halo.addColorStop(0, hsl(190, 100, 60, 0.3 * (0.25 + vitality * 0.75)));
    halo.addColorStop(0.45, hsl(190, 100, 50, 0.1 * (0.25 + vitality * 0.75)));
    halo.addColorStop(1, "rgba(0,0,0,0)");
    ctx.fillStyle = halo;
    ctx.beginPath();
    ctx.arc(0, 0, r * 3.4, 0, TAU);
    ctx.fill();

    for (let lobe = 0; lobe < 4; lobe += 1) {
      const a = this.t * 0.00023 + (lobe / 4) * TAU;
      const ox = Math.cos(a) * r * 0.52;
      const oy = Math.sin(a) * r * 0.34;
      const lr = r * (0.62 + Math.sin(this.t * 0.0016 + lobe) * 0.09);
      const g = ctx.createRadialGradient(ox, oy, 0, ox, oy, lr);
      g.addColorStop(0, hsl(186, 100, 78, 0.5 * (0.3 + vitality * 0.7)));
      g.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(ox, oy, lr, 0, TAU);
      ctx.fill();
    }

    const core = ctx.createRadialGradient(0, 0, 0, 0, 0, r);
    const hot = 0.35 + vitality * 0.65;
    core.addColorStop(0, `rgba(255,255,255,${0.75 * hot + 0.15})`);
    core.addColorStop(0.28, hsl(186, 100, 72, 0.85 * hot + 0.1));
    core.addColorStop(0.7, hsl(190, 100, 45, 0.35 * hot + 0.05));
    core.addColorStop(1, "rgba(0,0,0,0)");
    ctx.fillStyle = core;
    ctx.beginPath();
    ctx.arc(0, 0, r, 0, TAU);
    ctx.fill();

    ctx.beginPath();
    ctx.arc(0, 0, r * 0.42, 0, TAU);
    ctx.fillStyle = `rgba(255,255,255,${0.28 + vitality * 0.5})`;
    ctx.fill();
    ctx.restore();
  }

  drawReticle(vitality) {
    const { ctx, cx, cy, unit } = this;
    const r = unit * 0.15 * 2.05;
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(this.t * 0.00004);
    ctx.strokeStyle = hsl(190, 100, 70, 0.16 + vitality * 0.2);
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
    ctx.restore();
  }
}

export { ELEMENT_CORES, NucleusRenderer, reducedMotion };