# ARIA OS sobre Kali Linux — Entorno dedicado, sin servidor, sin navegador

> Propuesta: ejecutar ARIA OS como **sistema operativo dedicado** basado en Kali Linux minimal, con ARIA como shell principal. Cero servidor HTTP, cero puertos abiertos, cero navegador por defecto. ARIA es la única interfaz y el único proceso de usuario.

---

## ¿Por qué Kali Linux como host de ARIA?

| Ventaja | Aplicación a ARIA |
|---------|-------------------|
| **Herramientas de red preinstaladas** (nmap, wireshark, aircrack-ng, metasploit, burpsuite) | ARIA puede escanear, auditar y actuar sobre la red local sin instalar dependencias extra |
| **Anonimato y privacidad** (tor, proxychains, macchanger, torsocks) | Agente autónomo que opera sin dejar rastro de red |
| **Entorno Linux estable y predecible** | Sin sorpresas de Windows Update, DLLs, conflictos de puerto o incompatibilidades de PyInstaller |
| **Live USB / ISO bootable** | Llevas ARIA en un USB y arrancas en cualquier PC como "sistema ARIA" dedicado |
| **Sin servidor HTTP por defecto** | Coincide exactamente con la arquitectura nativa de `aria_native.py` |
| **Disco cifrado (LUKS)** | Memoria local de ARIA (SQLite, Chroma, JSON) protegida físicamente |

---

## Arquitectura propuesta "ARIA OS Kali"

```
┌─────────────────────────────────────────────────────────────┐
│              Hardware (PC dedicado / Live USB)              │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                    Kernel Linux (Kali minimal)              │
│              (sin X11 por defecto, solo lo necesario)       │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│              Window Manager ligero (i3 / XFCE)              │
│              Solo la ventana de ARIA; no hay navegador      │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│              ARIA OS Nativa (PyQt5, proceso único)          │
│  ┌─────────────┐  ┌──────────────────┐  ┌─────────────┐    │
│  │     UI      │  │   Logic Engine   │  │  AI Provider│    │
│  │  (PyQt5)    │  │  (llamada directa)│  │ Ollama/local│    │
│  └─────────────┘  └──────────────────┘  └─────────────┘    │
│          Cero puertos TCP · Cero HTTP · Cero red requerida  │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│              Red (solo si ARIA lo necesita)                 │
│  Ollama (localhost:11434) · Tor · escaneo de red opcional   │
└─────────────────────────────────────────────────────────────┘
```

---

## Pasos para construir el entorno

### 1. Instalar Kali Linux minimal

```bash
# Descargar kali-linux-minimal (sin entorno de escritorio pesado)
# Instalar en disco o USB persistente con LUKS
# Durante la instalación, no marcar "Desktop environment" ni "Web server"
```

### 2. Instalar dependencias de ARIA

```bash
# Actualizar sistema
sudo apt update && sudo apt full-upgrade -y

# Python + PyQt5 + Ollama + herramientas de red
sudo apt install -y python3 python3-pip python3-venv \
    python3-pyqt5 python3-pyqt5.qtsvg \
    ollama git curl wget

# Crear entorno Python para ARIA
python3 -m venv /opt/aria/venv
/opt/aria/venv/bin/pip install --upgrade pip
/opt/aria/venv/bin/pip install python-dotenv

# Descargar modelo de visión local
ollama pull granite3.2-vision:2b
```

### 3. Desplegar ARIA OS nativa

