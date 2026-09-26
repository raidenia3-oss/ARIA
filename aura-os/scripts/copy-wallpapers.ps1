# AURA OS - Copiar fotos al USB para slideshow
# Uso: .\copy-wallpapers.ps1 -Source "C:\Users\User\Pictures\Wallpapers"

param(
    [string]$Source = "",
    [string]$USBDest = ""
)

$ErrorActionPreference = 'SilentlyContinue'

Write-Host ''
Write-Host '=============================================================' -ForegroundColor Cyan
Write-Host '  AURA OS - Wallpaper Slideshow Setup' -ForegroundColor Cyan
Write-Host '=============================================================' -ForegroundColor Cyan
Write-Host ''

# Detectar USB
if (-not $USBDest) {
    $usb = Get-Volume | Where-Object { $_.DriveType -eq 'Removable' -and $_.DriveLetter } | Select-Object -First 1
    if ($usb) {
        $USBDest = $usb.DriveLetter + ':\'
        Write-Host "USB detectado: $USBDest ($($usb.FileSystemLabel))" -ForegroundColor Green
    } else {
        Write-Host 'ERROR: No se encontro USB conectado.' -ForegroundColor Red
        pause
        exit 1
    }
}

# Crear carpeta de wallpapers
$wallpaperDir = "$USBDest\wallpapers"
if (-not (Test-Path $wallpaperDir)) {
    New-Item -Path $wallpaperDir -ItemType Directory -Force | Out-Null
    Write-Host "Carpeta creada: $wallpaperDir" -ForegroundColor Green
}

# Si no especifica source, usar Pictures
if (-not $Source) {
    $Source = "$env:USERPROFILE\Pictures"
    Write-Host "Usando carpeta por defecto: $Source" -ForegroundColor Yellow
}

# Verificar que existe
if (-not (Test-Path $Source)) {
    Write-Host "ERROR: Carpeta no encontrada: $Source" -ForegroundColor Red
    pause
    exit 1
}

# Copiar fotos
Write-Host ''
Write-Host "Copiando fotos desde: $Source" -ForegroundColor Cyan
Write-Host "Destino: $wallpaperDir" -ForegroundColor Cyan
Write-Host ''

$copied = 0
$extensions = @('*.jpg', '*.jpeg', '*.png', '*.JPG', '*.JPEG', '*.PNG')

foreach ($ext in $extensions) {
    $files = Get-ChildItem -Path $Source -Filter $ext -File -ErrorAction SilentlyContinue
    foreach ($file in $files) {
        $dest = Join-Path $wallpaperDir $file.Name
        if (-not (Test-Path $dest)) {
            Copy-Item $file.FullName -Destination $dest -Force
            Write-Host "  Copiado: $($file.Name)" -ForegroundColor Gray
            $copied++
        }
    }
}

Write-Host ''
Write-Host '=============================================================' -ForegroundColor Green
Write-Host "  ✓ $copied fotos copiadas al USB" -ForegroundColor Green
Write-Host '=============================================================' -ForegroundColor Green
Write-Host ''
Write-Host 'Proximos pasos:' -ForegroundColor Yellow
Write-Host '  1. Bootear USB VIVIANA' -ForegroundColor White
Write-Host '  2. Ejecutar installer' -ForegroundColor White
Write-Host '  3. Las fotos se rotan automaticamente cada 30 segundos' -ForegroundColor White
Write-Host ''
Write-Host 'Para cambiar intervalo o efecto, ejecuta en Alpine:' -ForegroundColor Gray
Write-Host '  sh /opt/aura/scripts/setup-wallpaper-slideshow.sh /mnt/usb/wallpapers 20 glow' -ForegroundColor Gray
Write-Host ''
pause
