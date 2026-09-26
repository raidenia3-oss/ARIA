# AURA Desktop App — User Guide

## Launch

- **Windows GUI**: double-click `aura_app.bat`
- **Windows Console**: double-click `aura_console.bat` or run `python aura_app.py`
- **PowerShell**: `pythonw.exe aura_app.py`

## Chat — Embedded Mode

The Chat tab is fully standalone. It uses `backend_embedded.py` running inside the app process.

- Type a message and press **Send** or **Enter**
- Conversation history is preserved during the session
- **No browser required**
- **No localhost required**
- **No external backend required**

The embedded chat responds to common queries about AURA, services, training, agents, and deployment.

### Chat Commands

- `/help` — show available commands
- `/clear` — clear chat history
- `/status` — show system status
- `/services` — list available services
- `/logs` — view logs
- `/train` — training info

## Advanced Chat

If you configure any of the following in `.env`, the embedded chat can use external AI providers:

- `GEMINI_API_KEY`
- `GROQ_API_KEY`
- `OPENROUTER_API_KEY`
- `HF_TOKEN`
- `LOCAL_LFM_BASE_URL` + `LOCAL_LFM_MODEL` (Ollama)

When no external provider is configured, the app uses its built-in local intelligence.

## Services

The Services tab shows the status of all AURA services retrieved from the backend.

- **Refresh** — reload status from backend
- **Start \<service\>** — launch a service locally
- **Stop Selected** — terminate a running service

Available services:
- `backend` — FastAPI server
- `frontend` — Next.js dev server
- `discord-bot` — Ruby Discord bot
- `hf-space` — Gradio inference server

## Training

The Training tab lets you launch fine-tuning jobs directly from the desktop.

1. Set **Model**, **Dataset**, and **Output** paths
2. Click **Start Training**
3. Output appears in the text area below

## Logs

The Logs tab streams logs in real time from `backend/uvicorn.log` and lets you refresh from the backend API.

## Settings

The Settings tab shows the contents of `.env`. You can edit and save directly from the desktop app.

- **Load .env** — read current `.env`
- **Save .env** — write changes back to `.env`

Restart services after saving to apply changes.
