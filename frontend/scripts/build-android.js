#!/usr/bin/env node
/**
 * AURA OS — AME Android Build Wrapper (BLOQUE 40).
 *
 * Ejecuta `next build` con la config dedicada (next.config.android.js →
 * output: 'export') y luego `cap sync android` para generar el proyecto
 * nativo Android con los assets web empaquetados.
 *
 * Sin dependencias de nube, sin telemetría, sin tokens en texto plano.
 */
const { spawnSync } = require("child_process");
const path = require("path");

const root = __dirname;
const nextConfig = path.join(root, "next.config.android.js");

// 1. next build con la config android (export estático).
const build = spawnSync("node", ["node_modules/next/dist/bin/next", "build"], {
  cwd: root,
  stdio: "inherit",
  env: { ...process.env, NEXT_CONFIG_FILE: nextConfig },
});
if (build.status !== 0) {
  console.error("[build:android] next build falló");
  process.exit(build.status || 1);
}

// 2. cap sync android (genera el proyecto nativo + copia assets).
const sync = spawnSync("npx", ["cap", "sync", "android"], {
  cwd: root,
  stdio: "inherit",
  env: { ...process.env, NEXT_CONFIG_FILE: nextConfig },
});
if (sync.status !== 0) {
  console.error("[build:android] cap sync android falló");
  process.exit(sync.status || 1);
}

console.log("[build:android] APK listo (assets en android/app/src/main/assets/)");