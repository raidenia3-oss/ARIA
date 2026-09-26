#!/usr/bin/env node
/**
 * CLINE SUPREMO - End-to-End Tests
 * Valida automáticamente que TODO funcione correctamente
 */

const https = require("https");
const http = require("http");
const fs = require("fs");
const path = require("path");

const BASE_URL =
  process.env.TEST_URL || "https://aura-web-chi-seven.vercel.app";
const RESULTS_FILE = path.join(__dirname, "..", "output", "e2e-results.json");
const LOG_FILE = path.join(__dirname, "..", "output", "e2e-tests.log");

class E2ETests {
  constructor() {
    this.results = [];
    this.passed = 0;
    this.failed = 0;
  }

  log(msg) {
    const line = `[${new Date().toISOString()}] ${msg}`;
    console.log(line);
    try {
      fs.mkdirSync(path.dirname(LOG_FILE), { recursive: true });
      fs.appendFileSync(LOG_FILE, line + "\n");
    } catch (e) {}
  }

  async fetch(url, options = {}) {
    return new Promise((resolve, reject) => {
      const client = url.startsWith("https") ? https : http;
      const req = client.get(
        url,
        { timeout: options.timeout || 10000, ...options },
        (res) => {
          let data = "";
          res.on("data", (chunk) => (data += chunk));
          res.on("end", () => resolve({ status: res.statusCode, data }));
        },
      );
      req.on("error", reject);
      req.end();
    });
  }

