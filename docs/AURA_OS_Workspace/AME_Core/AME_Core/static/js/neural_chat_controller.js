/**
 * Neural Chat Controller — UI/UX Ciberpunk para AME
 * Modos: Standard (streaming) | Neural Room (multi-agent) | Global Memory
 * ==================================================================
 * Se conecta al backend AURA_Core/neural/ai_router.py
 */

class NeuralChatController {
    constructor(containerId = "neural-chat") {
        this.container = document.getElementById(containerId) || this._buildContainer(containerId);
        this.mode = "standard"; // standard | neural_room | memory_inject
        this.history = [];
        this._initUI();
    }

    _buildContainer(id) {
        const div = document.createElement("div");
        div.id = id;
        div.style.cssText = `
            background: #0a0a12; border: 1px solid #00f0ff33;
            border-radius: 12px; padding: 16px; font-family: 'Courier New', monospace;
            color: #00f0ff; max-width: 800px; margin: 20px auto;
        `;
        document.body.appendChild(div);
        return div;
    }

    _initUI() {
        this.container.innerHTML = `
            <div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;">
                <button data-mode="standard" class="nc-btn active">⚡ Standard</button>
                <button data-mode="neural_room" class="nc-btn">🧠 Neural Room</button>
                <button data-mode="memory_inject" class="nc-btn">💾 Global Memory</button>
            </div>
            <div id="nc-messages" style="height:300px;overflow-y:auto;margin-bottom:12px;
                background:#05050f;border-radius:8px;padding:8px;"></div>
            <div style="display:flex;gap:8px;">
                <textarea id="nc-input" rows="2" style="flex:1;background:#05050f;color:#00f0ff;
                    border:1px solid #00f0ff44;border-radius:6px;padding:8px;resize:none;"
                    placeholder="Escribe tu mensaje..."></textarea>
                <button id="nc-send" style="background:#00f0ff22;color:#00f0ff;border:1px solid #00f0ff;
                    border-radius:6px;padding:8px 16px;cursor:pointer;">▶</button>
            </div>
            <div id="nc-status" style="margin-top:8px;font-size:12px;color:#00f0ff88;"></div>
        `;

        // Eventos
        this.container.querySelectorAll(".nc-btn").forEach((btn) => {
            btn.onclick = () => this._setMode(btn.dataset.mode);
        });
        this.container.querySelector("#nc-send").onclick = () => this._send();
        this.container.querySelector("#nc-input").onkeydown = (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                this._send();
            }
        };
        this.messagesEl = this.container.querySelector("#nc-messages");
        this.inputEl = this.container.querySelector("#nc-input");
        this.statusEl = this.container.querySelector("#nc-status");
    }

    _setMode(mode) {
        this.mode = mode;
        this.container
            .querySelectorAll(".nc-btn")
            .forEach(
                (b) => (b.style.borderColor = b.dataset.mode === mode ? "#00f0ff" : "#00f0ff33"),
            );
        this._log(
            `Modo: ${mode === "standard" ? "Standard" : mode === "neural_room" ? "Neural Room" : "Global Memory"}`,
        );
    }

    _log(msg) {
        this.statusEl.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
    }

    _addMessage(role, content) {
        const div = document.createElement("div");
        const isUser = role === "user";
        div.style.cssText = `
            margin: 4px 0; padding: 6px 10px; border-radius: 6px;
            background: ${isUser ? "#00f0ff11" : "#0f0f1a"};
            border-left: 2px solid ${isUser ? "#00f0ff" : "#7b2ff7"};
            white-space: pre-wrap; word-break: break-word;
        `;
        div.innerHTML = `<strong>${isUser ? "👤 Tú" : "🤖 AURA"}:</strong><br>${content}`;
        this.messagesEl.appendChild(div);
        this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
    }

    async _send() {
        const msg = this.inputEl.value.trim();
        if (!msg) return;
        this.inputEl.value = "";
        this._addMessage("user", msg);
        this.history.push({ role: "user", content: msg });

        if (this.mode === "neural_room") {
            await this._neuralRoomRequest(msg);
        } else {
            await this._standardRequest(msg);
        }
    }

    async _standardRequest(msg) {
        this._log("Enviando...");
        const endpoint =
            this.mode === "memory_inject"
                ? "https://aura-server-01.vercel.app/api/neural/chat?memory=1"
                : "https://aura-server-01.vercel.app/api/neural/chat";

        try {
            const resp = await fetch(endpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ prompt: msg, mode: this.mode }),
            });
            const data = await resp.json();
            const reply = data.response || data.error || "Sin respuesta";
            this._addMessage("assistant", reply);
            this.history.push({ role: "assistant", content: reply });
            this._log(`✅ ${data.provider || "local"} — ${data.latency_ms || "?"}ms`);
        } catch (e) {
            this._addMessage("assistant", `⚠️ Error: ${e.message}`);
            this._log("❌ Falló la conexión");
        }
    }

    async _neuralRoomRequest(msg) {
        this._log("🧠 Ejecutando Neural Room (paralelo)...");
        try {
            const resp = await fetch("https://aura-server-01.vercel.app/api/neural/room", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ prompt: msg }),
            });
            const data = await resp.json();
            const providers = ["gemini", "nvidia_nim", "groq", "openrouter"];
            providers.forEach((p) => {
                if (data[p]) {
                    const preview = data[p].substring(0, 120);
                    this._addMessage("assistant", `[${p}] ${preview}...`);
                }
            });
            this._log("✅ Neural Room completo");
        } catch (e) {
            this._addMessage("assistant", `⚠️ Error Neural Room: ${e.message}`);
        }
    }
}

// Auto-inicialización
document.addEventListener("DOMContentLoaded", () => {
    window.neuralChat = new NeuralChatController("neural-chat");
});
