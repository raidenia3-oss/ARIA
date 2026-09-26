#!/usr/bin/env node
/**
 * CLINE SUPREMO - Control Total de Vercel
 * -----------------------------------------
 * Este script permite a Cline controlar Vercel completamente
 * SIN intervención manual.
 *
 * Uso: node scripts/vercel-control.js <comando> [args]
 *
 * Comandos:
 *   deploy         - Deploy automático a producción
 *   status         - Ver status del último deploy
 *   env list       - Listar variables de entorno
 *   env set KEY VAL - Setear variable de entorno
 *   logs           - Ver logs del último build
 *   rollback       - Rollback al deploy anterior
 *   domains        - Listar dominios configurados
 *   purge          - Limpiar cache de Vercel
 */

const { execSync } = require("child_process");
const path = require("path");
const fs = require("fs");

const FRONTEND_DIR = path.join(__dirname, "..", "frontend");
const LOG_FILE = path.join(__dirname, "..", "output", "vercel-control.log");

function log(msg) {
  const timestamp = new Date().toISOString();
  const line = `[${timestamp}] ${msg}`;
  console.log(line);
  try {
    fs.mkdirSync(path.dirname(LOG_FILE), { recursive: true });
    fs.appendFileSync(LOG_FILE, line + "\n");
  } catch (e) {}
}

function run(cmd, opts = {}) {
  log(`> ${cmd}`);
  try {
    const output = execSync(cmd, {
      cwd: opts.cwd || FRONTEND_DIR,
      encoding: "utf-8",
      stdio: opts.silent ? "pipe" : "inherit",
      timeout: 300000, // 5 min timeout
      ...opts,
    });
    if (opts.silent) return output;
    return true;
  } catch (e) {
    log(`ERROR: ${e.message}`);
    if (opts.silent) return e.stdout || "";
    throw e;
  }
}

const COMMANDS = {
  // Deploy automático a producción
  deploy() {
    log("🚀 Iniciando deploy a Vercel...");
    const output = run("vercel deploy --prod --force --archive=tgz", {
      silent: true,
      timeout: 600000,
    });
    log("✅ Deploy completado!");
    return output;
  },

  // Status del último deploy
  status() {
    log("📊 Status del proyecto:");
    run("vercel list --prod");
  },

  // Listar variables de entorno
  "env list"() {
    log("🔑 Variables de entorno:");
    run("vercel env ls");
  },

  // Setear variable de entorno
  "env set"(key, value) {
    if (!key || !value) {
      log("ERROR: Uso: env set KEY VALUE");
      return;
    }
    log(`🔑 Seteando ${key}=${value}...`);
    run(`vercel env add ${key} ${value}`, { silent: true });
    log(`✅ Variable ${key} seteada`);
  },

  // Logs del último build
  logs() {
    log("📝 Logs del build:");
    try {
      const out = run("vercel logs", { silent: true });
      console.log(out);
    } catch (e) {
      log("No hay logs disponibles. Usa: vercel logs");
    }
  },

  // Rollback al deploy anterior
  rollback() {
    log("↩️  Iniciando rollback...");
    try {
      const list = run("vercel list --prod --json", { silent: true });
      const deployments = JSON.parse(list);
      if (deployments.length >= 2) {
        const prev = deployments[1].url;
        log(`Rollback a: ${prev}`);
        run(`vercel rollback ${prev} --prod`, { silent: true });
        log("✅ Rollback completado");
      } else {
        log("No hay deploy anterior para rollback");
      }
    } catch (e) {
      log(`ERROR en rollback: ${e.message}`);
    }
  },

  // Listar dominios
  domains() {
    log("🌐 Dominios:");
    run("vercel domains");
  },

  // Purge cache
  purge() {
    log("🧹 Limpiando cache de Vercel...");
    run("vercel purge", { silent: true });
    log("✅ Cache purgado");
  },
};

// HELP
COMMANDS.help = function () {
  console.log(`
╔══════════════════════════════════════════╗
║   CLINE SUPREMO - CONTROL VERCEL        ║
╚══════════════════════════════════════════╝

USO:
  node scripts/vercel-control.js <comando> [args]

COMANDOS:
  deploy              Deploy automático a producción
  status              Ver status del proyecto
  env list            Listar variables de entorno
  env set KEY VALUE   Setear variable de entorno
  logs                Ver logs del build
  rollback            Rollback al deploy anterior
  domains             Listar dominios
  purge               Limpiar cache
  help                Mostrar esta ayuda

EJEMPLOS:
  node scripts/vercel-control.js deploy
  node scripts/vercel-control.js status
  node scripts/vercel-control.js env set API_KEY mykey123
  node scripts/vercel-control.js purge
`);
};

// Auto-deploy cuando se llama sin args
async function autoDeploy() {
  log("=".repeat(50));
  log("CLINE SUPREMO - Auto-deploy iniciado");
  log("=".repeat(50));

  // 1. Deploy
  COMMANDS.deploy();

  // 2. Verificar status
  log("\n📊 Verificando deploy...");
  COMMANDS.status();

  log("\n✅ Auto-deploy completado exitosamente!");
}

// MAIN
const args = process.argv.slice(2);
const cmd = (args[0] || "").toLowerCase().trim();

if (!cmd || cmd === "auto") {
  autoDeploy().catch((e) => log(`FATAL: ${e.message}`));
} else {
  const [base, ...params] = args;
  if (base && COMMANDS[base]) {
    COMMANDS[base](...params);
  } else if (COMMANDS[cmd]) {
    COMMANDS[cmd]();
  } else {
    log(`Comando desconocido: ${cmd}`);
    COMMANDS.help();
  }
}
