# AURA OS - Windows Native Installer
# Ejecuta AURA directamente en Windows sin WSL/VM/USB boot
# NO toca C: ni D: como particiones

param()
$ErrorActionPreference = 'Stop'

Write-Host ''
Write-Host '=============================================================' -ForegroundColor Cyan
Write-Host '  AURA OS - Windows Native Mode' -ForegroundColor Cyan
Write-Host '=============================================================' -ForegroundColor Cyan
Write-Host ''

function Write-Step($msg) { Write-Host "[*] $msg" -ForegroundColor Yellow }
function Write-Ok($msg)   { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Err($msg)  { Write-Host "[ERR] $msg" -ForegroundColor Red }

# ============================================
# PASO 1: Verificar Python
# ============================================
Write-Step 'Verificando Python...'
$python = Get-Command python3 -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python -ErrorAction SilentlyContinue
}
if (-not $python) {
    Write-Err 'Python no encontrado.'
    Write-Host 'Descargalo de: https://www.python.org/downloads/windows/' -ForegroundColor Yellow
    Write-Host 'Durante instalacion: marcar "Add Python to PATH"' -ForegroundColor Yellow
    pause
    exit 1
}
Write-Ok "Python detectado: $($python.Source)"

# ============================================
# PASO 2: Verificar backend
# ============================================
Write-Step 'Verificando backend AURA...'
$backendDir = 'C:\Users\User\Downloads\AURA\backend'
if (-not (Test-Path $backendDir)) {
    Write-Err "Backend no encontrado en: $backendDir"
    pause
    exit 1
}
Write-Ok 'Backend encontrado'

# ============================================
# PASO 3: Crear venv
# ============================================
Write-Step 'Creando Python venv...'
$venvDir = 'C:\Users\User\Downloads\AURA\aura-os\venv'
if (-not (Test-Path $venvDir)) {
    python -m venv $venvDir
}
Write-Ok 'venv listo'

# ============================================
# PASO 4: Instalar dependencias
# ============================================
Write-Step 'Instalando dependencias Python...'
$requirements = Join-Path $backendDir 'requirements.txt'
if (Test-Path $requirements) {
    python -m venv $venvDir
    & $venvDir\Scripts\python.exe -m pip install --upgrade pip setuptools wheel 2>&1 | Out-Null
    & $venvDir\Scripts\python.exe -m pip install -r $requirements 2>&1 | Out-Null
} else {
    python -m venv $venvDir
    & $venvDir\Scripts\python.exe -m pip install fastapi uvicorn redis websockets pydantic aiofiles python-dotenv 2>&1 | Out-Null
}
Write-Ok 'Dependencias instaladas'

# ============================================
# PASO 5: Configurar .env
# ============================================
Write-Step 'Configurando .env...'
$envPath = Join-Path $backendDir '.env'
if (-not (Test-Path $envPath)) {
    $envContent = @'
AURA_HOST=0.0.0.0
AURA_PORT=8000
AURA_ENV=production
DATABASE_URL=sqlite:///./aura.db
REDIS_URL=redis://localhost:6379/0
LOG_LEVEL=info
AURA_OS=true
AURA_LIVE_BOOT=true
AURA_LANGUAGE=en_US
AURA_TIMEZONE=America/Argentina/Buenos_Aires
'@
    Set-Content -Path $envPath -Value $envContent -Encoding UTF8
}
Write-Ok '.env configurado'

# ============================================
# PASO 6: Crear script de inicio
# ============================================
Write-Step 'Creando script de inicio...'
$startScript = Join-Path 'C:\Users\User\Downloads\AURA\aura-os\scripts' 'start-aura-windows.ps1'
$startContent = @'
# AURA OS - Windows Native Start
$venv = "C:\Users\User\Downloads\AURA\aura-os\venv\Scripts\Activate.ps1"
$backend = "C:\Users\User\Downloads\AURA\backend"

Write-Host ""
Write-Host "=============================================================" -ForegroundColor Cyan
Write-Host "  AURA OS - Backend Starting" -ForegroundColor Cyan
Write-Host "=============================================================" -ForegroundColor Cyan
Write-Host ""

# Activar venv
Write-Host "[*] Activating venv..." -ForegroundColor Yellow
. $venv

# Iniciar backend
Write-Host "[*] Starting AURA Backend..." -ForegroundColor Yellow
Write-Host "    Backend: http://localhost:8000" -ForegroundColor Cyan
Write-Host "    Health:  curl http://localhost:8000/health" -ForegroundColor Cyan
Write-Host ""
Write-Host "Presiona Ctrl+C para detener." -ForegroundColor Gray
Write-Host ""

Set-Location $backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
'@
Set-Content -Path $startScript -Value $startContent -Encoding UTF8
Write-Ok "Script creado: $startScript"

# ============================================
# PASO 7: Crear acceso directo
# ============================================
Write-Step 'Creando acceso directo...'
$shortcutPath = "$env:USERPROFILE\Desktop\AURA OS (Windows).lnk"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = 'powershell.exe'
$shortcut.Arguments = "-ExecutionPolicy Bypass -File `"$startScript`""
$shortcut.WorkingDirectory = 'C:\Users\User\Downloads\AURA\aura-os\scripts'
$shortcut.IconLocation = '%SystemRoot%\System32\shell32.dll,13'
$shortcut.Save()
Write-Ok "Acceso directo: $shortcutPath"

# ============================================
# FIN
# ============================================
Write-Host ''
Write-Host '=============================================================' -ForegroundColor Green
Write-Host '  AURA OS - WINDOWS NATIVE LISTO' -ForegroundColor Green
Write-Host '=============================================================' -ForegroundColor Green
Write-Host ''
Write-Host 'Para iniciar AURA:' -ForegroundColor Cyan
Write-Host "  Doble clic en: $shortcutPath" -ForegroundColor White
Write-Host ''
Write-Host 'Backend: http://localhost:8000' -ForegroundColor Cyan
Write-Host 'Health:  curl http://localhost:8000/health' -ForegroundColor Cyan
Write-Host ''
Write-Host 'IMPORTANTE:' -ForegroundColor Yellow
Write-Host '  - No toca C: ni D: como particiones' -ForegroundColor White
Write-Host '  - No requiere reiniciar' -ForegroundColor White
Write-Host '  - No modifica Windows' -ForegroundColor White
Write-Host ''
pause
