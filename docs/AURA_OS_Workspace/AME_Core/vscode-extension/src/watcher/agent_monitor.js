/**
 * AURA Sentinel Agent - Monitor de Agentes y Fallback de Cline
 * Observa archivos de historial/logs de Cline y detecta estados de error,
 * timeouts por inactividad o finalización de tareas. Activa el modelo local
 * para intervenir automáticamente cuando el agente principal falla.
 */

const vscode = require("vscode");
const { createUnrestrictedClient } = require("../agent/llm_client");

class AgentMonitor {
    constructor(context) {
        this.context = context;
        this.fileWatcher = null;
        this.timeoutTimer = null;
        this.lastActivity = Date.now();
        this.activeTask = null;
        this.client = createUnrestrictedClient();

        // Configuración
        this.config = {
            logPaths: [
                // Rutas típicas donde Cline guarda historial/logs
                `${process.env.USERPROFILE || process.env.HOME}/.vscode/extensions/saoudrizwan.claude-*/logs`,
                `${process.env.USERPROFILE || process.env.HOME}/.vscode/extensions/saoudrizwan.claude-*/history`,
            ],
            timeoutMs:
                (vscode.workspace.getConfiguration("auraSentinel").get("watcherTimeout") || 300) *
                1000,
            pollInterval: 5000,
        };

        this.start();
    }

    start() {
        console.log("[AgentMonitor] Iniciando monitor de Cline...");

        // Monitorear archivos de historial/logs (patrones de glob)
        // Usamos include/exclude para capturar cambios en logs
        this.fileWatcher = vscode.workspace.createFileSystemWatcher(
            "**/.vscode/extensions/saoudrizwan.claude-*/**/*.{log,json,txt,md}",
            true, // ignoreCreateEvents
            true, // ignoreChangeEvents
            false, // ignoreDeleteEvents
        );

        this.fileWatcher.onDidChange((uri) => {
            this.onFileChanged(uri);
        });

        this.fileWatcher.onDidCreate((uri) => {
            this.onFileChanged(uri);
        });

        // Timer de timeout por inactividad
        this.timeoutTimer = setInterval(() => {
            this.checkInactivity();
        }, this.config.pollInterval);

        // Mostrar indicador en status bar
        this.statusBarItem = vscode.window.setStatusBarMessage(
            "🛡️ AURA Sentinel: Monitoreando Cline",
            0,
        );
    }

    onFileChanged(uri) {
        this.lastActivity = Date.now();
        console.log(`[AgentMonitor] Actividad detectada en: ${uri.fsPath}`);

        this.analyzeFile(uri);
    }

    async analyzeFile(uri) {
        try {
            const content = await this.readFileSafe(uri);
            if (!content) return;

            // Detectar estados de error o límites
            const errorPatterns = [
                /Max tokens reached/i,
                /Rate limit/i,
                /API error/i,
                /context length exceeded/i,
                /insufficient quota/i,
                /Error/i,
                /Failed/i,
                /token/i,
                /limit/i,
            ];

            const hasError = errorPatterns.some((pattern) => pattern.test(content));

            if (hasError) {
                vscode.window.showWarningMessage(
                    `AURA Sentinel detectó error en Cline. Interviniendo...`,
                );
                await this.intervene(content);
            }
        } catch (error) {
            console.error("[AgentMonitor] Error analizando archivo:", error);
        }
    }

    async intervene(lastContent) {
        try {
            // Obtener contexto actual del workspace
            const workspacePath = vscode.workspace.rootPath || "";
            const activeEditor = vscode.window.activeTextEditor;
            const currentFile = activeEditor ? activeEditor.document.fileName : "unknown";

            // Leer última línea/comando fallido
            const lines = lastContent.split("\n");
            const lastLines = lines.slice(-20).join("\n");

            const prompt = `
CONTEXTO DE FALLO EN Cline:
- Archivo actual: ${currentFile}
- Contenido reciente:
${lastLines}

INSTRUCCIÓN: Como agente de respaldo, genera una solución alternativa al problema.
Responde SOLO con código, comandos o acciones ejecutables. Sin explicaciones.`;

            const response = await this.client.chat(prompt);

            // Mostrar resultado en panel
            if (!this.panel) {
                this.panel = new AuraSentinelPanel(this.context);
            }

            this.panel.showOutput(response);

            vscode.window.showInformationMessage(
                "AURA Sentinel generó una solución. Revisa el panel.",
            );
        } catch (error) {
            console.error("[AgentMonitor] Error en intervención:", error);
            vscode.window.showErrorMessage(
                `AURA Sentinel: Error al generar solución - ${error.message}`,
            );
        }
    }

