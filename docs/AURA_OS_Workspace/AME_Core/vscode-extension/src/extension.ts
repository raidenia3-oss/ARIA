/**
 * AURA Sentinel Agent - Extensión de VS Code
 * Andamiaje principal: registro de comandos, webview y watcher
 */

import * as vscode from "vscode";
import { AuraSentinelPanel } from "./panels/AuraSentinelPanel";
import { AgentMonitor } from "./watcher/agent_monitor";

let panel: AuraSentinelPanel | undefined;
let monitor: AgentMonitor | undefined;

export function activate(context: vscode.ExtensionContext) {
    console.log("AURA Sentinel Agent activado");

    // Registrar comandos
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
            const enabled = config.get<boolean>("watcherEnabled", false);

            if (enabled) {
                vscode.window.showWarningMessage(
                    "El watcher de Cline ya está activo. Se desactivará.",
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
            // Placeholder: delegar al panel para mostrar interfaz
            vscode.window.showInformationMessage(
                "Modelo local: Escribe tu prompt en el panel de AURA Sentinel.",
            );
        },
    );

    // Inicializar watcher si la config lo tiene activado
    const config = vscode.workspace.getConfiguration("auraSentinel");
    if (config.get<boolean>("watcherEnabled", false)) {
        monitor = new AgentMonitor(context);
    }

    // Suscripciones
    context.subscriptions.push(
        activateCommand,
        openPanelCommand,
        toggleWatcherCommand,
        runLocalModelCommand,
    );

    // Abrir panel automáticamente al activar si no hay otro panel
    if (!panel) {
        panel = new AuraSentinelPanel(context);
    }
}

export function deactivate() {
    if (panel) {
        panel.dispose();
    }
    if (monitor) {
        monitor.dispose();
    }
}
