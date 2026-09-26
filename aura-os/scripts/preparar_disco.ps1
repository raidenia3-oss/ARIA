# AURA OS - Preparador de Disco
# Este script te guia para crear el espacio no asignado de 20GB en D:
# y verifica que todo este listo para instalar Arch Linux

param(
    [int]$SizeMB = 20480
)

Write-Host ''
Write-Host '=============================================================' -ForegroundColor Cyan
Write-Host '  AURA OS - Preparador de Disco (Solo lectura/guia)' -ForegroundColor Cyan
Write-Host '=============================================================' -ForegroundColor Cyan
Write-Host ''

Write-Host '--- DISCOS FISICOS ---' -ForegroundColor Yellow
Get-Disk | Select-Object Number, FriendlyName,
  @{N='SizeGB';E={[math]::Round($_.Size/1GB,1)}},
  @{N='UnallocatedGB';E={[math]::Round($_.LargestFreeExtent/1GB,1)}},
  PartitionStyle | Format-Table -AutoSize

Write-Host '--- VOLUMENES / ESPACIO LIBRE ---' -ForegroundColor Yellow
Get-Volume | Where-Object DriveLetter | Select-Object DriveLetter, FileSystemLabel,
  @{N='SizeGB';E={[math]::Round($_.Size/1GB,1)}},
  @{N='FreeGB';E={[math]::Round($_.SizeRemaining/1GB,1)}} | Format-Table -AutoSize

Write-Host '--- PARTICIONES ---' -ForegroundColor Yellow
Get-Partition | Select-Object DiskNumber, PartitionNumber, DriveLetter, Size, Type | Format-Table -AutoSize

$disk = Get-Disk -Number 0
$unallocGB = [math]::Round($disk.LargestFreeExtent/1GB,1)

Write-Host '--- VERIFICACION ---' -ForegroundColor Yellow
if ($unallocGB -ge ($SizeMB/1024)) {
    Write-Host "OK: Hay $unallocGB GB no asignados (se necesitan $($SizeMB/1024) GB)" -ForegroundColor Green
    Write-Host ''
    Write-Host 'Ya podes seguir con:' -ForegroundColor Cyan
    Write-Host '  1. Descargar Rufus + ISO Arch Linux'
    Write-Host '  2. Grabar ISO en USB VIVIANA'
    Write-Host '  3. Bootear desde USB y ejecutar install-aura.sh'
} else {
    Write-Host "FALTA ESPACIO: Hay $unallocGB GB no asignados, se necesitan $($SizeMB/1024) GB" -ForegroundColor Red
    Write-Host ''
    Write-Host 'ACCION REQUERIDA: crear espacio no asignado en D:' -ForegroundColor Yellow
    Write-Host ''
    Write-Host 'Pasos:' -ForegroundColor White
    Write-Host '  1. Presiona Win + R'
    Write-Host '  2. Escribe: diskmgmt.msc'
    Write-Host '  3. Clic derecho sobre la barra de D:'
    Write-Host "  4. Elegir: Reducir volumen..."
    Write-Host "  5. Escribir: $SizeMB MB (20 GB)"
    Write-Host '  6. Clic en Reducir'
    Write-Host ''
    Write-Host 'NO formatees el espacio gris que aparece. NO le asignes letra.' -ForegroundColor Red
    Write-Host ''
    Write-Host 'Despues de crear el espacio no asignado, volve a ejecutar este script para verificar.' -ForegroundColor Cyan
}
