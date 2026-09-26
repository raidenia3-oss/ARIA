# 🔍 **Diagnóstico y Solución para Problemas de Conexión en AME**

## 📌 **Análisis del Problema**
El error "Failed to fetch" indica que el APK de AME no puede conectarse al servidor. Esto puede deberse a múltiples causas:
1. **Configuración incorrecta en `ame_config.json`**
2. **Falta de archivos clave en el dispositivo**
3. **Servidor no iniciado correctamente**
4. **Rutas incorrectas en el APK**

---

## 🔧 **Paso 1: Verificar y Configurar `ame_config.json`**

### **1.1 Ubicar y revisar `ame_config.json`**
El archivo debe estar en `/sdcard/` o en la ruta que el APK espera. Verificaremos su contenido:

```bash
# En tu celular (Termux):
ls /sdcard/ame_config.json
cat /sdcard/ame_config.json
```

### **1.2 Ejemplo de configuración correcta**
El archivo debe contener algo similar a:
```json
{
  "server_url": "https://tuyo.trycloudflare.com",
  "api_endpoint": "/api",
  "ws_endpoint": "/ws",
  "auth_token": "tu_token_secreto"
}
```

---

## 📂 **Paso 2: Verificar Estructura del Repositorio en el Dispositivo**

### **2.1 Verificar carpeta `scripts` en el dispositivo**
```bash
# En tu celular (Termux):
ls ~/aura-ame/scripts/
ls ~/aura-ame/scripts/test_ame_connection.py
```

### **2.2 Copiar archivos clave a `/sdcard/` (si no existen)**
Si los archivos no están en `/sdcard/`, copiarlos desde el repositorio local:
```bash
# En tu celular (Termux):
mkdir -p /sdcard/aura-ame/scripts
cp ~/aura-ame/scripts/test_ame_connection.py /sdcard/aura-ame/scripts/
cp ~/aura-ame/scripts/ame_config_generator.py /sdcard/aura-ame/scripts/
```

---

## 🚀 **Paso 3: Configurar el Servidor Localmente**

### **3.1 Iniciar el servidor en tu PC**
```bash
# En tu PC:
cd C:\Users\User\Downloads\AURA
python scripts/start_aura.py
```

### **3.2 Verificar que el túnel Cloudflare esté activo**
```bash
# En tu PC:
python scripts/setup_cloudflare.py
```

---

## 🔄 **Paso 4: Probar Conexión desde el Dispositivo**

### **4.1 Ejecutar script de prueba en el dispositivo**
```bash
# En tu celular (Termux):
cd ~/aura-ame/scripts
python test_ame_connection.py
```

### **4.2 Si el script falla, revisar permisos y rutas**
```bash
# Verificar permisos
chmod +x ~/aura-ame/scripts/test_ame_connection.py

# Ejecutar con Python explícito
python3 ~/aura-ame/scripts/test_ame_connection.py
```

---

## 🎯 **Paso 5: Solución de Problemas Comunes**

### **5.1 Error: "File not found"**
- **Causa**: El script no encuentra rutas relativas.
- **Solución**: Modificar el script para usar rutas absolutas:
  ```python
  import os
  os.chdir("/sdcard/aura-ame/scripts")
  ```

### **5.2 Error: "Connection refused"**
- **Causa**: El servidor no está corriendo o el túnel Cloudflare no está activo.
- **Solución**:
  1. Verificar que `start_aura.py` esté corriendo en tu PC.
  2. Verificar que el túnel Cloudflare esté activo:
     ```bash
     # En tu PC:
     netstat -ano | findstr "8080"  # Verificar puerto
     ```

### **5.3 Error: "Invalid URL"**
- **Causa**: La URL en `ame_config.json` es incorrecta.
- **Solución**: Actualizar el archivo con la URL correcta del túnel Cloudflare.

---

## 📌 **Paso 6: Configuración Final del APK**

### **6.1 Verificar que el APK use la ruta correcta**
El APK debe buscar `ame_config.json` en:
- `/sdcard/aura-ame/ame_config.json` (recomendado)
- `/sdcard/ame_config.json` (alternativo)

### **6.2 Copiar configuración a la ruta correcta**
```bash
# En tu celular (Termux):
cp /sdcard/aura-ame/ame_config.json /sdcard/
```

---

## 🔄 **Paso 7: Ejemplo de Script de Prueba (`test_ame_connection.py`)**

Si el archivo no existe, crearemos uno básico para probar la conexión:

```python
#!/usr/bin/env python3
import requests
import json
import os

# Ruta absoluta al archivo de configuración
config_path = "/sdcard/aura-ame/ame_config.json"

# Cargar configuración
try:
    with open(config_path, 'r') as f:
        config = json.load(f)
except Exception as e:
    print(f"Error al cargar configuración: {e}")
    print(f"Verificando si el archivo existe en: {config_path}")
    exit(1)

# Probar conexión HTTP
try:
    response = requests.get(f"{config['server_url']}{config['api_endpoint']}/health")
    print(f"Conexión exitosa! Código de estado: {response.status_code}")
    print(f"Respuesta: {response.text}")
except Exception as e:
    print(f"Error de conexión: {e}")
    print(f"URL usada: {config['server_url']}{config['api_endpoint']}/health")
```

---

## 🎉 **Resumen de Acciones Recomendadas**

1. **Verificar y configurar `ame_config.json`** en `/sdcard/`.
2. **Copiar archivos clave** (`test_ame_connection.py`, `ame_config_generator.py`) a `/sdcard/aura-ame/scripts/`.
3. **Iniciar el servidor** en tu PC con `start_aura.py`.
4. **Configurar túnel Cloudflare** en tu PC.
5. **Ejecutar script de prueba** en el dispositivo.
6. **Verificar logs** en ambos dispositivos para diagnosticar errores.

---

## 📌 **Notas Importantes**

- **Usa siempre WiFi** para evitar problemas de latencia.
- **Verifica que el APK tenga permisos** para acceder a `/sdcard/`.
- **Reinicia el APK** después de hacer cambios en la configuración.
- **Si usas Cloudflare**, asegúrate de que el túnel esté activo y la URL sea correcta.

---