# AURA OS - Preparador de USB para Alpine
# Este script prepara el USB con Alpine + AURA installer
# NO toca C: ni D:

param(
    [string]$USBDest = "",
    [string]$AURARoot = "C:\Users\User\Downloads\AURA"
)

Write-Host ''
Write-Host '=============================================================' -ForegroundColor Cyan
Write-Host '  AURA OS - Preparador de USB Alpine' -ForegroundColor Cyan
Write-Host '=============================================================' -ForegroundColor Cyan
Write-Host ''

# Detectar USB automaticamente
if (-not $USBDest) {
    $usb = Get-Volume | Where-Object { $_.DriveType -eq 'Removable' -and $_.DriveLetter } | Select-Object -First 1
    if ($usb) {
        $USBDest = $usb.DriveLetter + ':\'
        Write-Host "USB detectado: $USBDest ($($usb.FileSystemLabel))" -ForegroundColor Green
    } else {
        Write-Host 'ERROR: No se encontro USB conectado.' -ForegroundColor Red
        Write-Host 'Conecta un USB de 7.3GB o mayor y vuelve a ejecutar.' -ForegroundColor Yellow
        pause
        exit 1
    }
}

Write-Host "Destino: $USBDest" -ForegroundColor Yellow
Write-Host "AURA Root: $AURARoot" -ForegroundColor Yellow
Write-Host ''

# Verificar espacio en USB
$usbDrive = Get-Volume -DriveLetter $USBDest.TrimEnd('\:')
$freeGB = [math]::Round($usbDrive.SizeRemaining / 1GB, 1)
Write-Host "Espacio libre en USB: ${freeGB}GB" -ForegroundColor Cyan

if ($freeGB -lt 4) {
    Write-Host 'ERROR: Necesitas al menos 4GB libres en el USB.' -ForegroundColor Red
    pause
    exit 1
}

# Crear carpetas
Write-Host ''
Write-Host '[1/4] Creando estructura de carpetas...' -ForegroundColor Yellow
New-Item -Path "$USBDest\aura-install" -ItemType Directory -Force | Out-Null
New-Item -Path "$USBDest\aura-install\backend" -ItemType Directory -Force | Out-Null
New-Item -Path "$USBDest\aura-install\scripts" -ItemType Directory -Force | Out-Null
Write-Host '  OK' -ForegroundColor Green

# Copiar installer script
Write-Host '[2/4] Copiando installer...' -ForegroundColor Yellow
$installerSrc = Join-Path $AURARoot 'aura-os\scripts\aura-installer.sh'
if (Test-Path $installerSrc) {
    Copy-Item $installerSrc -Destination "$USBDest\aura-install\aura-installer.sh" -Force
    Write-Host "  Copiado: aura-installer.sh" -ForegroundColor Green
} else {
    Write-Host "  ERROR: No se encontro $installerSrc" -ForegroundColor Red
    pause
    exit 1
}

# Copiar backend de AURA
Write-Host '[3/4] Copiando backend AURA...' -ForegroundColor Yellow
$backendSrc = Join-Path $AURARoot 'backend'
if (Test-Path $backendSrc) {
    Copy-Item $backendSrc -Destination "$USBDest\aura-install\backend" -Recurse -Force
    $backendFiles = (Get-ChildItem $backendSrc -Recurse -File).Count
    Write-Host "  Copiados ${backendFiles} archivos de backend" -ForegroundColor Green
} else {
    Write-Host "  ADVERTENCIA: No se encontro backend en $backendSrc" -ForegroundColor Yellow
    Write-Host '  El installer intentara descargarlo desde internet.' -ForegroundColor Yellow
}

# Copiar scripts adicionales
Write-Host '[4/4] Copiando scripts adicionales...' -ForegroundColor Yellow
$scriptsSrc = Join-Path $AURARoot 'aura-os\scripts'
if (Test-Path $scriptsSrc) {
    Copy-Item "$scriptsSrc\*.sh" -Destination "$USBDest\aura-install\scripts\" -Force -ErrorAction SilentlyContinue
    $scriptFiles = (Get-ChildItem "$scriptsSrc\*.sh" -ErrorAction SilentlyContinue).Count
    if ($scriptFiles -gt 0) {
        Write-Host "  Copiados ${scriptFiles} scripts" -ForegroundColor Green
    }
}

# Verificacion final
Write-Host ''
Write-Host '=============================================================' -ForegroundColor Cyan
Write-Host '  USB PREPARADO' -ForegroundColor Green
Write-Host '=============================================================' -ForegroundColor Cyan
Write-Host ''
Write-Host "Ubicacion: $USBDest" -ForegroundColor White
Write-Host 'Estructura:' -ForegroundColor White
Get-ChildItem "$USBDest\aura-install" -Recurse | Select-Object FullName -First 20 | ForEach-Object {
    Write-Host "  $($_.FullName.Replace($USBDest, ''))" -ForegroundColor Gray
}
Write-Host ''
Write-Host 'PROXIMOS PASOS:' -ForegroundColor Yellow
Write-Host '  1. Descargar Alpine Linux: https://alpinelinux.org/downloads/' -ForegroundColor White
Write-Host '     Archivo: alpine-virt-3.19.1-x86_64.iso (150MB)' -ForegroundColor Gray
Write-Host '  2. Grabar Alpine en USB con Rufus (MBR + FAT32)' -ForegroundColor White
Write-Host '  3. Bootear desde USB' -ForegroundColor White
Write-Host '  4. En Alpine, ejecutar:' -ForegroundColor White
Write-Host '     mount /dev/sdb1 /mnt/usb' -ForegroundColor Cyan
Write-Host '     sh /mnt/usb/aura-install/aura-installer.sh' -ForegroundColor Cyan
Write-Host ''
Write-Host 'NOTA: El USB sera formateado. Asegurate de que este vacio.' -ForegroundColor Red
Write-Host ''

pause
