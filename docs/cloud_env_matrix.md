# Multi-Cloud Env Matrix

## Vercel (Frontend)

- `VITE_API_URL`: `@railway_api_url` (Vercel secret que apunta a Railway)

## Railway (Backend)

- `RAILWAY_API_URL`: URL pública de Railway (usada por Vercel)
- `HF_API_TOKEN`: Token de Hugging Face (para Spaces/Missions)
- `HF_SPACE_URL`: URL del Space de HF
- `VERCEL_FRONTEND_URL`: URL del deploy en Vercel

## Hugging Face Spaces

- Sincronización: `.github/workflows/hf_sync.yml`
- Se actualiza al hacer push a main usando Git LFS hacia HF

## VS Code (.env local)

```env
VITE_API_URL=http://localhost:8000
RAILWAY_API_URL=http://localhost:8000
HF_API_TOKEN=hf_xxx
HF_SPACE_URL=https://usuario-hf-space.hf.space
VERCEL_FRONTEND_URL=http://localhost:3000
```
