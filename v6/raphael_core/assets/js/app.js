/**
 * Wiring for the Raphael Core HUD.
 *
 * Responsibilities: navigation (top bar + energy rail), scroll reveal, the
 * custom cursor, the blueprints carousel, copy-to-clipboard on the terminal
 * blocks, and the polling loop that feeds api.js into the DOM and into the
 * nucleus renderer.
 *
 * Rule inherited from the backend: the DOM only ever shows values that came
 * from a probe or from this repository's own file tree. Unreachable is a
 * first-class state with its own colour and its own copy.
 */

import { ELEMENT_CORES, NucleusRenderer, reducedMotion } from "./nucleus.js";
import { AXUM_BASE, readCore, resolveBase, storeBase } from "./api.js";
import { EVOLUTION_CHAIN, GEOMETRY, RAPHAEL_SUB_SKILLS } from "./lore.js";

const SECTIONS = [
  { id: "hero", label: "01 — Nucleo" },
  { id: "core", label: "02 — Core" },
  { id: "skills", label: "03 — Raphael" },
  { id: "access", label: "04 — Access" },
  { id: "start", label: "05 — Start" },
  { id: "blueprints", label: "06 — Blueprints" },
  { id: "end", label: "07 — End" },
];

const BLUEPRINTS = [
  {
    tag: "identidad",
    title: "Nucleo vivo",
    body: "Responde /health con el estado del proceso y su modo de despliegue, y /health/detailed con la sonda real de base de datos, Redis y modelo local.",
    path: "backend/main.py",
  },
  {
    tag: "enjambre",
    title: "APEX swarm",
    body: "Enjambre multi-agente con ciclo de vida tipado. El dashboard recibe por agente estado derivado del latido, tarea en curso y contadores.",
    path: "backend/agent_swarm.py",
  },
  {
    tag: "catalogo",
    title: "12 roles APEX",
    body: "Catalogo de roles con color, icono, descripcion y capacidades. Es lo que enciende las orbitas del nucleo.",
    path: "backend/agents/agent_roles.py",
  },
  {
    tag: "estado",
    title: "Estado del enjambre",
    body: "Contadores del enjambre: agentes por rol, cola, bus, planes e historico. Ojo: tiene dos handlers con la misma ruta y gana el primero que se registro.",
    path: "backend/swarm_routes.py",
  },
  {
    tag: "orquestador",
    title: "Orquestador de tareas",
    body: "Enruta cada tarea, recupera contexto, ejecuta con el modelo seleccionado y conserva en memoria el modelo usado.",
    path: "backend/agents/orchestrator.py",
  },
  {
    tag: "router",
    title: "Router de proveedores",
    body: "AIRouter con ocho proveedores OpenAI-compatibles, prioridad, timeout y modelo por defecto. El mas barato es Groq y el unico local es Ollama.",
    path: "backend/ai_router.py",
  },
  {
    tag: "memoria",
    title: "Puente de memoria LLM",
    body: "Puente entre el backend y los adaptadores de LLM. Es la dependencia que obligo a trackear todo el paquete backend/llm.",
    path: "backend/llm/memory_bridge.py",
  },
  {
    tag: "workflows",
    title: "Motor de workflows",
    body: "Motor de workflows con su propio singleton. Antes colisionaba con el motor de reglas y /api/chat devolvia 500.",
    path: "backend/automation/workflow_engine.py",
  },
  {
    tag: "reglas",
    title: "Motor de reglas",
    body: "Doce metodos de reglas sobre el singleton automation_engine. Es el motor que usa el backend al enrutar una peticion.",
    path: "backend/automation/engine.py",
  },
  {
    tag: "gateway",
    title: "Gateway Axum",
    body: "Gateway en Rust. Los endpoints sin implementar devuelven 501 y la telemetria no medida se marca como unavailable.",
    path: "v6/axum-poc/src/main.rs",
  },
  {
    tag: "computer-use",
    title: "Nucleo computer-use",
    body: "Captura, descripcion de pantalla y ejecucion de acciones. Los cinco endpoints sin implementacion responden 501, no datos falsos.",
    path: "v6/axum-poc/src/computer.rs",
  },
  {
    tag: "visual",
    title: "Orb 3D",
    body: "Orb de siete capas con doce particulas, anillos y ráfagas. Base visual del nucleo que se ve detras de esta pagina.",
    path: "v5/src/components/OrbVisual/OrbVisual.tsx",
  },
  {
    tag: "mobile",
    title: "Estado en movil",
    body: "Modelos Dart del cliente movil. Aun sin verificar: no ha pasado flutter analyze. Declarado en STATUS.md.",
    path: "v6/airi_mobile/lib/models/pc_state.dart",
  },
];