```bash
# Clonar o copiar el proyecto AURA al sistema Kali
sudo mkdir -p /opt/aria
sudo cp -r /ruta/a/AURA/ARIA_APP /opt/aria/
sudo cp -r /ruta/a/AURA/backend /opt/aria/  # opcional, para skills futuras

# Configurar .env para Kali
cat > /opt/aria/ARIA_APP/.env << 'EOF'
ARIA_OLLAMA_URL=http://localhost:11434
ARIA_OLLAMA_MODEL=granite3.2-vision:2b
ARIA_SYSTEM_PROMPT=Eres ARIA, asistente autónomo sobre Kali Linux. Responde en español.
AURA_MEMORY_DIR=/opt/aria/data/memory
AURA_ASSETS_DIR=/opt/aria/ARIA_APP/assets
EOF

# Crear servicio systemd para arranque automático
sudo tee /etc/systemd/system/aria-os.service << 'EOF'
[Unit]
Description=ARIA OS Native Desktop
After=network-online.target ollama.service
Wants=network-online.target

[Service]
Type=simple
User=aria
WorkingDirectory=/opt/aria/ARIA_APP
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/aria/venv/bin/python /opt/aria/ARIA_APP/aria_native.py
Restart=always
RestartSec=5
Environment=DISPLAY=:0

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable aria-os.service
sudo systemctl start aria-os.service
```

### 4. Configurar arranque automático de la UI (autostart del WM)

```bash
# Para i3:
echo "exec --no-startup-id /opt/aria/venv/bin/python /opt/aria/ARIA_APP/aria_native.py" \
    >> /home/aria/.config/i3/config

# Para XFCE: agregar a "Sesión y arranque" → "Aplicación automática"
```

### 5. Verificación

```bash
# Comprobar que no hay puertos abiertos (salvo Ollama si se usa)
sudo ss -tlnp

# Comprobar proceso ARIA
ps aux | grep aria_native

# Comprobar Ollama
curl -s http://localhost:11434/api/tags | python3 -m json.tool
```

---

## Skills específicas para entorno Kali

Dado que Kali trae herramientas de red, se pueden añadir habilidades nativas a ARIA:

| Skill | Comando Kali subyacente | Uso en ARIA |
|-------|------------------------|-------------|
| `net_scan` | `nmap -sS <target>` | Escanear puertos abiertos en la red local |
| `wifi_scan` | `iwlist scan` / `nmcli device wifi list` | Escanear redes WiFi cercanas |
| `mac_spoof` | `macchanger -r <iface>` | Cambiar MAC para anonimato |
| `tor_status` | `systemctl status tor` | Verificar anonimato de red |
| `whois_lookup` | `whois <domain>` | Consultar registros de dominio |
| `packet_capture` | `tcpdump -i <iface> -c 100` | Capturar tráfico de red |

Estas skills se agregan a `NativeLogicEngine._skills` sin tocar la UI ni crear endpoints HTTP.

---

## Ventajas sobre Windows + FastAPI

| Dimensión | Windows + FastAPI (:8000) | Kali + ARIA OS Nativo |
|-----------|--------------------------|----------------------|
| Puertos abiertos | 8000 (HTTP) | Cero |
| Superficie de ataque | Alta (servidor web expuesto) | Mínima (ningún servidor) |
| Dependencia de red | Sí (localhost obligatorio) | No (offline-capable) |
| Anonimato | Ninguno | Tor, proxychains, macchanger |
| Portabilidad | Instalado sobre Windows existente | USB bootable, cualquier PC |
| UI | Navegador / webview | Ventana PyQt5 nativa, fullscreen posible |
| Disco | Sin cifrado por defecto | LUKS cifrado |

---

## Limitaciones conocidas

- **PyQt5 en Kali**: requiere `python3-pyqt5` y un servidor X/Wayland corriendo. Si se usa sin entorno gráfico, ARIA no mostrará ventana (pero el logic engine sigue funcionando vía línea de comandos).
- **Ollama en Kali**: se instala por separado (`ollama pull granite3.2-vision:2b`). Si no hay GPU, corre en CPU (más lento).
- **Hotkeys globales**: `keyboard` y `pystray` están orientados a Windows. En Kali se usaría `xdotool` o `wmctrl` para el wake word / summon global.

---

## Siguiente paso recomendado

1. Probar `ARIA_APP/aria_native.py` en Windows (ya funciona como app nativa).
2. Crear una ISO de Kali Linux minimal con ARIA preinstalada y configurada para auto-arrancar.
3. Probar en hardware dedicado o Live USB persistente.
