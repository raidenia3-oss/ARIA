Write-Host '--- PARTICIONES ---'
Get-Partition | Select-Object DiskNumber, PartitionNumber, DriveLetter, Size, Type | Format-Table -AutoSize
Write-Host '--- VOLUMENES / ESPACIO LIBRE ---'
Get-Volume | Where-Object DriveLetter | Select-Object DriveLetter, FileSystemLabel,
  @{N='SizeGB';E={[math]::Round($_.Size/1GB,1)}},
  @{N='FreeGB';E={[math]::Round($_.SizeRemaining/1GB,1)}} | Format-Table -AutoSize
Write-Host '--- DISCOS FISICOS ---'
Get-Disk | Select-Object Number, FriendlyName,
  @{N='SizeGB';E={[math]::Round($_.Size/1GB,1)}}, PartitionStyle | Format-Table -AutoSize
Write-Host '--- USB DETECTADO ---'
Get-Disk | Where-Object BusType -eq 'USB' | Select-Object Number, FriendlyName,
  @{N='SizeGB';E={[math]::Round($_.Size/1GB,1)}} | Format-Table -AutoSize