const REFRESH_MS = 10000;

/**
 * Boot lines. Every one of these is a fact about this repository, checked at
 * load: no invented latencies, no fake "connected in 12ms". If the numbers
 * change the lines change with them, and the last line says what it actually
 * found rather than what it hoped to find.
 */
const BOOT_LINES = [
  "ARIA RAPHAEL CORE // nucleo de arquitectura elemental",
  "sitio estatico: sin bundler, sin npm, sin WebGL",
  "element cores definidos: 6",
  `onda estacionaria: ${GEOMETRY.lobes} lobulos`,
  `anillos giroscopicos: ${GEOMETRY.rings.length}`,
  `nodos de destello: ${GEOMETRY.nodes.length}`,
  `endpoints ARIA enlazados: ${ELEMENT_CORES.length}`,
  `blueprints verificados en el arbol: ${BLUEPRINTS.length}`,
  `sub-skills de Raphael declaradas: ${RAPHAEL_SUB_SKILLS.length}`,
  "medicion en curso...",
];

const els = {
  canvas: document.getElementById("nucleus-canvas"),
  rail: document.getElementById("rail"),
  railHead: document.getElementById("rail-head"),
  topnav: document.querySelector(".topnav"),
  telemetry: document.getElementById("telemetry"),
  cores: document.getElementById("cores"),
  skills: document.getElementById("skills-grid"),
  stageKanji: document.getElementById("stage-kanji"),
  stageLabel: document.getElementById("stage-label"),
  stageTrack: document.getElementById("stage-track"),
  pill: document.getElementById("backend-pill"),
  pillLabel: document.getElementById("backend-label"),
  apiBase: document.getElementById("api-base"),
  apiApply: document.getElementById("api-apply"),
  measuredAt: document.getElementById("measured-at"),
  footerState: document.getElementById("footer-state"),
  track: document.getElementById("carousel-track"),
  carPrev: document.getElementById("car-prev"),
  carNext: document.getElementById("car-next"),
  carCount: document.getElementById("car-count"),
  boot: document.getElementById("boot"),
  bootLines: document.getElementById("boot-lines"),
  halo: document.querySelector(".cursor-halo"),
  dot: document.querySelector(".cursor-dot"),
};

const renderer = new NucleusRenderer(els.canvas, ELEMENT_CORES);

/* ---------- navigation ---------- */

function buildRail() {
  const nodes = SECTIONS.map((section) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "rail-node";
    btn.dataset.target = section.id;
    btn.dataset.state = "unavailable";
    btn.innerHTML = `<span class="rail-node__label">${section.label}</span><span class="rail-node__dot"></span>`;
    els.rail.append(btn);
    return btn;
  });

  const onClick = (event) => {
    const target = event.target.closest("[data-target]");
    if (!target) return;
    const section = document.getElementById(target.dataset.target);
    if (section) section.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "start" });
  };

  els.rail.addEventListener("click", onClick);
  els.topnav.addEventListener("click", onClick);
  document.addEventListener("click", (event) => {
    const target = event.target.closest("button[data-target]");
    if (!target || els.rail.contains(target) || els.topnav.contains(target)) return;
    const section = document.getElementById(target.dataset.target);
    if (section) section.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth" });
  });

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        nodes.forEach((node) => {
          node.setAttribute("aria-current", String(node.dataset.target === entry.target.id));
        });
        els.topnav.querySelectorAll("button").forEach((btn) => {
          btn.setAttribute("aria-current", String(btn.dataset.target === entry.target.id));
        });
      });
    },
    { rootMargin: "-45% 0px -45% 0px" },
  );
  SECTIONS.forEach((section) => {
    const node = document.getElementById(section.id);
    if (node) observer.observe(node);
  });

  return { nodes, observer };
}

/* ---------- reveal ---------- */

/**
 * Split-letter title, the technique off the buildonaut hangar hero, where every
 * glyph of "Welcome to the Buildonaut Hangar" is its own inline-block with a
 * staggered delay. Here the text is split into word spans and only the words
 * cascade, because 26 letters is a lot of motion for a title nobody asked to
 * dance. The original string stays in `aria-label`, so screen readers get the
 * sentence and not the gaps.
 */
