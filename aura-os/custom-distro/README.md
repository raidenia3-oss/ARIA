# 🛡️ AURA OS Custom Distro

**Tu propia distribución de Linux personalizada** con AURA IA, Ruby, y tema Caelestia.

## 🎯 Características

- **Base:** Alpine Linux ultra-ligero (150MB)
- **Entorno:** Hyprland Wayland con tema Caelestia (purple/blue gradient)
- **IA:** AURA Backend integrado (FastAPI)
- **Ruby:** Runtime + herramientas de seguridad
- **CLI:** `aura_cli.rb` - Chat con AURA en Ruby
- **Tools:** `custom_tools.rb` - Escaneo de puertos, WHOIS, HTTP headers, GeoIP, hashes
- **Panel:** `panel.sh` - Panel superior con info del sistema
- **Dashboard:** Web UI en `http://localhost:8080`

## 🏗️ Estructura

```
custom-distro/
├── alpine-rootfs/
│   ├── etc/
│   │   └── skel/.config/hypr/
│   │       └── hyprland.conf          # Theme Caelestia
│   ├── opt/aura/scripts/
│   │   ├── aura_cli.rb                # CLI Ruby
│   │   ├── custom_tools.rb            # Herramientas hacking
│   │   └── panel.sh                   # Panel sistema
│   └── root/
│       └── aura-personalizada.sh      # Inicio de distro
├── build.sh                           # Constructor ISO
├── packages.x86_64                    # Paquetes Alpine
└── out/
    └── aura-os-custom.iso             # ISO final
```

## 🚀 Uso rápido

### Opción A: USB Live (recomendada)
```bash
# Desde Alpine/Arch/WSL
cd custom-distro
sudo bash build.sh

# Grabar ISO en USB
sudo dd if=out/aura-os-custom.iso of=/dev/sdX bs=4M status=progress
```

### Opción B: WSL2/VirtualBox
1. Montar ISO en VM
2. Bootear
3. Ejecutar: `sh /root/aura-personalizada.sh`

## 🖼️ Wallpaper Slideshow 3D

### Características
- **Fotos personalizadas** desde carpeta USB
- **Mejora automática** por foto:
  - Auto-level / auto-gamma
  - Sharpening + denoise
  - Brillo/contraste óptimo
- **Efectos 3D por foto:**
  - `3d`: blur + colorize purple + vignette + depth
  - `blur`: blur artístico + brillo
  - `glow`: glow cyan + blur leve
  - `normal`: sin efecto
- **Rotación automática** cada X segundos
- Integrado con Hyprland wallpaper

### Uso
```bash
# Configurar con tus fotos (desde USB o disco)
sh /opt/aura/scripts/setup-wallpaper-slideshow.sh /mnt/usb/wallpapers 30 3d

# Parámetros:
#   1: carpeta de fotos
#   2: intervalo en segundos (default: 30)
#   3: efecto (3d|blur|glow|normal)

# Iniciar rotador
sh /opt/aura/scripts/wallpaper-rotator.sh &

# Agregar más fotos:
# 1. Copia fotos a la carpeta
# 2. Ejecuta setup-wallpaper-slideshow.sh de nuevo
```

### Carpetas soportadas
- `/mnt/usb/wallpapers`
- `/mnt/usb/Photos`
- `/mnt/usb/Fotos`
- Cualquier ruta que le pases como parámetro

### Formatos soportados
- `.jpg`, `.jpeg`, `.png`
- Se detectan automáticamente

## 🔧 Herramientas Ruby

```bash
ruby /opt/aura/scripts/custom_tools.rb
```

Comandos:
- `scan <host>` - Escaneo de puertos
- `whois <domain>` - WHOIS
- `ping <host>` - Ping
- `http <url>` - HTTP headers
- `geo <ip>` - GeoIP
- `hash <text>` - Hash generator
- `encode/decode <text>` - Base64
- `uuid` - Generar UUID
- `aura <message>` - Chat con AURA

## 📋 Credenciales

| Item | Valor |
|------|-------|
| Usuario | `aura` |
| Password | `aura123` |
| Backend | http://localhost:8000 |
| Dashboard | http://localhost:8080 |

## 🔨 Construir desde Windows

1. Usar WSL2 o VirtualBox con Alpine
2. Copiar carpeta `custom-distro/` a Linux
3. Ejecutar: `sudo bash build.sh`
4. ISO lista en `out/aura-os-custom.iso`
