# 📱 **TERMUX BRIDGE SETUP — Guía Completa para Conectar Android con AURA Core**

Este documento detalla cómo configurar la conexión entre **Termux en Android** y **AURA Core en PC** para un funcionamiento integrado y seguro.

---

## 🔗 **Requisitos Previos**

### **En la PC (AURA Core)**
1. **Python 3.11+** instalado
2. **Git** instalado
3. **Cloudflare Tunnel** configurado (usando `scripts/setup_cloudflare.py`)
4. **Servicios AURA** corriendo (`scripts/start_aura.py`)

### **En el Celular (Android)**
1. **Termux** instalado desde [F-Droid](https://f-droid.org/es/packages/com.termux/)
2. **Permisos de almacenamiento** (para acceder a `/sdcard/`)
3. **Conexión a internet** (WiFi o datos móviles)
4. **ADB (Android Debug Bridge)** instalado en la PC (opcional para transferencia de archivos)

---

## 🔧 **Configuración Paso a Paso**

---

### **1️⃣ Configuración Inicial en Termux**

#### **Instalar dependencias básicas**
```bash
pkg update && pkg upgrade -y
pkg install python git openssh -y
```

#### **Configurar Python 3.10+**
```bash
pkg install python -y
python --version  # Verificar que sea 3.10+
```

#### **Clonar el repositorio AURA**
```bash
cd ~
git clone https://github.com/TU_USUARIO/aura-ame.git
cd aura-ame
```

---

### **2️⃣ Configuración del Túnel Cloudflare (PC → Android)**

#### **En la PC (AURA Core)**
```bash
# Configurar túnel Cloudflare (si no lo has hecho)
python scripts/setup_cloudflare.py
# Selecciona opción [1] para trycloudflare.com (gratis)

# Generar configuración para AME
python scripts/ame_config_generator.py
```

#### **Transferir `ame_config.json` al Celular**
```bash
# Opción 1: Usando ADB (recomendado)
adb push aura_urls/ame_config.json /sdcard/

# Opción 2: Manual (copiar desde PC a Android usando apps como Solid Explorer)
```

#### **Verificar que el archivo esté en `/sdcard/`**
```bash
ls /sdcard/ame_config.json
```

---

### **3️⃣ Configuración de la Conexión SSH (Opcional pero Recomendado)**

#### **En la PC (AURA Core)**
Instalar **sshd** (servidor SSH) en Termux:
```bash
# En Termux (Android)
pkg install openssh -y
sshd
```

#### **Configurar clave SSH en la PC**
```bash
# Generar clave SSH en la PC (si no existe)
ssh-keygen -t ed25519 -C "aura_android_bridge"

# Copiar clave pública al celular
cat ~/.ssh/id_ed25519.pub | ssh user@TERMUX_IP "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

#### **Conectarse desde la PC al Celular**
```bash
# Encontrar la IP del celular en Termux
ifconfig | grep "inet " | grep -v 127.0.0.1

# Conectarse vía SSH
ssh user@TERMUX_IP -p 8022
```

---

### **4️⃣ Configuración de la Conexión Directa (WiFi Local)**

#### **En la PC (AURA Core)**
Asegúrate de que los servicios estén corriendo:
```bash
python scripts/start_aura.py
```

#### **En el Celular (Termux)**
Verificar conexión al EventBus local:
```bash
python scripts/test_ame_connection.py
```

**Salida esperada:**
```
🎉 ¡Conexión exitosa! AME puede comunicarse con AURA Core
```

---

### **5️⃣ Configuración de la Conexión Remota (Cloudflare Tunnel)**

#### **Verificar que el túnel esté activo**
```bash
# En la PC (verificar URLs del túnel)
cat aura_urls.json
```

#### **Configurar AME para usar el túnel**
```bash
# En Termux (verificar que ame_config.json apunte al túnel)
cat /sdcard/ame_config.json
```

**Ejemplo de `ame_config.json`:**
```json
{
  "network": {
    "eventbus_url": "wss://aura-eventbus.TU_DOMINIO.trycloudflare.com",
    "godot_url": "wss://aura-godot.TU_DOMINIO.trycloudflare.com",
    "dashboard_url": "https://TU_DOMINIO.trycloudflare.com"
  }
}
```

#### **Conectar AME al túnel**
```bash
# En Termux
cd ~/aura-ame
python join_swarm.py --server wss://aura-eventbus.TU_DOMINIO.trycloudflare.com
```

---

### **6️⃣ Configuración de Actualizaciones Automáticas**

#### **En la PC (AURA Core)**
```bash
# Iniciar actualizador automático (revisa cada hora)
nohup python scripts/auto_updater.py > update_log.txt 2>&1 &
```

#### **En el Celular (Termux)**
```bash
# Iniciar actualizador automático (revisa cada 6 horas)
python scripts/ame_updater.py
```

#### **Verificar actualizaciones manualmente**
```bash
# En Termux
python scripts/ame_updater.py --test
```

---

### **7️⃣ Configuración de Firewall y Puertos**

#### **En la PC (AURA Core)**
Asegúrate de que los puertos estén abiertos:
- **8765**: EventBus (WebSocket)
- **9090**: Godot Bridge (WebSocket)
- **5000**: Dashboard (HTTP)
- **5004**: API de Discord Shield (HTTP)
- **8080**: Proxy Discord Shield (HTTP/HTTPS)

#### **En Android (Termux)**
Permitir conexiones salientes:
```bash
# Verificar que no haya firewalls bloqueando
pkg install iptables -y
iptables -L  # Verificar reglas
```

---

### **8️⃣ Configuración de Termux para Ejecución en Segundo Plano**

#### **Instalar `termux-api` para notificaciones**
```bash
pkg install termux-api -y
```

#### **Configurar `termux-boot` para inicio automático**
```bash
# Editar el archivo de inicio
echo "cd ~/aura-ame && python scripts/ame_updater.py" >> ~/.bashrc
```

#### **Habilitar ejecución en segundo plano**
```bash
# Instalar screen o tmux para mantener procesos activos
pkg install screen -y
screen -dmS aura python scripts/ame_updater.py
```

---

## 🔄 **Flujo de Conexión Integrado**

```
Celular (Termux)
    → /sdcard/ame_config.json (configuración)
    → wss://aura-eventbus.TU_DOMINIO.trycloudflare.com (EventBus)
    ↓ Cloudflare Tunnel (trycloudflare.com)
PC (AURA Core)
    ← EventBus (puerto 8765)
    ← Godot Bridge (puerto 9090)
    ← Dashboard (puerto 5000)
```

---

## 📡 **Verificación de Conexión**

### **En la PC (AURA Core)**
```bash
# Verificar estado del sistema
python scripts/health_check.py

# Verificar logs de conexión
tail -f aura_status.json
```

### **En el Celular (Termux)**
```bash
# Verificar conexión
python scripts/test_ame_connection.py

# Verificar logs de actualización
cat /sdcard/update_ame_log.txt

# Verificar estado del bot Rollercoin
curl http://localhost:5003/status
```

---

## 🔐 **Seguridad y Buenas Prácticas**

1. **No compartas `ame_config.json`** con terceros
2. **Usa contraseñas seguras** para Termux y AURA Core
3. **Desactiva el túnel** cuando no lo uses:
   ```bash
   # En la PC
   pkill cloudflared
   ```
4. **Actualiza regularmente** tanto en PC como en Android
5. **Usa VPN** si estás en una red pública

---

## 📱 **Solución de Problemas**

| Problema | Solución |
|----------|----------|
| **No se puede conectar a EventBus** | Verifica que `start_aura.py` esté corriendo en la PC |
| **Error de certificado en Cloudflare** | Ejecuta `python scripts/setup_cloudflare.py` nuevamente |
| **Termux no tiene permisos en `/sdcard/`** | Ejecuta `termux-setup-storage` y reinicia Termux |
| **Conexión lenta** | Usa WiFi en lugar de datos móviles |
| **Proxy no funciona** | Verifica que el certificado esté instalado en el sistema |
| **Actualizaciones fallan** | Ejecuta manualmente `git pull` y verifica logs |

---

## 🎯 **Resumen de Comandos Útiles**

| Comando | Descripción |
|---------|-------------|
| `python scripts/start_aura.py` | Iniciar servicios en la PC |
| `python scripts/ame_config_generator.py` | Generar config para Android |
| `adb push aura_urls/ame_config.json /sdcard/` | Transferir config al celular |
| `python scripts/test_ame_connection.py` | Verificar conexión desde Android |
| `python scripts/auto_updater.py` | Actualizar PC automáticamente |
| `python scripts/ame_updater.py` | Actualizar Android automáticamente |
| `curl http://localhost:5003/status` | Ver estado del bot Rollercoin |
| `curl http://localhost:5004/status` | Ver estado del Discord Shield |

---

## 📢 **Contribuir al Proyecto**

1. **Haz un fork** del repositorio
2. **Crea una rama** para tu feature: `git checkout -b feature/nueva-funcionalidad`
3. **Haz commit** de tus cambios: `git commit -m "Añadir nueva funcionalidad"`
4. **Sube a la rama**: `git push origin feature/nueva-funcionalidad`
5. **Abre un Pull Request**

---