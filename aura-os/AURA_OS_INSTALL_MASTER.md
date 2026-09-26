# AURA OS + AME MOBILE — PLAN MAESTRO FUSIONADO
## Instalación dual boot segura | Windows intacto | Automatizada

```
╔════════════════════════════════════════════════════════════════════════╗
║                                                                        ║
║        AURA OS: Sistema Operativo Personalizado (Arch Linux)          ║
║        AME Launcher: Móvil sincronizado con AURA                      ║
║                                                                        ║
║              Dual Boot Seguro | Windows Intacto | Totalmente          ║
║                        Automatizado                                    ║
║                                                                        ║
╚════════════════════════════════════════════════════════════════════════╝
```

---

## 📋 RESUMEN EJECUTIVO

**AURA** es el sistema operativo de escritorio basado en Arch Linux con:
- Hyprland + Caelestia Shell como interfaz moderna
- Godot 4.x como HUD/visualización 3D
- FastAPI backend como cerebro del sistema
- Control por gestos con MediaPipe
- Autoaprendizaje profundo y narrativa coherente

**AME** es el launcher móvil (Android/iOS) que:
- Descubre AURA automáticamente vía mDNS
- Sincroniza en tiempo real con el desktop
- Envía comandos de voz/texto al cerebro de AURA
- Muestra telemetría y notificaciones del sistema

**Windows se mantiene intacto** mediante GRUB dual boot.

**Tiempo total:** 30-60 minutos  
**Riesgo:** BAJO (backup automático, rollback posible)

---

## ⚠️ REQUISITOS PREVIOS

### Hardware
- PC/Laptop con SSD 256GB+ (recomendado 512GB)
- GPU NVIDIA o AMD (drivers incluidos)
- 16GB RAM mínimo (32GB recomendado)
- Conexión WiFi estable
- Móvil Android 11+ o iOS 14+ (para AME)

### Software
- Windows 10/11 instalado y funcionando
- Conexión a internet
- 1 pendrive/USB 8GB+ vacío
- Acceso a BIOS/UEFI

### Backup
```powershell
# En Windows (PowerShell como Admin):
wbadmin start backup -backupTarget:E: -include:C: -allCritical -quiet
```

---

## ✅ CHECKLIST DE SEGURIDAD

- [ ] Backup completo de Windows creado
- [ ] Acceso a BIOS/UEFI confirmado
- [ ] USB disponible (8GB+)
- [ ] Espacio libre en SSD (mínimo 150GB)
- [ ] Conexión WiFi disponible
- [ ] Contraseña de Windows anotada

**Si algo no está marcado, no continúes.**

---

## 📊 PASO 1: PREPARAR WINDOWS

### 1.1 Reducir partición C:

```
Windows + R → diskmgmt.msc → Enter
Click derecho en "C:" → Shrink Volume
Enter amount: 150000 MB (150GB) MÍNIMO
Click: Shrink
Esperar 5-10 minutos
```

**Resultado:** Espacio sin asignar (gris) para AURA OS.

---

## 🔌 PASO 2: CREAR USB BOOTEABLE

### Opción A: Windows (Rufus)
1. Descargar Rufus: https://rufus.ie/
2. Conectar USB (será ELIMINADO)
3. Ejecutar Rufus:
   - Device: Tu USB
   - Boot selection: archlinux-2024.01.01-x86_64.iso
   - Partition scheme: GPT
   - Target system: UEFI (non-CSM)
   - File system: FAT32
   - Click: START
   - Esperar ~5 minutos

### Opción B: Linux/Mac
```bash
sudo umount /dev/sdX1 2>/dev/null
sudo dd if=archlinux-2024.01.01-x86_64.iso of=/dev/sdX bs=4M status=progress
sudo sync
sudo eject /dev/sdX
```

---

## ⚙️ PASO 3: INSTALAR ARCH LINUX (Automatizado)

### 3.1 Bootear desde USB
```
1. Reiniciar PC
2. Presionar: F2, F10, DEL o ESC (según marca)
3. Buscar: Boot Order / Boot Sequence
4. Cambiar a: USB / UEFI USB
5. Guardar y salir
```

### 3.2 Conectar WiFi
```bash
iwctl
[iwctl]# device list
[iwctl]# station <device> scan
[iwctl]# station <device> connect <SSID>
[iwctl]# exit
ping -c 3 google.com
```

### 3.3 Ejecutar instalador automatizado

```bash
curl -O https://raw.githubusercontent.com/aura-os/install/main/install-aura.sh
chmod +x install-aura.sh
sudo bash install-aura.sh
```

