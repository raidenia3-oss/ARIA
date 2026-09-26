# AURA Deployment Guide

## 1. Overview

Este documento describe el despliegue de `AURA` en modo 24/7, con PM2 para persistencia, tunelización remota y watchdog de escaneo Wi-Fi.

## 2. Requisitos

- Python 3.10+ instalado
- Node.js + npm instalados
- PM2 instalado globalmente: `npm install -g pm2`
- `ngrok` o `cloudflared` instalados para túneles remotos

## 3. Ejecutar localmente

Desde la carpeta raíz del proyecto:

```powershell
cd "C:\Users\User\Downloads\AURA"
python .\AME_Core\servidor_ame.py
```

Luego abre: `http://localhost:5000`

## 4. Configurar PM2

El archivo de configuración está en `ecosystem.config.js`.

### Linux / macOS

```bash
cd /path/to/AURA
pm2 start ecosystem.config.js --name aura-servidor-ame
pm2 save
pm2 status
```

Si el intérprete Python de tu entorno virtual no es `/home/user/AURA/env/bin/python`, actualiza `ecosystem.config.js` con la ruta correcta.

### Windows

Ejecuta PowerShell como administrador:

```powershell
cd "C:\Users\User\Downloads\AURA"
powershell -ExecutionPolicy Bypass -File .\setup_pm2_autostart.ps1
```

Esto iniciará PM2 y creará una tarea de inicio automática llamada `AURA-Startup`.

## 5. Control de túneles remotos

El servidor Flask expone endpoints para iniciar/detener/consultar túneles:

- `POST /api/tunnel/start`
  - Body JSON: `{ "type": "ngrok" }` o `{ "type": "cloudflared" }`
- `POST /api/tunnel/stop`
- `GET /api/tunnel/status`

Ejemplo con `curl`:

```bash
curl -X POST http://localhost:5000/api/tunnel/start -H "Content-Type: application/json" -d "{\"type\":\"ngrok\"}"
```

## 6. Watchdog de WiFi

El módulo de telemetría Wi-Fi ahora incluye monitoreo activo.

Endpoints:

- `POST /api/wifi_watchdog/start`
- `POST /api/wifi_watchdog/stop`
- `GET /api/wifi_watchdog/status`

El watchdog se inicia automáticamente al arrancar `servidor_ame.py`.

## 7. Ajustes de seguridad

- Usa `ngrok` con token de autenticación si expones el servicio a internet.
- Para `cloudflared`, configura tu cuenta Cloudflare y túnel antes de usarlo.
- Asegura el servidor Flask con un proxy inverso o firewall si se publica públicamente.

## 8. Troubleshooting

- Si `pm2` no arranca, revisa `./logs/aura-error.log` y `./logs/aura-out.log`.
- Si el túnel no arranca, verifica que `ngrok` o `cloudflared` estén instalados y accesibles en PATH.
- Si la API de WiFi devuelve error, revisa que `telemetria_radio.py` exista en `AME_Core/`.
- Si el watchdog no muestra salud correcta, usa `GET /api/wifi_watchdog/status` para revisar `last_watchdog_message`.

## 9. Archivos clave

- `AME_Core/servidor_ame.py`
- `AME_Core/telemetria_radio.py`
- `AME_Core/tunnel_manager.py`
- `ecosystem.config.js`
- `setup_pm2_autostart.ps1`
