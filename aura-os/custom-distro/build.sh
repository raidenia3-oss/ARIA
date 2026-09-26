#!/bin/bash
# AURA OS Custom Distro - Build Script
# Construye ISO personalizada de Alpine + AURA + Ruby + Hyprland

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build"
ISO_DIR="${SCRIPT_DIR}/out"
ISO_NAME="aura-os-custom.iso"

echo "╔════════════════════════════════════════════╗"
echo "║   AURA OS Custom Distro - Build System    ║"
echo "╚════════════════════════════════════════════╝"
echo ""

# Verificar que estamos en Linux
if [[ "$(uname)" != "Linux" ]]; then
    echo "ERROR: Este script debe ejecutarse en Linux"
    exit 1
fi

# Instalar dependencias
echo "[+] Instalando dependencias..."
sudo pacman -S --needed --noconfirm archiso git squashfs-tools libisoburn 2>/dev/null || \
sudo apt-get install -y archiso git squashfs-tools libisoburn 2>/dev/null || \
apk add archiso git squashfs-tools xorriso 2>/dev/null || true

# Limpiar build anterior
echo "[+] Limpiando build anterior..."
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR" "$ISO_DIR"

# Descargar Alpine minirootfs
echo "[+] Descargando Alpine Linux..."
ALPINE_VERSION="3.19.1"
ALPINE_URL="https://dl-cdn.alpinelinux.org/alpine/v3.19/releases/x86_64/alpine-minirootfs-${ALPINE_VERSION}-x86_64.tar.gz"

if [ ! -f "${BUILD_DIR}/alpine-minirootfs.tar.gz" ]; then
    wget -q "$ALPINE_URL" -O "${BUILD_DIR}/alpine-minirootfs.tar.gz"
fi

# Extraer rootfs
echo "[+] Extrayendo rootfs..."
mkdir -p "${BUILD_DIR}/rootfs"
tar -xzf "${BUILD_DIR}/alpine-minirootfs.tar.gz" -C "${BUILD_DIR}/rootfs"

# Copiar archivos personalizados
echo "[+] Copiando archivos personalizados..."
cp -r "${SCRIPT_DIR}/alpine-rootfs/"* "${BUILD_DIR}/rootfs/"

# Crear script de instalación de paquetes
echo "[+] Creando script de instalación..."
cat > "${BUILD_DIR}/rootfs/install-packages.sh" << 'PKGS'
#!/bin/sh
set -e

echo "Instalando paquetes AURA..."
apk update
apk add --no-cache \
    bash curl wget git \
    python3 py3-pip \
    postgresql postgresql-contrib \
    redis \
    py3-fastapi py3-uvicorn \
    py3-websockets py3-pydantic py3-aiofiles \
    hyprland wayland libxkbcommon \
    pipewire pipewire-pulse \
    mesa mesa-dri-gallium \
    alacritty ttf-dejavu noto-fonts \
    jq ruby ruby-dev \
    busybox-extras

echo "✓ Paquetes instalados"
PKGS

chmod +x "${BUILD_DIR}/rootfs/install-packages.sh"

# Crear ISO
echo "[+] Creando ISO..."
cd "${BUILD_DIR}/rootfs"

# Comprimir con squashfs
if command -v mksquashfs &> /dev/null; then
    mksquashfs "${BUILD_DIR}/rootfs" "${BUILD_DIR}/aura.squashfs" -noappend -comp xz 2>/dev/null || true
fi

# Crear ISO con xorriso
if command -v xorriso &> /dev/null; then
    xorriso -as mkisofs \
        -iso-level 3 \
        -full-iso9660-filenames \
        -volid "AURA_OS_CUSTOM" \
        -output "${ISO_DIR}/${ISO_NAME}" \
        "${BUILD_DIR}/rootfs" 2>/dev/null || true
fi

# Si no se pudo crear ISO con xorriso, crear tarball
if [ ! -f "${ISO_DIR}/${ISO_NAME}" ]; then
    echo "[!] ISO no creada, creando tarball..."
    tar -czf "${ISO_DIR}/aura-os-custom.tar.gz" -C "${BUILD_DIR}/rootfs" .
fi

echo ""
echo "╔════════════════════════════════════════════╗"
echo "║      AURA OS Custom - BUILD COMPLETE      ║"
echo "╚════════════════════════════════════════════╝"
echo ""
echo "Output: ${ISO_DIR}/${ISO_NAME}"
echo ""
