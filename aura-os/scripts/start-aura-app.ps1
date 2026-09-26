param(
    [switch]$Install,
    [switch]$Start,
    [switch]$Stop,
    [switch]$Status,
    [switch]$Exe
)

$ErrorActionPreference = 'Stop'
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$AURA_ROOT = Split-Path -Parent (Split-Path -Parent $SCRIPT_DIR)
$APP_DIR = Join-Path $AURA_ROOT "AURA_APP"
$RUNNER = Join-Path $APP_DIR "run_app.py"
$VENV = Join-Path $AURA_ROOT ".venv"
$PID_FILE = Join-Path $APP_DIR "logs\backend.pid"

function Write-Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$ts] $msg"
}

function Test-Venv {
    if (-not (Test-Path (Join-Path $VENV "Scripts\python.exe"))) {
        Write-Log "Creando entorno virtual..."
        python -m venv $VENV
        Write-Log "Venv creado en $VENV"
    }
    return Join-Path $VENV "Scripts\python.exe"
}

function Install-App {
    $python = Test-Venv
    $req = Join-Path $APP_DIR "requirements.txt"
    Write-Log "Instalando dependencias..."
    $oldPref = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & $python -m pip install -r $req --quiet 2>&1
    & $python -m pip install "faster-whisper" "vosk" "openwakeword" "sounddevice" "pyttsx3" "pywebview" "pyautogui" "psutil" "pillow" --quiet 2>&1
    $ErrorActionPreference = $oldPref
    Write-Log "Dependencias instaladas."
}

function Start-AppExe {
    $exe = Join-Path $AURA_ROOT "dist\AURA OS.exe"
    if (-not (Test-Path $exe)) {
        Write-Log "ERROR: No se encuentra $exe. Ejecuta build-aura-app.bat primero."
        exit 1
    }
    Stop-Process -Name "python" -Force -ErrorAction SilentlyContinue
    Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 1
    Write-Log "Lanzando AURA OS .exe..."
    Start-Process -FilePath $exe -NoNewWindow
    Start-Sleep -Seconds 8
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 5
        Write-Log "Backend online: $($r.Content)"
    } catch {
        Write-Log "Backend iniciando... verifica manualmente."
    }
}

function Start-App {
    $python = Test-Venv
    if (Test-Path $PID_FILE) {
        $oldPid = Get-Content $PID_FILE -ErrorAction SilentlyContinue
        if ($oldPid -and (Get-Process -Id $oldPid -ErrorAction SilentlyContinue)) {
            Write-Log "AURA App corriendo (PID $oldPid). Usa -Stop."
            exit 0
        }
    }
    $logDir = Join-Path $APP_DIR "logs"
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
    Write-Log "Iniciando AURA App..."
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $python
    $psi.Arguments = "`"$RUNNER`""
    $psi.WorkingDirectory = $AURA_ROOT
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $proc = [System.Diagnostics.Process]::Start($psi)
    $proc.Id | Out-File -FilePath $PID_FILE -Encoding ascii
    Write-Log "Backend iniciado (PID $($proc.Id))."
    Start-Sleep -Seconds 3
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 5
        Write-Log "Backend online: $($r.Content)"
    } catch {
        Write-Log "Backend iniciando... verifica manualmente."
    }
    Write-Log "API: http://localhost:8000/docs"
    Write-Log "OpenAI compat: POST http://localhost:8000/chat/completions"
}

function Stop-App {
    if (Test-Path $PID_FILE) {
        $pid_val = Get-Content $PID_FILE -ErrorAction SilentlyContinue
        if ($pid_val -and (Get-Process -Id $pid_val -ErrorAction SilentlyContinue)) {
            Write-Log "Deteniendo AURA App (PID $pid_val)..."
            Stop-Process -Id $pid_val -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 1
            Remove-Item $PID_FILE -Force -ErrorAction SilentlyContinue
            Write-Log "Detenido."
            return
        }
        Remove-Item $PID_FILE -Force -ErrorAction SilentlyContinue
    }
    Write-Log "No PID file. Deteniendo todos los procesos de AURA App..."
    Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*$APP_DIR*" } | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Log "Procesos detenidos."
}

function Show-Status {
    Write-Log "=== AURA App Status ==="
    if (Test-Path $PID_FILE) {
        $pid_val = Get-Content $PID_FILE
        $proc = Get-Process -Id $pid_val -ErrorAction SilentlyContinue
        if ($proc) { Write-Log "Backend: RUNNING (PID $pid_val)" } else { Write-Log "Backend: NOT RUNNING (PID file stale)" }
    } else {
        Write-Log "Backend: NOT RUNNING (no PID file)"
    }
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 3
        Write-Log "Health: $($r.Content)"
    } catch {
        Write-Log "Health: UNREACHABLE"
    }
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:8000/api/agent/status" -UseBasicParsing -TimeoutSec 3
        Write-Log "Agent: $($r.Content)"
    } catch {
        Write-Log "Agent: UNREACHABLE"
    }
}

if ($Install) { Install-App; Start-App }
elseif ($Stop) { Stop-App }
elseif ($Status) { Show-Status }
elseif ($Exe) { Start-AppExe }
else { Start-App }
