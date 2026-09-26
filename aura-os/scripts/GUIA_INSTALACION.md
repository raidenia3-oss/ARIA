# 🚀 Guía de Instalación AURA OS — MÚLTIPLES OPCIONES

> **Garantía:** Ninguna de estas opciones toca C: ni D: como particiones.

---

## 🎯 OPCIÓN 1: APP WINDOWS (Recomendada - Más simple)

### Descripción
AURA se ejecuta como aplicación de Windows usando WSL2. No requiere bootear USB ni escribir comandos complejos.

### Ventajas
- **Doble clic para iniciar** (acceso directo en escritorio)
- **NO toca C: ni D:** como particiones
- **Accesible desde navegador** en `http://localhost:8000`
- **No requiere reiniciar** la PC
- **Se actualiza automáticamente**

### Requisitos
- Windows 10/11 con virtualización habilitada
- ~10GB de espacio en disco (para WSL2)

### Instalación

1. **Ejecutar instalador:**
   ```powershell
   powershell -ExecutionPolicy Bypass -File "C:\Users\User\Downloads\AURA\aura-os\scripts\install-wsl2.ps1"
   ```

2. **Reiniciar si lo pide** (solo la primera vez)

3. **Iniciar AURA:**
   - Doble clic en **AURA OS** del escritorio
   - O ejecutar: `start-aura.ps1`

4. **Verificar:**
   ```bash
   curl http://localhost:8000/health
   ```

### Detener AURA
- Cerrar la ventana de PowerShell
- O presionar `Ctrl+C`

---

## 🎯 OPCIÓN 2: USB ALPINE LIVE (Portátil)

### Descripción
AURA bootea desde USB sin tocar disco. Ideal para llevar a cualquier lado.

### Ventajas
- **No toca C: ni D:** en absoluto
- **Bootea en cualquier PC**
- **Todo en RAM** (4-5GB del USB)
- **Portátil**

### Requisitos
- USB de 7.3GB o más
- Acceso a BIOS/UEFI para cambiar boot order

### Instalación

1. **Descargar Alpine:** https://alpinelinux.org/downloads/
2. **Preparar USB:**
   ```powershell
   powershell -ExecutionPolicy Bypass -File "C:\Users\User\Downloads\AURA\aura-os\scripts\preparar-usb-alpine.ps1"
   ```
3. **Grabar con Rufus** (MBR + FAT32)
4. **Bootear USB** → F12 → seleccionar USB
5. **Ejecutar en Alpine:**
   ```bash
   mount /dev/sdb2 /mnt/usb 2>/dev/null || mount /dev/sda2 /mnt/usb
   sh /mnt/usb/aura-install/aura-installer.sh
   ```

---

## 🎯 OPCIÓN 3: VM VIRTUALBOX (Aislamiento total)

### Descripción
AURA corre en una máquina virtual completamente aislada.

### Ventajas
- **Cero riesgo** para Windows
- **Snapshots** para guardar estado
- **Port forwarding** para acceder desde Windows

### Instalación

1. **Instalar VirtualBox:** https://www.virtualbox.org/
2. **Ejecutar:**
   ```batch
   C:\Users\User\Downloads\AURA\aura-os\scripts\setup_vm_windows.bat
   ```
3. **Iniciar VM** desde VirtualBox Manager

---

## 🎯 OPCIÓN 4: NATIVA (Requiere espacio en disco)

### Descripción
Instala AURA permanentemente en disco con dual-boot Windows.

### Requisitos
- 20GB de espacio no asignado en disco
- Crear espacio desde Windows: `diskmgmt.msc` → reducir D:

### Instalación

1. **Crear espacio no asignado** (20GB) desde Windows
2. **Crear USB booteable** con Rufus
3. **Bootear USB** → ejecutar `install-aura.sh`
4. **GRUB** detecta Windows automáticamente

---

## 📊 Comparación de opciones

| Característica | WSL2 App | USB Alpine | VM VirtualBox | Nativa |
|---------------|----------|------------|---------------|--------|
| Toca C:/D: | NO | NO | NO | SI |
| Reinicio | NO | SI | NO | SI |
| Portátil | NO | SI | NO | NO |
| Persistencia | SI | NO | SI | SI |
| Rendimiento | Alto | Medio | Medio-Alto | Nativo |
| Complejidad | Baja | Media | Media | Alta |

---

## 🚀 Inicio rápido (WSL2 App)

```powershell
# Instalar (una sola vez)
powershell -ExecutionPolicy Bypass -File "C:\Users\User\Downloads\AURA\aura-os\scripts\install-wsl2.ps1"

# Iniciar (doble clic en escritorio)
# O desde PowerShell:
powershell -ExecutionPolicy Bypass -File "C:\Users\User\Downloads\AURA\aura-os\scripts\start-aura.ps1"
```

---

## ✅ Verificación

```bash
# Backend respondiendo
curl http://localhost:8000/health

# Ver servicios en WSL
wsl -d AURA-OS -u root systemctl status redis

# Ver logs
wsl -d AURA-OS -u root tail -f /var/log/syslog
```
