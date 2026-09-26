import * as vscode from "vscode";

/**
 * AURA Sentinel Agent - Panel webview compartido.
 * Usado tanto por el comando "Abrir Panel" como por el watcher de Cline
 * para mostrar la intervención/solución generada por el modelo local.
 */
export class AuraSentinelPanel {
    public panel: vscode.WebviewPanel | undefined;
    private context: vscode.ExtensionContext;

    constructor(context: vscode.ExtensionContext) {
        this.context = context;
        this.createPanel();
    }

    private createPanel(): void {
        this.panel = vscode.window.createWebviewPanel(
            "auraSentinelPanel",
            "AURA Sentinel",
            vscode.ViewColumn.Beside,
            { enableScripts: true },
        );
        this.panel.webview.html = this.getHtml("");
        this.panel.onDidDispose(() => {
            this.panel = undefined;
        });
    }

    public reveal(): void {
        if (this.panel) {
            this.panel.reveal();
        }
    }

    public showOutput(text: string): void {
        if (!this.panel) {
            this.createPanel();
        }
        if (this.panel) {
            this.panel.title = "AURA Sentinel - Intervención";
            this.panel.webview.html = this.getHtml(text);
        }
    }

    private getHtml(content: string): string {
        const escaped = (content || "")
            .replace(/\\/g, "\\\\")
            .replace(/`/g, "\\`")
            .replace(/\$/g, "\\$");

        return `
            <html>
            <body>
                <h1>AURA Sentinel - Intervención Automática</h1>
                <pre id="output" style="background: #1e1e1e; color: #d4d4d4; padding: 12px; border-radius: 4px; font-family: monospace; white-space: pre-wrap;"></pre>
                <p><em>Generado por el modelo local (LM Studio / Ollama).</em></p>
                <script>
                    document.getElementById("output").textContent = \`${escaped}\`;
                </script>
            </body>
            </html>
        `;
    }

    public dispose(): void {
        if (this.panel) {
            this.panel.dispose();
            this.panel = undefined;
        }
    }
}
