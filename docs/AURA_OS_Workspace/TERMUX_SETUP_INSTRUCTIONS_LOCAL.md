# 📱 **INSTRUCCIONES PARA CONFIGURAR TERMUX (USANDO REPOSITORIO LOCAL)**

Este documento te guiará paso a paso para configurar tu dispositivo Android con Termux usando el repositorio AURA que ya tienes en tu PC. **No necesitarás descargar nada desde internet en tu celular**.

---

## 📌 **Requisitos Previos**

1. **Termux instalado** desde [F-Droid](https://f-droid.org/es/packages/com.termux/)
2. **Termux:API instalado** desde [F-Droid](https://f-droid.org/es/packages/com.termux.api/)
3. **Conexión a internet estable** (WiFi recomendado)
4. **Acceso a `/sdcard/`** (Termux debe tener permisos de almacenamiento)
5. **Repositorio AURA en tu PC** (ya clonado y configurado)

---

## 🔧 **Paso 1: Transferir el Repositorio a tu Celular**

### **1.1 Copiar la carpeta `aura-ame` desde tu PC a tu celular**

#### **Opción A: Usando una app de archivos (recomendado)**
1. **En tu PC**:
   - Copia la carpeta completa `aura-ame` a una USB o computadora intermedia.

2. **En tu celular**:
   - Conecta tu celular a esa computadora/USB.
   - Usa una app como **Solid Explorer** o **FX File Explorer** para copiar la carpeta `aura-ame` a la raíz de tu almacenamiento interno (`/sdcard/`).

#### **Opción B: Usando ADB (si tienes acceso)**
```bash
# En tu PC:
adb push aura-ame /sdcard/
```

### **1.2 Verificar que la carpeta esté en `/sdcard/`**
```bash
ls /sdcard/aura-ame
```
*(Si no aparece, repite el Paso 1.1)*

---

## 📥 **Paso 2: Configurar Termux en tu Celular**

### **2.1 Abre Termux y ejecuta los siguientes comandos**
```bash
pkg update -y && pkg upgrade -y
pkg install python git openssh curl wget termux-api -y
termux-setup-storage
```

### **2.2 Mover la carpeta `aura-ame` a tu directorio home**
```bash
mv /sdcard/aura-ame ~/aura-ame
cd ~/aura-ame
```

### **2.3 Instalar dependencias Python**
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 🔄 **Paso 3: Configurar Cloudflare en tu PC**

**Debes hacer esto en tu computadora (PC) antes de continuar:**

### **3.1 Configurar el túnel Cloudflare**
```bash
cd ruta/aura-ame
python scripts/setup_cloudflare.py
```
- Selecciona la opción `[1]` para `trycloudflare.com` (gratis).

### **3.2 Generar configuración para Android**
```bash
python scripts/ame_config_generator.py
```

### **3.3 Transferir `ame_config.json` a tu celular**
#### **Opción A: Usando ADB (si tienes acceso)**
```bash
adb push aura_urls/ame_config.json /sdcard/
```

#### **Opción B: Manual (sin ADB)**
1. Copia el archivo `aura_urls/ame_config.json` desde tu PC a una USB o computadora intermedia.
2. Conecta tu celular a esa computadora/USB.
3. Copia el archivo `ame_config.json` a la raíz de tu almacenamiento interno (`/sdcard/`).

---

## 🔐 **Paso 4: Configurar SSH (Opcional pero Recomendado)**

### **4.1 Configurar SSH en tu celular**
```bash
pkg install openssh -y
mkdir -p ~/.ssh
chmod 700 ~/.ssh
```

### **4.2 Generar clave SSH en tu PC (si no lo has hecho)**
```bash
ssh-keygen -t ed25519 -C "tu_email@example.com"
```

### **4.3 Obtener tu clave pública y agregarla a tu celular**
1. **En tu PC**, obtén tu clave pública:
   ```bash
   cat ~/.ssh/id_ed25519.pub
   ```
2. **En tu celular**, edita el archivo de autorización:
   ```bash
   nano ~/.ssh/authorized_keys
   ```
   - Pega tu clave pública y guarda el archivo (Ctrl+O, Enter, Ctrl+X).

### **4.4 Iniciar el servidor SSH**
```bash
sshd
```

---

## 🚀 **Paso 5: Ejecutar el Script de Configuración Local**

### **5.1 Descargar el script de configuración local**
```bash
wget https://raw.githubusercontent.com/raidenia3-oss/AURA-server.01/main/TERMUX_SETUP_SCRIPT.sh
```

### **5.2 Hacer el script ejecutable**
```bash
chmod +x TERMUX_SETUP_SCRIPT.sh
```

### **5.3 Ejecutar el script**
```bash
./TERMUX_SETUP_SCRIPT.sh
```
*(El script ya está configurado para usar el repositorio local y no requiere descargas adicionales)*

---

## 📡 **Paso 6: Verificar la Configuración**

### **6.1 Verificar que `ame_config.json` esté en `/sdcard/`**
```bash
ls /sdcard/ame_config.json
```
*(Si no aparece, repite el Paso 3.3)*

### **6.2 Probar la conexión con AURA Core**
```bash
python scripts/test_ame_connection.py
```
**Salida esperada:**
```
🎉 ¡Conexión exitosa! AME puede comunicarse con AURA Core
```

---

## 🔄 **Paso 7: Iniciar Servicios en tu PC**

Asegúrate de que los siguientes servicios estén corriendo en tu PC:
```bash
cd ruta/aura-ame
python scripts/start_aura.py
```

---

## 🔍 **Paso 8: Verificar el Estado del Sistema**

### **En tu Celular (Termux)**
```bash
# Verificar logs de actualización
cat /sdcard/update_ame_log.txt

# Verificar procesos en ejecución
ps aux | grep ame_updater
```

### **En tu PC (AURA Core)**
```bash
python scripts/health_check.py
```

---

## 🔄 **Paso 9: Solución de Problemas Comunes**

| Problema | Solución |
|----------|----------|
| **`ame_config.json` no encontrado** | Copia el archivo desde tu PC a `/sdcard/` usando ADB o manualmente. |
| **Conexión fallida a EventBus** | Verifica que `start_aura.py` esté corriendo en tu PC. |
| **Error de certificado en Cloudflare** | Ejecuta `python scripts/setup_cloudflare.py` nuevamente en tu PC. |
| **Termux no tiene permisos en `/sdcard/`** | Ejecuta `termux-setup-storage` y reinicia Termux. |
| **Script falla en algún paso** | Ejecuta cada comando manualmente para identificar el error. |

---

## 🎯 **Resumen de lo Configurado**

✅ **Termux actualizado** con todas las dependencias necesarias.
✅ **Repositorio AURA transferido** desde tu PC a tu celular.
✅ **Configuración de Cloudflare** lista para usar (solo necesitas transferir `ame_config.json`).
✅ **SSH configurado** (opcional pero recomendado para acceso remoto).
✅ **Actualizador automático** en segundo plano (`ame_updater.py`).
✅ **Conexión probada** con `test_ame_connection.py`.

---

## 📢 **Instrucciones Finales**

1. **Asegúrate de que `start_aura.py` esté corriendo en tu PC**.
2. **Verifica que el túnel Cloudflare esté activo** en tu PC.
3. **Ejecuta `python scripts/ame_config_generator.py` en tu PC** si actualizaste algo.
4. **Transfiere el nuevo `ame_config.json` a `/sdcard/`** si lo actualizaste.
5. **El actualizador automático se ejecutará cada 6 horas** en segundo plano.
6. **Los logs están en `/sdcard/update_ame_log.txt`**.

---

## 🔄 **Actualizaciones Automáticas**

El script configura un actualizador automático que se ejecuta cada 6 horas. Puedes verificarlo con:
```bash
# Verificar que el proceso esté corriendo
ps aux | grep ame_updater

# Verificar logs
cat /sdcard/update_ame_log.txt
```

---

## 📌 **Notas Importantes**

- **No compartas `ame_config.json`** con terceros.
- **Usa contraseñas seguras** para Termux y AURA Core.
- **Desactiva el túnel Cloudflare** cuando no lo uses:
  ```bash
  pkill cloudflared
  ```
- **Usa WiFi** en lugar de datos móviles para mejor estabilidad.

---

## 🎯 **Pasos Resumidos para Configuración Rápida**

1. **Transferir `aura-ame` a `/sdcard/`** (usando USB o ADB).
2. **Mover carpeta a `~/aura-ame`** y configurar permisos.
3. **Instalar dependencias** con `pip install -r requirements.txt`.
4. **Configurar Cloudflare en tu PC** y transferir `ame_config.json`.
5. **Ejecutar el script de configuración** (`./TERMUX_SETUP_SCRIPT.sh`).
6. **Iniciar servicios en tu PC** (`python scripts/start_aura.py`).
7. **Verificar conexión** (`python scripts/test_ame_connection.py`).

---