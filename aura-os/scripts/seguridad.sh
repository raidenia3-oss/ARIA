#!/bin/bash
# AURA OS - Security Check Script
# EJECUTAR ESTE SCRIPT PRIMERO antes de install-aura.sh
# Uso: sudo bash seguridad.sh
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   AURA OS - Verificacion de Seguridad    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"

echo -e "\n${YELLOW}[VERIFICACION] Listando discos y particiones...${NC}"
echo -e "${BLUE}================================${NC}"
sudo fdisk -l | grep -E "Disk /|Device|Type|EFI|Microsoft|Windows|Free"
echo -e "${BLUE}================================${NC}"

echo -e "\n${YELLOW}[VERIFICACION] Buscando particiones de Windows (C: y D:)...${NC}"
WINDOWS_PARTS=$(sudo fdisk -l | grep "NTFS" | awk '{print $1}')
if [ -z "$WINDOWS_PARTS" ]; then
    echo -e "${RED}ERROR: No se encontraron particiones NTFS (Windows)${NC}"
    exit 1
fi
echo -e "${BLUE}Particiones Windows detectadas:${NC}"
for part in $WINDOWS_PARTS; do
    echo -e "  ${YELLOW}$part${NC}"
done

echo -e "\n${YELLOW}[VERIFICACION] Buscando particion EFI de Windows...${NC}"
EFI_PART=$(sudo fdisk -l | grep "EFI System" | awk '{print $1}' | head -1)
if [ -z "$EFI_PART" ]; then
    echo -e "${RED}ERROR: No se encontro particion EFI de Windows${NC}"
    exit 1
fi
echo -e "${GREEN}✓ EFI de Windows detectada: $EFI_PART (NO se tocara)${NC}"

echo -e "\n${YELLOW}[VERIFICACION] Buscando espacio no asignado...${NC}"
FREE_SPACE=$(sudo fdisk -l | grep "Free space")
if [ -z "$FREE_SPACE" ]; then
    echo -e "${RED}ERROR: No hay espacio no asignado en el disco${NC}"
    echo -e "${YELLOW}Debes crear 20GB de espacio no asignado desde Windows (diskmgmt.msc)${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Espacio no asignado detectado:${NC}"
echo "$FREE_SPACE"

echo -e "\n${YELLOW}[VERIFICACION] Confirmando discos objetivo...${NC}"
echo -e "${BLUE}Disco principal (NVMe):${NC}"
sudo fdisk -l | grep "Disk /dev/nvme0n1" || echo -e "${YELLOW}No se detecto /dev/nvme0n1${NC}"
echo -e "${BLUE}Disco USB (no usado para instalacion):${NC}"
sudo fdisk -l | grep "Disk /dev/sda" || echo -e "${YELLOW}No se detecto /dev/sda como USB${NC}"

echo -e "\n${RED}╔════════════════════════════════════════════╗${NC}"
echo -e "${RED}║           ADVERTENCIA DE SEGURIDAD        ║${NC}"
echo -e "${RED}╚════════════════════════════════════════════╝${NC}"
echo -e "${RED}Este script SOLO tocara el espacio NO ASIGNADO.${NC}"
echo -e "${RED}NUNCA tocara C:, D:, ni la particion EFI de Windows.${NC}"
echo -e "${RED}Las particiones que se crearan:${NC}"
echo -e "  ${YELLOW}- SWAP: 1GB${NC}"
echo -e "  ${YELLOW}- ROOT: 12GB${NC}"
echo -e "  ${YELLOW}- HOME: 7GB${NC}"
echo -e "  ${YELLOW}- Total: 20GB${NC}"
echo -e "  ${YELLOW}- EFI: compartido con Windows (solo se monta)${NC}"

echo -e "\n${BLUE}Si ves C: o D: en la lista de arriba, el script los IGNORARA.${NC}"
echo -e "${BLUE}Si no ves 'No asignado' en la lista, CANCELA AHORA.${NC}"

echo -e "\n${YELLOW}[CONFIRMACION] Escribe 'SI ACEPTO' para continuar, o cualquier otra cosa para cancelar:${NC}"
read -r CONFIRM
if [ "$CONFIRM" != "SI ACEPTO" ]; then
    echo -e "${RED}Instalacion cancelada por el usuario.${NC}"
    exit 0
fi

echo -e "${GREEN}✓ Seguridad verificada. Ahora ejecuta: sudo bash install-aura.sh${NC}"
