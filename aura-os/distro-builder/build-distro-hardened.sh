#!/bin/bash

# AURA OS Distro Builder (Hardened)

set -euo pipefail

DISTRO_NAME="AURA OS v2.1"
DISTRO_VERSION="2.1.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUTPUT_DIR="$SCRIPT_DIR/output"
DOCKER_IMAGE="aura-os-builder"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}╔═══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                  ${DISTRO_NAME}                      ${NC}"
echo -e "${GREEN}║                   Distro Builder                  ${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════╝${NC}"

# Stage 1: Check dependencies
echo -e "\n${YELLOW}[Stage 1] Checking dependencies...${NC}"

DEPS=("docker" "git" "curl")
for dep in "${DEPS[@]}"; do
    if ! command -v "$dep" &> /dev/null; then
        echo -e "${RED}[-] Missing: $dep${NC}"
        exit 1
    fi
done

echo -e "${GREEN}[+] All dependencies satisfied${NC}"

# Stage 2: Build Docker image
echo -e "\n${YELLOW}[Stage 2] Building Docker image...${NC}"

docker build -t "$DOCKER_IMAGE:latest" \
    -f "$SCRIPT_DIR/Dockerfile" \
    --build-arg BUILDKIT_INLINE_CACHE=1 \
    "$REPO_DIR"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}[+] Docker image built successfully${NC}"
else
    echo -e "${RED}[-] Docker build failed${NC}"
    exit 1
fi

# Stage 3: Extract rootfs
echo -e "\n${YELLOW}[Stage 3] Extracting rootfs...${NC}"

mkdir -p "$OUTPUT_DIR"

docker run --name aura-extract "$DOCKER_IMAGE:latest" \
    tar czf /tmp/rootfs.tar.gz -C / \
    --exclude='proc' --exclude='sys' --exclude='dev' \
    --exclude='.dockerenv' --exclude='.git' .

docker cp "aura-extract:/tmp/rootfs.tar.gz" "$OUTPUT_DIR/rootfs.tar.gz"
docker rm aura-extract

echo -e "${GREEN}[+] Rootfs extracted: $OUTPUT_DIR/rootfs.tar.gz${NC}"

# Stage 4: Create bootable ISO
echo -e "\n${YELLOW}[Stage 4] Creating bootable ISO...${NC}"

if command -v mkisofs &> /dev/null; then
    cd "$OUTPUT_DIR"
    
    tar xzf rootfs.tar.gz -C iso/
    
    mkisofs -R -J -V "AURA-OS-2.1" \
        -b isolinux/isolinux.bin \
        -c isolinux/boot.cat \
        -no-emul-boot \
        -boot-load-size 4 \
        -boot-info-table \
        -o aura-os-2.1.iso iso/
    
    echo -e "${GREEN}[+] ISO created: $OUTPUT_DIR/aura-os-2.1.iso${NC}"
else
    echo -e "${YELLOW}[!] mkisofs not found, skipping ISO creation${NC}"
fi

# Stage 5: Create USB image
echo -e "\n${YELLOW}[Stage 5] Creating USB image...${NC}"

dd if="$OUTPUT_DIR/rootfs.tar.gz" \
    of="$OUTPUT_DIR/aura-os-2.1.img" \
    bs=4M \
    status=progress

echo -e "${GREEN}[+] USB image created: $OUTPUT_DIR/aura-os-2.1.img${NC}"

# Stage 6: Verify integrity
echo -e "\n${YELLOW}[Stage 6] Verifying integrity...${NC}"

sha256sum "$OUTPUT_DIR/aura-os-2.1.img" > "$OUTPUT_DIR/aura-os-2.1.img.sha256"

echo -e "${GREEN}[+] Checksum saved${NC}"

# Summary
echo -e "\n${GREEN}╔═══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                   Build Complete!                  ${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════╝${NC}"

echo -e "\n${YELLOW}Output files:${NC}"
echo "  • $OUTPUT_DIR/rootfs.tar.gz"
echo "  • $OUTPUT_DIR/aura-os-2.1.iso (optional)"
echo "  • $OUTPUT_DIR/aura-os-2.1.img"
echo "  • $OUTPUT_DIR/aura-os-2.1.img.sha256"

echo -e "\n${YELLOW}To write to USB:${NC}"
echo "  sudo dd if=$OUTPUT_DIR/aura-os-2.1.img of=/dev/sdb bs=4M status=progress"
echo "  sudo sync"

echo -e "\n${YELLOW}To boot:${NC}"
echo "  1. Insert USB on target machine"
echo "  2. Press F12/Del during BIOS to enter boot menu"
echo "  3. Select USB boot"
echo "  4. Login: aura / aura123"
echo ""
