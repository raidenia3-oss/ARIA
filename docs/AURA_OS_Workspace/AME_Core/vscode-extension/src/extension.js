/**
 * AURA Sentinel Agent - Extension de VS Code
 * Scaffold principal. Todo el codigo aqui para evitar errores de bundler/imports.
 */

const vscode = require("vscode");

const extensionId = "aura-sentinel.agent";
let panel;
let monitor;

function activate(context) {
    console.log("AURA Sentinel Agent activado");

    const activateCommand = vscode.commands.registerCommand("auraSentinel.activate", async () => {
        vscode.window.showInformationMessage(
            "AURA Sentinel Agent: Activado. Usa Ctrl+Shift+S para abrir el panel.",
        );
        if (!panel) {
            panel = new AuraSentinelPanel(context);
        }
    });

    const openPanelCommand = vscode.commands.registerCommand("auraSentinel.openPanel", () => {
        if (!panel) {
            panel = new AuraSentinelPanel(context);
        } else {
            panel.reveal();
        }
    });

    const toggleWatcherCommand = vscode.commands.registerCommand(
        "auraSentinel.toggleWatcher",
        async () => {
            const config = vscode.workspace.getConfiguration("auraSentinel");
            const enabled = config.get("watcherEnabled", false);

            if (enabled) {
                vscode.window.showWarningMessage(
                    "El watcher de Cline ya esta activo. Se desactivara.",
                );
                if (monitor) {
                    monitor.dispose();
                    monitor = undefined;
                }
            } else {
                vscode.window.showInformationMessage("Activando watcher de Cline...");
                monitor = new AgentMonitor(context);
                vscode.window.setStatusBarMessage("🛡️ AURA Sentinel: Monitoreando Cline", 0);
            }

            await config.update("watcherEnabled", !enabled, true);
        },
    );

    const runLocalModelCommand = vscode.commands.registerCommand(
        "auraSentinel.runLocalModel",
        async () => {
            if (!panel) {
                panel = new AuraSentinelPanel(context);
            }
            vscode.window.showInformationMessage(
                "Modelo local: Escribe tu prompt en el panel de AURA Sentinel.",
            );
        },
    );

    const config = vscode.workspace.getConfiguration("auraSentinel");
    if (config.get("watcherEnabled", false)) {
        monitor = new AgentMonitor(context);
    }

    context.subscriptions.push(
        activateCommand,
        openPanelCommand,
        toggleWatcherCommand,
        runLocalModelCommand,
    );

    if (!panel) {
        panel = new AuraSentinelPanel(context);
    }
}

function deactivate() {
    if (panel) {
        panel.dispose();
    }
    if (monitor) {
        monitor.dispose();
    }
}

class AuraSentinelPanel {
    constructor(context) {
        this.context = context;
        this.panel = vscode.window.createWebviewPanel(
            "auraSentinelPanel",
            "AURA Sentinel",
            vscode.ViewColumn.Beside,
            { enableScripts: true },
        );
        this.panel.webview.html = this.getHtml();
    }

    reveal() {
        if (this.panel) {
            this.panel.reveal();
        }
    }

    dispose() {
        if (this.panel) {
            this.panel.dispose();
        }
    }

    getHtml() {
        return "<html><body><h1>AURA Sentinel Agent</h1><p>Panel listo.</p></body></html>";
    }
}

class AgentMonitor {
    constructor(context) {
        this.context = context;
    }

    dispose() {
        // TODO: detener watcher
    }
}

module.exports = {
    activate,
    deactivate,
};