function buildSplitTitle() {
  const target = document.querySelector("[data-split]");
  if (!target) return;
  const original = target.textContent.trim();
  const words = original.split(/\s+/);
  target.textContent = "";
  target.dataset.split = "done";
  words.forEach((word, wordIndex) => {
    const span = document.createElement("span");
    span.className = "split__word";
    span.style.setProperty("--i", String(wordIndex));
    for (const char of word) {
      const letter = document.createElement("span");
      letter.className = "split__char";
      letter.setAttribute("aria-hidden", "true");
      letter.textContent = char;
      span.append(letter);
    }
    const gap = document.createElement("span");
    gap.className = "split__gap";
    gap.setAttribute("aria-hidden", "true");
    gap.textContent = " ";
    target.append(span, gap);
  });
  target.setAttribute("aria-label", original);
  if (reducedMotion) target.dataset.split = "static";
}

/* ---------- compact mode ---------- */

/**
 * The reference reactor ships `setCompactMode`, which drops its sample counts on
 * small screens. Same idea here: below 760px the standing wave and the tendrils
 * sample every other point, and the four lobes stay because they are the shape.
 */
function bindCompactMode() {
  const query = matchMedia("(max-width: 760px)");
  const apply = () => renderer.setCompactMode(query.matches);
  if (typeof query.addEventListener === "function") query.addEventListener("change", apply);
  else query.addListener(apply);
  apply();
}

function buildReveal() {
  const targets = document.querySelectorAll(".reveal");
  if (!("IntersectionObserver" in window)) {
    targets.forEach((el) => el.classList.add("is-in"));
    return;
  }
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-in");
        observer.unobserve(entry.target);
      });
    },
    { threshold: 0, rootMargin: "0px 0px -12% 0px" },
  );
  targets.forEach((el) => observer.observe(el));
}

/* ---------- cursor ---------- */

function buildCursor() {
  const fine = matchMedia("(pointer: fine)").matches;
  if (!fine) return;
  let x = innerWidth / 2;
  let y = innerHeight / 2;
  let hx = x;
  let hy = y;
  let visible = false;

  addEventListener(
    "pointermove",
    (event) => {
      x = event.clientX;
      y = event.clientY;
      renderer.setPointer((x / innerWidth) * 2 - 1, (y / innerHeight) * 2 - 1);
      if (visible) return;
      visible = true;
      hx = x;
      hy = y;
      if (reducedMotion) return;
      els.halo.style.opacity = "0.85";
      els.dot.style.opacity = "1";
      document.body.style.cursor = "none";
    },
    { passive: true },
  );

  if (reducedMotion) return;
  const tick = () => {
    hx += (x - hx) * 0.18;
    hy += (y - hy) * 0.18;
    els.halo.style.transform = `translate(${hx - 10}px, ${hy - 10}px)`;
    els.dot.style.transform = `translate(${x - 2}px, ${y - 2}px)`;
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

/**
 * Boot terminal. The pattern comes from the buildonaut splash, but the copy
 * refuses to fake telemetry: every line is a count this page can verify.
 */
function buildBoot() {
  if (!els.boot || !els.bootLines || reducedMotion) {
    if (els.boot) els.boot.remove();
    return;
  }
  let line = 0;
  let char = 0;
  const tick = () => {
    if (line >= BOOT_LINES.length) {
      els.boot.dataset.done = "true";
      return;
    }
    const text = BOOT_LINES[line];
    char += 2;
    if (char >= text.length) {
      char = text.length;
      line += 1;
      els.bootLines.append(`${text}\n`);
      setTimeout(tick, 90);
      return;
    }
    els.bootLines.textContent = `${BOOT_LINES.slice(0, line).join("\n")}\n${text.slice(0, char)}`;
    setTimeout(tick, 12);
  };
  els.bootLines.textContent = "";
  setTimeout(tick, 140);
  setTimeout(() => {
    els.boot.dataset.done = "true";
  }, 160 + BOOT_LINES.length * 260);
}

/* ---------- copy ---------- */

function buildCopy() {
  document.querySelectorAll(".terminal[data-copy]").forEach((block) => {
    block.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(block.textContent.trim());
        block.dataset.copied = "true";
        setTimeout(() => delete block.dataset.copied, 1200);
      } catch {
        block.dataset.copied = "false";
        block.title = "el navegador no permitio copiar: selecciona el texto a mano";
        setTimeout(() => delete block.dataset.copied, 2400);
      }
    });
  });
}

