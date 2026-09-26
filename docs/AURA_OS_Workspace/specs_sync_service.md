# 📜 **SPECIFICATIONS: LIVE-SYNC SERVICE**
## **Automated CI/CD for AURA/AME (PC → Android/Termux)**
**Version:** 1.0.0
**Date:** 02/06/2026
**Status:** Proposal & Specifications
**Author:** System Architect

---

## 🎯 **Objective**
Implement a **Live-Sync Service** that automatically synchronizes code changes from the PC development environment to the Android device (via Termux) using **rsync** over the existing SSH tunnel. This service will eliminate manual intervention by:
1. Monitoring file changes in development directories (`AURA_Core` and `AME_Core`).
2. Automatically syncing modified files to the mobile device.
3. Ignoring heavy directories (`.git`, `node_modules`, etc.) to optimize performance.

---

## 📋 **System Overview**

### **1. Components**
| **Component**               | **Description**                                                                                     |
|-----------------------------|-------------------------------------------------------------------------------------------------|
| **Watchdog Monitor**        | Uses Python's `watchdog` library to detect file changes in real-time.                              |
| **Sync Engine**             | Executes `rsync` commands to synchronize files over SSH to the mobile device.                     |
| **Configuration Manager**   | Loads and manages sync settings from `sync_config.json`.                                           |
| **Logging System**          | Records sync operations and errors for debugging and monitoring.                                   |
| **SSH Bridge**              | Uses existing SSH tunnel (port 8022) to communicate with Termux on the mobile device.            |

---

## 🔧 **Architecture & Data Flow**

### **1. Event-Driven Architecture**
```mermaid
graph TD
    A[Development Directory] --> B[Watchdog Monitor]
    B --> C[File Change Event]
    C --> D[Sync Engine]
    D --> E[SSH Tunnel]
    E --> F[Mobile Device (Termux)]
    D --> G[Logging System]
    G --> H[Sync Logs]
```

### **2. Key Components**

#### **1. Watchdog Monitor**
- **Library:** `watchdog`
- **Input:** Directories to monitor (`AURA_Core`, `AME_Core`).
- **Output:** File system events (`on_modified`, `on_created`, `on_deleted`).
- **Features:**
  - Recursive monitoring of subdirectories.
  - Ignores specified directories and file extensions.

#### **2. Sync Engine**
- **Tool:** `rsync`
- **Protocol:** SSH (port 8022)
- **Features:**
  - Syncs only modified files (not full directory copies).
  - Supports deletion of files on the mobile device if they no longer exist locally.
  - Creates remote directories as needed.

#### **3. Configuration Manager**
- **File:** `sync_config.json`
- **Parameters:**
  - Local and remote directories.
  - SSH connection details (host, port, user).
  - Ignored directories and file extensions.
  - Sync interval and retry settings.

#### **4. Logging System**
- **File:** `sync_service.log`
- **Features:**
  - Logs all sync operations (successes and failures).
  - Records timestamps and file paths.
  - Provides debug-level details for troubleshooting.

---

## 📡 **Communication Protocol**

### **1. SSH Tunnel Configuration**
- **Host:** `localhost` (via existing reverse SSH tunnel)
- **Port:** `8022` (Termux default SSH port)
- **User:** `user` (Termux default user)
- **Remote Directory:** `/data/data/com.termux/files/home/AME_Core`

### **2. rsync Command Examples**
#### **Synchronize a Modified File**
```bash
rsync -avz --delete --exclude='.git' --exclude='node_modules' \
    /path/to/local/file user@localhost:/data/data/com.termux/files/home/AME_Core/path/to/remote/file
```

#### **Delete a File on Mobile Device**
```bash
ssh -p 8022 user@localhost "rm -f /data/data/com.termux/files/home/AME_Core/path/to/remote/file"
```

---

## 📋 **Configuration File (`sync_config.json`)**

### **1. Default Configuration**
```json
{
    "version": "1.0.0",
    "local_dev_dir": "AURA_Core",
    "remote_app_dir": "/data/data/com.termux/files/home/AME_Core",
    "watch_dirs": ["AURA_Core", "AME_Core"],
    "ssh_host": "localhost",
    "ssh_port": 8022,
    "ssh_user": "user",
    "ignored_dirs": [
        ".git", "node_modules", "__pycache__", ".venv", ".env",
        ".vscode", "dist", "build", "logs", "spec", "AURA-Desktop"
    ],
    "excluded_extensions": [
        ".log", ".pyc", ".pyo", ".pyd", ".exe", ".dll", ".so",
        ".min.js", ".min.css", ".db", ".sqlite", ".lock"
    ],
    "sync_interval": 60,
    "log_file": "sync_service.log",
    "max_retries": 3,
    "retry_delay": 5,
    "verbose": true
}
```

---

## 🔄 **Operation Workflow**

### **1. Initial Setup**
1. **Configure SSH Tunnel:**
   - Ensure the reverse SSH tunnel is established between PC and mobile device (port 8022).
   - Verify SSH key-based authentication is set up.

2. **Set Up Configuration:**
   - Edit `sync_config.json` to match your environment.
   - Example:
     ```bash
     python sync_to_mobile.py --setup
     ```
   - This creates a default configuration file.

