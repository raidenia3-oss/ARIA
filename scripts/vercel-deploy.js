// Vercel Deployment Automation for Cline
const fetch = require("node-fetch");
const fs = require("fs");

const VERCEL_TOKEN =
  process.env.VERCEL_TOKEN ||
  fs.readFileSync("vercel-token.txt", "utf-8").trim();
const PROJECT_ID = "aura-web-chi-seven";
const API_BASE = "https://api.vercel.com";

class VercelAutomation {
  constructor(token, projectId) {
    this.token = token;
    this.projectId = projectId;
  }

  async request(method, endpoint, body = null) {
    const url = `${API_BASE}${endpoint}`;
    const opts = {
      method,
      headers: {
        Authorization: `Bearer ${this.token}`,
        "Content-Type": "application/json",
      },
    };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(url, opts);
    const data = await res.json();
    if (!res.ok) {
      console.error("Vercel API Error:", data);
      throw new Error(data.message || "Vercel API failed");
    }
    return data;
  }

  async setEnvironmentVariables(vars) {
    console.log("[Vercel] Configurando variables de entorno...");
    for (const [key, value] of Object.entries(vars)) {
      try {
        await this.request("POST", `/v9/projects/${this.projectId}/env`, {
          key,
          value,
          type: "encrypted",
          target: ["production", "preview", "development"],
        });
        console.log(`✅ ${key} configurada`);
      } catch (e) {
        console.log(`⚠️ ${key} ya existe o error:`, e.message);
      }
    }
  }

  async getProjectStatus() {
    console.log("[Vercel] Obteniendo estado del proyecto...");
    const project = await this.request("GET", `/v9/projects/${this.projectId}`);
    return project;
  }

  async redeploy() {
    console.log("[Vercel] Triggeando redeploy...");
    const result = await this.request("POST", `/v13/deployments`, {
      name: this.projectId,
      project: this.projectId,
      source: "cli",
    });
    console.log(`✅ Deployment ID: ${result.id}`);
    return result;
  }

  async getDeploymentLogs(limit = 50) {
    console.log("[Vercel] Obteniendo logs...");
    const project = await this.getProjectStatus();
    const latestDeployment = project.latestDeployments?.[0]?.id;
    if (!latestDeployment) {
      console.log("No deployments found");
      return;
    }
    const logs = await this.request(
      "GET",
      `/v11/deployments/${latestDeployment}/logs?limit=${limit}`,
    );
    console.log(JSON.stringify(logs, null, 2));
    return logs;
  }

  async listEnvironmentVariables() {
    console.log("[Vercel] Listando variables...");
    const envs = await this.request(
      "GET",
      `/v9/projects/${this.projectId}/env`,
    );
    console.log(JSON.stringify(envs, null, 2));
    return envs;
  }
}

(async () => {
  if (!VERCEL_TOKEN) {
    console.error("❌ VERCEL_TOKEN no configurado");
    process.exit(1);
  }
  const vercel = new VercelAutomation(VERCEL_TOKEN, PROJECT_ID);
  const command = process.argv[2];
  try {
    switch (command) {
      case "set-env":
        await vercel.setEnvironmentVariables({
          DATABASE_URL: process.env.DATABASE_URL,
          FASTAPI_URL: process.env.FASTAPI_URL,
          CRON_SECRET: process.env.CRON_SECRET,
        });
        break;
      case "redeploy":
        await vercel.redeploy();
        break;
      case "logs":
        await vercel.getDeploymentLogs();
        break;
      case "status":
        const status = await vercel.getProjectStatus();
        console.log("Project Name:", status.name);
        console.log("Latest Deploy:", status.latestDeployments?.[0]?.id);
        console.log("State:", status.latestDeployments?.[0]?.state);
        break;
      case "env-list":
        await vercel.listEnvironmentVariables();
        break;
      default:
        console.log(
          `\nUsage:\n  node scripts/vercel-deploy.js set-env      (Configurar variables)\n  node scripts/vercel-deploy.js redeploy     (Triggerear deploy)\n  node scripts/vercel-deploy.js logs         (Ver logs)\n  node scripts/vercel-deploy.js status       (Estado del proyecto)\n  node scripts/vercel-deploy.js env-list     (Listar variables)\n`,
        );
    }
  } catch (e) {
    console.error("Error:", e.message);
    process.exit(1);
  }
})();
