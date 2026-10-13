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

function Test-CanaryBehavior {
  $canaryDir = Join-Path $PSScriptRoot '.scratch\canary_test'
  $canaryFile = Join-Path $canaryDir 'secret.xyz'
  $null = New-Item -ItemType Directory -Path $canaryDir -Force -ErrorAction SilentlyContinue
  'CANARY_SECRET_CONTENT' | Set-Content $canaryFile -Encoding UTF8 -ErrorAction Stop

  $pyPath = "C:\Users\User\Downloads\AURA\.venv\Scripts\python.exe"
  $policyScript = @"
import sys
sys.path.insert(0, r'$PSScriptRoot')
from app.policy import Policy, AccessLevel, PathRisk

policy = Policy()
policy.fs_roots = [r'$PSScriptRoot']
policy.add_rule('work/**', AccessLevel.READ)

from pathlib import Path
canary = Path(r'$canaryFile')
allowed, reason = policy.check_path(str(canary), policy.fs_roots, PathRisk.READ)
print(f'allowed={allowed}')
print(f'reason={reason}')
"@

  $result = & $pyPath -c $policyScript 2>&1
  Remove-Item $canaryDir -Recurse -Force -ErrorAction SilentlyContinue

  if ($result -match 'allowed=False') {
    return 'PASS'
  }
  return 'FAIL'
}

function Test-ZeroTracesSnapshot {
  $keys = @(
    'HKCU:\Environment',
    'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders'
  )
  $paths = @(
    $env:TEMP,
    $env:TMP,
    $env:APPDATA,
    $env:LOCALAPPDATA
  )

  $ariaProcs = Get-Process -ErrorAction SilentlyContinue | Where-Object { 
    $_.Path -and $_.Path -like '*aria-usb*' -or 
    $_.ProcessName -like '*aria*' 
  }
  $ariaPorts = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.OwningProcess -in $ariaProcs.Id }

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

  $pathAccessible = @()
  foreach ($p in $paths) {
    if (Test-Path $p) {
      $pathAccessible += $p
    }
  }

  if ($ariaProcs.Count -eq 0 -and $ariaPorts.Count -eq 0 -and $ariaRegChanges.Count -eq 0 -and $pathAccessible.Count -eq $paths.Count) {
    return 'PASS'
  }
  return 'FAIL'
}

$checks['gitignore_scratch'] = Test-GitIgnoreScratch
$checks['canary_behavior'] = Test-CanaryBehavior
$checks['zero_traces_snapshot'] = Test-ZeroTracesSnapshot

$allRequiredPass = ($checks['gitignore_scratch'] -eq 'PASS' -and $checks['canary_behavior'] -eq 'PASS' -and $checks['zero_traces_snapshot'] -eq 'PASS')
$incomplete = ($checks['canary_behavior'] -ne 'PASS' -or $checks['zero_traces_snapshot'] -ne 'PASS')

if (-not $allRequiredPass) {
  $failed = $checks.GetEnumerator() | Where-Object { $_.Value -ne 'PASS' } | ForEach-Object { $_.Key + '=' + $_.Value }
  Write-Host "VERIFY: FAIL $($failed -join ', ')"
  exit 1
}
if ($incomplete) {
  Write-Host 'VERIFY: INCOMPLETE (canary/zero_traces pending)'
  exit 0
}
Write-Host 'VERIFY: PASS'
exit 0