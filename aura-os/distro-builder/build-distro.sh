#!/bin/bash

# AURA OS — Custom Alpine + Hyprland Distro Builder
# Uso: ./build-distro.sh

set -e

DISTRO_NAME="AURA-OS"
DISTRO_VERSION="2.0"
BUILD_DIR="build"
OUTPUT_ISO="$BUILD_DIR/aura-os-${DISTRO_VERSION}.iso"
ROOT_FS="$BUILD_DIR/rootfs"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     AURA OS — Custom Linux Distro Builder                     ║"
echo "║     Alpine + Hyprland + AURA + Ruby                           ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ════════════════════════════════════════════════════════════════════════════
# 1. Crear estructura de directorios
# ════════════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}[1/7] Creating directory structure...${NC}"
mkdir -p "$BUILD_DIR"
mkdir -p "$ROOT_FS"

# ════════════════════════════════════════════════════════════════════════════
# 2. Descargar Alpine mini rootfs
# ════════════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}[2/7] Downloading Alpine rootfs...${NC}"

ALPINE_VERSION="3.18"
ALPINE_ARCH="x86_64"
ALPINE_URL="https://dl-cdn.alpinelinux.org/alpine/v${ALPINE_VERSION}/releases/${ALPINE_ARCH}/alpine-minirootfs-${ALPINE_VERSION}.0-${ALPINE_ARCH}.tar.gz"

if [ ! -f "$BUILD_DIR/alpine-minirootfs.tar.gz" ]; then
    echo "Downloading Alpine ${ALPINE_VERSION}..."
    wget -q -O "$BUILD_DIR/alpine-minirootfs.tar.gz" "$ALPINE_URL"
    echo -e "${GREEN}✓ Downloaded${NC}"
else
    echo -e "${GREEN}✓ Already cached${NC}"
fi

# Extract
echo "Extracting..."
tar -xzf "$BUILD_DIR/alpine-minirootfs.tar.gz" -C "$ROOT_FS"

# ════════════════════════════════════════════════════════════════════════════
# 3. Configurar Alpine base
# ════════════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}[3/7] Configuring Alpine base system...${NC}"

# APK repos
cat > "$ROOT_FS/etc/apk/repositories" << 'EOF'
https://dl-cdn.alpinelinux.org/alpine/v3.18/main
https://dl-cdn.alpinelinux.org/alpine/v3.18/community
https://dl-cdn.alpinelinux.org/alpine/v3.18/testing
EOF

# Actualizar apk
chroot "$ROOT_FS" apk update --quiet

# Instalar paquetes base
echo "Installing base packages..."
chroot "$ROOT_FS" apk add --no-cache \
    linux-lts \
    linux-lts-dev \
    libc-dev \
    grub \
    grub-efi \
    mkinitfs \
    e2fsprogs \
    dosfstools \
    util-linux \
    kmod \
    sudo \
    openssh \
    curl \
    wget \
    git \
    vim \
    nano \
    htop \
    tmux \
    zsh \
    zsh-vcs \
    bash-completion \
    ca-certificates

echo -e "${GREEN}✓ Base packages installed${NC}"

# ════════════════════════════════════════════════════════════════════════════
# 4. Instalar Wayland + Hyprland
# ════════════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}[4/7] Installing Wayland + Hyprland...${NC}"

chroot "$ROOT_FS" apk add --no-cache \
    wayland \
    wayland-dev \
    weston \
    weston-dev \
    libxkbcommon \
    libxkbcommon-dev \
    xwayland \
    mesa \
    mesa-dev \
    glu \
    glu-dev \
    libdrm \
    libdrm-dev \
    pixman \
    pixman-dev \
    hyprland \
    hyprland-dev \
    hyprlock \
    hypridle \
    hyprpaper \
    waybar \
    wofi \
    wl-clipboard \
    wf-shell \
    swaybg

echo -e "${GREEN}✓ Hyprland installed${NC}"

# ════════════════════════════════════════════════════════════════════════════
# 5. Instalar AURA + Dependencies
# ════════════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}[5/7] Installing AURA OS + dependencies...${NC}"

# Python + FastAPI
chroot "$ROOT_FS" apk add --no-cache \
    python3 \
    python3-dev \
    py3-pip \
    py3-cryptography \
    py3-cffi \
    ffmpeg \
    redis \
    postgresql-client

