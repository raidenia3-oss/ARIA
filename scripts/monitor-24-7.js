const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:3000";
const INTERVAL_MS = 5 * 60 * 1000;
const TIMEOUT_MS = Number(process.env.MONITOR_TIMEOUT_MS || 5000);

function log(level, msg) {
  console.log(`[${new Date().toISOString()}] ${level} ${msg}`);
}

async function check(name, path, opts = {}) {
  const start = Date.now();
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), opts.timeout || TIMEOUT_MS);
    const res = await fetch(`${BASE_URL}${path}`, { signal: ctrl.signal });
    clearTimeout(timer);
    const ms = Date.now() - start;
    const withinBudget = opts.maxMs ? ms <= opts.maxMs : true;
    const ok = res.ok && withinBudget;
    log(
      ok ? "OK " : "FAIL",
      `${name} ${path} -> ${res.status} (${ms}ms)` +
        (opts.maxMs ? ` [budget ${opts.maxMs}ms]` : ""),
    );
    return ok;
  } catch (err) {
    log("FAIL", `${name} ${path} -> ERROR ${err.message}`);
    return false;
  }
}

async function runOnce() {
  log("INFO", `Monitoreo 24/7 iniciado (${BASE_URL})`);
  const results = [
    await check("Health", "/api/health", { maxMs: 500 }),
    await check("IntegrationsStatus", "/api/integrations/status"),
    await check("Webhooks", "/api/webhooks"),
    await check("AMECore", "/api/ame-core"),
  ];
  const failed = results.filter((r) => !r).length;
  if (failed > 0) {
    log("ALERT", `${failed} chequeo(s) fallando - notificar responsable`);
  } else {
    log("OK ", "Todos los sistemas operativos");
  }
  return failed;
}

function start() {
  runOnce();
  setInterval(runOnce, INTERVAL_MS);
}

module.exports = { runOnce, check, start };

if (require.main === module) {
  start();
}
