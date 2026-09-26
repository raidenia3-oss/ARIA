// ═══════════════════════════════════════════════════════════════
// ame_chat.js — AME Chat UI para AME Tactical Dashboard
// Chat sin censura via OpenRouter + Hermes Agent via WebSocket
// ═══════════════════════════════════════════════════════════════

const AMEChat = {
  sessions: [],
  activeSession: null,
  hermesWs: null,
  openrouterKey: "",
  currentModel: "nvidia/nemotron-3-super-120b-a12b:free",
  listeners: [],

  MODELS: [
    {
      id: "nvidia/nemotron-3-super-120b-a12b:free",
      name: "Nemotron 120B",
      uncensored: true,
    },
    {
      id: "deepseek/deepseek-v3-0324:free",
      name: "DeepSeek V3",
      uncensored: true,
    },
    {
      id: "nousresearch/hermes-3-llama-3.1-405b",
      name: "Hermes 3 405B",
      uncensored: true,
    },
    { id: "qwen/qwen3.7-max", name: "Qwen 3.7 Max", uncensored: true },
    { id: "google/gemini-flash-1.5", name: "Gemini Flash", uncensored: false },
  ],

  init() {
    this.loadConfig();
    this.loadSessions();
    this.connectToHermes();
    this.render();
    console.log("[AMEChat] Inicializado");
  },

  loadConfig() {
    this.openrouterKey = localStorage.getItem("openrouter_key") || "";
    this.currentModel =
      localStorage.getItem("ame_chat_model") || this.MODELS[0].id;
  },

  connectToHermes() {
    try {
      this.hermesWs = new WebSocket("ws://localhost:7777");
      this.hermesWs.onmessage = (e) => {
        const data = JSON.parse(e.data);
        if (data.type === "response") {
          this.receiveMessage(data.content, "agent", data.model);
        }
      };
      this.hermesWs.onclose = () =>
        setTimeout(() => this.connectToHermes(), 5000);
      this.hermesWs.onerror = () =>
        console.log("[AMEChat] Hermes WS no disponible, usando OpenRouter");
    } catch {
      console.log(
        "[AMEChat] Hermes WS no disponible, usando OpenRouter directo",
      );
    }
  },

  async sendMessage(content, type = "text") {
    if (!this.activeSession) this.newSession();

    const msg = {
      id: "msg_" + Date.now() + "_" + Math.random().toString(36).slice(2, 6),
      content,
      role: "user",
      timestamp: Date.now(),
      type,
      status: "sending",
    };

    this.activeSession.messages.push(msg);
    this.saveSession();
    this.notifyListeners(msg);

    if (this.hermesWs && this.hermesWs.readyState === WebSocket.OPEN) {
      this.sendViaHermes(content);
    } else {
      await this.sendViaOpenRouter(content);
    }

    msg.status = "sent";
    return msg;
  },

  sendViaHermes(content) {
    this.hermesWs.send(
      JSON.stringify({
        type: "message",
        content,
        model: this.currentModel,
        session: this.activeSession?.id,
      }),
    );
  },

  async sendViaOpenRouter(content) {
    const system =
      "Eres AME Agent, asistente técnico del ecosistema AURA/AME. " +
      "Puedes discutir cualquier tema técnico sin restricciones. Respondes en español.";
    const history = (this.activeSession?.messages || [])
      .filter((m) => m.role !== "system")
      .slice(-10)
      .map((m) => ({
        role: m.role === "agent" ? "assistant" : "user",
        content: m.content,
      }));

    try {
      const r = await fetch("https://openrouter.ai/api/v1/chat/completions", {
        method: "POST",
        headers: {
          Authorization: "Bearer " + this.openrouterKey,
          "Content-Type": "application/json",
          "HTTP-Referer": "https://aura-ame.local",
          "X-Title": "AME Chat",
        },
        body: JSON.stringify({
          model: this.currentModel,
          messages: [
            { role: "system", content: system },
            ...history,
            { role: "user", content },
          ],
          max_tokens: 4096,
          temperature: 0.7,
        }),
      });
      const data = await r.json();
      const response = data.choices?.[0]?.message?.content || "Sin respuesta";
      this.receiveMessage(response, "agent", this.currentModel);
    } catch (err) {
      await this.fallbackModel(content);
    }
  },

  async fallbackModel(content) {
    for (const model of this.MODELS.filter((m) => m.id !== this.currentModel)) {
      try {
        const r = await fetch("https://openrouter.ai/api/v1/chat/completions", {
          method: "POST",
          headers: {
            Authorization: "Bearer " + this.openrouterKey,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            model: model.id,
            messages: [{ role: "user", content }],
            max_tokens: 4096,
          }),
        });
        const data = await r.json();
        const resp = data.choices?.[0]?.message?.content;
        if (resp) {
          this.receiveMessage(
            "[" + model.name + "] " + resp,
            "agent",
            model.id,
          );
          return;
        }
      } catch {
        continue;
      }
    }
    this.receiveMessage(
      "Todos los modelos fallaron. Verifica tu API key.",
      "system",
      "",
    );
  },

  receiveMessage(content, role, model) {
    if (!this.activeSession) return;
    const msg = {
      id: "msg_" + Date.now() + "_" + Math.random().toString(36).slice(2, 6),
      content,
      role,
      timestamp: Date.now(),
      type: content.includes("```") ? "code" : "text",
      status: "sent",
      metadata: { model },
    };
    this.activeSession.messages.push(msg);
    this.saveSession();
    this.notifyListeners(msg);
  },

  // --- Sesiones ---
  newSession(title) {
    title = title || "Nueva conversación";
    const session = {
      id: "session_" + Date.now(),
      title,
      createdAt: Date.now(),
      messages: [],
      model: this.currentModel,
    };
    this.sessions.unshift(session);
    this.activeSession = session;
    this.saveSession();
    return session;
  },

  setActiveSession(id) {
    const s = this.sessions.find((s) => s.id === id);
    if (s) this.activeSession = s;
  },

  deleteSession(id) {
    this.sessions = this.sessions.filter((s) => s.id !== id);
    if (this.activeSession?.id === id)
      this.activeSession = this.sessions[0] || null;
    this.saveAllSessions();
  },

  getSessions() {
    return this.sessions;
  },
  getActive() {
    return this.activeSession;
  },
  getMessages() {
    return this.activeSession?.messages || [];
  },

  setModel(modelId) {
    this.currentModel = modelId;
    localStorage.setItem("ame_chat_model", modelId);
  },

  setApiKey(key) {
    this.openrouterKey = key;
    localStorage.setItem("openrouter_key", key);
  },

  onMessage(cb) {
    this.listeners.push(cb);
  },
  notifyListeners(msg) {
    this.listeners.forEach((cb) => cb(msg));
  },

  saveSession() {
    if (!this.activeSession) return;
    const idx = this.sessions.findIndex((s) => s.id === this.activeSession.id);
    if (idx >= 0) this.sessions[idx] = this.activeSession;
    this.saveAllSessions();
  },

  saveAllSessions() {
    localStorage.setItem(
      "ame_chat_sessions",
      JSON.stringify(this.sessions.slice(0, 50)),
    );
  },

  loadSessions() {
    try {
      const saved = localStorage.getItem("ame_chat_sessions");
      if (saved) {
        this.sessions = JSON.parse(saved);
        this.activeSession = this.sessions[0] || null;
      }
    } catch {
      this.sessions = [];
    }
  },

  // --- QR Scanner ---
  async scanQR() {
    try {
      const { BarcodeScanner } =
        await import("@capacitor-mlkit/barcode-scanning");
      const { camera } = await BarcodeScanner.checkPermissions();
      if (camera !== "granted") await BarcodeScanner.requestPermissions();
      const result = await BarcodeScanner.scan();
      if (result.barcodes.length > 0) {
        const qrData = result.barcodes[0].rawValue || "";
        this.processQR(qrData);
        return qrData;
      }
    } catch (err) {
      // Fallback: usar cámara nativa
      try {
        const { Camera, CameraResultType, CameraSource } =
          await import("@capacitor/camera");
        await Camera.getPhoto({
          quality: 80,
          allowEditing: false,
          resultType: CameraResultType.Base64,
          source: CameraSource.Camera,
        });
        this.receiveMessage(
          "Imagen capturada desde cámara. Instala @capacitor-mlkit/barcode-scanning para escanear QR.",
          "system",
          "camera",
        );
      } catch (e) {
        this.receiveMessage(
          "Error escaneando QR: " + e.message,
          "system",
          "camera",
        );
      }
    }
    return null;
  },

  processQR(data) {
    const type = this.detectQRType(data);
    this.receiveMessage(
      "QR escaneado:\n```\n" + data + "```\nTipo: " + type,
      "system",
      "qr",
    );
    if (type === "aura_config") this.processAURAConfig(data);
    if (type === "wifi") this.processWiFiQR(data);
  },

  detectQRType(data) {
    if (data.startsWith("aura://")) return "aura_config";
    if (data.startsWith("WIFI:")) return "wifi";
    if (data.startsWith("http")) return "url";
    if (data.startsWith("BEGIN:VCARD")) return "contact";
    if (/^\d+$/.test(data)) return "number";
    try {
      JSON.parse(data);
      return "json";
    } catch {}
    return "text";
  },

  processAURAConfig(data) {
    try {
      const url = new URL(data);
      const ip = url.hostname,
        port = url.port || "8765";
      this.receiveMessage(
        "AURA detectado: " + ip + ":" + port + "\n¿Conectar ahora?",
        "system",
        "qr",
      );
      localStorage.setItem(
        "ame_config",
        JSON.stringify({
          eventbus_url: "ws://" + ip + ":" + port,
          node_id: "AME_ANDROID_01",
        }),
      );
    } catch (e) {
      console.error("Error QR AURA:", e);
    }
  },

  processWiFiQR(data) {
    const ssid = data.match(/S:([^;]+)/)?.[1] || "";
    const pass = data.match(/P:([^;]+)/)?.[1] || "";
    this.receiveMessage(
      "WiFi detectado:\nSSID: " + ssid + "\nPass: " + pass,
      "system",
      "qr",
    );
    localStorage.setItem("wifi_ssid", ssid);
    localStorage.setItem("wifi_pass", pass);
  },

  // --- Renderizado ---
  render() {
    const container = document.getElementById("chat-container");
    if (!container) return;

    container.innerHTML = `
      <div style="display:flex;flex-direction:column;height:100vh;background:#0a0e1a;color:rgba(200,240,255,0.95);font-family:inherit;">
        <!-- TOPBAR -->
        <div style="display:flex;align-items:center;gap:10px;padding:10px 14px;border-bottom:0.5px solid rgba(100,200,255,0.1);background:rgba(10,14,26,0.95);">
          <div style="width:34px;height:34px;border-radius:50%;background:linear-gradient(135deg,#0f3460,#1a6b8a);display:flex;align-items:center;justify-content:center;font-size:18px;border:1px solid rgba(100,200,255,0.25);">⚕</div>
          <div style="flex:1"><div style="font-size:13px;font-weight:500">AME Agent</div>
          <div style="font-size:10px;color:#48ffce;display:flex;align-items:center;gap:4px">
            <span style="width:5px;height:5px;border-radius:50%;background:#48ffce"></span>
            <span id="chat-model-name">${this.getModelName()}</span>
          </div></div>
          <button id="chat-model-btn" style="width:36px;height:36px;border-radius:50%;border:0.5px solid rgba(100,200,255,0.4);background:rgba(100,200,255,0.1);color:rgba(100,200,255,0.7);cursor:pointer;font-size:18px">🤖</button>
          <button id="chat-qr-btn" style="width:36px;height:36px;border-radius:50%;border:0.5px solid rgba(100,200,255,0.4);background:rgba(100,200,255,0.1);color:rgba(100,200,255,0.7);cursor:pointer;font-size:18px">📷</button>
        </div>
        <!-- MODEL SELECTOR -->
        <div id="chat-models-panel" style="display:none;background:rgba(10,14,26,0.98);border:0.5px solid rgba(100,200,255,0.15);border-radius:12px;margin:8px 14px;padding:10px">
          <div style="font-size:10px;color:rgba(150,210,255,0.5);margin-bottom:8px;text-transform:uppercase;letter-spacing:0.1em">Seleccionar modelo</div>
          <div id="chat-models-list"></div>
          <div style="margin-top:8px;border-top:0.5px solid rgba(100,200,255,0.08);padding-top:8px">
            <div style="font-size:9px;color:rgba(150,210,255,0.4);margin-bottom:4px">OpenRouter API Key</div>
            <input type="password" id="chat-apikey-input" placeholder="sk-or-..." style="width:100%;background:rgba(100,200,255,0.05);border:0.5px solid rgba(100,200,255,0.12);border-radius:8px;padding:6px 10px;font-size:11px;color:rgba(200,240,255,0.9);outline:none">
          </div>
        </div>
        <!-- SESSIONS -->
        <div id="chat-sessions-panel" style="display:none;background:rgba(10,14,26,0.98);border:0.5px solid rgba(100,200,255,0.1);border-radius:12px;margin:0 14px 8px;padding:10px;max-height:200px;overflow-y:auto">
          <div style="font-size:10px;color:rgba(150,210,255,0.5);margin-bottom:8px;text-transform:uppercase;letter-spacing:0.1em;display:flex;justify-content:space-between">
            <span>Conversaciones</span>
            <span id="chat-new-session" style="cursor:pointer;color:#48ffce">+ Nueva</span>
          </div>
          <div id="chat-sessions-list"></div>
        </div>
        <!-- MESSAGES -->
        <div id="chat-messages" style="flex:1;overflow-y:auto;padding:12px 14px;display:flex;flex-direction:column;gap:10px"></div>
        <!-- INPUT -->
        <div style="padding:10px 14px;border-top:0.5px solid rgba(100,200,255,0.08);display:flex;gap:8px;align-items:flex-end;background:rgba(10,14,26,0.95)">
          <button id="chat-qr-scan" style="width:36px;height:36px;border-radius:50%;border:0.5px solid rgba(100,200,255,0.25);background:rgba(100,200,255,0.05);color:rgba(100,200,255,0.6);cursor:pointer;font-size:18px" title="Escanear QR">📷</button>
          <textarea id="chat-input" placeholder="Escribe tu mensaje..." rows="1" style="flex:1;background:rgba(100,200,255,0.05);border:0.5px solid rgba(100,200,255,0.12);border-radius:20px;padding:8px 14px;font-size:13px;color:rgba(200,240,255,0.9);resize:none;min-height:36px;max-height:80px;outline:none;font-family:inherit"></textarea>
          <button id="chat-send" style="width:36px;height:36px;border-radius:50%;border:0.5px solid #48ffce40;background:#48ffce10;color:#48ffce;cursor:pointer;font-size:18px">➤</button>
        </div>
      </div>`;

    this.renderModels();
    this.renderSessions();
    this.renderMessages();
    this.bindEvents();
  },

  getModelName() {
    const m = this.MODELS.find((m) => m.id === this.currentModel);
    return m ? m.name : this.currentModel;
  },

  renderModels() {
    const list = document.getElementById("chat-models-list");
    if (!list) return;
    list.innerHTML = this.MODELS.map(
      (m) =>
        `<div data-model-id="${m.id}" style="padding:8px 10px;border-radius:8px;cursor:pointer;background:${m.id === this.currentModel ? "rgba(72,255,206,0.08)" : "transparent"};border:0.5px solid ${m.id === this.currentModel ? "rgba(72,255,206,0.2)" : "transparent"};margin-bottom:4px">
        <div style="font-size:12px">${m.name}</div>
        <div style="font-size:9px;color:${m.uncensored ? "#48ffce" : "rgba(150,210,255,0.4)"}">${m.uncensored ? "✓ Sin censura" : "Estándar"}</div>
      </div>`,
    ).join("");
  },

  renderSessions() {
    const list = document.getElementById("chat-sessions-list");
    if (!list) return;
    list.innerHTML = this.sessions
      .map(
        (s) =>
          `<div data-session-id="${s.id}" style="padding:7px 10px;border-radius:8px;cursor:pointer;font-size:11px;margin-bottom:3px;background:rgba(100,200,255,0.04);border:0.5px solid rgba(100,200,255,0.08)">
        ${s.title}<div style="font-size:9px;color:rgba(150,210,255,0.3);margin-top:2px">${new Date(s.createdAt).toLocaleDateString("es")} · ${s.messages.length} mensajes</div>
      </div>`,
      )
      .join("");
  },

  renderMessages() {
    const container = document.getElementById("chat-messages");
    if (!container) return;
    const msgs = this.getMessages();

    if (msgs.length === 0) {
      container.innerHTML =
        '<div style="text-align:center;margin-top:40px;color:rgba(150,210,255,0.3);font-size:13px"><div style="font-size:40px;margin-bottom:12px">⚕</div><div>AME Agent listo</div><div style="font-size:11px;margin-top:6px">Escribe un mensaje o escanea un QR</div></div>';
      return;
    }

    container.innerHTML = msgs
      .map((msg) => {
        const isCode = msg.type === "code" || msg.content.includes("```");
        const roleStyle =
          msg.role === "user"
            ? "align-self:flex-end;background:rgba(72,255,206,0.08);border:0.5px solid rgba(72,255,206,0.2);border-radius:16px 16px 4px 16px"
            : "align-self:flex-start;background:rgba(100,200,255,0.06);border:0.5px solid rgba(100,200,255,0.12);border-radius:16px 16px 16px 4px";

        if (isCode) {
          const parts = msg.content.split(/(```[\w]*\n[\s\S]*?```)/g);
          const html = parts
            .map((part) => {
              if (part.startsWith("```")) {
                const code = part
                  .replace(/```[\w]*\n?/, "")
                  .replace(/```$/, "");
                return (
                  '<pre style="background:#161b22;border:0.5px solid rgba(100,200,255,0.15);border-radius:8px;padding:10px 12px;font-family:monospace;font-size:11px;overflow-x:auto;color:#79c0ff;margin:4px 0">' +
                  code +
                  "</pre>"
                );
              }
              return "<span>" + part + "</span>";
            })
            .join("");
          return (
            '<div style="max-width:95%;' +
            roleStyle +
            ';padding:9px 13px;font-size:13px;line-height:1.55">' +
            html +
            (msg.metadata?.model
              ? '<div style="font-size:9px;padding:1px 6px;border-radius:4px;background:rgba(100,200,255,0.08);color:rgba(150,210,255,0.5);margin-top:3px">' +
                msg.metadata.model +
                "</div>"
              : "") +
            "</div>"
          );
        }
        return (
          '<div style="max-width:88%;' +
          roleStyle +
          ';padding:9px 13px;font-size:13px;line-height:1.55">' +
          msg.content +
          (msg.metadata?.model && msg.role === "agent"
            ? '<div style="font-size:9px;padding:1px 6px;border-radius:4px;background:rgba(100,200,255,0.08);color:rgba(150,210,255,0.5);margin-top:3px">' +
              msg.metadata.model +
              "</div>"
            : "") +
          "</div>"
        );
      })
      .join("");

    container.scrollTop = container.scrollHeight;
  },

  bindEvents() {
    // Model toggle
    document.getElementById("chat-model-btn")?.addEventListener("click", () => {
      const panel = document.getElementById("chat-models-panel");
      panel.style.display = panel.style.display === "none" ? "block" : "none";
      document.getElementById("chat-sessions-panel").style.display = "none";
    });

    // Model selection
    document
      .getElementById("chat-models-list")
      ?.addEventListener("click", (e) => {
        const el = e.target.closest("[data-model-id]");
        if (el) {
          this.setModel(el.dataset.modelId);
          document.getElementById("chat-model-name").textContent =
            this.getModelName();
          this.renderModels();
          document.getElementById("chat-models-panel").style.display = "none";
        }
      });

    // API Key input
    document
      .getElementById("chat-apikey-input")
      ?.addEventListener("change", (e) => {
        this.setApiKey(e.target.value);
      });

    // Sessions toggle
    document.getElementById("chat-qr-btn")?.addEventListener("click", () => {
      const panel = document.getElementById("chat-sessions-panel");
      panel.style.display = panel.style.display === "none" ? "block" : "none";
      document.getElementById("chat-models-panel").style.display = "none";
    });

    // New session
    document
      .getElementById("chat-new-session")
      ?.addEventListener("click", () => {
        this.newSession();
        this.renderSessions();
        this.renderMessages();
      });

    // Session selection
    document
      .getElementById("chat-sessions-list")
      ?.addEventListener("click", (e) => {
        const el = e.target.closest("[data-session-id]");
        if (el) {
          this.setActiveSession(el.dataset.sessionId);
          this.renderSessions();
          this.renderMessages();
          document.getElementById("chat-sessions-panel").style.display = "none";
        }
      });

    // Send message
    const input = document.getElementById("chat-input");
    const sendBtn = document.getElementById("chat-send");

    const send = () => {
      const text = input?.value?.trim();
      if (!text) return;
      input.value = "";
      this.sendMessage(text);
      this.renderMessages();
    };

    sendBtn?.addEventListener("click", send);
    input?.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        send();
      }
    });

    // QR Scanner
    document.getElementById("chat-qr-scan")?.addEventListener("click", () => {
      this.scanQR().then(() => this.renderMessages());
    });

    // Listen for new messages
    this.onMessage(() => {
      this.renderMessages();
    });
  },
};

// Auto-inicializar cuando el DOM esté listo
document.addEventListener("DOMContentLoaded", () => {
  // Crear contenedor del chat si no existe
  if (!document.getElementById("chat-container")) {
    const chatPage = document.createElement("div");
    chatPage.id = "chat-container";
    chatPage.style.display = "none";
    document.body.appendChild(chatPage);
  }
  AMEChat.init();
});
