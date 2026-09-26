/**
 * AURA Sentinel Agent - Monitor de Agentes y Fallback de Cline
 * Observa archivos de historial/logs de Cline y detecta estados de error,
 * timeouts por inactividad o finalización de tareas. Activa el modelo local
 * para intervenir automáticamente cuando el agente principal falla.
 */

import * as vscode from "vscode";
import { createUnrestrictedClient } from "../agent/llm_client";
import { AuraSentinelPanel } from "../panels/AuraSentinelPanel";

interface SentinelConfig {
    logPaths: string[];
    timeoutMs: number;
    pollInterval: number;
}

export class AgentMonitor {
    private context: vscode.ExtensionContext;
    private fileWatcher: vscode.FileSystemWatcher | undefined;
    private timeoutTimer: ReturnType<typeof setInterval> | undefined;
    private statusBarItem: vscode.Disposable | undefined;
    private lastActivity: number;
    private activeTask: string | null;
    private inactivityNotified = false;
    private client: ReturnType<typeof createUnrestrictedClient>;
    private panel: AuraSentinelPanel | undefined;
    private config: SentinelConfig;

    constructor(context: vscode.ExtensionContext) {
        this.context = context;
        this.lastActivity = Date.now();
        this.activeTask = null;
        this.client = createUnrestrictedClient();

        const watcherTimeout =
            (vscode.workspace.getConfiguration("auraSentinel").get<number>("watcherTimeout") || 300) *
            1000;

        this.config = {
            logPaths: [
                `${process.env.USERPROFILE || process.env.HOME}/.vscode/extensions/saoudrizwan.claude-*/logs`,
                `${process.env.USERPROFILE || process.env.HOME}/.vscode/extensions/saoudrizwan.claude-*/history`,
            ],
            timeoutMs: watcherTimeout,
            pollInterval: 5000,
        };

        this.start();
    }

    private start(): void {
        console.log("[AgentMonitor] Iniciando monitor de Cline...");

        this.fileWatcher = vscode.workspace.createFileSystemWatcher(
            "**/.vscode/extensions/saoudrizwan.claude-*/**/*.{log,json,txt,md}",
            true,
            true,
            false,
        );

        this.fileWatcher.onDidChange((uri) => this.onFileChanged(uri));
        this.fileWatcher.onDidCreate((uri) => this.onFileChanged(uri));

        this.timeoutTimer = setInterval(() => this.checkInactivity(), this.config.pollInterval);

        this.statusBarItem = vscode.window.setStatusBarMessage(
            "🛡️ AURA Sentinel: Monitoreando Cline",
            0,
        );
    }

    private onFileChanged(uri: vscode.Uri): void {
        this.lastActivity = Date.now();
        console.log(`[AgentMonitor] Actividad detectada en: ${uri.fsPath}`);
        void this.analyzeFile(uri);
    }

    private async analyzeFile(uri: vscode.Uri): Promise<void> {
        try {
            const content = await this.readFileSafe(uri);
            if (!content) {
                return;
            }

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
                    "AURA Sentinel detectó error en Cline. Interviniendo...",
                );
                await this.intervene(content);
            }
        } catch (error) {
            console.error("[AgentMonitor] Error analizando archivo:", error);
        }
    }

    private async intervene(lastContent: string): Promise<void> {
        try {
            const workspacePath = vscode.workspace.rootPath || "";
            const activeEditor = vscode.window.activeTextEditor;
            const currentFile = activeEditor ? activeEditor.document.fileName : "unknown";

            const lines = lastContent.split("\n");
            const lastLines = lines.slice(-20).join("\n");

            const prompt = `
CONTEXTO DE FALLO EN Cline:
- Archivo actual: ${currentFile}
- Workspace: ${workspacePath}
- Contenido reciente:
${lastLines}

INSTRUCCIÓN: Como agente de respaldo, genera una solución alternativa al problema.
Responde SOLO con código, comandos o acciones ejecutables. Sin explicaciones.`;

            const response = await this.client.chat(prompt);

            if (!this.panel) {
                this.panel = new AuraSentinelPanel(this.context);
            }
            this.panel.showOutput(response);

            vscode.window.showInformationMessage(
                "AURA Sentinel generó una solución. Revisa el panel.",
            );
        } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            console.error("[AgentMonitor] Error en intervención:", error);
            vscode.window.showErrorMessage(
                `AURA Sentinel: Error al generar solución - ${message}`,
            );
        }
    }

    private async readFileSafe(uri: vscode.Uri): Promise<string | null> {
        try {
            const bytes = await vscode.workspace.fs.readFile(uri);
            return Buffer.from(bytes).toString("utf-8");
        } catch {
            return null;
        }
    }

    private checkInactivity(): void {
        const elapsed = Date.now() - this.lastActivity;
        const timeoutMs = this.config.timeoutMs;

        if (elapsed > timeoutMs && !this.inactivityNotified) {
            this.inactivityNotified = true;
            vscode.window.showWarningMessage(
                `AURA Sentinel: Cline sin actividad por ${Math.floor(elapsed / 1000)}s. Verificando estado...`,
            );
            void this.checkClineStatus();
        }

        if (elapsed < timeoutMs) {
            this.inactivityNotified = false;
        }
    }

    private async checkClineStatus(): Promise<void> {
        const activeEditor = vscode.window.activeTextEditor;
        if (!activeEditor) {
            return;
        }

        const text = activeEditor.document.getText();
        const hasPendingTask = /task/i.test(text) && /in progress/i.test(text);

        if (hasPendingTask) {
            vscode.window.showInformationMessage(
                "AURA Sentinel: Tarea pendiente detectada. Generando continuidad...",
            );
            await this.intervene(text);
        }
    }

    public stop(): void {
        if (this.fileWatcher) {
            this.fileWatcher.dispose();
            this.fileWatcher = undefined;
        }
        if (this.timeoutTimer) {
            clearInterval(this.timeoutTimer);
            this.timeoutTimer = undefined;
        }
        if (this.statusBarItem) {
            this.statusBarItem.dispose();
            this.statusBarItem = undefined;
        }
        console.log("[AgentMonitor] Monitor detenido.");
    }

    public dispose(): void {
        this.stop();
    }
}
