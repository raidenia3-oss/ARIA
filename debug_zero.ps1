$ariaProcs = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -like '*aria*' -or $_.ProcessName -like '*llama*' }
Write-Host "ariaProcs: $($ariaProcs.Count)"
$ariaProcs | ForEach-Object { Write-Host "  $($_.ProcessName) PID=$($_.Id)" }

$ariaPorts = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.OwningProcess -in $ariaProcs.Id }
Write-Host "ariaPorts: $($ariaPorts.Count)"

$keys = @('HKCU:\Environment', 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders')
$ariaRegChanges = @()
foreach ($key in $keys) {
  try {
    $vals = Get-ItemProperty $key -ErrorAction SilentlyContinue
    if ($vals) {
      $ariaRelated = $vals.PSObject.Properties | Where-Object { $_.Name -like '*aria*' -or $_.Name -like '*ARIA*' }
      if ($ariaRelated) { $ariaRegChanges += $key }
    }
  } catch {}
}
Write-Host "ariaRegChanges: $($ariaRegChanges.Count)"

$paths = @($env:TEMP, $env:TMP, $env:APPDATA, $env:LOCALAPPDATA)
$pathAccessible = @()
foreach ($p in $paths) {
  if (Test-Path $p) {
    $pathAccessible += $p
  }
}
Write-Host "pathAccessible: $($pathAccessible.Count) / $($paths.Count)"