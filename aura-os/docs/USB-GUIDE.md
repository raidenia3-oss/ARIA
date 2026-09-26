# AURA OS USB Boot Guide

Bootable Alpine Linux with AURA backend, Go tools, and Ruby toolkit.

## System Requirements

- **USB Drive**: 16GB+ (Kingston DataTraveler or similar)
- **Target Machine**:
  - UEFI or BIOS boot support
  - 4GB+ RAM
  - 2+ GHz CPU
  - Network connectivity

## Building from Source

### Step 1: Install Build Dependencies

```bash
# Debian/Ubuntu
sudo apt install docker.io git curl

# macOS
brew install docker git curl

# Alpine (run on Alpine host)
apk add docker git curl
```

### Step 2: Clone AURA Repo

```bash
git clone https://github.com/your-repo/aura.git
cd aura/aura-os/distro-builder
```

### Step 3: Build Distro

```bash
chmod +x build-distro-hardened.sh
./build-distro-hardened.sh
```

**Output:**
- `output/aura-os-2.1.img` — Bootable image
- `output/aura-os-2.1.img.sha256` — Checksum

### Step 4: Write to USB

**Linux:**
```bash
# Identify USB device
lsblk
# Write image
sudo dd if=output/aura-os-2.1.img of=/dev/sdX bs=4M status=progress
sudo sync
```

**macOS:**
```bash
# Identify USB device
diskutil list
# Unmount
diskutil unmountDisk /dev/diskX
# Write image
sudo dd if=output/aura-os-2.1.img of=/dev/rdiskX bs=4m
sudo diskutil eject /dev/diskX
```

**Windows:**
Use [Rufus](https://rufus.ie/) or [Win32 Disk Imager]

### Step 5: Boot from USB

1. Insert USB on target machine
2. Restart and enter BIOS/UEFI setup
   - Press `F2`, `F10`, `F12`, or `Del` (varies by manufacturer)
3. Change boot order to USB first
4. Save and boot
5. Select boot option at GRUB menu

## First Boot

### Login

```
Username: aura
Password: aura123
```

### Desktop

Hyprland tiling window manager starts automatically.

**Shortcuts:**
- `Super+A` → AURA Chat
- `Super+C` → C2 Console
- `Super+P` → Pentest Help
- `Super+M` → Port Scanner
- `Super+L` → Lock Screen
- `Super+Q` → Kill Window
- `Super+T` → Open Terminal

### Verify Installation

```bash
# Check AURA backend
aura --status

# List available tools
aura-pentest help

# Test network tools
aura-ruby network info
```

### AURA API

- **Web UI**: http://localhost:8000
- **API Docs**: http://localhost:8000/api/docs
- **Health**: http://localhost:8000/health
- **Omniroute**: http://localhost:8000/api/providers

## Post-Install Setup

After first boot, run the post-installation script:

```bash
sudo /opt/aura/post-install.sh
```

This will:
- Create the `aura` user
- Build Go tools from source
- Install Ruby gems
- Set up Python backend dependencies
- Configure SSH
- Create systemd service for AURA backend

## Available Tools

### Network Tools
| Tool | Description |
|------|-------------|
| `aura-scanner` | Port scanner |
| `aura-resolver` | DNS resolver |
| `aura-enum` | Subdomain enumerator |
| `aura-c2-server` | C2 controller |
| `aura-c2-agent` | Deploy agents |
| `aura-c2-client` | CLI client |
| `aura-pentest` | Security testing suite |
| `aura-ruby` | Ruby CLI tools |

### Ruby Penetration Testing
```bash
# SQL Injection
aura-pentest sqli test http://target.com/login username

# XSS Testing
aura-pentest xss test http://target.com/search q

# Payload Generation
aura-pentest payload revshell python 192.168.1.100 4444
aura-pentest payload webshell php
```

## Troubleshooting

### USB Won't Boot
- Verify checksum: `sha256sum aura-os-2.1.img`
- Try `dd` with larger block size: `bs=8M`
- Enable "Legacy Boot" in BIOS

### AURA Backend Not Starting
```bash
# Check service
systemctl status aura

# Start manually
cd /opt/aura/backend && python main.py

# Check logs
tail -f /var/log/aura.log
```

### Ruby Tools Not Found
```bash
# Reinstall gems
cd /opt/aura/ruby-tools
bundle install

# Check path
echo $PATH
```

## Image Size

| Component | Size |
|-----------|------|
| Alpine base | 150 MB |
| Hyprland + deps | 250 MB |
| AURA backend | 300 MB |
| Ruby tooling | 200 MB |
| **Total** | ~900 MB |
