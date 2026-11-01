# instalar_backup.ps1  -  registra el respaldo diario como Tarea Programada (SIN admin).
# Uso (una sola vez):  powershell -NoProfile -ExecutionPolicy Bypass -File instalar_backup.ps1
$ErrorActionPreference = 'Stop'
$script = "C:\Users\User\Downloads\AURA\backup_aria.ps1"
$nombre = "ARIA Backup GitHub"
if (-not (Test-Path $script)) { Write-Host "No existe $script"; exit 1 }
$tr = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`""
& schtasks.exe /Create /TN $nombre /TR $tr /SC DAILY /ST 21:00 /F
if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "LISTO: respaldo diario a las 21:00 registrado como tarea '$nombre'." -ForegroundColor Green
    Write-Host "Probarlo ya:    schtasks /Run /TN `"$nombre`""
    Write-Host "Ver su estado:  schtasks /Query /TN `"$nombre`" /V /FO LIST"
    Write-Host "Quitarlo:       schtasks /Delete /TN `"$nombre`" /F"
    Write-Host "Registro en:    C:\Users\User\Downloads\AURA\logs\backup_aria.log"
} else {
    Write-Host "No se pudo crear la tarea (codigo $LASTEXITCODE)." -ForegroundColor Red
}
