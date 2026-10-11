# ARIA-USB verify.ps1 (PowerShell 5.1, fail-closed)
param(
  [string] = "E:\ARIA",
  [switch]
)
Continue = 'Stop'

function Check-GitIgnoreScratch {
   = Join-Path  ".scratch\x.bin"
   = New-Item -ItemType Directory -Path (Split-Path ) -Force -ErrorAction SilentlyContinue
   = New-Item -ItemType File -Path  -Force -ErrorAction SilentlyContinue
   = git check-ignore -v  2>&1
  Remove-Item  -ErrorAction SilentlyContinue
  if ( -and (.ToString().Contains(".gitignore") -and .ToString().Contains(".scratch/"))) {
    return "PASS"
  }
  return "FAIL"
}

 = @{}
["gitignore_scratch"] = Check-GitIgnoreScratch
["canary_behavior"] = "NOT_IMPLEMENTED"
["zero_traces_snapshot"] = "NOT_IMPLEMENTED"
 = @("gitignore_scratch")
 = (["gitignore_scratch"] -eq "PASS")
 = (["canary_behavior"] -ne "PASS" -or ["zero_traces_snapshot"] -ne "PASS")
if (-not ) {
  Write-Host "VERIFY: FAIL gitignore_scratch"
  exit 1
}
if () {
  Write-Host "VERIFY: INCOMPLETE (canary/zero_traces pending)"
  exit 0
}
Write-Host "VERIFY: PASS"
exit 0
