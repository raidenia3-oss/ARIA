# AURA OS - WSL2 App Installer
# Instala AURA como app de Windows usando WSL2
# NO toca C: ni D: como particiones

param()
$ErrorActionPreference = 'Stop'

Write-Host ''
Write-Host '=============================================================' -ForegroundColor Cyan
Write-Host '  AURA OS - Instalador WSL2 (app de Windows)' -ForegroundColor Cyan
Write-Host '=============================================================' -ForegroundColor Cyan
Write-Host ''

function Write-Step($msg) { Write-Host "[*] $msg" -ForegroundColor Yellow }
function Write-Ok($msg)   { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Err($msg)  { Write-Host "[ERR] $msg" -ForegroundColor Red }

# ============================================
# PASO 1: Habilitar WSL2
# ============================================
Write-Step 'Verificando WSL2...'
$wsl = wsl --status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Step 'WSL2 no instalado. Instalando...'
    dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart | Out-Null
    dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart | Out-Null
    Write-Ok 'Caracteristicas habilitadas. Reinicia Windows y volve a ejecutar este script.'
    pause
    exit 0
}
Write-Ok 'WSL2 detectado.'

# ============================================
# PASO 2: Instalar distro
# ============================================
Write-Step 'Verificando distro Linux...'
$distros = wsl --list --quiet 2>&1
$distroName = 'AURA-OS'

if ($distros -notcontains $distroName) {
    Write-Step "Instalando distro $distroName en WSL2..."
    
    $ubuntuIso = "$env:TEMP\ubuntu.appx"
    if (-not (Test-Path $ubuntuIso)) {
        Invoke-WebRequest -Uri 'https://aka.ms/wslubuntu2204' -OutFile $ubuntuIso
    }
    
    Add-AppxPackage -Path $ubuntuIso | Out-Null
    
    # Importar como AURA-OS
    $installDir = "$env:LOCALAPPDATA\AURA-OS"
    if (-not (Test-Path $installDir)) { New-Item -Path $installDir -ItemType Directory -Force | Out-Null }
    
    wsl --import $distroName $installDir "$env:TEMP\ubuntu.tar" --version 2 | Out-Null
    
    # Configurar usuario
    Write-Step 'Configurando usuario root...'
    wsl -d $distroName -u root bash -lc "useradd -m -s /bin/bash aura && echo 'aura:aura123' | chpasswd && usermod -aG sudo aura"
    
    Write-Ok "Distro $distroName instalada."
} else {
    Write-Ok "Distro $distroName ya existe."
}

# ============================================
# PASO 3: Instalar dependencias en WSL
# ============================================
Write-Step 'Instalando dependencias en WSL...'
wsl -d $distroName -u root bash -lc "apt-get update && apt-get install -y python3 python3-venv python3-pip postgresql redis git curl wget build-essential"
Write-Ok 'Dependencias instaladas.'

# ============================================
# PASO 4: Copiar AURA a WSL
# ============================================
Write-Step 'Copiando AURA a WSL...'
$auraSrc = 'C:\Users\User\Downloads\AURA'
$wslDst = '/opt/aura'

wsl -d $distroName -u root bash -lc "mkdir -p $wslDst && chown -R aura:aura $wslDst"

# Montar disco C: en WSL y copiar
wsl -d $distroName -u root bash -lc "cp -r /mnt/c/Users/User/Downloads/AURA/backend $wslDst/ 2>/dev/null || true"
wsl -d $distroName -u root bash -lc "cp -r /mnt/c/Users/User/Downloads/AURA/scripts $wslDst/ 2>/dev/null || true"
wsl -d $distroName -u root bash -lc "cp -r /mnt/c/Users/User/Downloads/AURA/godot $wslDst/ 2>/dev/null || true"

Write-Ok 'AURA copiado a WSL.'

# ============================================
# PASO 5: Configurar Python venv
# ============================================
Write-Step 'Configurando Python venv...'
wsl -d $distroName -u aura bash -lc "cd /opt/aura/backend && python3 -m venv venv && . venv/bin/activate && pip install --upgrade pip setuptools wheel && pip install -r requirements.txt 2>/dev/null || pip install fastapi uvicorn redis websockets pydantic aiofiles python-dotenv"
Write-Ok 'Python venv listo.'

# ============================================
# PASO 6: Crear .env
# ============================================
Write-Step 'Creando configuracion .env...'
$envContent = @'
AURA_HOST=0.0.0.0
AURA_PORT=8000
AURA_ENV=production
DATABASE_URL=sqlite:///./aura.db
REDIS_URL=redis://localhost:6379/0
LOG_LEVEL=info
AURA_OS=true
DISPLAY_SERVER=wayland
AURA_MOBILE_SYNC=true
AURA_LIVE_BOOT=true
AURA_LANGUAGE=en_US
AURA_TIMEZONE=America/Argentina/Buenos_Aires
'@

$envContent | wsl -d $distroName -u root tee /opt/aura/backend/.env > $null
wsl -d $distroName -u root bash -lc "chown aura:aura /opt/aura/backend/.env"
Write-Ok '.env creado.'

# ============================================
# PASO 7: Crear script de inicio
# ============================================
Write-Step 'Creando script de inicio...'
$startScript = @'
#!/bin/bash
# AURA OS - WSL2 Startup
# Uso: start-aura.sh

echo "Iniciando AURA OS en WSL2..."

# Iniciar Redis
redis-server --daemonize yes 2>/dev/null || true

# Iniciar AURA Backend
cd /opt/aura/backend
. /opt/aura/venv/bin/activate
python -m uvicorn main:app --host 0.0.0.0 --port 8000 &
AURA_PID=$!

echo ""
echo "=================================================="
echo "  AURA OS - Backend Iniciado"
echo "=================================================="
echo ""
echo "Backend: http://localhost:8000"
echo "Health:  curl http://localhost:8000/health"
echo "PID:     $AURA_PID"
echo ""
echo "Para detener: kill $AURA_PID"
echo ""

# Mantener corriendo
wait $AURA_PID
'@

$startScript | wsl -d $distroName -u root tee /usr/local/bin/start-aura.sh > $null
wsl -d $distroName -u root bash -lc "chmod +x /usr/local/bin/start-aura.sh && chown aura:aura /usr/local/bin/start-aura.sh"
Write-Ok 'Script de inicio creado.'

# ============================================
# PASO 8: Crear acceso directo en Windows
# ============================================
Write-Step 'Creando acceso directo...'
$shortcutPath = "$env:USERPROFILE\Desktop\AURA OS.lnk"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = 'wsl.exe'
$shortcut.Arguments = "-d $distroName -u root /usr/local/bin/start-aura.sh"
$shortcut.WorkingDirectory = "$env:USERPROFILE"
$shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,13"
$shortcut.Save()
Write-Ok "Acceso directo creado: $shortcutPath"

# ============================================
# FIN
# ============================================
Write-Host ''
Write-Host '=================================================' -ForegroundColor Green
Write-Host '  AURA OS - WSL2 APP LISTA' -ForegroundColor Green
Write-Host '=================================================' -ForegroundColor Green
Write-Host ''
Write-Host 'Acceso directo: Desktop\AURA OS.lnk' -ForegroundColor Cyan
Write-Host 'Backend: http://localhost:8000' -ForegroundColor Cyan
Write-Host 'Health: curl http://localhost:8000/health' -ForegroundColor Cyan
Write-Host ''
Write-Host 'Para iniciar: doble clic en el acceso directo del escritorio' -ForegroundColor Yellow
Write-Host 'Para detener: cerrar la ventana o Ctrl+C' -ForegroundColor Yellow
Write-Host ''
pause
