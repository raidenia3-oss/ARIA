# 📊 AURA OS — Estado del Proyecto

## 🎯 Objetivo
Crear tu propia distro Linux personalizada con AURA IA, Ruby, Hyprland y tema Caelestia, lista para ejecutarse desde USB o WSL2.

## ✅ Completado (sin intervención física)
- [x] USB VIVIANA preparado con Alpine ISO + AURA_INSTALL
- [x] Scripts de instalación para Alpine Live
- [x] Backend AURA + dependencias Python
- [x] CLI chat texto (`aura-cli.sh`)
- [x] CLI chat voz (`aura-voice.sh`)
- [x] Dashboard web (`aura-dashboard.html`)
- [x] CLI Ruby (`aura_cli.rb`) — chat con AURA en Ruby
- [x] Herramientas Ruby (`custom_tools.rb`) — scan, whois, ping, geo, hash, encode/decode, uuid
- [x] Panel sistema (`panel.sh`) — info del sistema estilo Caelestia
- [x] Script de inicio (`aura-personalizada.sh`) — arranca servicios + menú interactivo
- [x] Theme Hyprland Caelestia (`hyprland.conf`) — purple/blue gradient, blur, animations
- [x] Build script ISO personalizada (`build.sh`)
- [x] Scripts WSL2 (`install-wsl2.ps1`, `start-aura.ps1`)
- [x] Scripts VirtualBox (`setup_vm_windows.bat`)
- [x] Diagnóstico del proyecto (`DIAGNOSTICO_PROYECTO.md`)

## ⏳ Bloqueado (requiere intervención física)
- [ ] Bootear USB VIVIANA → Alpine → ejecutar installer
- [ ] Habilitar WSL2 en Windows (features + reboot + posible BIOS)
- [ ] Instalar VirtualBox/Docker

## 📁 Archivos listos
```
aura-os/
├── scripts/
│   ├── aura-installer.sh          # Installer Alpine
│   ├── verify-backend.sh          # Verificación backend
│   ├── aura-cli.sh                # Chat texto
│   ├── aura-voice.sh              # Chat voz
│   ├── aura-dashboard.html        # Dashboard web
│   ├── preparar-usb-alpine.ps1    # Preparar USB
│   ├── install-wsl2.ps1           # Instalar WSL2
│   ├── start-aura.ps1             # Iniciar AURA WSL2
│   └── setup_vm_windows.bat       # VM VirtualBox
├── custom-distro/
│   ├── alpine-rootfs/
│   │   ├── etc/skel/.config/hypr/hyprland.conf
│   │   ├── opt/aura/scripts/
│   │   │   ├── aura_cli.rb
│   │   │   ├── custom_tools.rb
│   │   │   └── panel.sh
│   │   └── root/
│   │       ├── aura-personalizada.sh
│   │       └── aura-personalizada-quick.sh
│   ├── build.sh
│   └── README.md
├── DIAGNOSTICO_PROYECTO.md
└── README.md
```

## 🚀 Cuándo se pueda ejecutar algo físico

### Opción A: USB Alpine (recomendada)
1. Apagar PC
2. Encender → F12 → USB VIVIANA
3. En Alpine:
   ```bash
   lsblk
   mount /dev/sdb2 /mnt/usb 2>/dev/null || mount /dev/sda2 /mnt/usb
   sh /mnt/usb/aura-install/aura-installer.sh
   ```

### Opción B: WSL2
1. PowerShell Admin:
   ```powershell
   wsl --install --no-distribution
   ```
2. Reboot
3. Ejecutar:
   ```powershell
   powershell -ExecutionPolicy Bypass -File "C:\Users\User\Downloads\AURA\aura-os\scripts\install-wsl2.ps1"
   ```

### Opción C: VirtualBox
1. Instalar VirtualBox
2. Ejecutar:
   ```batch
   C:\Users\User\Downloads\AURA\aura-os\scripts\setup_vm_windows.bat
   ```

## 🔮 Próximos pasos (sin intervención física)
- [ ] Crear theme de iconos Caelestia
- [ ] Crear wallpaper personalizado
- [ ] Agregar más herramientas Ruby
- [ ] Mejorar dashboard web
- [ ] Documentar API de AURA backend
- [ ] Preparar scripts de backup/restore
