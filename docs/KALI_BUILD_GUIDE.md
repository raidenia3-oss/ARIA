# ARIA OS Kali — Guía de Construcción del Entorno Dedicado

Convierte Kali Linux en **ARIA OS**: entorno dedicado, sin servidor HTTP, sin puertos abiertos, sin navegador. ARIA es la única interfaz de usuario.

> **Desde Windows sin WSL2 ni Docker**: no puedes construir una ISO de Kali directamente. Usa las **Vías A o B** (VM preconstruida o Vagrant) que no requieren host de build Linux.

---

## Vías disponibles

| Vía | Método | Requiere host Linux | Dificultad | Ideal para |
|-----|--------|---------------------|------------|------------|
| **A** | VM preconstruida de Kali (OVA/VirtualBox) + `kali-aria-setup.sh` | No | ⭐ Fácil | Uso inmediato desde Windows |
| **B** | Vagrant con box Kali + provisioning automático | No | ⭐⭐ Medio | Automatización reproducible |
| **C** | Build ISO custom con `live-build` | **Sí** | ⭐⭐⭐ Avanzado | ISO propia, USB persistente |

---

## Vía A — VM preconstruida de Kali + setup (recomendado desde Windows)

### Paso 1: Descargar e importar VM Kali preconstruida

Desde PowerShell en Windows:

```powershell
# Ejecutar el script de importación (instala VirtualBox primero)
.\import-kali-aria.ps1
```

Este script:
1. Descarga la VM Kali Linux preconstruida desde `cdimage.kali.org`
2. La importa en VirtualBox
3. Configura 4 GB RAM, 2 CPUs, aceleración 3D

O manualmente:
1. Descarga VirtualBox: https://www.virtualbox.org/wiki/Downloads
2. Descarga Kali VM (VirtualBox): https://cdimage.kali.org/kali-images/virtual-images/
3. Importa el `.ova` o `.vbox` en VirtualBox Manager

### Paso 2: Ejecutar setup de ARIA dentro de la VM

Inicia la VM Kali, inicia sesión (`kali` / `kali`), abre terminal y ejecuta:

```bash
# Copiar el proyecto AURA y el setup a la VM
# Opción 1: Carpeta compartida de VirtualBox (configurada en el VM)
sudo mkdir -p /opt/aria-build
sudo cp -r /media/sf_AURA/* /opt/aria-build/  # si usas carpeta compartida

# Opción 2: Descargar kali-aria-setup.sh
sudo curl -fsSL https://raw.githubusercontent.com/TU-REPO/kali-aria-setup.sh -o /tmp/kali-aria-setup.sh

# Ejecutar setup (como root)
sudo bash /tmp/kali-aria-setup.sh
```

El script `kali-aria-setup.sh` instala todo:
- Python 3 + PyQt5 + venv
- Ollama + modelo `granite3.2-vision:2b`
- Herramientas de red Kali (nmap, tcpdump, macchanger, tor, whois, nmcli)
- Usuario `aria` sin privilegios sudo
- Systemd service `aria-os.service`
- Autostart XFCE + LightDM autologin
- Firewall nftables restrictivo, hardening de servicios

### Paso 3: Reiniciar y verificar

```bash
# Reiniciar VM para autostart de ARIA
sudo reboot

# Verificación después del reinicio
ps aux | grep aria_native          # Proceso ARIA activo
sudo ss -tlnp                       # Cero puertos TCP (salvo Ollama 127.0.0.1:11434)
curl -s http://127.0.0.1:11434/api/tags  # Modelo Ollama disponible
sudo systemctl status aria-os       # Servicio systemd
```

---

## Vía B — Vagrant con Kali + ARIA (provisioning automático)

### Requisitos en Windows
- Vagrant: https://www.vagrantup.com/
- VirtualBox: https://www.virtualbox.org/wiki/Downloads

### Uso

```powershell
# Desde C:\Users\User\Downloads\AURA
vagrant up
```

El `Vagrantfile` incluido:
1. Descarga la box `kalilinux/rolling`
2. Configura 4 GB RAM, 2 CPUs, GUI (VirtualBox)
3. Sincroniza la carpeta AURA al guest
4. Ejecuta `kali-aria-setup.sh` automáticamente
5. ARIA arranca al iniciar la VM

### Comandos útiles

