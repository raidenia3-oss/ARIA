$procsBefore = Get-Process | Select-Object -ExpandProperty Id | Sort-Object
$portsBefore = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty LocalPort | Sort-Object -Unique

Start-Sleep -Milliseconds 500

$procsAfter = Get-Process | Select-Object -ExpandProperty Id | Sort-Object
$portsAfter = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty LocalPort | Sort-Object -Unique

$procDiff = Compare-Object $procsBefore $procsAfter
$portDiff = Compare-Object $portsBefore $portsAfter

Write-Host "procDiff: $($procDiff.Count)"
Write-Host "portDiff: $($portDiff.Count)"

$paths = @($env:TEMP, $env:TMP, $env:APPDATA, $env:LOCALAPPDATA)
$pathAccessible = @()
foreach ($p in $paths) {
  if (Test-Path $p) {
    $pathAccessible += $p
  }
}
Write-Host "pathAccessible: $($pathAccessible.Count) / $($paths.Count)"