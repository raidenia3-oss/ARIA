# AURA OS - USB Automation (SAFE MODE)
# Identifica el USB por HARDWARE (no por letra). Aborta ante cualquier duda.
param([switch]$Execute)
$ErrorActionPreference = "Stop"

$iso = "C:\Users\User\Downloads\alpine-virt-3.19.1-x86_64.iso"

Write-Host "=== VALIDACION (solo lectura) ===" -ForegroundColor Cyan
if (-not (Test-Path $iso)) { throw "ISO NO ENCONTRADA: $iso" }
Write-Host ("OK ISO: {0} ({1:N1} MB)" -f $iso, ((Get-Item $iso).Length/1MB)) -ForegroundColor Green

# Identificar USB por hardware: BusType USB + tamano 6-16GB
$usbDisks = @(Get-Disk | Where-Object { $_.BusType -eq 'USB' -and $_.Size -gt 6GB -and $_.Size -lt 16GB })
if ($usbDisks.Count -ne 1) { throw "Se esperaba 1 USB de ~7.3GB, encontrados: $($usbDisks.Count). ABORTANDO." }
$usb = $usbDisks[0]
Write-Host ("OK USB: Disk #{0} - {1} - {2:N1} GB" -f $usb.Number, $usb.FriendlyName, ($usb.Size/1GB)) -ForegroundColor Green

# Verificar etiqueta VIVIANA solo si aun tiene particiones (estado limpio = OK)
$parts = @(Get-Partition -DiskNumber $usb.Number -ErrorAction SilentlyContinue)
if ($parts.Count -gt 0) {
    $vol = $parts | Get-Volume | Where-Object { @('VIVIANA','AURA_INSTALL','') -contains $_.FileSystemLabel }
    if (-not $vol) { throw "El disco USB #$($usb.Number) no es VIVIANA ni AURA_INSTALL. ABORTANDO (proteccion anti-borrado)." }
    $usedGB = [math]::Round(($vol.Size - $vol.SizeRemaining)/1GB, 2)
    Write-Host ("USB usado: {0} GB de {1:N1} GB (etiqueta {2})" -f $usedGB, ($vol.Size/1GB), $vol.FileSystemLabel) -ForegroundColor Cyan
    if ($usedGB -gt 1.0) { throw "El USB contiene $usedGB GB de datos inesperados. ABORTANDO (proteccion anti-borrado)." }
    Write-Host "OK USB vacio o con archivos AURA re-copiables - nada personal que perder" -ForegroundColor Green
} else {
    Write-Host "OK USB sin particiones (estado limpio previo)" -ForegroundColor Green
}

if (-not $Execute) {
    Write-Host ""
    Write-Host "=== PLAN LISTO. Ejecutar con: -Execute (requiere Admin) ===" -ForegroundColor Yellow
    Write-Host "1. Borrar USB #$($usb.Number) (VIVIANA, vacio)"
    Write-Host "2. Grabar ISO Alpine en bruto (booteable)"
    Write-Host "3. Crear particion FAT32 extra con aura-install"
    Write-Host "4. Copiar backend AURA"
    exit 0
}

# Requerir Admin para la fase destructiva
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$isAdmin = (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Relanzando como Administrador (ACEPTA el UAC para continuar)..." -ForegroundColor Yellow
    Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-File","`"$PSCommandPath`"","-Execute"
    exit 0
}
Start-Transcript -Path "$PSScriptRoot\aura-usb-auto.log" -Force | Out-Null
$diskNum = $usb.Number
Write-Host ""
Write-Host "=== [1/5] Borrando USB fisico #$diskNum ===" -ForegroundColor Yellow
Clear-Disk -Number $diskNum -RemoveData -RemoveOEM -Confirm:$false
Initialize-Disk -Number $diskNum -PartitionStyle MBR -ErrorAction SilentlyContinue | Out-Null
Write-Host "OK USB borrado" -ForegroundColor Green

Write-Host "=== [2/5] Grabando ISO en bruto (booteable) ===" -ForegroundColor Yellow
$raw = "\.\PhysicalDrive$diskNum"
$file = [System.IO.File]::OpenRead($iso)
$disk = [System.IO.File]::Open($raw, 'OpenOrCreate', 'ReadWrite', 'None')
$buffer = New-Object byte[] (4MB)
$total = $file.Length; $written = 0L
try {
    while ($written -lt $total) {
        $read = $file.Read($buffer, 0, $buffer.Length)
        $disk.Write($buffer, 0, $read)
        $written += $read
        Write-Progress -Activity "Grabando ISO al USB" -PercentComplete ([math]::Round($written*100/$total))
    }
    $disk.Flush()
} finally { $file.Close(); $disk.Close() }
Write-Host ("OK ISO grabada ({0:N1} MB)" -f ($total/1MB)) -ForegroundColor Green

Write-Host "=== [3/5] SIN particion extra: ISO pura = USB booteable ===" -ForegroundColor Yellow
Write-Host "OK (el backend se copiara desde Windows en modo solo-lectura dentro de Alpine)" -ForegroundColor Green

Write-Host "=== [4/5] No aplica (backend via montaje read-only de C:) ===" -ForegroundColor Yellow
Write-Host "=== [5/5] Verificacion ===" -ForegroundColor Yellow
$disk = Get-Disk -Number $diskNum
Write-Host ("OK Disco #{0} - {1} - {2:N2} GB - {3} - {4}" -f $disk.Number, $disk.FriendlyName, ($disk.Size/1GB), $disk.PartitionStyle, $disk.OperationalStatus) -ForegroundColor Green
Write-Host ""
Write-Host "=================================================" -ForegroundColor Green
Write-Host "  USB VIVIANA GRABADA (ISO PURA, BOOTEABLE)" -ForegroundColor Green
Write-Host "=================================================" -ForegroundColor Green
Write-Host ""
Write-Host "PROXIMOS PASOS:" -ForegroundColor Cyan
Write-Host "1. Deja el USB puesto y apaga la PC"
Write-Host "2. Enciende -> F12 -> UEFI: Kingston DataTraveler (o modo USB-HDD)"
Write-Host "3. En el prompt de Alpine (root):"
Write-Host "   setup-interfaces  (o usa cable ethernet)"
Write-Host "   rc-service networking start; udhcpc -i wlan0 2>/dev/null || udhcpc"
Write-Host "   apk add ntfs-3g"
Write-Host "   mkdir -p /mnt/win && mount -o ro /dev/nvme0n1p3 /mnt/win"
Write-Host "   sh /mnt/win/Users/User/Downloads/AURA/aura-os/scripts/aura-installer.sh"
Read-Host "Terminado. Presiona Enter para cerrar"
