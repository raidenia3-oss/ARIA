Write-Host '=== VERIFICACION DE INTEGRIDAD C: y D: (solo lectura) ==='
Write-Host ''
Write-Host '--- 1. Estructura de particiones del Disco 0 (sistema) ---'
Get-Partition -DiskNumber 0 | Select-Object PartitionNumber, DriveLetter,
  @{N='SizeGB';E={[math]::Round($_.Size/1GB,2)}}, @{N='OffsetGB';E={[math]::Round($_.Offset/1GB,2)}}, Type |
  Format-Table -AutoSize

Write-Host '--- 2. Volumenes y espacio libre ---'
Get-Volume | Where-Object DriveLetter | Select-Object DriveLetter, FileSystemLabel, FileSystem, HealthStatus,
  @{N='SizeGB';E={[math]::Round($_.Size/1GB,1)}},
  @{N='FreeGB';E={[math]::Round($_.SizeRemaining/1GB,1)}} | Format-Table -AutoSize

Write-Host '--- 3. Estado de salud de los discos (SMART) ---'
Get-PhysicalDisk | Select-Object DeviceId, FriendlyName, MediaType, HealthStatus, OperationalStatus |
  Format-Table -AutoSize

Write-Host '--- 4. Windows C: accesible y archivos del sistema presentes ---'
$winCheck = @('C:\Windows\System32\ntoskrnl.exe','C:\Windows\explorer.exe','C:\Users\User\NTUSER.DAT','C:\Boot\BCD')
foreach ($f in $winCheck) {
  if (Test-Path $f) { Write-Host "  OK  $f" -ForegroundColor Green }
  else { Write-Host "  FALTA  $f" -ForegroundColor Red }
}

Write-Host ''
Write-Host '--- 5. Cantidad de archivos del sistema Windows (integridad) ---'
$sysCount = (Get-ChildItem 'C:\Windows\System32' -File -ErrorAction SilentlyContinue).Count
Write-Host "  C:\Windows\System32: $sysCount archivos" -ForegroundColor $(if ($sysCount -gt 2000) {'Green'} else {'Red'})

Write-Host ''
Write-Host '--- 6. D: accesible y datos personales presentes ---'
$users = (Get-ChildItem 'C:\Users' -Directory -ErrorAction SilentlyContinue).Count
Write-Host "  C:\Users: $users carpetas de usuario" -ForegroundColor Green
$dTop = (Get-ChildItem 'D:\' -ErrorAction SilentlyContinue | Measure-Object).Count
Write-Host "  D:\ raiz: $dTop elementos visibles" -ForegroundColor Green
Get-ChildItem 'D:\' -ErrorAction SilentlyContinue | Select-Object -First 10 Name,
  @{N='Tipo';E={if($_.PSIsContainer){'carpeta'}else{'archivo'}}} | Format-Table -AutoSize

Write-Host '--- 7. Estado del USB (lo que SI fue modificado) ---'
Get-Disk -Number 1 | Select-Object Number, FriendlyName, @{N='SizeGB';E={[math]::Round($_.Size/1GB,1)}}, PartitionStyle |
  Format-Table -AutoSize
Get-Partition -DiskNumber 1 -ErrorAction SilentlyContinue | Select-Object PartitionNumber, DriveLetter,
  @{N='SizeGB';E={[math]::Round($_.Size/1GB,2)}}, Type | Format-Table -AutoSize
