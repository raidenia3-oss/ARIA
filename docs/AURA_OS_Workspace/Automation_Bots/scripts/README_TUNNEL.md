# 🌐 Guía: Cloudflare Tunnel para AURA Core

**Objetivo:** Acceder a AURA Core desde AME (Android/Termux) desde cualquier red, no solo WiFi local.

---

## 📋 Requisitos

1. **Python 3.10+** instalado en la PC
2. **cloudflared** (se instala automáticamente con `setup_cloudflare.py`)
3. Opcional: Dominio propio registrado en Cloudflare
4. Opcional: Cuenta gratuita de Cloudflare (para dominio propio)

---

## 🚀 Instalación Rápida (trycloudflare.com — Gratis)

```bash
# 1. Ejecutar el script de configuración (modo gratis sin cuenta)
python scripts/setup_cloudflare.py
# Selecciona opción [1] → trycloudflare.com

# 2. Iniciar servicios
python scripts/start_aura.py

# 3. Verificar URLs en la consola de cloudflared
# Aparecerán URLs tipo: https://random-abc.trycloudflare.com

# 4. Generar config para el celular
python scripts/ame_config_generator.py

# 5. Copiar al celular
adb push aura_urls/ame_config.json /sdcard/ame_config.json
```

---

## 🌍 Con Dominio Propio (Producción)

```bash
# 1. Ejecutar el script con opción [2]
python scripts/setup_cloudflare.py
# Selecciona opción [2] → dominio propio

# Seguir las instrucciones en pantalla:
# - Login con Cloudflare
# - Crear túnel
# - Configurar DNS routes

# 2. Iniciar todo
python scripts/start_aura.py

# 3. Generar config para AME
python scripts/ame_config_generator.py

# 4. Copiar al celular
adb push aura_urls/ame_config.json /sdcard/ame_config.json
```

---

## 📱 Desde el Celular (Termux + AME)

### Opción A: Usando el config generado
```bash
# En Termux
cd ~/aura
python join_swarm.py --server wss://aura-eventbus.TU_DOMINIO.workers.dev --secret TU_CLAVE
```

### Opción B: WiFi Local (sin túnel)
```bash
# En Termux
cd ~/aura
python join_swarm.py --server ws://192.168.1.100:8765 --secret TU_CLAVE
```

---

## 🗂️ Estructura de Archivos

```
AURA/
├── scripts/
│   ├── setup_cloudflare.py      # Instala + configura túnel
│   ├── start_aura.py            # Inicia todo + monitorea
│   ├── ame_config_generator.py  # Genera ame_config.json
│   └── README_TUNNEL.md         # Este archivo
│
├── aura_urls.json               # URLs generadas (output de setup)
├── aura_urls/
│   └── ame_config.json          # Config para el celular (copiar a /sdcard/)
│
├── AURA_Core/
│   ├── config.json              # Config AURA PC
│   └── godot_bridge.py          # Godot WebSocket (puerto 9090)
│
├── AME_Core/
│   └── servidor_ame.py          # Servidor AME (puerto 5000)
│
└── cloudflared/
    └── config.yml               # Config Cloudflare Tunnel
```

---

## 🔧 Troubleshooting

| Problema | Solución |
|----------|----------|
| `cloudflared: command not found` | Ejecutar `python scripts/setup_cloudflare.py` |
| `TLS handshake failed` | Verificar que el servicio local esté corriendo |
| `Failed to fetch` desde AME | Verificar que `ame_config.json` esté en `/sdcard/` |
| `403 Forbidden` | Token de acceso expirado, re-ejecutar setup |
| Timeout en AME | Aumentar `timeout` en `ame_config.json` (default 30s) |
| DNS no resuelve | Esperar 1-2 minutos después de configurar routes |

---

## 🔐 Seguridad

- Nunca commitear `aura_urls.json` a repositorios públicos
- El campo `AURA_SECRET_KEY` en `config.json` es sensible
- Usar HTTPS (cloudflare tunnel) para producción
- Rotar credenciales de cloudflared cada 90 días

---

*Última actualización: 2026-06-03*