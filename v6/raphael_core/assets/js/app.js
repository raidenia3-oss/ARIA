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

const SECTIONS = [
  { id: "hero", label: "01 — Nucleo" },
  { id: "core", label: "02 — Core" },
  { id: "access", label: "03 — Access" },
  { id: "start", label: "04 — Start" },
  { id: "blueprints", label: "05 — Blueprints" },
  { id: "end", label: "06 — End" },
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

const els = {
  canvas: document.getElementById("nucleus-canvas"),
  rail: document.getElementById("rail"),
  railHead: document.getElementById("rail-head"),
  topnav: document.querySelector(".topnav"),
  telemetry: document.getElementById("telemetry"),
  cores: document.getElementById("cores"),
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
  if (reducedMotion || !matchMedia("(pointer: fine)").matches) return;
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
      if (!visible) {
        visible = true;
        hx = x;
        hy = y;
        els.halo.style.opacity = "0.85";
        els.dot.style.opacity = "1";
      }
      document.body.style.cursor = "none";
    },
    { passive: true },
  );

  const tick = () => {
    hx += (x - hx) * 0.18;
    hy += (y - hy) * 0.18;
    els.halo.style.transform = `translate(${hx - 10}px, ${hy - 10}px)`;
    els.dot.style.transform = `translate(${x - 2}px, ${y - 2}px)`;
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
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
  els.footerState.textContent = `${data.base} · ${label} · ${new Date(data.measured_at).toLocaleTimeString()}`;

  data.cores.forEach((core) => renderer.setCoreState(core.id, core.state));
  renderer.setVitality(measured / total);

  const accessNode = rail.nodes[SECTIONS.findIndex((section) => section.id === "access")];
  if (accessNode) accessNode.dataset.state = state;
}

/* ---------- loop ---------- */

let inFlight = false;

async function refresh(rail) {
  if (inFlight) return;
  inFlight = true;
  els.pill.dataset.state = "probing";
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
  buildCursor();
  buildCopy();
  buildCarousel();

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

  run();
  setInterval(run, REFRESH_MS);
}

boot();