/* ---------- carousel ---------- */

function buildCarousel() {
  BLUEPRINTS.forEach((bp) => {
    const card = document.createElement("article");
    card.className = "blueprint";
    card.innerHTML = `
      <p class="blueprint__tag"><span class="tag tag--measured">${bp.tag}</span> fuente: repositorio</p>
      <h3 class="blueprint__title">${bp.title}</h3>
      <p class="blueprint__body">${bp.body}</p>
      <code class="blueprint__path">${bp.path}</code>`;
    els.track.append(card);
  });

  let index = 0;
  const perView = () => {
    const card = els.track.firstElementChild;
    const viewport = els.track.parentElement;
    if (!card || !viewport) return 1;
    const cardWidth = card.getBoundingClientRect().width;
    if (!cardWidth) return 1;
    return Math.max(1, Math.floor((viewport.getBoundingClientRect().width + 16) / cardWidth));
  };
  const maxIndex = () => Math.max(0, BLUEPRINTS.length - perView());

  const paint = () => {
    const card = els.track.firstElementChild;
    if (!card) return;
    const width = card.getBoundingClientRect().width + 16;
    index = Math.min(index, maxIndex());
    els.track.style.transform = `translateX(${-index * width}px)`;
    els.carPrev.disabled = index === 0;
    els.carNext.disabled = index >= maxIndex();
    els.carCount.textContent = `${String(index + 1).padStart(2, "0")} / ${String(BLUEPRINTS.length).padStart(2, "0")}`;
  };

  els.carPrev.addEventListener("click", () => {
    index = Math.max(0, index - 1);
    paint();
  });
  els.carNext.addEventListener("click", () => {
    index = Math.min(maxIndex(), index + 1);
    paint();
  });
  addEventListener("resize", paint);
  paint();
}

/* ---------- render ---------- */

function node(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}

const STATE_LABEL = { ok: "measured", degraded: "degraded", unavailable: "unavailable" };

/**
 * The tag reports the endpoint's own `data_source`, not our verdict. /health
 * answers 200 and the process is demonstrably alive, but it declares
 * `data_source: "unavailable"` because it probes nothing, so labelling it
 * "measured" would repeat exactly the lie the backend refuses to tell.
 */
function stateTag(state, dataSource) {
  const key = dataSource === "unavailable" && state === "ok" ? "unavailable" : STATE_LABEL[state] ?? "unavailable";
  return node("span", `tag tag--${key}`, key);
}

/**
 * One readable value per sub-skill, all derived from the same probe results the
 * rest of the page uses. When nothing was measured the value says so instead of
 * falling back to a placeholder number.
 */
function subSkillReadings(data) {
  const total = data.cores.length;
  const measured = data.cores.filter((c) => c.data_source === "measured").length;
  const answering = data.cores.filter((c) => c.state === "ok" || c.state === "degraded");
  const silent = data.cores.filter((c) => c.state === "unavailable");
  const latencies = data.cores
    .map((c) => c.latency_ms)
    .filter((ms) => typeof ms === "number" && Number.isFinite(ms));
  const mean = latencies.length
    ? Math.round(latencies.reduce((a, b) => a + b, 0) / latencies.length)
    : null;
  return {
    "thought-acceleration": {
      value: mean === null ? "—" : `${mean} ms`,
      note: mean === null
        ? "sin latencia medida todavia"
        : `media de ${latencies.length} sondas que respondieron`,
    },
    "analytical-appraisal": {
      value: `${answering.length}/${total}`,
      note: `${data.cores.filter((c) => c.state === "ok").length} ok · ${
        data.cores.filter((c) => c.state === "degraded").length
      } degraded · ${silent.length} unavailable`,
    },
    "parallel-calculation": {
      value: `${total} en paralelo`,
      note: "las seis sondas salen en el mismo Promise.all, no en serie",
    },
    "chant-annulment": {
      value: silent.length === 0 ? "0 apagados" : `${silent.length} apagado${silent.length === 1 ? "" : "s"}`,
      note: silent.length === 0
        ? "todo respondio"
        : silent.map((c) => c.detail || c.id).join(" · "),
    },
    "all-of-creation": {
      value: `${measured}/${total} anillos`,
      note: "un anillo del mandala por sonda medida",
    },
    alteration: {
      value: `${measured}/${total}`,
      note: "sondas con data_source measured",
    },
  };
}