```powershell
vagrant up                    # Crear y provisionar VM
vagrant ssh                   # Conectar a la VM
vagrant reload                # Reiniciar VM
vagrant halt                  # Apagar VM
vagrant destroy               # Eliminar VM
```

---

## Vía C — Build ISO custom con live-build (requiere host Kali Linux)

Si tienes acceso a un host Kali Linux (físico o VM), puedes construir una ISO personalizada de ARIA OS.

```bash
# 1. Instalar dependencias de build
sudo apt update && sudo apt install -y git live-build cdebootstrap curl rsync

# 2. Clonar scripts de Kali Live
cd ~ && git clone https://gitlab.com/kalilinux/build-scripts/kali-live.git && cd kali-live

# 3. Copiar configuración de ARIA
cp -r /ruta/a/AURA/kali-config ~/kali-live/

# 4. Copiar proyecto AURA al chroot (durante el build)
sudo mkdir -p /opt/aria-build
sudo rsync -aHAX /ruta/a/AURA/ /opt/aria-build/AURA/
sudo chown -R root:root /opt/aria-build/AURA

# 5. Construir ISO
./build.sh --clean
time ./build.sh --verbose --variant xfce

# 6. Resultado: images/kali-*/kali-linux-*-live-amd64.iso
```

La ISO resultante incluye: XFCE ligero, ARIA preinstalada, Ollama, hardening, autostart, y usuario `aria`.

---

## Archivos entregados

```
AURA/
├── kali-aria-setup.sh              # Setup completo para Kali (Vía A y B)
├── Vagrantfile                     # Vagrant + box Kali + provisioning (Vía B)
├── import-kali-aria.ps1            # PowerShell: descargar e importar VM Kali (Vía A)
├── kali-config/                    # Configuración para build ISO custom (Vía C)
│   ├── package-lists/
│   │   └── aria-minimal.list.chroot
│   ├── hooks/live/
│   │   ├── 0900-install-aria-deps.hook.chroot
│   │   └── 0910-harden-kali.hook.chroot
│   └── includes.chroot/
│       ├── etc/systemd/system/aria-os.service
│       ├── etc/xdg/autostart/aria.desktop
│       ├── etc/lightdm/lightdm.conf.d/10-aria-autologin.conf
│       ├── etc/dpkg/dpkg.cfg.d/99-aria-nodocs
│       └── usr/local/bin/aria-start.sh
├── ARIA_APP/native_core.py         # Núcleo ARIA nativo (11 skills, sin HTTP)
├── ARIA_APP/aria_native.py         # Entry point nativo
└── docs/KALI_BUILD_GUIDE.md        # Esta guía
```

---

## Skills de red disponibles en ARIA OS Kali

| Skill | Comando subyacente | Permiso |
|-------|-------------------|---------|
| `net_scan` | `nmap -sn --disable-arp-ping <target>` | cap_net_raw |
| `wifi_scan` | `nmcli device wifi list` | usuario normal |
| `mac_spoof` | `macchanger -r <iface>` | cap_net_admin |
| `tor_status` | `systemctl is-active tor` | usuario normal |
| `whois_lookup` | `whois <domain>` | usuario normal |
| `packet_capture` | `tcpdump -i <iface> -c <n> -n` | cap_net_raw |

---

## Comandos de verificación post-instalación

```bash
# ¿ARIA corriendo?
ps aux | grep aria_native

# ¿Puertos abiertos (cero TCP salvo Ollama localhost)?
sudo ss -tlnp

# ¿Ollama disponible?
curl -s http://127.0.0.1:11434/api/tags

# ¿Servicio systemd?
sudo systemctl status aria-os
sudo systemctl status ollama

# ¿Firewall activo?
sudo nft list ruleset

# ¿Usuario aria sin sudo?
id aria
sudo -l -U aria   # debe mostrar sin privilegios

# ¿Logs de ARIA?
journalctl -u aria-os --since -1h
tail -f /var/log/aria/aria.log
```

---

## Siguientes pasos

1. **Desde Windows**: Ejecuta `.\import-kali-aria.ps1` para importar VM Kali, luego ejecuta `kali-aria-setup.sh` dentro de la VM.
2. **Con Vagrant**: `vagrant up` para provisioning automático completo.
3. **Con host Kali Linux**: Usa la Vía C para construir tu propia ISO custom.
4. Una vez ARIA corriendo, prueba las skills de red: `net_scan`, `wifi_scan`, `tor_status`, `whois_lookup`.
