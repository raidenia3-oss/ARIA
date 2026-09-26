# AURA OS - Backup/Restore para Windows
# Respaldar y restaurar configuración de AURA desde Windows

param(
    [switch]$Backup,
    [switch]$Restore,
    [string]$BackupPath = ""
)

$ErrorActionPreference = 'SilentlyContinue'

Write-Host ''
Write-Host '=============================================================' -ForegroundColor Cyan
Write-Host '  AURA OS - Backup/Restore System' -ForegroundColor Cyan
Write-Host '=============================================================' -ForegroundColor Cyan
Write-Host ''

$AURA_ROOT = "C:\Users\User\Downloads\AURA"
$BACKUP_DIR = "$AURA_ROOT\backups"

# Crear directorio de backups
if (-not (Test-Path $BACKUP_DIR)) {
    New-Item -Path $BACKUP_DIR -ItemType Directory -Force | Out-Null
}

if ($Backup) {
    Write-Host '=== BACKUP MODE ===' -ForegroundColor Yellow
    Write-Host ''
    
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $backupFile = "$BACKUP_DIR\aura-backup-${timestamp}.zip"
    
    Write-Host "Creating backup: $backupFile" -ForegroundColor Cyan
    
    # Archivos a respaldar
    $itemsToBackup = @(
        "$AURA_ROOT\aura-os\scripts",
        "$AURA_ROOT\aura-os\custom-distro",
        "$AURA_ROOT\backend",
        "$AURA_ROOT\agent_bridge.py"
    )
    
    # Crear ZIP
    if (Test-Path $backupFile) { Remove-Item $backupFile -Force }
    
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    
    [System.IO.Compression.ZipFile]::CreateFromDirectory(
        $AURA_ROOT,
        $backupFile,
        [System.IO.Compression.CompressionLevel]::Optimal,
        $false
    )
    
    $backupSize = (Get-Item $backupFile).Length / 1MB
    Write-Host "✓ Backup created: $backupFile" -ForegroundColor Green
    Write-Host "  Size: $([math]::Round($backupSize, 2)) MB" -ForegroundColor Gray
    Write-Host ''
    
} elseif ($Restore) {
    Write-Host '=== RESTORE MODE ===' -ForegroundColor Yellow
    Write-Host ''
    
    if (-not $BackupPath) {
        Write-Host 'Available backups:' -ForegroundColor Cyan
        Get-ChildItem $BACKUP_DIR -Filter "*.zip" | ForEach-Object {
            Write-Host "  $($_.Name) ($([math]::Round($_.Length/1MB, 2)) MB)" -ForegroundColor Gray
        }
        Write-Host ''
        Write-Host -NoNewline 'Enter backup file to restore: '
        $BackupPath = Read-Host
    }
    
    if (-not (Test-Path $BackupPath)) {
        Write-Host "ERROR: Backup not found: $BackupPath" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "Restoring from: $BackupPath" -ForegroundColor Cyan
    Write-Host ''
    
    # Extraer backup
    $tempDir = "$env:TEMP\aura-restore-$$"
    if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
    New-Item -Path $tempDir -ItemType Directory -Force | Out-Null
    
    Expand-Archive -Path $BackupPath -DestinationPath $tempDir -Force
    
    # Restaurar archivos
    Write-Host '[1/3] Restoring scripts...' -ForegroundColor Yellow
    $scriptsDest = "$AURA_ROOT\aura-os\scripts"
    if (Test-Path "$tempDir\aura-os\scripts") {
        Copy-Item "$tempDir\aura-os\scripts\*" -Destination $scriptsDest -Recurse -Force
        Write-Host '✓ Scripts restored' -ForegroundColor Green
    }
    
    Write-Host '[2/3] Restoring custom-distro...' -ForegroundColor Yellow
    $distroDest = "$AURA_ROOT\aura-os\custom-distro"
    if (Test-Path "$tempDir\aura-os\custom-distro") {
        Copy-Item "$tempDir\aura-os\custom-distro\*" -Destination $distroDest -Recurse -Force
        Write-Host '✓ Custom distro restored' -ForegroundColor Green
    }
    
    Write-Host '[3/3] Restoring backend...' -ForegroundColor Yellow
    $backendDest = "$AURA_ROOT\backend"
    if (Test-Path "$tempDir\backend") {
        Copy-Item "$tempDir\backend\*" -Destination $backendDest -Recurse -Force
        Write-Host '✓ Backend restored' -ForegroundColor Green
    }
    
    # Limpiar
    Remove-Item $tempDir -Recurse -Force
    
    Write-Host ''
    Write-Host '╔════════════════════════════════════════════╗' -ForegroundColor Green
    Write-Host '║     Restore Complete                      ║' -ForegroundColor Green
    Write-Host '╚════════════════════════════════════════════╝' -ForegroundColor Green
    Write-Host ''
    
} else {
    Write-Host 'Usage:' -ForegroundColor Yellow
    Write-Host '  .\backup-restore.ps1 -Backup' -ForegroundColor White
    Write-Host '  .\backup-restore.ps1 -Restore' -ForegroundColor White
    Write-Host ''
}
