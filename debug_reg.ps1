$keys = @('HKCU:\Environment', 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders')
foreach ($key in $keys) {
  try {
    $vals = Get-ItemProperty $key -ErrorAction SilentlyContinue
    if ($vals) {
      $ariaRelated = $vals.PSObject.Properties | Where-Object { $_.Name -like '*aria*' -or $_.Name -like '*ARIA*' }
      if ($ariaRelated) { Write-Host ('ARIA found in ' + $key + ': ' + $ariaRelated) }
    }
  } catch { Write-Host ('Error: ' + $key) }
}