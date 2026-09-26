# 🔗 **INTEGRACIÓN DE VS CODE CON TERMUX (Android)**

**Guía para controlar Termux desde Visual Studio Code en tu PC**

Esta guía te permitirá interactuar con Termux en tu celular Android directamente desde Visual Studio Code en tu PC, facilitando el desarrollo, depuración y ejecución de comandos.

---

## 📌 **Requisitos Previos**

1. **Visual Studio Code** instalado en tu PC
2. **Termux** instalado en tu celular Android
3. **Termux:API** instalado en tu celular
4. **Conexión a internet estable** (WiFi recomendado)
5. **SSH configurado** en Termux (como en la guía anterior)

---

## 🔧 **Paso 1: Configurar SSH en Termux**

Si aún no lo has hecho, sigue estos pasos para configurar SSH en tu celular:

```bash
# En tu celular (Termux)
pkg install openssh -y
mkdir -p ~/.ssh
chmod 700 ~/.ssh
```

### **Generar clave SSH en tu PC**

```bash
# En tu PC (abre PowerShell o Terminal)
ssh-keygen -t ed25519 -C "tu_email@example.com"
```

### **Obtener la clave pública y agregarla a tu celular**

1. **En tu PC**, obtén tu clave pública:

    ```bash
    cat ~/.ssh/id_ed25519.pub
    ```

    _(Copia todo el texto, incluyendo `ssh-rsa AAAAB3NzaC1yc2E...`)_

2. **En tu celular**, edita el archivo de autorización:

    ```bash
    nano ~/.ssh/authorized_keys
    ```

    - Pega tu clave pública y guarda el archivo (Ctrl+O, Enter, Ctrl+X).

3. **Iniciar el servidor SSH**:
    ```bash
    sshd
    ```

---

## 🖥️ **Paso 2: Configurar VS Code para Conectarse a Termux**

### **2.1 Instalar la extensión Remote - SSH**

1. Abre **Visual Studio Code** en tu PC.
2. Ve a la pestaña de extensiones (Ctrl+Shift+X).
3. Busca **"Remote - SSH"** y instálala (de Microsoft).

### **2.2 Configurar la conexión SSH**

1. Abre la paleta de comandos (Ctrl+Shift+P).
2. Busca y selecciona **"Remote-SSH: Add New SSH Host"**.
3. Pega la siguiente línea (reemplaza `TERMUX_IP` con la IP de tu celular):
    ```
    ssh user@TERMUX_IP -p 8022
    ```
    _(Para encontrar la IP de tu celular, ejecuta `ifconfig` en Termux y busca la dirección IP de `wlan0` o `eth0`)_

---

## 🔄 **Paso 3: Conectarte a Termux desde VS Code**

1. **En VS Code**, abre la paleta de comandos (Ctrl+Shift+P).
2. Busca y selecciona **"Remote-SSH: Connect to Host..."**.
3. Selecciona la conexión que acabas de configurar (`user@TERMUX_IP`).

_(VS Code se conectará a tu celular y abrirá una ventana de desarrollo remota)_

---

## 🚀 **Paso 4: Usar VS Code con Termux**

### **4.1 Abrir archivos directamente desde Termux**

- Una vez conectado, puedes abrir y editar archivos directamente desde tu celular.
- Ejemplo: Abre `~/aura-ame/scripts/test_ame_connection.py` para editarlo.

### **4.2 Ejecutar comandos en Termux desde VS Code**

- Usa la terminal integrada de VS Code para ejecutar comandos en Termux.
- Ejemplo:
    ```bash
    python scripts/test_ame_connection.py
    pip install -r requirements.txt
    ```

### **4.3 Depuración remota**

1. Configura un archivo `.vscode/launch.json` en tu proyecto local.
2. Ejemplo de configuración para depurar Python:
    ```json
    {
        "version": "0.2.0",
        "configurations": [
            {
                "name": "Python: Termux",
                "type": "python",
                "request": "launch",
                "program": "${workspaceFolder}/scripts/test_ame_connection.py",
                "args": [],
                "cwd": "${workspaceFolder}",
                "console": "integratedTerminal",
                "justMyCode": true
            }
        ]
    }
    ```

---

## 📂 **Paso 5: Transferir Archivos entre PC y Termux**

### **5.1 Usar el Explorador de Archivos de VS Code**

1. Una vez conectado a Termux, el explorador de archivos de VS Code mostrará los archivos de tu celular.
2. Puedes arrastrar y soltar archivos entre tu PC y el almacenamiento de tu celular.

### **5.2 Usar comandos de línea**

```bash
# Copiar archivo desde PC a Termux
scp ~/ruta/local/aura-ame/user@TERMUX_IP:/home/user/aura-ame/

# Copiar archivo desde Termux a PC
scp user@TERMUX_IP:/home/user/aura-ame/archivo.txt ~/ruta/local/
```

---

## 🔐 **Paso 6: Configuración Avanzada (Opcional)**

### **6.1 Configurar un alias para la conexión SSH**

1. Edita el archivo `~/.ssh/config` en tu PC.
2. Añade la siguiente línea (reemplaza `TERMUX_IP`):

    ```
    Host termux
      HostName TERMUX_IP
      User user
      Port 8022
      IdentityFile ~/.ssh/id_ed25519
    ```

3. Ahora puedes conectarte simplemente con:
    ```bash
    ssh termux
    ```

### **6.2 Configurar VS Code para abrir automáticamente el proyecto**

1. Crea un archivo `~/.vscode/settings.json` en tu PC con:
    ```json
    {
        "remote.SSH.remotePath": "/home/user/aura-ame",
        "workbench.startupEditor": "welcomePage",
        "files.autoSave": "afterDelay",
        "editor.formatOnSave": true
    }
    ```

---

## 🎯 **Paso 7: Solución de Problemas Comunes**

| Problema                                    | Solución                                                                                              |
| ------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| **Conexión SSH fallida**                    | Verifica que `sshd` esté corriendo en Termux y que la clave pública esté en `~/.ssh/authorized_keys`. |
| **No se puede encontrar la IP del celular** | Ejecuta `ifconfig` en Termux y busca la dirección IP de `wlan0` o `eth0`.                             |
| **VS Code no muestra archivos de Termux**   | Asegúrate de estar conectado a la sesión SSH y verifica que el path sea correcto.                     |
| **Permisos denegados**                      | Ejecuta `chmod -R 755 ~/aura-ame` en Termux para dar permisos adecuados.                              |
| **Conexión lenta**                          | Usa WiFi en lugar de datos móviles.                                                                   |

---
