# AURA OS v2.0 — Installation Guide

Instrucciones paso a paso para instalar AURA en tu sistema.

**Tabla de contenidos:**
1. [Windows](#windows)
2. [Linux](#linux)
3. [macOS](#macos)
4. [Docker](#docker)
5. [Cloud](#cloud)
6. [Troubleshooting](#troubleshooting)

---

## Windows

### Opción 1: Standalone .exe (Recomendado - 5 minutos)

**Requisitos:**
- Windows 10/11 (cualquier versión)
- 500 MB espacio libre
- No requiere software adicional

**Pasos:**

1. **Descargar**
   - Ir a [Releases](https://github.com/tu-usuario/AURA/releases)
   - Descargar `AURA OS v2.0.exe` (155 MB)
   - Guardar en `C:\Users\{tu_usuario}\Downloads\`

2. **Ejecutar installer**
   ```
   Doble clic en AURA OS v2.0.exe
   ```
   - Acepta permisos (si pide)
   - Espera 30 segundos

3. **Verificar instalación**
   - Busca acceso directo **"AURA OS"** en escritorio
   - Debería haber un ícono con logo AURA

4. **Iniciar AURA**
   - Doble clic en **AURA OS**
   - Se abre ventana nativa
   - Verás interfaz con orb animado
   - ✅ Listo

**¿Qué hace el installer?**
- Copia `AURA OS.exe` a `C:\Program Files\AURA\`
- Crea acceso directo en escritorio
- Configura puerto 8000
- Crea carpeta `~\.aura\` para datos

**Desinstalar:**
- Control Panel → Programas → AURA OS → Desinstalar
- O eliminar carpeta `C:\Program Files\AURA\`

---

### Opción 2: Desde Código Python (Desarrollo - 15 minutos)

**Requisitos:**
- Python 3.10+ (descargar desde [python.org](https://www.python.org/downloads/))
- Git (descargar desde [git-scm.com](https://git-scm.com/))
- 2 GB espacio libre

**Pasos:**

1. **Descargar repositorio**
   ```powershell
   # Abrir PowerShell (Win+R → powershell)
   cd C:\Users\{tu_usuario}\Downloads
   git clone https://github.com/tu-usuario/AURA.git
   cd AURA
   ```

2. **Crear entorno virtual**
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   ```
   
   Verás que el prompt cambia a algo como:
   ```
   (venv) C:\Users\{tu_usuario}\Downloads\AURA>
   ```

3. **Instalar dependencias**
   ```powershell
   pip install --upgrade pip setuptools wheel
   pip install -r requirements.txt
   ```
   
   Esto tardará 3-5 minutos descargando paquetes.

4. **Ejecutar AURA**
   ```powershell
   python backend/main.py
   ```
   
   Verás algo como:
   ```
   INFO:     Uvicorn running on http://0.0.0.0:8000
   ```

5. **Abrir en navegador**
   ```
   Start → Edge/Chrome → http://localhost:8000
   ```
   
   ✅ Listo

**Parar AURA:**
```powershell
Ctrl+C
```

**Próxima vez:**
```powershell
cd C:\Users\{tu_usuario}\Downloads\AURA
.\venv\Scripts\activate
python backend/main.py
```

---

### Opción 3: Instalar como Servicio Windows (Avanzado)

**Requisitos:**
- Completar Opción 2 primero
- PowerShell como Admin

**Pasos:**

1. **Crear script de inicio**
   ```powershell
   # Como admin:
   cd AURA
   New-Item -Path "scripts\aura-service.ps1" -ItemType File -Force
   ```

2. **Copiar contenido** (en `scripts/aura-service.ps1`):
   ```powershell
   $venvPath = "C:\Users\{tu_usuario}\Downloads\AURA\venv\Scripts\python.exe"
   $mainPath = "C:\Users\{tu_usuario}\Downloads\AURA\backend\main.py"
   
   & $venvPath $mainPath
   ```

3. **Registrar como servicio** (con NSSM):
   ```powershell
   # Descargar NSSM desde nssm.cc
   # Luego:
   nssm install AuraOS $venvPath $mainPath
   nssm start AuraOS
   ```

4. **Verificar servicio**
   ```powershell
   services.msc
   # Buscar "AuraOS" y verifica "Running"
   ```

**Parar servicio:**
```powershell
nssm stop AuraOS
```

---

## Linux

### Ubuntu/Debian

**Requisitos:**
- Ubuntu 20.04 LTS o superior
- `sudo` permisos
- 2 GB espacio libre

**Pasos:**

1. **Instalar Python**
   ```bash
   sudo apt update
   sudo apt install -y python3.10 python3.10-venv python3-pip git
   ```

2. **Clonar repositorio**
   ```bash
   cd ~
   git clone https://github.com/tu-usuario/AURA.git
   cd AURA
   ```

3. **Crear venv**
   ```bash
   python3.10 -m venv venv
   source venv/bin/activate
   ```

4. **Instalar dependencias**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

5. **Ejecutar**
   ```bash
   python backend/main.py
   ```

6. **Abrir navegador**
   ```bash
   firefox http://localhost:8000
   ```

**Instalar como servicio systemd:**

1. **Crear archivo de servicio:**
   ```bash
   sudo nano /etc/systemd/system/aura-os.service
   ```

2. **Pegar:**
   ```ini
   [Unit]
   Description=AURA OS v2.0
   After=network.target
   
   [Service]
   Type=simple
   User=tu_usuario
   WorkingDirectory=/home/tu_usuario/AURA
   ExecStart=/home/tu_usuario/AURA/venv/bin/python /home/tu_usuario/AURA/backend/main.py
   Restart=always
   RestartSec=10
   
   [Install]
   WantedBy=multi-user.target
   ```

3. **Guardar:** `Ctrl+X → Y → Enter`

4. **Activar:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable aura-os
   sudo systemctl start aura-os
   ```

5. **Ver estado:**
   ```bash
   sudo systemctl status aura-os
   ```

6. **Ver logs:**
   ```bash
   sudo journalctl -u aura-os -f
   ```

---

### Fedora/RHEL

```bash
sudo dnf install -y python3.10 python3.10-devel git

cd ~
git clone https://github.com/tu-usuario/AURA.git
cd AURA

python3.10 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
python backend/main.py
```

---

### Arch Linux

```bash
sudo pacman -S python git

cd ~
git clone https://github.com/tu-usuario/AURA.git
cd AURA

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt
python backend/main.py
```

---

## macOS

**Requisitos:**
- macOS 11+ (Big Sur o superior)
- Homebrew (descargar desde [brew.sh](https://brew.sh/))
- 2 GB espacio libre

**Pasos:**

1. **Instalar Python con Homebrew**
   ```bash
   brew install python@3.10 git
   ```

2. **Clonar repositorio**
   ```bash
   cd ~
   git clone https://github.com/tu-usuario/AURA.git
   cd AURA
   ```

3. **Crear venv**
   ```bash
   python3.10 -m venv venv
   source venv/bin/activate
   ```

4. **Instalar dependencias**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

5. **Ejecutar**
   ```bash
   python backend/main.py
   ```

6. **Abrir navegador**
   ```bash
   open http://localhost:8000
   ```

**Instalar como servicio LaunchAgent:**

1. **Crear archivo:**
   ```bash
   nano ~/.config/launchd/local.aura-os.plist
   ```

2. **Pegar:**
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
     <key>Label</key>
     <string>local.aura-os</string>
     <key>ProgramArguments</key>
     <array>
       <string>/Users/tu_usuario/AURA/venv/bin/python</string>
       <string>/Users/tu_usuario/AURA/backend/main.py</string>
     </array>
     <key>RunAtLoad</key>
     <true/>
     <key>StandardOutPath</key>
     <string>/tmp/aura.log</string>
     <key>StandardErrorPath</key>
     <string>/tmp/aura-error.log</string>
   </dict>
   </plist>
   ```

3. **Cargar:**
   ```bash
   launchctl load ~/.config/launchd/local.aura-os.plist
   ```

4. **Ver logs:**
   ```bash
   tail -f /tmp/aura.log
   ```

---

## Docker

**Requisitos:**
- Docker Desktop instalado (desde [docker.com](https://www.docker.com/products/docker-desktop))
- 1 GB RAM mínimo

**Pasos:**

1. **Clonar y navegar**
   ```bash
   git clone https://github.com/tu-usuario/AURA.git
   cd AURA
   ```

2. **Construir imagen**
   ```bash
   docker build -t aura-os:latest .
   ```
   
   Esto tardará 5-10 minutos.

3. **Ejecutar contenedor**
   ```bash
   docker run -d \
     -p 8000:8000 \
     -v ~/.aura:/root/.aura \
     --name aura \
     aura-os:latest
   ```

4. **Abrir navegador**
   ```
   http://localhost:8000
   ```

5. **Ver logs**
   ```bash
   docker logs -f aura
   ```

6. **Parar**
   ```bash
   docker stop aura
   ```

7. **Reiniciar**
   ```bash
   docker start aura
   ```

**Docker Compose (más fácil):**

1. **Crear `docker-compose.yml`:**
   ```yaml
   version: '3.8'
   
   services:
     aura:
       build: .
       ports:
         - "8000:8000"
       volumes:
         - ~/.aura:/root/.aura
       environment:
         - AURA_ENV=production
       restart: always
   ```

2. **Ejecutar:**
   ```bash
   docker-compose up -d
   ```

3. **Ver estado:**
   ```bash
   docker-compose ps
   ```

---

## Cloud

### PythonAnywhere

**Requisitos:**
- Cuenta en [pythonanywhere.com](https://www.pythonanywhere.com/)
- Plan Beginner+ ($5/mes)

**Pasos:**

1. **Crear cuenta**
   - Ir a pythonanywhere.com
   - Sign up → Beginner plan

2. **Abrir Web console**
   - Dashboard → Consoles → New console → Bash

3. **Clonar y configurar**
   ```bash
   git clone https://github.com/tu-usuario/AURA.git
   cd AURA
   mkvirtualenv --python=/usr/bin/python3.10 aura
   pip install -r requirements.txt
   ```

4. **Configurar WSGI app**
   - Web → Add new web app
   - Framework: WSGI
   - Python: 3.10
   - Editar `/var/www/...._wsgi.py`:
   
   ```python
   import sys
   sys.path.insert(0, '/home/tu_usuario/AURA')
   
   from backend.main import app
   
   application = app
   ```

5. **Reload web app**
   - Web → Reload

6. **Acceder**
   ```
   https://tu_usuario.pythonanywhere.com
   ```

### Railway

**Requisitos:**
- Cuenta en [railway.app](https://railway.app/)
- GitHub conectado

**Pasos:**

1. **Conectar GitHub**
   - railway.app → Login con GitHub

2. **Nuevo proyecto**
   - New → Deploy from GitHub
   - Seleccionar repositorio AURA

3. **Configurar variables**
   - Project → Settings → Variables
   - `PYTHON_VERSION=3.10`
   - `ENVIRONMENT=production`

4. **Deploy**
   - Click Deploy
   - Esperar 5-10 minutos

5. **Acceder**
   ```
   https://tu-app.railway.app
   ```

### Render

**Requisitos:**
- Cuenta en [render.com](https://render.com/)
- GitHub conectado

**Pasos:**

1. **Crear Procfile**
   En raíz del repo, crear archivo `Procfile`:
   ```
   web: python backend/main.py --host 0.0.0.0 --port $PORT
   ```

2. **Conectar Render**
   - render.com → New Web Service
   - Conectar con GitHub
   - Seleccionar repositorio

3. **Configurar**
   - Name: `aura-os`
   - Environment: `Python 3`
   - Build command: `pip install -r requirements.txt`
   - Start command: `python backend/main.py --host 0.0.0.0 --port $PORT`

4. **Deploy**
   - Click Deploy
   - Esperar 5-10 minutos

5. **Acceder**
   ```
   https://aura-os.onrender.com
   ```

---

## Troubleshooting

### "Python no encontrado"

**Windows:**
```powershell
# Descargar desde python.org
# O:
choco install python  # Si tienes Chocolatey
```

**Linux:**
```bash
sudo apt install python3.10 python3.10-venv
```

**macOS:**
```bash
brew install python@3.10
```

### "Puerto 8000 en uso"

```bash
# Encontrar qué lo usa:
Windows:  netstat -ano | findstr :8000
Linux:    lsof -i :8000
macOS:    lsof -i :8000

# Cambiar puerto en AURA:
# Editar backend/main.py
# if __name__ == "__main__":
#     uvicorn.run(..., port=8001)  # Cambiar a 8001
```

### "Permiso denegado (Linux/macOS)"

```bash
chmod +x backend/main.py
chmod +x venv/bin/python
```

### "pip no instala dependencias"

```bash
# Actualizar pip
pip install --upgrade pip

# Limpiar caché
pip cache purge

# Reintentar
pip install -r requirements.txt
```

### "Backend se congela"

```bash
# Presionar Ctrl+C para detener

# Aumentar timeout
export UVICORN_TIMEOUT=120

# Reiniciar
python backend/main.py
```

### "No puedo abrir http://localhost:8000"

1. Verifica que backend esté corriendo
   ```bash
   Verás: "Uvicorn running on..."
   ```

2. Intenta con IP local
   ```
   http://127.0.0.1:8000
   ```

3. Verifica firewall
   ```
   Windows: Settings → Firewall → Allow app
   ```

---

## Requisitos de Sistema

| Componente | Mínimo | Recomendado |
|-----------|--------|------------|
| **RAM** | 1 GB | 4 GB |
| **CPU** | Dual-core | Quad-core |
| **Almacenamiento** | 500 MB | 2 GB |
| **Python** | 3.10 | 3.11+ |
| **OS** | Windows 10, Ubuntu 20.04 | Windows 11, Ubuntu 22.04 |

---

## Verificar Instalación

Después de instalar, verifica que todo funciona:

```bash
# 1. Backend corriendo
curl http://localhost:8000/health

# Response esperado:
{
  "status": "ok",
  "backend": "running",
  "skills": 16
}

# 2. Abrir en navegador
http://localhost:8000

# 3. Ver Swagger UI
http://localhost:8000/docs

# 4. Ver API docs
http://localhost:8000/redoc
```

---

## Próximos Pasos

Después de instalar:

1. **Lee User Guide** — docs/USER_GUIDE.md
2. **Crea reglas de automation** — docs/AUTOMATION.md
3. **Desarrolla plugins** — docs/PLUGINS.md
4. **Contribuye** — docs/DEVELOPMENT.md

---

## Soporte

- **Issues** — [GitHub Issues](https://github.com/tu-usuario/AURA/issues)
- **Discussions** — [GitHub Discussions](https://github.com/tu-usuario/AURA/discussions)
- **Email** — support@aura-os.dev

---

*Última actualización: 31 Agosto 2024*
