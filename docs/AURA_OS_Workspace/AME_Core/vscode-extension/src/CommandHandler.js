// ═══════════════════════════════════════════════════════════════
// CommandHandler.js — Manejador de acciones de la extensión VS Code
// Lee archivos, sugiere código, ejecuta terminal, Godot, compila APK
// ═══════════════════════════════════════════════════════════════

const vscode = require("vscode");
const { exec } = require("child_process");
const path = require("path");

class CommandHandler {
    constructor(colabClient) {
        this.colab = colabClient;
    }

    /** Ejecutar acción según tipo */
    async execute(action, args = {}) {
        switch (action) {
            case "readFile":
                return this.readActiveFile();
            case "suggestCode":
                return this.suggestCode(args.code, args.instruction);
            case "runTerminal":
                return this.runTerminal(args.command);
            case "connectAura":
                return this.connectAuraCore();
            case "compileApk":
                return this.compileAndDeploy(args.projectPath);
            case "openGodot":
                return this.openGodot(args.projectPath);
            case "getEditorContent":
                return this.getEditorContent();
            default:
                return `Acción desconocida: ${action}`;
        }
    }

    /** Leer archivo activo en el editor */
    async readActiveFile() {
        const editor = vscode.window.activeTextEditor;
        if (!editor) return "No hay archivo abierto";
        const doc = editor.document;
        return `Archivo: ${doc.fileName}\n\n${doc.getText().slice(0, 5000)}`;
    }

    /** Obtener contenido del editor activo */
    async getEditorContent() {
        const editor = vscode.window.activeTextEditor;
        if (!editor) return "";
        return editor.document.getText();
    }

    /** Sugerir código según el contexto */
    async suggestCode(code, instruction) {
        const prompt = instruction
            ? `Contexto:\n\`\`\`\n${code || ""}\n\`\`\`\n\nInstrucción: ${instruction}`
            : `Analiza y mejora este código:\n\`\`\`\n${code || ""}\n\`\`\``;

        const response = await this.colab.send(prompt);

        // Si hay editor activo, aplicar sugerencia
        const editor = vscode.window.activeTextEditor;
        if (editor && response.includes("```")) {
            const changed = response.match(/```[\w]*\n([\s\S]*?)```/);
            if (changed) {
                editor.edit((eb) => {
                    const sel = editor.selection;
                    eb.replace(
                        sel.isEmpty ? new vscode.Range(0, 0, editor.document.lineCount, 0) : sel,
                        changed[1],
                    );
                });
            }
        }

        return response;
    }

    /** Ejecutar comando en terminal de VS Code */
    async runTerminal(command) {
        const terminal = vscode.window.createTerminal("AME Agent");
        terminal.show();
        terminal.sendText(command);
        return `Ejecutando: ${command}`;
    }

    /** Conectar con AURA Core local */
    async connectAuraCore() {
        const wsUrl = "ws://localhost:8765";
        return `Conectando a AURA Core en ${wsUrl}... (WebSocket no implementado en esta versión)`;
    }

    /** Compilar APK y desplegar */
    async compileAndDeploy(projectPath) {
        const dir = projectPath || vscode.workspace.rootPath;
        if (!dir) return "Abre un proyecto Android primero";

        const terminal = vscode.window.createTerminal("AME Build");
        terminal.show();

        // Sincronizar Capacitor
        terminal.sendText(`cd "${dir}" && npx cap sync android 2>&1`);

        // Compilar APK debug
        setTimeout(() => {
            terminal.sendText(`cd "${dir}" && cd android && ./gradlew assembleDebug 2>&1`);
        }, 5000);

        // Instalar en dispositivo conectado
        setTimeout(() => {
            terminal.sendText(
                "adb install -r android/app/build/outputs/apk/debug/app-debug.apk 2>&1",
            );
        }, 120000);

        return "Compilación iniciada. Revisa la terminal de VS Code.";
    }

    /** Abrir proyecto Godot Engine */
    async openGodot(projectPath) {
        const godotBin = process.platform === "win32" ? "godot.exe" : "godot";
        const proj = projectPath || vscode.workspace.rootPath;

        try {
            exec(`"${godotBin}" --path "${proj}"`, (err) => {
                if (err) {
                    vscode.window.showErrorMessage(
                        "Godot no encontrado. Instálalo o configura la ruta.",
                    );
                }
            });
            return `Abriendo Godot en: ${proj}`;
        } catch {
            return "Godot no disponible en el PATH";
        }
    }
}

exports.CommandHandler = CommandHandler;
