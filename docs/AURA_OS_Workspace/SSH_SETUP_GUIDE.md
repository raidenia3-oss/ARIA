# 🔐 **Guía de Configuración SSH para Termux (Paso a Paso)**

Basado en la información que proporcionaste, aquí tienes una guía detallada para configurar SSH en tu dispositivo Termux y conectarlo a Visual Studio Code.

---

## 📌 **Información Obtenida de tu Terminal**

- **IP de tu dispositivo**: `10.1.172.91` (de `ccmni0`)
- **OpenSSH ya está instalado** (versión 10.3p1-1)
- **Directorio `.ssh` creado correctamente** con permisos `700`
- **Servidor SSH no se inició correctamente** (necesitamos solucionarlo)

---

## 🔧 **Paso 1: Configurar la Clave SSH en tu PC**

### **1.1 Generar una clave SSH en tu PC (si no lo has hecho)**

Abre una terminal en tu PC y ejecuta:

```bash
ssh-keygen -t ed25519 -C "tu_email@example.com"
```

- Presiona `Enter` para aceptar la ubicación predeterminada.
- Establece una contraseña (opcional, pero recomendado).

### **1.2 Obtener tu clave pública**

```bash
cat ~/.ssh/id_ed25519.pub
```

- Copia **todo el contenido** (incluyendo `ssh-rsa AAAAB3NzaC1yc2E...`).

---

## 📥 **Paso 2: Configurar la Clave SSH en Termux**

### **2.1 Agregar tu clave pública a Termux**

Ejecuta en tu terminal de Termux:

```bash
echo "PEGA_AQUI_TU_CLAVE_PUBLICA" > ~/.ssh/authorized_keys
```

_(Reemplaza `PEGA_AQUI_TU_CLAVE_PUBLICA` con la clave que copiaste de tu PC)_

### **2.2 Verificar permisos**

```bash
chmod 600 ~/.ssh/authorized_keys
```

---

## 🚀 **Paso 3: Iniciar el Servidor SSH Correctamente**

### **3.1 Instalar OpenSSH (si no está instalado)**

```bash
pkg install openssh -y
```

### **3.2 Iniciar el servidor SSH en segundo plano**

```bash
sshd
```

_(Si no funciona, prueba con:)_

```bash
sshd -D
```

### **3.3 Verificar que SSH esté corriendo**

```bash
ps | grep sshd
```

_(Deberías ver algo como: `sshd: /usr/bin/sshd [listening]`)_

---

## 🖥️ **Paso 4: Configurar VS Code para Conectarse a Termux**

### **4.1 Instalar la extensión Remote-SSH en VS Code**

1. Abre **Visual Studio Code**.
2. Ve a la pestaña de extensiones (Ctrl+Shift+X).
3. Busca e instala **"Remote - SSH"** (de Microsoft).

### **4.2 Agregar la conexión SSH**

1. Abre la paleta de comandos (Ctrl+Shift+P).
2. Busca y selecciona **"Remote-SSH: Add New SSH Host"**.
3. Pega la siguiente línea (reemplaza `10.1.172.91` con tu IP si es diferente):
    ```
    ssh user@10.1.172.91 -p 8022
    ```

---

## 🔄 **Paso 5: Conectarte a Termux desde VS Code**

### **5.1 Conectar a tu dispositivo**

1. Abre la paleta de comandos (Ctrl+Shift+P).
2. Busca y selecciona **"Remote-SSH: Connect to Host..."**.
3. Selecciona la conexión que acabas de configurar (`user@10.1.172.91`).

### **5.2 Solución de problemas comunes**

Si no puedes conectarte:

- **Verifica que SSH esté corriendo**:
    ```bash
    ps | grep sshd
    ```
- **Reinicia el servidor SSH**:
    ```bash
    pkill sshd
    sshd
    ```
- **Verifica el firewall**:
    ```bash
    termux-setup-storage
    ```
    _(Asegúrate de que no haya restricciones en el firewall de Android)_

---

## 🎯 **Paso 6: Verificar la Conexión**

### **6.1 Desde tu PC, prueba la conexión SSH**

```bash
ssh user@10.1.172.91 -p 8022
```

_(Si te pide contraseña, ingresa la que configuraste en tu PC con `ssh-keygen`)_

### **6.2 Si no funciona, prueba con un puerto alternativo**

```bash
sshd -p 2222
```

_(Luego usa en VS Code: `ssh user@10.1.172.91 -p 2222`)_

---

## 📌 **Notas Importantes**

- **Usa siempre WiFi** para evitar problemas de latencia y desconexiones.
- **No compartas tus credenciales SSH** con terceros.
- **Si usas un puerto diferente a 8022**, asegúrate de actualizarlo en VS Code y en el comando SSH.

---

## 🔄 **Solución de Problemas Adicionales**

### **Si `sshd` no se inicia correctamente**

Prueba con:

```bash
sshd -D -e /sdcard/sshd.log
```

_(Esto guardará los logs de error en `/sdcard/sshd.log` para que puedas revisarlos)_

### **Si hay problemas de permisos**

```bash
chmod 755 /data/data/com.termux/files/usr/sbin/sshd
```

---

## 🎉 **Resumen de Comandos Clave**

```bash
# En tu PC:
ssh-keygen -t ed25519 -C "tu_email@example.com"
cat ~/.ssh/id_ed25519.pub  # Copiar clave pública

# En Termux:
mkdir -p ~/.ssh
chmod 700 ~/.ssh
echo "TU_CLAVE_PUBLICA" > ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```
