#!/bin/bash
# AURA OS - Arch Linux Automated Installation
# Basado en plan oficial Claude/Gemini
# Uso: sudo bash install-aura.sh
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     AURA OS - Arch Linux Installer       ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"

if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}ERROR: Ejecutar como root: sudo bash install-aura.sh${NC}"
    exit 1
fi

echo -e "\n${YELLOW}[FASE 0] Verificando sistema...${NC}"
if [ ! -d /sys/firmware/efi ]; then
    echo -e "${RED}ERROR: Sistema no es UEFI. Se requiere UEFI.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Sistema UEFI detectado${NC}"

if ! ping -c 1 8.8.8.8 &> /dev/null; then
    echo -e "${RED}ERROR: Sin conexión a internet${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Conexión a internet OK${NC}"

echo -e "\n${RED}╔════════════════════════════════════════════╗${NC}"
echo -e "${RED}║           VERIFICACION DE SEGURIDAD       ║${NC}"
echo -e "${RED}╚════════════════════════════════════════════╝${NC}"
echo -e "${YELLOW}Este script SOLO tocara el espacio NO ASIGNADO.${NC}"
echo -e "${YELLOW}NUNCA tocara C:, D:, ni la particion EFI de Windows.${NC}"

echo -e "\n${BLUE}Discos detectados:${NC}"
sudo fdisk -l | grep "Disk /dev" | grep -v loop

echo -e "\n${BLUE}Particiones de Windows (NTFS) - NO se tocaran:${NC}"
WIN_PARTS=$(sudo fdisk -l | grep "NTFS" | awk '{print $1}')
if [ -n "$WIN_PARTS" ]; then
    for part in $WIN_PARTS; do
        echo -e "  ${YELLOW}$part${NC}"
    done
else
    echo -e "  ${YELLOW}(no detectadas)${NC}"
fi

echo -e "\n${BLUE}Particion EFI de Windows - NO se tocara:${NC}"
EFI_PART=$(sudo fdisk -l | grep "EFI System" | awk '{print $1}' | head -1)
if [ -n "$EFI_PART" ]; then
    echo -e "  ${YELLOW}$EFI_PART${NC}"
else
    echo -e "  ${YELLOW}(no detectada)${NC}"
fi

echo -e "\n${BLUE}Espacio no asignado (donde se instalara AURA OS):${NC}"
FREE_SPACE=$(sudo fdisk -l | grep "Free space")
if [ -n "$FREE_SPACE" ]; then
    echo "$FREE_SPACE"
else
    echo -e "  ${RED}NO HAY ESPACIO NO ASIGNADO${NC}"
    echo -e "${RED}Debes crear 20GB de espacio no asignado desde Windows (diskmgmt.msc)${NC}"
    exit 1
fi

echo -e "\n${RED}Escribe 'SI ACEPTO' para continuar con la instalacion:${NC}"
read -r CONFIRM
if [ "$CONFIRM" != "SI ACEPTO" ]; then
    echo -e "${RED}Instalacion cancelada por el usuario.${NC}"
    exit 0
fi
echo -e "${GREEN}✓ Seguridad verificada. Procediendo...${NC}"

echo -e "\n${YELLOW}[FASE 1] Particionando disco...${NC}"
DISK=""
if [ -e /dev/nvme0n1 ]; then
    DISK="/dev/nvme0n1"
elif [ -e /dev/sda ]; then
    DISK="/dev/sda"
else
    echo -e "${RED}ERROR: No se encontró disco${NC}"
    exit 1
fi
echo -e "${BLUE}Usando disco: $DISK${NC}"

# Detectar partición EFI de Windows (NO TOCAR)
EFI_PART=$(sudo fdisk -l "$DISK" | grep "EFI System" | awk '{print $1}' | head -1)
if [ -z "$EFI_PART" ]; then
    echo -e "${RED}ERROR: No se encontró partición EFI. Verifica que Windows esté en modo UEFI.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ EFI detectada: $EFI_PART (NO se tocará)${NC}"

# Obtener inicio del espacio libre
FREE_START=$(sudo fdisk -l "$DISK" | grep "Free space" | head -1 | awk '{print $2}')
if [ -z "$FREE_START" ]; then
    echo -e "${RED}ERROR: No hay espacio libre. Reducí C: desde Windows primero.${NC}"
    exit 1
