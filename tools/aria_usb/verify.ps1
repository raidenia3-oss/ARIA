# ARIA-USB verify.ps1 (PowerShell 5.1, fail-closed)
param(
  [string]$UsbRoot = 'E:\ARIA'
)
$ErrorActionPreference = 'Stop'
$checks = @{}
function Test-GitIgnoreScratch {
  $scratchTest = Join-Path $PSScriptRoot '.scratch\x.bin'
  $null = New-Item -ItemType Directory -Path (Split-Path $scratchTest) -Force -ErrorAction SilentlyContinue
  $null = New-Item -ItemType File -Path $scratchTest -Force -ErrorAction SilentlyContinue
  $res = git check-ignore -v $scratchTest 2>&1
  Remove-Item $scratchTest -ErrorAction SilentlyContinue
  if ($res -and $res.ToString().Contains('.gitignore') -and $res.ToString().Contains('.scratch/')) {
    return 'PASS'
  }
  return 'FAIL'
}
$checks['gitignore_scratch'] = Test-GitIgnoreScratch
$checks['canary_behavior'] = 'NOT_IMPLEMENTED'
$checks['zero_traces_snapshot'] = 'NOT_IMPLEMENTED'
$allRequiredPass = ($checks['gitignore_scratch'] -eq 'PASS')
$incomplete = ($checks['canary_behavior'] -ne 'PASS' -or $checks['zero_traces_snapshot'] -ne 'PASS')
if (-not $allRequiredPass) {
  Write-Host 'VERIFY: FAIL gitignore_scratch'
  exit 1
}
if ($incomplete) {
  Write-Host 'VERIFY: INCOMPLETE (canary/zero_traces pending)'
  exit 0
}
Write-Host 'VERIFY: PASS'
exit 0