# Ruby
chroot "$ROOT_FS" apk add --no-cache \
    ruby \
    ruby-dev \
    ruby-etc \
    ruby-irb \
    ruby-rdoc \
    ruby-bundler \
    gcc \
    make \
    musl-dev

# Firefox para GUI
chroot "$ROOT_FS" apk add --no-cache \
    firefox-esr \
    font-dejavu \
    font-noto \
    font-noto-cjk

echo -e "${GREEN}✓ AURA dependencies installed${NC}"

# ════════════════════════════════════════════════════════════════════════════
# 6. Crear usuario y configurar sistema
# ════════════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}[6/7] Configuring system...${NC}"

# Usuario aura
echo "Creating aura user..."
chroot "$ROOT_FS" addgroup -S aura
chroot "$ROOT_FS" adduser -S -G aura -h /home/aura -s /bin/zsh aura
echo "aura:aura123" | chroot "$ROOT_FS" chpasswd

# Sudo
chroot "$ROOT_FS" addgroup aura wheel
echo "%wheel ALL=(ALL) NOPASSWD:ALL" >> "$ROOT_FS/etc/sudoers"

# Hostname
echo "aura-os" > "$ROOT_FS/etc/hostname"

# Fstab
cat > "$ROOT_FS/etc/fstab" << 'EOF'
/dev/sda1    /boot    vfat    defaults,noatime    0    2
/dev/sda2    /        ext4    defaults,noatime    0    1
EOF

# Crear estructura de AURA
mkdir -p "$ROOT_FS/home/aura/.aura"
mkdir -p "$ROOT_FS/opt/aura"
mkdir -p "$ROOT_FS/var/lib/aura"

# Script de auto-inicio AURA
cat > "$ROOT_FS/usr/local/bin/aura-start" << 'EOFSCRIPT'
#!/bin/sh
cd /opt/aura
python3 backend/main.py --host 0.0.0.0 --port 8000
EOFSCRIPT

chmod +x "$ROOT_FS/usr/local/bin/aura-start"

# Script de status
cat > "$ROOT_FS/usr/local/bin/aura" << 'EOFSCRIPT'
#!/bin/sh
case "$1" in
  start)
    aura-start &
    ;;
  stop)
    pkill -f "python3 backend/main.py"
    ;;
  status)
    curl -s http://localhost:8000/health | jq '.' || echo "AURA is not running"
    ;;
  *)
    echo "Usage: aura {start|stop|status}"
    ;;
esac
EOFSCRIPT

chmod +x "$ROOT_FS/usr/local/bin/aura"

# Hyprland config
mkdir -p "$ROOT_FS/home/aura/.config/hypr"
cat > "$ROOT_FS/home/aura/.config/hypr/hyprland.conf" << 'EOFHYPR'
# AURA OS — Hyprland Config

monitor=,preferred,auto,1

env = XCURSOR_SIZE,24

input {
    kb_layout = us
    kb_variant =
    kb_model =
    kb_options =
    kb_rules =
    follow_mouse = 1
    touchpad {
        natural_scroll = yes
    }
}

general {
    gaps_in = 5
    gaps_out = 20
    border_size = 2
    col.active_border = rgba(33ccffee) rgba(00ff99ee) 45deg
    col.inactive_border = rgba(595959aa)
    layout = dwindle
}

decoration {
    rounding = 10
    blur = yes
    blur_size = 3
    blur_passes = 1
    opacity = 0.9
    drop_shadow = yes
    shadow_range = 4
    shadow_render_power = 3
}

animations {
    enabled = yes
    bezier = myBezier, 0.05, 0.9, 0.1, 1.05
    animation = windows, 1, 10, myBezier
    animation = windowsOut, 1, 10, default, popin 80%
    animation = border, 1, 10, default
    animation = borderangle, 1, 10, default
    animation = fade, 1, 7, default
    animation = workspaces, 1, 6, default
}

dwindle {
    pseudotile = yes
    preserve_split = yes
}

$mod = SUPER

bind = $mod, Q, killactive,
bind = $mod, M, exit,
bind = $mod, V, togglefloating,
bind = $mod, D, exec, wofi --show drun
bind = $mod, P, pseudo,
bind = $mod, J, togglesplit,