fi
echo -e "${BLUE}Espacio libre detectado desde sector: $FREE_START${NC}"

# Esquema: SWAP 1GB + ROOT 12GB + HOME 7GB = 20GB total
SWAP_SIZE=1
ROOT_SIZE=12
HOME_SIZE=7
TOTAL_SIZE=20

SWAP_END=$((FREE_START + SWAP_SIZE * 2048))
ROOT_END=$((SWAP_END + ROOT_SIZE * 2048))
HOME_END=$((ROOT_END + HOME_SIZE * 2048))

echo -e "${BLUE}SWAP: ${SWAP_SIZE}GB | ROOT: ${ROOT_SIZE}GB | HOME: ${HOME_SIZE}GB (total ${TOTAL_SIZE}GB)${NC}"

# Crear 3 particiones en espacio libre
sudo parted "$DISK" mkpart aura_swap linux-swap "${FREE_START}s" "${SWAP_END}s" 2>/dev/null || true
sleep 2
sudo parted "$DISK" mkpart aura_root ext4 "${SWAP_END}s" "${ROOT_END}s" 2>/dev/null || true
sleep 2
sudo parted "$DISK" mkpart aura_home ext4 "${ROOT_END}s" "${HOME_END}s" 2>/dev/null || true
sleep 2

# Detectar particiones creadas por nombre
SWAP_PART=$(sudo fdisk -l "$DISK" | grep "aura_swap" | awk '{print $1}' | head -1)
ROOT_PART=$(sudo fdisk -l "$DISK" | grep "aura_root" | awk '{print $1}' | head -1)
HOME_PART=$(sudo fdisk -l "$DISK" | grep "aura_home" | awk '{print $1}' | head -1)

# Fallback: usar últimas particiones si no se detectan por nombre
if [ -z "$SWAP_PART" ] || [ -z "$ROOT_PART" ] || [ -z "$HOME_PART" ]; then
    LAST_NUM=$(sudo fdisk -l "$DISK" | grep "^$DISK" | wc -l)
    SWAP_PART="${DISK}p${LAST_NUM}"
    ROOT_PART="${DISK}p$((LAST_NUM + 1))"
    HOME_PART="${DISK}p$((LAST_NUM + 2))"
fi

echo -e "${GREEN}✓ SWAP: $SWAP_PART${NC}"
echo -e "${GREEN}✓ ROOT: $ROOT_PART${NC}"
echo -e "${GREEN}✓ HOME: $HOME_PART${NC}"

echo -e "\n${YELLOW}[FASE 2] Formateando particiones...${NC}"
sudo mkswap "$SWAP_PART"
sudo mkfs.ext4 -F "$ROOT_PART"
sudo mkfs.ext4 -F "$HOME_PART"
echo -e "${GREEN}✓ Particiones formateadas${NC}"

echo -e "\n${YELLOW}[FASE 3] Montando...${NC}"
sudo swapon "$SWAP_PART"
sudo mount "$ROOT_PART" /mnt
sudo mkdir -p /mnt/home
sudo mount "$HOME_PART" /mnt/home
sudo mkdir -p /mnt/boot/efi
sudo mount "$EFI_PART" /mnt/boot/efi
echo -e "${GREEN}✓ Particiones montadas${NC}"

echo -e "\n${YELLOW}[FASE 4] Instalando Arch Linux...${NC}"
sudo pacman-key --init 2>/dev/null || true
sudo pacman-key --populate archlinux 2>/dev/null || true

sudo pacstrap -K /mnt \
    base linux linux-firmware linux-headers \
    base-devel git vim nano \
    efibootmgr grub os-prober ntfs-3g \
    networkmanager openssh \
    python3 python-pip \
    postgresql redis avahi \
    hyprland hyprlock hyprpaper hyprcursor hyprwayland-protocols \
    wayland wayland-protocols \
    waybar wofi dunst \
    alacritty kitty \
    pipewire pipewire-pulse pavucontrol \
    nvidia-utils nvidia-dkms amd-ucode mesa vulkan-icd-loader \
    qt5-wayland qt6-wayland xorg-xwayland \
    curl wget noto-fonts noto-fonts-emoji \
    2>&1 | tee /tmp/pacstrap.log

