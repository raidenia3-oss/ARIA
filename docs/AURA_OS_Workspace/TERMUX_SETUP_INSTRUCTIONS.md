# 📱 **INSTRUCCIONES DETALLADAS PARA CONFIGURAR TERMUX EN ANDROID**

Este documento te guiará paso a paso para configurar tu dispositivo Android con Termux y conectarlo a AURA Core. Sigue estas instrucciones **en orden** para evitar errores.

---

## 📌 **Requisitos Previos**

1. **Termux instalado** desde [F-Droid](https://f-droid.org/es/packages/com.termux/)
2. **Termux:API** instalado desde [F-Droid](https://f-droid.org/es/packages/com.termux.api/)
3. **Conexión a internet estable** (WiFi recomendado)
4. **Acceso a `/sdcard/`** (Termux debe tener permisos de almacenamiento)

---

## 🔧 **Paso 1: Ejecutar el Script de Configuración**

### **1.1 Abre Termux**
- Abre la aplicación **Termux** en tu celular.

### **1.2 Descarga el script de configuración**
```bash
wget https://raw.githubusercontent.com/TU_USUARIO/aura-ame/main/TERMUX_SETUP_SCRIPT.sh
```
*(Reemplaza `TU_USUARIO` con el usuario real del repositorio)*

### **1.3 Haz el script ejecutable**
```bash
chmod +x TERMUX_SETUP_SCRIPT.sh
```

### **1.4 Ejecuta el script**
```bash
./TERMUX_SETUP_SCRIPT.sh
```
*(Si te pide confirmación, escribe `yes` y presiona ENTER)*

---

## 📥 **Paso 2: Configurar Cloudflare en tu PC**

**Debes hacer esto en tu computadora (PC) antes de continuar:**

### **2.1 Configurar el túnel Cloudflare**
```bash
cd ruta/aura-ame
python scripts/setup_cloudflare.py
```
- Selecciona la opción `[1]` para `trycloudflare.com` (gratis).

### **2.2 Generar configuración para Android**
```bash
python scripts/ame_config_generator.py
```

### **2.3 Transferir `ame_config.json` a tu celular**
#### **Opción A: Usando ADB (si tienes acceso)**
```bash
adb push aura_urls/ame_config.json /sdcard/
```

#### **Opción B: Manual (sin ADB)**
1. Copia el archivo `aura_urls/ame_config.json` desde tu PC a una computadora o USB.
2. Conecta tu celular a esa computadora/USB.
3. Copia el archivo `ame_config.json` a la carpeta `/sdcard/` de tu celular.

---

## 🔄 **Paso 3: Verificar la Configuración**

### **3.1 Verificar que el archivo esté en `/sdcard/`**
```bash
ls /sdcard/ame_config.json
```
*(Si no aparece, repite el Paso 2.3)*

### **3.2 Probar la conexión**
```bash
python scripts/test_ame_connection.py
```
**Salida esperada:**
```
🎉 ¡Conexión exitosa! AME puede comunicarse con AURA Core
```

---

## 🚀 **Paso 4: Iniciar Servicios en tu PC**

Asegúrate de que los siguientes servicios estén corriendo en tu PC:

```bash
cd ruta/aura-ame
python scripts/start_aura.py
```

---

## 🔐 **Paso 5: Configuración Adicional (Opcional pero Recomendado)**

### **5.1 Configurar SSH (para acceso remoto)**
El script ya configuró SSH, pero debes reemplazar la clave pública con la tuya:

1. **Genera una clave SSH en tu PC** (si no lo has hecho):
   ```bash
   ssh-keygen -t ed25519 -C "tu_email@example.com"
   ```

2. **Obtén tu clave pública**:
   ```bash
   cat ~/.ssh/id_ed25519.pub
   ```

3. **Edita el archivo de autorización en tu celular**:
   ```bash
   nano ~/.ssh/authorized_keys
   ```
   - Pega tu clave pública y guarda el archivo (Ctrl+O, Enter, Ctrl+X).

4. **Inicia el servidor SSH**:
   ```bash
   sshd
   ```

### **5.2 Verificar procesos en ejecución**
```bash
ps | grep -E "ame_updater|sshd"
```
*(Debes ver procesos como `sshd` y `ame_updater`)*

---

## 📡 **Paso 6: Verificar el Estado del Sistema**

### **En tu PC (AURA Core)**
```bash
python scripts/health_check.py
```

### **En tu Celular (Termux)**
```bash
# Verificar logs de actualización
cat /sdcard/update_ame_log.txt

# Verificar estado del actualizador
ps aux | grep ame_updater
```

---

## 🔄 **Paso 7: Solución de Problemas**

| Problema | Solución |
|----------|----------|
| **`ame_config.json` no encontrado** | Copia el archivo desde tu PC a `/sdcard/` |
| **Conexión fallida a EventBus** | Verifica que `start_aura.py` esté corriendo en tu PC |
| **Error de certificado en Cloudflare** | Ejecuta `python scripts/setup_cloudflare.py` nuevamente en tu PC |
| **Termux no tiene permisos en `/sdcard/`** | Ejecuta `termux-setup-storage` y reinicia Termux |
| **Script falla en algún paso** | Ejecuta cada comando manualmente para identificar el error |

---

## 🎯 **Resumen de lo Configurado**

✅ **Termux actualizado** con todas las dependencias necesarias.
✅ **Repositorio AURA clonado** en `/home/user/aura-ame`.
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