El script instalará Arch Linux automáticamente:
- Particionado seguro (no toca Windows)
- GRUB dual boot configurado
- Hyprland + Caelestia + Godot
- Backend AURA copiado y configurado
- Servicios systemd habilitados

**Tiempo:** 15-20 minutos

---

## 🔄 PASO 4: CONFIGURAR GRUB DUAL BOOT

### 4.1 Verificar detección de Windows
```bash
sudo os-prober
sudo grub-mkconfig -o /boot/grub/grub.cfg
```

### 4.2 Personalizar GRUB
```bash
sudo vim /etc/default/grub
```

Cambiar:
```
GRUB_DEFAULT=0              # AURA OS primero
GRUB_TIMEOUT=5              # 5 segundos de espera
GRUB_TIMEOUT_STYLE=menu     # Mostrar menú
GRUB_DISABLE_OS_PROBER=false
```

Regenerar:
```bash
sudo grub-mkconfig -o /boot/grub/grub.cfg
```

---

## 🖥️ PASO 5: CONFIGURAR ESCRITORIO

### 5.1 Instalar dependencias
```bash
sudo pacman -Syu
sudo pacman -S --noconfirm \
    hyprland hyprlock hyprpaper hyprcursor \
    waybar wofi dunst \
    alacritty kitty \
    qt5-wayland qt6-wayland \
    xorg-xwayland \
    pipewire pipewire-pulse pavucontrol \
    nvidia-utils nvidia-dkms amd-ucode \
    godot
```

### 5.2 Configurar Hyprland
```bash
mkdir -p ~/.config/hypr
nano ~/.config/hypr/hyprland.conf
```

Pegar configuración AURA:
```
monitor=,preferred,auto,1

input {
    kb_layout = us,es
    follow_mouse = 1
}

general {
    gaps_in = 5
    gaps_out = 20
    border_size = 2
    col.active_border = rgba(8a2be2ff) rgba(38bdf8ff) 45deg
    col.inactive_border = rgba(0a0e27ff)
    layout = master
}

$mainMod = SUPER

bind = $mainMod, Return, exec, alacritty
bind = $mainMod, D, exec, wofi --show drun
bind = $mainMod, Q, killactive,
bind = $mainMod, M, exit,
bind = $mainMod, A, exec, /opt/aura/shell/aura-shell

exec-once = hyprpaper
exec-once = dunst
exec-once = waybar
exec-once = systemctl --user start aura-brain.service
exec-once = systemctl --user start aura-gesture.service
```

### 5.3 Crear servicios systemd
```bash
sudo nano /etc/systemd/system/aura-brain.service
```

```ini
[Unit]
Description=AURA Brain (FastAPI Backend)
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=aura
WorkingDirectory=/opt/aura/backend
ExecStart=/opt/aura/venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo nano /etc/systemd/system/aura-gesture.service
```

```ini
[Unit]
Description=AURA Gesture Control
After=display-manager.service

[Service]
Type=simple
User=aura
ExecStart=python3 /opt/aura/gesture/gesture_control.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical.target
```

Habilitar:
```bash
sudo systemctl daemon-reload
sudo systemctl enable aura-brain
sudo systemctl enable aura-gesture
sudo systemctl start aura-brain
sudo systemctl start aura-gesture
```

---

## 🧠 PASO 6: CONFIGURAR BACKEND AURA

### 6.1 Copiar backend
```bash
sudo mkdir -p /opt/aura/{backend,shell,gesture,data}
sudo chown -R aura:aura /opt/aura
cp -r /mnt/windows_share/AURA/backend /opt/aura/
cp -r /mnt/windows_share/AURA/scripts /opt/aura/
```

### 6.2 Setup Python
```bash
cd /opt/aura
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

### 6.3 Configurar .env
```bash
nano /opt/aura/backend/.env
```

```
DATABASE_URL=postgresql://aura:aura@localhost/aura_db
REDIS_URL=redis://localhost:6379/0
GROQ_API_KEY=<tu-key>
MISTRAL_API_KEY=<tu-key>
DEEPSEEK_API_KEY=<tu-key>
OPENROUTER_API_KEY=<tu-key>
GEMINI_API_KEY=<tu-key>
NVIDIA_API_KEY=<tu-key>
ZAI_API_KEY=<tu-key>
HF_TOKEN=<tu-key>
```

### 6.4 Setup PostgreSQL
```bash
sudo systemctl start postgresql
sudo -u postgres psql << 'PSQL'
CREATE USER aura WITH PASSWORD 'aura';
CREATE DATABASE aura_db OWNER aura;
GRANT ALL PRIVILEGES ON DATABASE aura_db TO aura;
\q
PSQL
```

### 6.5 Exportar Godot HUD
```bash
cp -r ~/AURA/godot /opt/aura/shell/
cd /opt/aura/shell/godot
godot --headless --export-release "Linux/X11" /opt/aura/shell/aura-shell
chmod +x /opt/aura/shell/aura-shell
```

---

## 📱 PASO 7: CONFIGURAR AME LAUNCHER

### 7.1 Crear proyecto Flutter
```bash
flutter create --template=app ame_launcher
cd ame_launcher
```

### 7.2 Configurar conexión a AURA
```dart
// lib/services/aura_service.dart
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:mdns_plugin/mdns_plugin.dart';