bind = $mod, left, movefocus, l
bind = $mod, right, movefocus, r
bind = $mod, up, movefocus, u
bind = $mod, down, movefocus, d

bind = $mod SHIFT, left, movewindow, l
bind = $mod SHIFT, right, movewindow, r
bind = $mod SHIFT, up, movewindow, u
bind = $mod SHIFT, down, movewindow, d

bind = $mod, 1, workspace, 1
bind = $mod, 2, workspace, 2
bind = $mod, 3, workspace, 3
bind = $mod, 4, workspace, 4
bind = $mod, 5, workspace, 5

bind = $mod SHIFT, 1, movetoworkspace, 1
bind = $mod SHIFT, 2, movetoworkspace, 2
bind = $mod SHIFT, 3, movetoworkspace, 3
bind = $mod SHIFT, 4, movetoworkspace, 4
bind = $mod SHIFT, 5, movetoworkspace, 5

bind = $mod, mouse_down, workspace, e+1
bind = $mod, mouse_up, workspace, e-1

windowrule = float,^(firefox)$
EOFHYPR

# Zsh config
cat > "$ROOT_FS/home/aura/.zshrc" << 'EOFZSH'
export EDITOR=nano
export PATH=$PATH:/opt/aura:/home/aura/.local/bin
alias ls='ls --color=auto'
alias ll='ls -lah'
alias cd..='cd ..'
alias aura-web='firefox http://localhost:8000'

# Prompt
PS1='aura@aura-os:%~ $ '

# Auto-start AURA si no está corriendo (opcional)
# if ! pgrep -f "python3 backend/main.py" > /dev/null; then
#     echo "Starting AURA OS..."
#     aura-start &
# fi
EOFZSH

chown -R aura:aura "$ROOT_FS/home/aura"

echo -e "${GREEN}✓ System configured${NC}"

# ════════════════════════════════════════════════════════════════════════════
# 7. Crear initramfs e ISO
# ════════════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}[7/7] Building ISO image...${NC}"

# Este paso requiere herramientas específicas. Para simplicidad,
# creamos un script que documenta el proceso manual.

cat > "$BUILD_DIR/MANUAL_ISO_BUILD.txt" << 'EOFISO'
Para crear la ISO manualmente (en Alpine):

1. Instalar herramientas:
   apk add iso-code xorriso syslinux xfsprogs

2. Copiar rootfs a estructura ISO:
   mkdir -p iso/boot iso/syslinux
   cp -r rootfs/* iso/
   
3. Copiar kernel e initramfs:
   cp rootfs/boot/vmlinuz-lts iso/boot/vmlinuz
   cp rootfs/boot/initramfs-lts iso/boot/initramfs

4. Configurar bootloader ISOLINUX:
   cat > iso/syslinux/isolinux.cfg << 'EOF'
   DEFAULT linux
   LABEL linux
   KERNEL /boot/vmlinuz
   APPEND initrd=/boot/initramfs root=/dev/ram0 console=ttyS0 console=tty0
   EOF

5. Crear ISO:
   xorriso -as mkisofs -o aura-os-2.0.iso \
     -isohybrid-mbr /usr/lib/syslinux/isohdpfx.bin \
     -c syslinux/boot.cat \
     -b syslinux/isolinux.bin -no-emul-boot \
     -boot-load-size 4 -boot-info-table \
     iso/

6. Verificar:
   file aura-os-2.0.iso
   ls -lh aura-os-2.0.iso
EOFISO

echo -e "${GREEN}✓ Rootfs ready at: $ROOT_FS${NC}"
echo -e "${YELLOW}Total size: $(du -sh $ROOT_FS | cut -f1)${NC}"

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗"
echo "║      ✅ Distro Build Complete!                                 ║"
echo "╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Next steps:"
echo "  1. Transfer rootfs to USB:"
echo "     ./write-usb.sh /dev/sdX"
echo ""
echo "  2. Boot from USB:"
echo "     - Insert USB"
echo "     - Restart and press F12"
echo "     - Select USB drive"
echo ""
echo "  3. Login:"
echo "     Username: aura"
echo "     Password: aura123"
echo ""
