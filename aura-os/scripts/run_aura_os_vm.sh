#!/usr/bin/env bash
# AURA OS - VM Test Script
# Ejecuta AURA OS en QEMU/KVM para testing

set -euo pipefail

ISO_PATH="${1:-./aura-os.iso}"
VM_DISK="${HOME}/aura-os-vm.qcow2"
MEMORY=4096
CPUS=4

echo "[+] Creando disco virtual si no existe..."
if [[ ! -f "${VM_DISK}" ]]; then
    qemu-img create -f qcow2 "${VM_DISK}" 20G
fi

echo "[+] Iniciando AURA OS en QEMU..."
qemu-system-x86_64 \
    -cdrom "${ISO_PATH}" \
    -drive file="${VM_DISK}",if=virtio,format=qcow2 \
    -m "${MEMORY}" \
    -smp "${CPUS}" \
    -enable-kvm \
    -net nic,model=virtio \
    -net user,hostfwd=tcp::8000-:8000,hostfwd=tcp::6379-:6379 \
    -display sdl \
    -name "AURA OS"

echo "[+] AURA OS VM cerrada."
