# AURA LOCAL — Guia de Inicio Rapido

## PASO 1: Pega tus API keys

Abrí `ame_backend/.env.local` y completá los campos vacios:

| Proveedor | Donde conseguir la key | Campo en .env.local |
|-----------|----------------------|---------------------|
| **Groq** | https://console.groq.com/keys | `GROQ_API_KEY=gsk_...` |
| **DeepSeek** | https://platform.deepseek.com/api_keys | `DEEPSEEK_API_KEY=sk-...` |
| **OpenRouter** | https://openrouter.ai/keys | `OPENROUTER_API_KEY=sk-or-v1-...` |
| **Nvidia NIM** | https://build.nvidia.com | `NVIDIA_API_KEY=nvapi-...` |
| **Mistral** | https://console.mistral.ai | `MISTRAL_API_KEY=...` |
| **Gemini** (opcional) | https://aistudio.google.com/app/apikey | `GEMINI_API_KEY=...` |

Jan no necesita key — ya esta instalado en tu PC.

## PASO 2: Ejecuta el setup wizard (opcional pero recomendado)

```bash
python scripts/setup_aura.py --check
```

Esto verifica que todo este instalado correctamente.

## PASO 3: Inicia AURA

```bash
scripts/start_aura_local.bat
```

Esto levanta:
- Jan (modelo local)
- Backend AURA (FastAPI en puerto 8000)
- AURA Core Agent

## PASO 4: Probar

```bash
curl -X POST http://localhost:8000/api/hybrid/unified/process \
  -H "Content-Type: application/json" \
  -d "{\"prompt\": \"crea un script python que sume dos numeros\"}"
```

## APPS CONFIGURADAS

| App | Estado | Como usar |
|-----|--------|-----------|
| **Jan** | Instalado y corriendo | Automatico |
| **Android Studio** | Instalado | Pedi "abre android studio" |
| **Obsidian** | Instalado | Pedi "abre obsidian" |
| **Unity Hub** | Instalado | Pedi "abre unity" |
| **Godot** | Instalado (zip en Downloads) | Extrae el zip o setea APPS_GODOT en .env.local |
| **OBS Studio** | No instalado | Instalalo cuando lo necesites |
| **Python** | Instalado | Pedi "ejecuta python script.py" |

## CONEXIONES DE DISPOSITIVOS

### Android (ADB)
```bash
# Conecta tu celular por USB con debugging activado
curl http://localhost:8000/api/devices/android
```

### Termux
```bash
# En Termux: pkg install openssh && sshd
# Luego:
curl http://localhost:8000/api/devices/termux
```

## ENDPOINTS PRINCIPALES

| URL | Funcion |
|-----|---------|
| http://localhost:8000/api/hybrid/unified/process | Chat unificado (IA + Apps + Aprendizaje) |
| http://localhost:8000/api/hybrid/unified/status | Estado del sistema |
| http://localhost:8000/api/local/apps/status | Estado de apps locales |
| http://localhost:8000/api/local/apps/launch | Lanzar app |
| http://localhost:8000/api/local/apps/python | Ejecutar script Python |
| http://localhost:8000/api/devices/status | Estado de dispositivos |
| http://localhost:8000/api/devices/android | Dispositivos Android |
| http://localhost:8000/api/devices/termux | Conexion Termux |
| http://localhost:8000/api/hybrid/memory/stats | Estadisticas de memoria RAG |
| http://localhost:8000/api/hybrid/memory/few-shot | Ejemplos few-shot |

## ENV VARIABLES IMPORTANTES

```env
# Si Godot no se detecta automaticamente:
APPS_GODOT=C:\ruta\al\godot.exe

# Si queres cambiar el modelo de Jan:
JAN_MODEL=qwen2.5-1.5b-instruct

# Si queres forzar modo cloud (sin Jan):
AURA_ROUTER_STRATEGY=cloud_only

# Si queres solo local (sin APIs cloud):
AURA_ROUTER_STRATEGY=local_first
```