function renderSkills(data) {
  const readings = subSkillReadings(data);
  els.skills.replaceChildren();
  RAPHAEL_SUB_SKILLS.forEach((skill) => {
    const reading = readings[skill.id] ?? { value: "—", note: "sin lectura" };
    const card = node("article", "skill");
    card.dataset.geometry = skill.geometry;
    card.append(
      node("p", "skill__kanji", skill.kanji),
      node("h3", "skill__label", skill.label),
      node("p", "skill__romaji", skill.romaji),
    );
    const foot = node("div", "skill__foot");
    foot.append(node("b", "skill__value", reading.value), node("span", "skill__note", reading.note));
    card.append(foot);
    els.skills.append(card);
  });
}

function renderStage(data) {
  const total = data.cores.length;
  const measured = data.cores.filter((c) => c.data_source === "measured").length;
  renderer.setStage(measured, total);
  const stage = EVOLUTION_CHAIN.find((s) => s.id === renderer.stage) ?? EVOLUTION_CHAIN[0];
  els.stageKanji.textContent = stage.kanji;
  els.stageLabel.textContent = stage.label;
  els.stageTrack.replaceChildren();
  EVOLUTION_CHAIN.forEach((rung) => {
    const item = node("li", "stage__rung");
    item.dataset.reached = String(EVOLUTION_CHAIN.indexOf(rung) <= EVOLUTION_CHAIN.indexOf(stage));
    item.dataset.current = String(rung.id === stage.id);
    item.append(node("span", null, rung.kanji), node("b", null, rung.label));
    els.stageTrack.append(item);
  });
}

function renderTelemetry(data) {
  els.telemetry.replaceChildren();
  data.cores.forEach((core) => {
    const row = node("div", "telemetry__row");
    row.dataset.state = core.state;
    row.append(
      node("span", "telemetry__led"),
      node("span", "telemetry__key", core.id),
    );
    const value = node("span", "telemetry__value");
    value.append(document.createTextNode(core.headline), document.createTextNode(" "));
    value.append(stateTag(core.state, core.data_source));
    row.append(value);
    const noteParts = [core.endpoint];
    if (core.data_source) noteParts.push(`data_source: ${core.data_source}`);
    if (core.latency_ms !== null && core.latency_ms !== undefined) noteParts.push(`${core.latency_ms} ms`);
    if (core.detail) noteParts.push(core.detail);
    row.append(node("span", "telemetry__note", noteParts.join(" · ")));
    els.telemetry.append(row);
  });
}

function extraRows(core) {
  const rows = [];
  if (core.id === "water" && core.checks.length) {
    core.checks.forEach((check) => {
      rows.push([check.key, check.value]);
    });
  }
  if (core.id === "earth" && core.agents.length) {
    core.agents.slice(0, 6).forEach((agent) => {
      rows.push([
        `${agent.icon} ${agent.name}`,
        `${agent.status}${agent.tasks_completed === null ? "" : ` · ${agent.tasks_completed} tareas`}`,
      ]);
    });
  }
  if (core.id === "wind" && core.counters.length) {
    core.counters.slice(0, 6).forEach((counter) => {
      rows.push([counter.key, String(counter.value)]);
    });
  }
  if (core.id === "light" && core.roles.length) {
    core.roles.slice(0, 6).forEach((role) => {
      rows.push([`${role.icon} ${role.name}`, role.role]);
    });
  }
  if (core.id === "shadow" && core.signals.length) {
    core.signals.forEach((signal) => {
      rows.push([signal.key, signal.value]);
    });
  }
  return rows;
}

