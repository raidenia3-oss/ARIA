#!/bin/bash
# AURA OS Custom Distro - Profile Definition
# Basado en archiso

# Configuracion basica
iso_name="aura-os"
iso_label="AURA_OS"
iso_publisher="AURA OS"
iso_application="AURA OS - Hacker / AI / Gaming Distro"
iso_version="1.0"
install_dir="arch"
work_dir="work"
out_dir="out"

# Configuracion de arch
arch="x86_64"
image_type="squashfs"

# Paquetes adicionales
pacman_conf="pacman.conf"

# Configuracion de boot
bootmode="bios+uefi"
