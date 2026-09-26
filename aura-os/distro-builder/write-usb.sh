#!/bin/bash

# Write AURA OS to USB drive
# Uso: ./write-usb.sh /dev/sdX

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 /dev/sdX"
    echo ""
    echo "Available drives:"
    lsblk -d -o NAME,SIZE,TYPE
    exit 1
fi

USB_DEVICE="$1"
BUILD_DIR="build"
ROOTFS="$BUILD_DIR/rootfs"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Validar que sea USB
if [[ ! "$USB_DEVICE" =~ ^/dev/sd[a-z]$ ]]; then
    echo -e "${RED}ERROR: Invalid device. Use /dev/sdX format (e.g., /dev/sdb)${NC}"
    exit 1
fi

# Advertencia
echo -e "${RED}WARNING: This will ERASE all data on $USB_DEVICE${NC}"
echo ""
echo "Device: $USB_DEVICE"
echo "Size: $(lsblk -d -o SIZE "$USB_DEVICE")"
echo ""
read -p "Type 'yes' to continue: " confirm

if [ "$confirm" != "yes" ]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo -e "${YELLOW}[1/5] Unmounting $USB_DEVICE...${NC}"
sudo umount "${USB_DEVICE}"* 2>/dev/null || true

echo -e "${YELLOW}[2/5] Creating partition table...${NC}"
sudo parted -s "$USB_DEVICE" mklabel gpt
sudo parted -s "$USB_DEVICE" mkpart primary ext4 1MiB 100%
sudo parted -s "$USB_DEVICE" set 1 boot on

PARTITION="${USB_DEVICE}1"
sleep 2

echo -e "${YELLOW}[3/5] Formatting ${PARTITION}...${NC}"
sudo mkfs.ext4 -F -L AURA-OS "$PARTITION"

echo -e "${YELLOW}[4/5] Mounting and copying files...${NC}"
MOUNT_DIR=$(mktemp -d)
sudo mount "$PARTITION" "$MOUNT_DIR"

# Copiar rootfs
sudo cp -av "$ROOTFS"/* "$MOUNT_DIR"/ | head -20
echo "..."

# Crear directorio para AURA
sudo mkdir -p "$MOUNT_DIR/opt/aura"

# Copiar AURA si está disponible
if [ -d "../../../backend" ]; then
    echo "Copying AURA OS..."
    sudo cp -r ../../../ "$MOUNT_DIR/opt/aura/" || true
fi

echo -e "${YELLOW}[5/5] Syncing and unmounting...${NC}"
sudo sync
sudo umount "$MOUNT_DIR"
rmdir "$MOUNT_DIR"

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗"
echo "║      ✅ AURA OS written to $USB_DEVICE                          ║"
echo "╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "You can now:"
echo "  1. Eject USB safely"
echo "  2. Insert into target PC"
echo "  3. Boot and press F12 to select USB"
echo "  4. Login: aura / aura123"
echo ""