  async post(url, body) {
    return new Promise((resolve, reject) => {
      const data = JSON.stringify(body);
      const urlObj = new URL(url);
      const client = url.startsWith("https") ? https : http;
      const req = client.request(
        url,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Content-Length": Buffer.byteLength(data),
          },
          timeout: 10000,
        },
        (res) => {
          let responseData = "";
          res.on("data", (chunk) => (responseData += chunk));
          res.on("end", () =>
            resolve({ status: res.statusCode, data: responseData }),
          );
        },
      );
      req.on("error", reject);
      req.write(data);
      req.end();
    });
  }

  pass(message) {
    this.passed++;
    this.results.push({ status: "✅", message });
    this.log(`  ✅ ${message}`);
  }

  fail(message, error = "") {
    this.failed++;
    this.results.push({ status: "❌", message, error });
    this.log(`  ❌ ${message}${error ? ` (${error})` : ""}`);
  }

  async testAMEPage() {
    this.log("\n1️⃣ Testing AME Main Page...");
    try {
      const res = await this.fetch(`${BASE_URL}/ame`);
      if (res.status === 200) {
        this.pass("GET /ame - Status 200");
        if (res.data.includes("AMEs Activos")) this.pass("Dashboard AME ok");
        else this.fail("Dashboard AME sin datos");
      } else {
        this.fail(`GET /ame - Status ${res.status}`);
      }
    } catch (e) {
      this.fail("GET /ame - Connection error", e.message);
    }
  }

  async testAMEDetail() {
    this.log("2️⃣ Testing AME Detail Page...");
    try {
      const res = await this.fetch(`${BASE_URL}/ame/1`);
      if (res.status === 200) {
        this.pass("GET /ame/1 - Status 200");
      } else {
        this.fail(`GET /ame/1 - Status ${res.status}`);
      }
    } catch (e) {
      this.fail("GET /ame/1 - Connection error", e.message);
    }
  }

  async testServiceWorker() {
    this.log("3️⃣ Testing Service Worker...");
    try {
      const res = await this.fetch(`${BASE_URL}/sw.js`);
      if (res.status === 200 && res.data.includes("CACHE_NAME")) {
        this.pass("Service Worker accessible");
      } else {
        this.fail(`Service Worker - Status ${res.status}`);
      }
    } catch (e) {
      this.fail("Service Worker error", e.message);
    }
  }

  async testManifest() {
    this.log("4️⃣ Testing Manifest.json...");
    try {
      const res = await this.fetch(`${BASE_URL}/manifest.json`);
      if (res.status === 200) {
        const manifest = JSON.parse(res.data);
        if (manifest.start_url === "/ame") this.pass("Manifest start_url ok");
        else this.fail("Manifest start_url incorrect");
        if (manifest.display === "standalone")
          this.pass("Manifest display=standalone");
        if (manifest.icons && manifest.icons.length > 0)
          this.pass("Manifest icons present");
      } else {
        this.fail(`Manifest - Status ${res.status}`);
      }
    } catch (e) {
      this.fail("Manifest error", e.message);
    }
  }

  async testAPI() {
    this.log("5️⃣ Testing API Endpoints...");
    try {
      const res = await this.post(`${BASE_URL}/api/ame-core`, {
        prompt: "Test de conexión",
      });
      if (res.status === 200) {
        this.pass("POST /api/ame-core - Status 200");
      } else {
        this.fail(`POST /api/ame-core - Status ${res.status}`);
      }
    } catch (e) {
      this.fail("POST /api/ame-core - Connection error", e.message);
    }
  }

  async testHFSpace() {
    this.log("6️⃣ Testing Hugging Face Space...");
    try {
      const res = await this.fetch(
        "https://raiden456-slut.hf.space/api/v1/status",
        { timeout: 5000 },
      );
      if (res.status === 200) {
        this.pass("✅ HF Space online");
      } else {
        this.fail("⚠️ HF Space offline (using local fallback)");
      }
    } catch (e) {
      this.fail(`⚠️ HF Space error: ${e.message} (using local fallback)`);
    }
  }

  async testPWA() {
    this.log("7️⃣ Testing PWA Configuration...");
    try {
      const res = await this.fetch(`${BASE_URL}/`);
      const html = res.data;
      if (html.includes("serviceWorker"))
        this.pass("Service Worker registered");
      if (html.includes("manifest.json")) this.pass("Manifest linked");
      if (html.includes("theme-color")) this.pass("Theme color set");
      if (html.includes("viewport")) this.pass("Viewport meta");
      if (html.includes("apple-mobile-web-app-capable"))
        this.pass("iOS PWA support");
    } catch (e) {
      this.fail("PWA test error", e.message);
    }
  }

  async testMobileViewport() {
    this.log("8️⃣ Testing Mobile Viewport...");
    try {
      const res = await this.fetch(`${BASE_URL}/ame`);
      if (
        res.data.includes('name="viewport"') ||
        res.data.includes("maximum-scale=1")
      ) {
        this.pass("Mobile viewport optimized");
      } else {
        this.fail("Mobile viewport not optimized");
      }
    } catch (e) {
      this.fail("Mobile viewport error", e.message);
    }
  }

  async runAll() {
    this.log("=".repeat(50));
    this.log("🧪 CLINE SUPREMO - E2E Tests");
    this.log("=".repeat(50));
    this.log(`Testing URL: ${BASE_URL}\n`);

    await this.testAMEPage();
    await this.testAMEDetail();
    await this.testServiceWorker();
    await this.testManifest();
    await this.testAPI();
    await this.testHFSpace();
    await this.testPWA();
    await this.testMobileViewport();

    this.printResults();
  }

  printResults() {
    this.log("\n" + "=".repeat(50));
    this.log("📊 RESULTADOS FINALES");
    this.log("=".repeat(50));

    this.results.forEach((r) =>
      this.log(`${r.status} ${r.message}${r.error ? ` (${r.error})` : ""}`),
    );

    this.log("\n" + "=".repeat(50));
    this.log(`✅ Pasados: ${this.passed} | ❌ Fallidos: ${this.failed}`);
    this.log("=".repeat(50));

    if (this.failed === 0) {
      this.log("\n🎉 ¡¡TODO FUNCIONA PERFECTAMENTE!!");
    } else {
      this.log(`\n⚠️ ${this.failed} tests fallaron - Revisar logs`);
    }

    // Guardar resultados
    const results = {
      timestamp: new Date().toISOString(),
      baseUrl: BASE_URL,
      passed: this.passed,
      failed: this.failed,
      total: this.passed + this.failed,
      details: this.results,
    };

    try {
      fs.mkdirSync(path.dirname(RESULTS_FILE), { recursive: true });
      fs.writeFileSync(RESULTS_FILE, JSON.stringify(results, null, 2));
      this.log(`\n📄 Resultados guardados en: ${RESULTS_FILE}`);
    } catch (e) {}
  }
}

new E2ETests().runAll();