3. **Test SSH Connection:**
   - The service automatically tests the SSH connection before starting.
   - If the connection fails, it logs an error and exits.

### **2. Starting the Service**
```bash
python sync_to_mobile.py
```
- **Options:**
  - `--config <file>`: Specify a custom configuration file.
  - `--setup`: Generate a default configuration file.

### **3. Service Operation**
1. **Monitoring:**
   - The service monitors `AURA_Core` and `AME_Core` for file changes.
   - Events: `on_modified`, `on_created`, `on_deleted`.

2. **Synchronization:**
   - When a file is modified, created, or deleted, the service triggers a sync.
   - For modifications/creations: Uses `rsync` to copy the file to the mobile device.
   - For deletions: Uses SSH to remove the file from the mobile device.

3. **Periodic Sync:**
   - Every 60 seconds (configurable), the service performs a full scan of monitored directories to ensure no files were missed.

4. **Error Handling:**
   - Retries failed sync operations up to 3 times with a 5-second delay between attempts.
   - Logs all errors for debugging.

---

## 📋 **Logging & Monitoring**

### **1. Log File Format**
- **File:** `sync_service.log`
- **Example Entry:**
  ```
  2026-06-02 12:00:00,123 - INFO - Cambio detectado en: AURA_Core/sync_to_mobile.py
  2026-06-02 12:00:00,456 - DEBUG - Ejecutando comando: ssh -p 8022 user@localhost mkdir -p /data/data/com.termux/files/home/AME_Core/AURA_Core
  2026-06-02 12:00:00,789 - INFO - Sincronización exitosa para: AURA_Core/sync_to_mobile.py
  ```

### **2. Log Levels**
| **Level**   | **Description**                                                                                     |
|-------------|-------------------------------------------------------------------------------------------------|
| `INFO`      | General operation messages (file changes, sync successes).                                         |
| `DEBUG`     | Detailed information for troubleshooting (commands executed, file paths).                          |
| `ERROR`     | Errors and failures (SSH connection issues, sync failures).                                       |
| `WARNING`   | Potential issues (ignored files, empty files).                                                     |

---

## 📌 **Usage Instructions for Architects**

### **1. Starting the Service**
```bash
# Iniciar el servicio con la configuración por defecto
python sync_to_mobile.py

# Iniciar con una configuración personalizada
python sync_to_mobile.py --config custom_sync_config.json
```

### **2. Generar Configuración por Defecto**
```bash
python sync_to_mobile.py --setup
```
- Esto generará un archivo `sync_config.json` con valores por defecto que puedes editar según tu entorno.

### **3. Verificar el Estado del Servicio**
- **Logs:** Revisa `sync_service.log` para ver el estado actual y cualquier error.
- **Terminal:** El servicio muestra mensajes en tiempo real en la consola.

### **4. Detener el Servicio**
- Presiona `Ctrl+C` en la terminal donde está ejecutándose el servicio.
- El servicio se detendrá de manera segura y cerrará todos los recursos.

---

## 📋 **Troubleshooting**

### **1. Problemas Comunes y Soluciones**
| **Problema**                          | **Solución**                                                                                     |
|---------------------------------------|-------------------------------------------------------------------------------------------------|
| **Conexión SSH fallida**              | Verificar que el túnel SSH esté activo y que las credenciales sean correctas.                  |
| **Permisos insuficientes en el móvil** | Asegurar que el usuario de Termux tenga permisos de escritura en `/data/data/com.termux/files/home`. |
| **Archivos ignorados incorrectamente** | Revisar la lista de `ignored_dirs` y `excluded_extensions` en `sync_config.json`.             |
| **Sincronización lenta**              | Reducir el número de directorios monitorizados o aumentar el intervalo de sincronización.       |
| **Errores de rsync**                  | Verificar que los directorios remotos existan y que el usuario SSH tenga permisos adecuados.   |

### **2. Comandos Útiles para Depuración**
```bash
# Probar conexión SSH manualmente
ssh -p 8022 user@localhost "echo 'SSH test successful'"

# Verificar permisos en el dispositivo móvil
ssh -p 8022 user@localhost "ls -la /data/data/com.termux/files/home/AME_Core"

# Ejecutar rsync manualmente para probar
rsync -avz --delete --exclude='.git' --exclude='node_modules' AURA_Core/ user@localhost:/data/data/com.termux/files/home/AME_Core/AURA_Core/
```

---

## 🎯 **Conclusion**
The **Live-Sync Service** provides a seamless, automated CI/CD pipeline for AURA/AME, ensuring that the mobile device always has the latest code without manual intervention. Key benefits include:
1. **Automated Synchronization:** Files are synced automatically when modified.
2. **Efficient Transfers:** Only changed files are transferred, reducing bandwidth and time.
3. **Real-Time Monitoring:** Watchdog detects changes instantly.
4. **Robust Error Handling:** Retries failed operations and logs detailed information.
5. **Configurable:** Easy to adjust ignored directories, sync intervals, and SSH settings.

**Next Steps:**
- Validate the specification with the Architect.
- Proceed to testing and deployment once approved.

---
**Ready for Architect Validation!**

---
**Nota:** El servicio está diseñado para ser resistente a fallos y fácil de monitorear. Los logs detallados permiten depurar cualquier problema que pueda surgir durante la sincronización.