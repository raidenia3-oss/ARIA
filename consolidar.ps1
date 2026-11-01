# consolidar.ps1 - sube todo el trabajo de ARIA_APP a la rama activa, con bloqueo de secretos.
# Uso: cd "C:\Users\User\Downloads\AURA"; powershell -NoProfile -ExecutionPolicy Bypass -File .\consolidar.ps1
$ErrorActionPreference = 'Continue'
$top = (& git.exe rev-parse --show-toplevel 2>$null)
if (-not $top) { Write-Host "No es repo git."; exit 1 }
Set-Location $top
$rama = (& git.exe rev-parse --abbrev-ref HEAD)
Write-Host "Repo: $top"
Write-Host "Rama activa: $rama"
Write-Host "Remoto: $(& git.exe remote get-url origin)"

# 1) ignorados de seguridad
$ign = ".gitignore"
$cont = if (Test-Path $ign) { Get-Content $ign -Raw } else { "" }
$add = @()
foreach ($f in @("credentials/","secure_vault/","cookies_copy/","ARIA_APP/data/",".godot/","tunnel_url.txt","tunnel_err.txt")) {
    if ($cont -notmatch [regex]::Escape($f)) { $add += $f }
}
if ($add.Count -gt 0) { Add-Content $ign ("`n# seguridad`n" + ($add -join "`n") + "`n"); Write-Host ("ignore+ " + ($add -join ",")) }

# 2) bloqueo de secretos rastreados
$peligro = (& git.exe ls-files) | Where-Object {
    $_ -match '(^|/)\.env($|\.)' -or $_ -match '(^|/)credentials/' -or $_ -match '(^|/)secure_vault/' -or
    $_ -match '(^|/)cookies_copy/' -or $_ -match '\.key$' -or $_ -match '\.pem$' -or $_ -match '\.secret$' -or $_ -match 'token'
}
if ($peligro) {
    Write-Host "*** Secretos rastreados: sacandolos del indice ***" -ForegroundColor Yellow
    foreach ($p in $peligro) { & git.exe rm --cached --ignore-unmatch -- "$p" | Out-Null; Write-Host "   quitado: $p" }
}

# 3) agregar ARIA_APP + scripts utiles + gitignore (NO -A: nada de basura del monorepo)
& git.exe add -- ARIA_APP .gitignore 2>$null
foreach ($s in @("fix_bom.py","scan_aria.py","limpiar_basura.py","usb_aria.py",
                 "subir_cerebro.ps1","backup_aria.ps1","instalar_backup.ps1","consolidar.ps1")) {
    if (Test-Path $s) { & git.exe add -- $s 2>$null }
}
if ($peligro) { & git.exe add -u 2>$null }

Write-Host ""; Write-Host "--- a commitear ---"; & git.exe status --short | Select-Object -First 40

& git.exe diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    $msg = "chore(aria): consolidar cerebro+memoria semantica+vision+pulso+seguridad (Claude)`n`nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
    & git.exe commit -m $msg | Out-Null
    & git.exe push origin $rama 2>&1 | Select-Object -Last 3
    if ($LASTEXITCODE -eq 0) { Write-Host "OK: subido a origin/$rama" -ForegroundColor Green } else { Write-Host "Push fallo (login?)" -ForegroundColor Red }
} else {
    Write-Host "Nada nuevo que consolidar (Kilo ya lo subio)."
}
