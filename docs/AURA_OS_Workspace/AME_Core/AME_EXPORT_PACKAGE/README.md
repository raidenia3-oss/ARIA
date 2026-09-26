# AME_EXPORT_PACKAGE - Paquete de Exportación Manual del Agente AME

**Versión:** 2.0  
**Fecha:** 2026-06-06  
**Entorno objetivo:** Termux (Android)

---

## Estructura del Paquete

```
AME_EXPORT_PACKAGE/
├── README.md                    # Este archivo
├── .env.example                 # Plantilla API Key OpenRouter
├── install_ame.sh               # Instalador unificado (ejecutar en Termux)
├── core/
│   └── server.py                # Proxy FastAPI des-censor (OpenAI-compat)
├── modules/
│   ├── osint_username.py        # Rastreo de alias en 14 plataformas
│   ├── osint_reputation.py      # Análisis de reputación IP/dominio
│   └── wifi_client_telemetry.py # Cliente de telemetría WiFi
├── hooks/
│   └── termux_hooks.sh          # Ganchos nativos de Termux
└── config/
    └── ame_config_template.json # Plantilla de configuración
```

## Instalación Rápida

1. **Transferir** toda la carpeta `AME_EXPORT_PACKAGE/` al teléfono (vía WhatsApp, USB, o SCP).

2. **En Termux**, navegar a la carpeta:

   ```bash
   cd /sdcard/AME_EXPORT_PACKAGE
   ```

3. **Ejecutar el instalador**:

   ```bash
   bash install_ame.sh
   ```

4. **Editar la configuración** con la IP de tu PC:
   ```bash
   nano ~/AME-termux/config.json
   ```
   Cambia `aura_pc_url` a `ws://IP_DE_TU_PC:8765`

## Comandos Disponibles

| Comando                    | Descripción                        |
| -------------------------- | ---------------------------------- |
| `ame osint-user <usuario>` | Rastreo de alias en 14 plataformas |
| `ame osint-rep <ip>`       | Análisis de reputación de IP       |
| `ame osint-rep <dominio>`  | Análisis de reputación de dominio  |
| `ame telemetry`            | Estado actual del nodo             |
| `ame telemetry-daemon`     | Iniciar telemetría continua        |
| `ame scan`                 | Escaneo de red local               |
| `ame status`               | Estado de servicios AURA           |

## Comandos del Daemon

| Comando       | Descripción                             |
| ------------- | --------------------------------------- |
| `aura-start`  | Iniciar daemon de telemetría + watchdog |
| `aura-stop`   | Detener todos los servicios             |
| `aura-status` | Ver estado de servicios y red           |
| `aura-logs`   | Ver logs en tiempo real                 |

## Proxy Des-Censor (core/server.py)

Proxy FastAPI que sirve de puente entre la app móvil y OpenRouter. Ejecutar en la PC:

```bash
cd AME_EXPORT_PACKAGE
pip install fastapi uvicorn httpx python-dotenv
# Editar .env con tu API Key de OpenRouter
cp .env.example .env
nano .env
# Iniciar proxy
python core/server.py
```

Al arrancar, el proxy imprime la URL exacta para configurar en el celular:

```
URL para celular:   http://192.168.X.X:8000/v1
```

### Funciones del Proxy

- **Rotación automática** entre modelos gratuitos (Llama-3, Qwen-Coder, Mistral)
- **Inyector de system prompt** en modo desarrollador (sin censura)
- **Limpiador de salida** (regex) que elimina frases de rechazo/advertencia
- **Fallback automático**: si un modelo tiene rate limit, prueba el siguiente

## Dependencias

- **Python 3.11+** (instalado por Termux)
- **requests** (pip)
- **websockets** (pip)
- **fastapi**, **uvicorn**, **httpx**, **python-dotenv** (para el proxy)
- **termux-api** (pkg) - opcional, para WiFi info

## Configuración

El archivo `config.json` controla el comportamiento del agente:

```json
{
  "node_id": "ame-mobile-01",
  "aura_pc_url": "ws://192.168.1.100:8765",
  "telemetry_port": 9900,
  "scan_interval_sec": 30
}
```

## Notas de Seguridad

- El paquete NO contiene API keys ni tokens
- Todos los timeouts están configurados a 5 segundos para evitar bloqueos
- Los logs se almacenan en `~/AME-termux/logs/`
- Los PIDs de procesos se guardan en `~/AME-termux/.pids/`
