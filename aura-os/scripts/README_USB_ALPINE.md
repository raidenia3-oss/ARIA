# 🚀 AURA OS - Guía Rápida (Alpine USB)

## ⚡ SOLUCIÓN DEFINITIVA: USB Alpine + AURA

**No toca C: ni D:. Todo corre desde USB en RAM.**

---

## 📋 REQUISITOS

- USB de **7.3GB o más** (el tuyo: VIVIANA, 7.32GB ✅)
- Windows 10/11 funcionando
- Conexión a internet para descargar Alpine
- **NO necesitas tocar discos C: ni D:**

---

## 🎯 PASOS (20 minutos total)

### PASO 1: Descargar Alpine Linux (2 minutos)

1. Ir a: https://alpinelinux.org/downloads/
2. Descargar: `alpine-virt-3.19.1-x86_64.iso` (150MB)
3. Guardar en: `C:\Users\User\Downloads\`

### PASO 2: Preparar USB con AURA (3 minutos)

1. **Conectar USB VIVIANA**
2. **Abrir PowerShell como Administrador**
3. Ejecutar:

```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\User\Downloads\AURA\aura-os\scripts\preparar-usb-alpine.ps1"
```

Esto:
- Formatea el USB (LO BORRA TODO)
- Copia `aura-installer.sh`
- Copia tu backend AURA
- Copia scripts adicionales

### PASO 3: Grabar Alpine en USB (5 minutos)

1. Descargar **Rufus**: https://rufus.ie/
2. Ejecutar Rufus (portable, no instala)
3. Configurar:
   - **Device:** VIVIANA (7.32GB)
   - **Boot selection:** `alpine-virt-3.19.1-x86_64.iso`
   - **Partition scheme:** MBR
   - **File system:** FAT32
4. Click **START** → esperar 3-5 minutos
5. Expulsar USB

### PASO 4: Bootear desde USB (2 minutos)

1. **Apagar PC completamente**
2. **Encender** y presionar tecla de boot:
   - Común: **F12**, **F11**, **Esc**, **F8**
3. Seleccionar: **USB VIVIANA**
4. Aparece prompt de Alpine: `localhost:~#`

### PASO 5: Ejecutar AURA Installer (5 minutos)

```bash
# Montar USB (generalmente /dev/sdb1)
mount /dev/sdb1 /mnt/usb

# Ejecutar installer
sh /mnt/usb/aura-install/aura-installer.sh

# Esperar 5-10 minutos (descarga paquetes, configura todo)
```

### PASO 6: Acceder a AURA (1 minuto)

```bash
# Reboot
reboot

# En GRUB/Alpine, seleccionar AURA
# Login: aura / aura123

# Verificar backend
curl http://localhost:8000/health
# Debe responder: {"status":"ok"}
```

---

## ✅ VERIFICACIÓN

```bash
# Verificar servicios
rc-status

# Verificar backend
curl http://localhost:8000/health

# Verificar usuario
whoami  # debe decir: aura

# Verificar Hyprland (si tienes GPU)
Hyprland
```

---

## 🔧 SOLUCIÓN DE PROBLEMAS

### USB no bootea
- Entrar a BIOS (F2/DEL)
- Cambiar boot order: USB primero
- Desactivar Secure Boot
- Desactivar Fast Boot

### No hay internet en Alpine
```bash
# Configurar DHCP
setup-interfaces

# O conectar WiFi
iwctl
station wlan0 scan
station wlan0 connect "TU_WIFI"
exit

# Verificar
ping -c 3 8.8.8.8
```

### No se encuentra AURA backend
El installer intenta copiar desde USB. Si falla:
```bash
# Montar USB manualmente
mount /dev/sdb1 /mnt/usb

# Copiar manualmente
mkdir -p /opt/aura
cp -r /mnt/usb/aura-install/backend /opt/aura/
cp -r /mnt/usb/aura-install/scripts /opt/aura/

# Re-ejecutar installer
sh /mnt/usb/aura-install/aura-installer.sh
```

### Backend no responde
```bash
# Ver logs
tail -f /var/log/messages

# Reiniciar manualmente
cd /opt/aura/backend
. /opt/aura/venv/bin/activate
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## 📊 VENTAJAS

| Característica | Valor |
|---------------|-------|
| Toca C:/D: | **NO** |
| Persistencia | RAM (se pierde al apagar) |
| Portabilidad | USB bootea en cualquier PC |
| Tamaño ISO | 150MB Alpine + paquetes |
| Tiempo total | 20 minutos |
| Backend AURA | Incluido |
| Hyprland | Incluido |
| Herramientas hacking | Incluidas |

---

## 🎯 COMANDOS ÚTILES EN AURA OS

```bash
# Usuario
su aura                    # Cambiar a usuario aura
sudo su                    # Root
passwd                     # Cambiar contraseña

# AURA Backend
curl http://localhost:8000/health
systemctl status aura-brain 2>/dev/null || echo "Modo live: servicios en RAM"

# Red
ip addr                    # Ver IP
ping -c 3 8.8.8.8         # Verificar internet
iwctl                     # Configurar WiFi

# Sistema
apk update                # Actualizar paquetes
apk add paquete           # Instalar paquete
rc-service redis start    # Iniciar servicio

# Apagar
poweroff                  # Apagar
reboot                    # Reiniciar
```

---

## 📁 ESTRUCTURA DEL USB

```
VIVIANA (USB)
├── boot/                  ← Alpine bootloader
├── aura-install/
│   ├── aura-installer.sh  ← Script principal
│   ├── backend/           ← AURA backend
│   ├── scripts/           ← Scripts adicionales
│   └── .env               ← Configuración
└── ...                    ← Archivos de Alpine
```

---

## 🚀 PRÓXIMOS PASOS DESPUÉS DE FUNCIONANDO

1. **Personalizar Hyprland:**
   ```bash
   nano ~/.config/hypr/hyprland.conf
   ```

2. **Agregar herramientas de hacking:**
   ```bash
   sudo apk add nmap wireshark metasploit
   ```

3. **Configurar GPU:**
   ```bash
   # NVIDIA
   sudo apk add nvidia-utils
   
   # AMD
   sudo apk add mesa-dri-gallium
   ```

4. **Sincronizar con Windows:**
   - Compartir carpeta en VirtualBox
   - O usar SCP desde Windows

---

**¿Empezamos?** Ejecutá:

```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\User\Downloads\AURA\aura-os\scripts\preparar-usb-alpine.ps1"
```