function renderCores(data) {
  els.cores.replaceChildren();
  data.cores.forEach((core) => {
    const spec = ELEMENT_CORES.find((c) => c.id === core.id);
    const card = node("article", "core-card");
    card.dataset.state = core.state;
    card.style.setProperty("--hue", String(spec.hue));

    const head = node("div", "core-card__head");
    head.append(node("h3", "core-card__name", spec.label), stateTag(core.state, core.data_source));
    card.append(head);
    card.append(node("p", "core-card__system", core.headline));
    card.append(node("code", "core-card__endpoint", core.endpoint));

    const rows = extraRows(core);
    if (rows.length) {
      const list = node("div", "core-card__rows");
      rows.forEach(([key, value]) => {
        const row = node("div", "core-card__row");
        row.append(node("span", null, key), node("b", null, value));
        list.append(row);
      });
      card.append(list);
    }

    const notes = [];
    if (core.service) notes.push(core.service);
    if (core.detail) notes.push(core.detail);
    if (core.data_source) notes.push(`data_source: ${core.data_source}`);
    if (core.latency_ms !== null && core.latency_ms !== undefined) notes.push(`${core.latency_ms} ms`);
    if (notes.length) card.append(node("p", "core-card__detail", notes.join(" · ")));

    els.cores.append(card);
  });
}

function renderStatusPill(data, rail) {
  const total = data.cores.length;
  const alive = data.cores.filter((core) => core.state === "ok").length;
  const degraded = data.cores.filter((core) => core.state === "degraded").length;
  // Counted by what the backend itself measured, not by what answered 200:
  // /health declares data_source "unavailable", so it never counts as measured.
  const measured = data.cores.filter((core) => core.data_source === "measured").length;
  const state = measured === total ? "measured" : alive + degraded > 0 ? "degraded" : "unavailable";
  const label =
    alive + degraded === 0
      ? "sin conexión"
      : `${measured}/${total} medidos · ${alive + degraded} responden`;

  els.pill.dataset.state = state;
  els.pillLabel.textContent = label;
  els.measuredAt.textContent = new Date(data.measured_at).toLocaleString();

  data.cores.forEach((core) => renderer.setCoreState(core.id, core.state));
  renderer.setVitality(measured / total);
  const nextState = measured === total ? "online" : measured > 0 ? "degraded" : "unavailable";
  if (nextState !== renderer.state) renderer.triggerPulse(0.7);
  renderer.setState(nextState);
  renderStage(data);
  renderSkills(data);

  // Read renderer.state only after setState, or the footer reports the state the
  // nucleus is leaving rather than the one it just entered.
  els.footerState.textContent = `${data.base} · ${label} · nucleo ${renderer.state} · ${new Date(data.measured_at).toLocaleTimeString()}`;

  const accessNode = rail.nodes[SECTIONS.findIndex((section) => section.id === "access")];
  if (accessNode) accessNode.dataset.state = state;
  const skillsNode = rail.nodes[SECTIONS.findIndex((section) => section.id === "skills")];
  if (skillsNode) skillsNode.dataset.state = state;
}

/* ---------- loop ---------- */

let inFlight = false;

async function refresh(rail) {
  if (inFlight) return;
  inFlight = true;
  els.pill.dataset.state = "probing";
  renderer.setState("scanning");
  try {
    const data = await readCore(els.apiBase.value.trim() || resolveBase());
    renderTelemetry(data);
    renderCores(data);
    renderStatusPill(data, rail);
  } finally {
    inFlight = false;
  }
}

function boot() {
  renderer.mount();

  const rail = buildRail();
  buildReveal();
  buildSplitTitle();
  buildCursor();
  buildCopy();
  buildCarousel();
  buildBoot();
  bindCompactMode();

  const base = resolveBase();
  els.apiBase.value = base;
  els.apiBase.placeholder = base || AXUM_BASE;

  const run = () => refresh(rail);
  els.apiApply.addEventListener("click", () => {
    const value = els.apiBase.value.trim();
    if (!value) return;
    storeBase(value);
    run();
  });
  els.apiBase.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    els.apiApply.click();
  });

  /*
   * Public surface. The reference orb is driven from outside through
   * `window.setBrahmaState` and friends; this HUD now answers to the same shape so
   * another surface (Electron, a test, the console) can drive the core without
   * importing anything. `refresh()` re-runs the six probes and is the only way to
   * change what the HUD claims: the controls can move pixels, never readings.
   */
  globalThis.ARIA = {
    nucleus: renderer.controls(),
    cores: ELEMENT_CORES,
    subSkills: RAPHAEL_SUB_SKILLS,
    refresh: run,
    get state() {
      return { nucleus: renderer.state, stage: renderer.stage, base: els.apiBase.value.trim() };
    },
  };

  run();
  setInterval(run, REFRESH_MS);
}

boot();