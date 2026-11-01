# backup_aria.ps1  -  respaldo automatico de ARIA a GitHub (SIN servidores/puertos).
# Lo ejecuta la Tarea Programada a diario. Seguro: solo archivos ya rastreados + ARIA_APP,
# jamas 'git add -A', con bloqueo de secretos.
$ErrorActionPreference = 'Continue'
$repo = "C:\Users\User\Downloads\AURA"
Set-Location $repo
$log = Join-Path $repo "logs\backup_aria.log"
try { New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null } catch {}
function Log($m) { $l = "{0}  {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m; Add-Content $log $l; Write-Host $l }

$top = (& git.exe rev-parse --show-toplevel 2>$null)
if (-not $top) { Log "ERROR: no es repo git"; exit 1 }

# 1) asegurar ignorados sensibles
$ign = ".gitignore"
$cont = if (Test-Path $ign) { Get-Content $ign -Raw } else { "" }
$add = @()
foreach ($f in @("credentials/","secure_vault/","cookies_copy/","ARIA_APP/data/")) { if ($cont -notmatch [regex]::Escape($f)) { $add += $f } }
if ($add.Count -gt 0) { Add-Content $ign ("`n" + ($add -join "`n") + "`n"); Log ("ignore+ " + ($add -join ",")) }

# 2) bloqueo de secretos ya rastreados
$peligro = (& git.exe ls-files) | Where-Object {
    $_ -match '(^|/)\.env($|\.)' -or $_ -match '(^|/)credentials/' -or $_ -match '(^|/)secure_vault/' -or
    $_ -match '(^|/)cookies_copy/' -or $_ -match '\.key$' -or $_ -match '\.pem$' -or $_ -match '\.secret$' -or $_ -match 'token'
}
if ($peligro) { foreach ($p in $peligro) { & git.exe rm --cached --ignore-unmatch -- "$p" | Out-Null }; Log ("SECRETO expulsado: " + ($peligro -join ",")) }

# 3) agregar SOLO lo seguro: cambios de archivos ya rastreados + nuevos bajo ARIA_APP
& git.exe add -u 2>$null
& git.exe add -- ARIA_APP .gitignore 2>$null

# 4) commit si hay algo
& git.exe diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    $rama = (& git.exe rev-parse --abbrev-ref HEAD)
    $msg = "backup automatico {0}`n`nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>" -f (Get-Date -Format 'yyyy-MM-dd HH:mm')
    & git.exe commit -m $msg | Out-Null
    & git.exe push origin $rama 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { Log "OK push rama=$rama" } else { Log "FALLO push (credenciales?) rama=$rama" }
} else {
    Log "sin cambios, nada que respaldar"
}