class AuraService {
  late WebSocketChannel _channel;
  final String _serviceName = '_aura._tcp';
  
  Future<void> discoverAura() async {
    try {
      final mdnsPlugin = MDnsPlugin();
      final services = await mdnsPlugin.lookup(_serviceName);
      if (services.isNotEmpty) {
        final service = services.first;
        final host = service.host ?? 'aura.local';
        final port = service.port ?? 8000;
        connectToAura('ws://$host:$port/ws/telemetry');
      }
    } catch (e) {
      connectToAura('ws://aura.local:8000/ws/telemetry');
    }
  }
  
  void connectToAura(String url) {
    _channel = WebSocketChannel.connect(Uri.parse(url));
    _channel.stream.listen((message) {
      final data = jsonDecode(message);
      onTelemetryUpdate(data);
    });
  }
  
  void onTelemetryUpdate(Map<String, dynamic> data) {
    print('CPU: ${data['cpu_percent']}%');
    print('RAM: ${data['ram_percent']}%');
    print('Agents: ${data['active_agents']}');
  }
}
```

### 7.3 Build e instalar
```bash
flutter build apk --release
adb install build/app/outputs/flutter-app/release/app-release.apk
```

---

## ✅ PASO 8: VERIFICAR TODO

### 8.1 Verificar AURA OS
```bash
curl http://localhost:8000/health
# Esperado: {"status": "ok"}

systemctl status aura-brain
systemctl status aura-gesture
```

### 8.2 Verificar Hyprland
```
Super (Windows key) → abre menú
Super + Return → terminal
Super + D → launcher
Super + A → AURA Shell (Godot)
```

### 8.3 Verificar AME
- Abrir AME Launcher en el móvil
- Debería descubrir AURA automáticamente
- Mostrar CPU/RAM/Agents
- Enviar comando de prueba

### 8.4 Verificar dual boot
```bash
sudo reboot
# En GRUB: seleccionar "Windows Boot Manager"
# Windows debería bootear normalmente
```

---

## 🔍 TROUBLESHOOTING

### GRUB no ve Windows
```bash
sudo os-prober
sudo grub-mkconfig -o /boot/grub/grub.cfg
```

### Hyprland no inicia
```bash
journalctl -xe
lspci | grep -E 'NVIDIA|AMD'
sudo pacman -S nvidia-dkms  # NVIDIA
```

### Backend no escucha en 8000
```bash
sudo netstat -tlnp | grep 8000
sudo systemctl restart aura-brain
```

### AME no conecta
```bash
nslookup aura.local
sudo ufw allow 8000/tcp
sudo ufw allow 5353/udp  # mDNS
```

---

## 📝 COMANDOS ÚTILES

```bash
# Actualizar sistema
sudo pacman -Syu

# Actualizar AURA backend
cd /opt/aura/backend
git pull
pip install -r requirements.txt -U
sudo systemctl restart aura-brain

# Ver logs
journalctl -u aura-brain -f

# Copiar archivos desde Windows
sudo mount -t cifs //windows-pc/share /mnt/share -o username=tu_user
```

---

## 🎯 CHECKLIST FINAL

- [ ] AURA OS bootea sin errores
- [ ] Windows bootea desde GRUB
- [ ] Backend responde en localhost:8000
- [ ] Hyprland compositor funcional
- [ ] Godot HUD abre con Super+A
- [ ] Gesture control detecta gestos
- [ ] AME descubre AURA vía mDNS
- [ ] AME muestra telemetría en vivo
- [ ] AME envía comandos a AURA
- [ ] Todos los servicios systemd habilitados

---

## 🚀 PRÓXIMOS PASOS

1. **Backup de Windows** (OBLIGATORIO)
2. **Reducir partición C:** en Windows
3. **Crear USB booteable** con Arch Linux
4. **Ejecutar install-aura.sh** desde el live USB
5. **Instalar AME** en el móvil
6. **Disfrutar** AURA + AME sincronizados

---

**¿Ejecutamos ya?** 🚀
