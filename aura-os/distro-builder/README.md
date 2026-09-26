# AURA OS — Custom Linux Distribution Builder

Construye una distribución Linux personalizada con Alpine, Hyprland, y AURA OS.

## Características

- **Base**: Alpine Linux 3.18 (lightweight, ~150MB)
- **Window Manager**: Hyprland (modern, tiling, Wayland)
- **Display Server**: Wayland
- **Shell**: Zsh + Oh My Zsh
- **Tools**: Ruby, Python, Node.js, Git
- **AURA**: Integrado y auto-inicia al bootear

## Requisitos

- Linux (para build)
- 15 GB espacio libre
- Docker (opcional, para build aislado)
- USB 8GB+ (para imagen final)

## Quick Start

```bash
cd aura-os/distro-builder
./build-distro.sh
./write-usb.sh /dev/sdX  # Reemplaza X con tu USB
```

## Tamaño

- Alpine base: 150 MB
- Hyprland + deps: 250 MB
- AURA OS: 300 MB
- Ruby tooling: 200 MB
- **Total**: ~900 MB (dejando 6.4 GB libres en USB 7.3GB)

## Boot

1. Inserta USB
2. Reinicia PC
3. Presiona F12 (o tu tecla de boot)
4. Selecciona USB (Kingston DataTraveler o similar)
5. Espera 15-20 segundos
6. Login: `aura` / `aura123`

## Primeros Pasos

```bash
# Verifica AURA
aura --status

# Inicia AURA
aura-start

# Abre navegador
firefox http://localhost:8000

# Ruby disponible
ruby --version
irb
```

## Customización

Edita `build-distro.sh` para agregar/quitar paquetes.

## Estructura del Proyecto

```
distro-builder/
├── README.md              # Este archivo
├── build-distro.sh        # Script principal de construcción
├── write-usb.sh           # Escribe ISO a USB
├── build-alpine.sh        # Construye base Alpine
├── build-hyprland.sh      # Instala Hyprland
├── build-aura.sh          # Instala AURA OS
├── build-ruby.sh          # Instala Ruby tooling
├── build-iso.sh           # Genera ISO final
├── overlay/               # Archivos de overlay
│   ├── etc/               # Configuración del sistema
│   ├── home/aura/         # Home del usuario
│   └── usr/local/bin/     # Scripts de AURA
├── configs/               # Configuraciones
│   ├── hyprland.conf      # Configuración de Hyprland
│   ├── waybar/            # Barra de tareas
│   └── wlogout/           # Logout menu
├── packages.txt           # Lista de paquetes Alpine
└── scripts/
    ├── post-install.sh    # Post-instalación en live
    └── first-boot.sh      # Primer boot del usuario
```

## Build Steps

1. `build-alpine.sh` — Descarga e instala Alpine base
2. `build-hyprland.sh` — Instala Hyprland + Wayland deps
3. `build-aura.sh` — Instala AURA OS en /opt/aura
4. `build-ruby.sh` — Instala Ruby + gems
5. `build-iso.sh` — Genera ISO booteable

## Build Aislado con Docker

```bash
docker build -t aura-distro-builder -f Dockerfile.builder .
docker run --rm -v $(pwd)/output:/output aura-distro-builder
```

## Troubleshooting

### Build falla en Hyprland
```bash
# Asegúrate de tener mesa-utils
apk add mesa-gl
```

### AURA no arranca
```bash
# Verifica servicios
aura --diagnose
```

### Ruby no funciona
```bash
# Reinstala
bundle install
```

### USB no bootea
```bash
# Verifica checksum
sha256sum aura-os.iso
```
