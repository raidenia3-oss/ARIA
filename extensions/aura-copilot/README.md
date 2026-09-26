# AURA Copilot

AURA Copilot brings AI assistance into VS Code with voice input, multimodal context, and tight integration with the AURA backend.

## Features

- Toggle voice input with `Ctrl+Alt+M` / `Cmd+Alt+M`
- Send selected code or text to the AURA Copilot WebView
- Automatic `.vsix` packaging and installation via `python scripts/install_copilot.py`

## Requirements

- Node.js >= 18
- VS Code >= 1.74.0
- AURA backend reachable at `http://localhost:8000` (configurable)

## Development

```bash
cd extensions/aura-copilot
npm install
npm run compile
```

## Packaging & Installation

```bash
python scripts/install_copilot.py
```

This will:
1. Run `npx vsce package`
2. Detect the local `code` binary
3. Install the generated `.vsix` with `--force`
4. Clean up the temporary `.vsix`

## Usage

Press `Ctrl+Alt+M` to start/stop voice recording. The captured audio is streamed to the AURA backend and the transcription is sent to the active AURA Copilot WebView panel.
