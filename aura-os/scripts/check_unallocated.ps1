Get-Disk -Number 0 | Select-Object Number,
  @{N='SizeGB';E={[math]::Round($_.Size/1GB,1)}},
  @{N='AllocatedGB';E={[math]::Round($_.AllocatedSize/1GB,1)}},
  @{N='UnallocatedGB';E={[math]::Round($_.LargestFreeExtent/1GB,1)}} | Format-List