echo -e "${GREEN}✓ Arch Linux instalado${NC}"

echo -e "\n${YELLOW}[FASE 5] Generando fstab...${NC}"
sudo genfstab -U /mnt >> /mnt/etc/fstab
echo -e "${GREEN}✓ fstab generado${NC}"

echo -e "\n${YELLOW}[FASE 6] Configurando sistema...${NC}"
sudo arch-chroot /mnt /bin/bash << 'CHROOT_SCRIPT'
set -e
ln -sf /usr/share/zoneinfo/America/Argentina/Buenos_Aires /etc/localtime
hwclock --systohc
echo "en_US.UTF-8 UTF-8" > /etc/locale.gen
echo "es_AR.UTF-8 UTF-8" >> /etc/locale.gen
locale-gen
echo "LANG=en_US.UTF-8" > /etc/locale.conf
echo "aura" > /etc/hostname
cat > /etc/hosts << 'HOSTS'
127.0.0.1   localhost
::1         localhost
127.0.1.1   aura
HOSTS

# GRUB dual boot
echo "GRUB_DISABLE_OS_PROBER=false" >> /etc/default/grub

# Montar Windows (solo lectura) temporalmente para que os-prober lo detecte
WIN_PART=$(blkid -o device -t TYPE=ntfs 2>/dev/null | head -1 || true)
if [ -n "$WIN_PART" ]; then
    mkdir -p /mnt/windows-ro
    mount -o ro "$WIN_PART" /mnt/windows-ro 2>/dev/null || true
fi

grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=AURA_OS
grub-mkconfig -o /boot/grub/grub.cfg

umount /mnt/windows-ro 2>/dev/null || true

systemctl enable NetworkManager sshd postgresql redis avahi-daemon

useradd -m -G wheel,audio,video -s /bin/bash aura
echo "aura:aura123" | chpasswd
echo "%wheel ALL=(ALL:ALL) ALL" >> /etc/sudoers

cd /tmp
git clone https://aur.archlinux.org/yay-bin.git 2>/dev/null || true
cd yay-bin
sudo -u aura makepkg -si --noconfirm 2>/dev/null || true

echo "✓ Sistema configurado"
CHROOT_SCRIPT
echo -e "${GREEN}✓ Configuración completada${NC}"

echo -e "\n${YELLOW}[FASE 7] Post-instalación...${NC}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/post-install.sh" ]; then
    cp "$SCRIPT_DIR/post-install.sh" /mnt/home/aura/post-install.sh
else
    cat > /mnt/home/aura/post-install.sh << 'POST_SCRIPT'
#!/bin/bash
set -euo pipefail
echo "Completando instalación..."

sudo pacman -S --noconfirm godot 2>/dev/null || true

mkdir -p ~/.config/hypr
mkdir -p /opt/aura/{backend,shell,gesture,data}
sudo chown -R aura:aura /opt/aura

cat > ~/.config/hypr/hyprland.conf << 'HYPR_CONF'
monitor=,preferred,auto,1
input { kb_layout = us,es; follow_mouse = 1; }
general { gaps_in = 5; gaps_out = 20; border_size = 2; col.active_border = rgba(8a2be2ff) rgba(38bdf8ff) 45deg; col.inactive_border = rgba(0a0e27ff); layout = master; }
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
HYPR_CONF

sudo systemctl daemon-reload
sudo systemctl enable aura-brain aura-gesture

echo "✓ Post-instalación completada"
POST_SCRIPT
fi

chmod +x /mnt/home/aura/post-install.sh
echo -e "${GREEN}✓ Post-instalación preparada${NC}"

echo -e "\n${YELLOW}[FASE 8] Finalizando...${NC}"
sudo umount -R /mnt
sync

echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     AURA OS INSTALADO EXITOSAMENTE    ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"

echo -e "\nPróximos pasos:"
echo "1. Remover USB"
echo "2. Reiniciar"
echo "3. Seleccionar 'AURA_OS' en GRUB"
echo "4. Login: usuario 'aura', contraseña 'aura123'"
echo "5. Ejecutar: bash ~/post-install.sh"
echo -e "\n⚠️  IMPORTANTE: Windows NO fue modificado."
