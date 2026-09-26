import * as vscode from "vscode";
import * as os from "os";
import * as nodePath from "path";

let statusBarItem: vscode.StatusBarItem;
let recording: RecordAudio | null = null;
let copilotPanel: vscode.WebviewPanel | null = null;

export function activate(context: vscode.ExtensionContext) {
  console.log("AURA Copilot activated");

  statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  statusBarItem.command = "aura.toggleVoice";
  statusBarItem.text = "$(mic) AURA Voice";
  statusBarItem.tooltip = "Toggle voice input";
  statusBarItem.show();
  context.subscriptions.push(statusBarItem);

  const toggleCommand = vscode.commands.registerCommand("aura.toggleVoice", async () => {
    if (recording) {
      await recording.stop();
      recording = null;
      statusBarItem.text = "$(mic) AURA Voice";
      statusBarItem.backgroundColor = undefined;
    } else {
      recording = new RecordAudio();
      statusBarItem.text = "$(mic) AURA Recording...";
      statusBarItem.backgroundColor = new vscode.ThemeColor("statusBarItem.errorBackground");
      await recording.start();
    }
  });

  const sendCommand = vscode.commands.registerCommand("aura.sendToCopilot", async () => {
    const editor = vscode.window.activeTextEditor;
    const text = editor?.selection ? editor.document.getText(editor.selection) : "";
    if (!text) {
      vscode.window.showWarningMessage("No text selected to send to AURA Copilot.");
      return;
    }
    await ensureCopilotPanel(context);
    await sendToActiveWebview({ type: "text", payload: text });
    vscode.window.showInformationMessage("Sent selection to AURA Copilot.");
  });

  context.subscriptions.push(toggleCommand, sendCommand);
}

async function ensureCopilotPanel(context: vscode.ExtensionContext): Promise<vscode.Webview> {
  if (copilotPanel) {
    copilotPanel.reveal(vscode.ViewColumn.Beside);
    return copilotPanel.webview;
  }

  copilotPanel = vscode.window.createWebviewPanel(
    "aura.copilot",
    "AURA Copilot",
    vscode.ViewColumn.Beside,
    { enableScripts: true }
  );

  copilotPanel.onDidDispose(() => {
    copilotPanel = null;
  });

  copilotPanel.webview.html = getHtmlForWebview(copilotPanel.webview);
  return copilotPanel.webview;
}

async function sendToActiveWebview(message: unknown) {
  if (!copilotPanel) {
    vscode.window.showWarningMessage("Open AURA Copilot panel to receive voice input.");
    return;
  }

  const payload = JSON.stringify(message);
  copilotPanel.webview.postMessage({ text: payload });
}

class RecordAudio {
  private child: import("child_process").ChildProcess | null = null;
  private chunks: Buffer[] = [];

  async start(): Promise<void> {
    const config = vscode.workspace.getConfiguration("aura");
    const backendUrl = config.get<string>("backendUrl", "http://localhost:8000");

    let recordScript: string | undefined;
    try {
      recordScript = require.resolve("node-record-lpcm16/lib/record");
    } catch {
      vscode.window.showWarningMessage("node-record-lpcm16 is not available. Install it to enable voice input.");
      return;
    }

    try {
      this.child = require("child_process").spawn(
        "node",
        [recordScript],
        { env: { ...process.env, AUDIO_RECORD_SAMPLE_RATE: "16000", AUDIO_RECORD_CHANNELS: "1" } }
      );

      if (this.child!.stdout) {
        this.child!.stdout.on("data", (data: Buffer) => {
          this.chunks.push(data);
        });
      }

      if (this.child!.stderr) {
        this.child!.stderr.on("data", (data: Buffer) => {
          console.error(`[aura-copilot] recorder stderr: ${data}`);
        });
      }

      this.child!.on("exit", () => {
        console.log("[aura-copilot] recorder exited");
        void this.upload(backendUrl);
      });

      vscode.window.setStatusBarMessage("$(mic) AURA recording...", 0);
    } catch (error) {
      vscode.window.showErrorMessage(`Failed to start voice recorder: ${error}`);
    }
  }

  async stop(): Promise<void> {
    if (this.child) {
      try {
        this.child.kill("SIGINT");
      } catch {
        // ignore
      }
      this.child = null;
    }
  }

  private async upload(backendUrl: string): Promise<void> {
    if (!this.chunks.length) {
      return;
    }

    const audioBuffer = Buffer.concat(this.chunks);
    this.chunks = [];

    try {
      const response = await fetch(`${backendUrl}/api/webrtc/audio/process`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: `vscode-${os.hostname()}`,
          audio: audioBuffer.toString("base64"),
        }),
      });

      if (!response.ok) {
        throw new Error(`Backend responded with ${response.status}`);
      }

      const data = (await response.json()) as { status?: string };
      const text = data.status ? `Voice processed: ${data.status}` : "Voice processed.";
      vscode.window.showInformationMessage(text);
      await sendToActiveWebview({ type: "audio_result", payload: data });
    } catch (error) {
      vscode.window.showErrorMessage(`AURA voice upload failed: ${error}`);
    }
  }
}

function getHtmlForWebview(webview: vscode.Webview): string {
  const scriptUri = webview.asWebviewUri(vscode.Uri.file(nodePath.join(__dirname, "..", "media", "main.js")));
  const styleUri = webview.asWebviewUri(vscode.Uri.file(nodePath.join(__dirname, "..", "media", "style.css")));

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AURA Copilot</title>
  <link rel="stylesheet" href="${styleUri}">
</head>
<body>
  <div id="app">
    <header>AURA Copilot</header>
    <main id="output">Waiting for input...</main>
  </div>
  <script src="${scriptUri}"></script>
</body>
</html>`;
}

export function deactivate() {
  if (recording) {
    recording.stop();
  }
}