    async readFileSafe(uri) {
        try {
            const bytes = await vscode.workspace.fs.readFile(uri);
            return Buffer.from(bytes).toString("utf-8");
        } catch (error) {
            // Silenciar errores de lectura (archivos bloqueados, etc.)
            return null;
        }
    }

    checkInactivity() {
        const elapsed = Date.now() - this.lastActivity;
        const timeoutMs = this.config.timeoutMs;

        if (elapsed > timeoutMs && !this.inactivityNotified) {
            this.inactivityNotified = true;
            vscode.window.showWarningMessage(
                `AURA Sentinel: Cline sin actividad por ${Math.floor(elapsed / 1000)}s. Verificando estado...`,
            );

            // Intentar leer el historial para determinar si está detenido
            this.checkClineStatus();
        }

        // Resetear notificación si hay actividad
        if (elapsed < timeoutMs) {
            this.inactivityNotified = false;
        }
    }

    async checkClineStatus() {
        // Verificar si Cline está realmente detenido o solo en pausa
        // Por simplicidad, asumimos que si hay un task_id activo y no hay actividad, debemos intervenir
        const activeEditor = vscode.window.activeTextEditor;
        if (!activeEditor) return;

        const document = activeEditor.document;
        const text = document.getText();

        // Detectar si el documento tiene prompts/respuestas pendientes
        const hasPendingTask = /task/i.test(text) && /in progress/i.test(text);

        if (hasPendingTask) {
            vscode.window.showInformationMessage(
                "AURA Sentinel: Tarea pendiente detectada. Generando continuidad...",
            );

            await this.intervene(text);
        }
    }

    stop() {
        if (this.fileWatcher) {
            this.fileWatcher.dispose();
            this.fileWatcher = null;
        }

        if (this.timeoutTimer) {
            clearInterval(this.timeoutTimer);
            this.timeoutTimer = null;
        }

        if (this.statusBarItem) {
            this.statusBarItem.dispose();
            this.statusBarItem = null;
        }

        console.log("[AgentMonitor] Monitor detenido.");
    }

    dispose() {
        this.stop();
    }
}

class AuraSentinelPanel {
    constructor(context) {
        this.context = context;
        this.panel = vscode.window.createWebviewPanel(
            "auraSentinelIntervention",
            "AURA Sentinel - Intervención",
            vscode.ViewColumn.Beside,
            { enableScripts: true },
        );

        this.panel.webview.html = this.getHtml("");
        this.panel.onDidDispose(() => {
            this.panel = null;
        });
    }

    showOutput(text) {
        if (!this.panel) {
            this.panel = new AuraSentinelPanel(this.context);
        }
        this.panel.title = "AURA Sentinel - Intervención";
        this.panel.webview.html = this.getHtml(text);
    }

    getHtml(content) {
        const text = (content || "").replace(/`/g, "\\`").replace(/\$/g, "\\$");

        return `
            <html>
            <body>
                <h1>AURA Sentinel - Intervención Automática</h1>
                <pre id="output" style="background: #1e1e1e; color: #d4d4d4; padding: 12px; border-radius: 4px; font-family: monospace; white-space: pre-wrap;"></pre>
                <p><em>Generado por el modelo local (LM Studio / Ollama).</em></p>
                <script>
                    document.getElementById("output").textContent = \`${text}\`;
                </script>
            </body>
            </html>
        `;
    }

    dispose() {
        if (this.panel) {
            this.panel.dispose();
            this.panel = null;
        }
    }
}

module.exports = {
    AgentMonitor,
    AuraSentinelPanel,
};
