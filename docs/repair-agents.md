# AURA — Auto-Repair & Agents Guide

## Repair Tab

The **Repair** tab diagnoses and fixes common issues in the project and VS Code installation without leaving the desktop app.

### Features

- **Scan Issues** — Detect missing dependencies, broken configs, syntax errors, missing env files, and broken VS Code settings.
- **Auto-Fix** — Automatically install missing npm packages, Ruby gems, recreate missing `.env`, `.vscode/extensions.json`, etc.
- **Run PowerShell Fixer** — Execute the full `fix_vscode_errors.ps1` repair script, which handles:
  - Reinstalling broken/missing VS Code extensions
  - Repairing `.vscode/settings.json`
  - Clearing oversized VS Code caches
  - Verifying Python/Ruby/Node environments
  - Checking Python syntax across the project

## Agents Tab

The **Agents** tab integrates coding agents directly into AURA so you can ask them to fix, build, or explain anything in the project.

### Supported Agents

| Agent | How it works |
|-------|--------------|
| **Kilo** | Uses `kilo` CLI if available. Detects local Kilo binary or falls back to PATH. |
| **Cline** | Uses `cline` CLI if available. Detects VS Code extension CLI or local binary. |

### Buttons

- **Send Prompt** — Send a free-form prompt to the selected agent.
- **Fix Errors in Project** — Sends a pre-written prompt asking the agent to scan the project, find errors, and fix them.
- **Scan Project** — Asks the agent to report issues without modifying files.

### Example Prompts

- "Fix all Python syntax errors in backend/ and services/"
- "Repair the VS Code workspace configuration in .vscode/"
- "Explain aura_app.py and suggest improvements"
- "Find missing imports in the Ruby Discord bot"

## Troubleshooting

### "Agent bridge unavailable"

Make sure `agent_bridge.py` is in the project root and importable. The desktop app will still work, but the Agents tab will be disabled.

### "No agents detected"

Install Kilo or Cline and make sure the CLI binary is in PATH, or available in the expected install location.

### PowerShell script blocked

Run PowerShell as Administrator and set:
```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```
