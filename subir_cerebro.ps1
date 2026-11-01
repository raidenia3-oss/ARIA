# subir_cerebro.ps1  -  Windows PowerShell  -  sube el cerebro+autoaprendizaje de ARIA a GitHub
# SEGURO: no hace 'git add -A'. Solo sube 3 archivos + .gitignore, y bloquea secretos.
# Uso:  powershell -NoProfile -ExecutionPolicy Bypass -File subir_cerebro.ps1
$ErrorActionPreference = 'Stop'

# --- 0) ubicarse en la raiz del repo ---
$top = (& git.exe rev-parse --show-toplevel 2>$null)
if (-not $top) { Write-Host "ERROR: esta carpeta no es un repo git."; exit 1 }
Set-Location $top
Write-Host "Repo: $top"
Write-Host "Remoto: $(& git.exe remote get-url origin)"
Write-Host ""

# --- 1) asegurar ignorados que faltan ---
$ign = ".gitignore"
$faltan = @("credentials/","secure_vault/","cookies_copy/","ARIA_APP/data/")
$cont = if (Test-Path $ign) { Get-Content $ign -Raw } else { "" }
$add = @()
foreach ($f in $faltan) { if ($cont -notmatch [regex]::Escape($f)) { $add += $f } }
if ($add.Count -gt 0) {
    Add-Content $ign ("`n# Secretos/datos locales (anadido automaticamente)`n" + ($add -join "`n") + "`n")
    Write-Host ("Anadidos a .gitignore: " + ($add -join ", "))
}

# --- 2) BLOQUEO DE SECRETOS: ¿hay algo sensible ya rastreado? ---
$tracked = & git.exe ls-files
$peligro = $tracked | Where-Object {
    $_ -match '(^|/)\.env($|\.)' -or
    $_ -match '(^|/)credentials/' -or
    $_ -match '(^|/)secure_vault/' -or
    $_ -match '(^|/)cookies_copy/' -or
    $_ -match '\.key$' -or $_ -match '\.pem$' -or $_ -match '\.secret$' -or
    $_ -match 'token'
}
if ($peligro) {
    Write-Host ""
    Write-Host "*** ATENCION: estos archivos SENSIBLES estaban rastreados por git ***" -ForegroundColor Red
    $peligro | ForEach-Object { Write-Host ("   " + $_) -ForegroundColor Red }
    Write-Host "Los saco del indice (git rm --cached) para que NO sigan subiendo." -ForegroundColor Yellow
    foreach ($p in $peligro) { & git.exe rm --cached --ignore-unmatch -- "$p" | Out-Null }
    Write-Host "NOTA: si alguno ya estaba en el historial publico, conviene rotar esa clave." -ForegroundColor Yellow
    Write-Host ""
} else {
    Write-Host "Bloqueo de secretos: OK, nada sensible rastreado."
}

# --- 3) rama de trabajo ---
$rama = "feat/cerebro-autoaprendizaje"
& git.exe rev-parse --verify $rama *> $null
if ($LASTEXITCODE -eq 0) { & git.exe checkout $rama } else { & git.exe checkout -b $rama }

# --- 4) agregar SOLO lo nuestro ---
$nuestros = @("ARIA_APP/aria_va_core.py","ARIA_APP/brain_engine.py","ARIA_APP/self_learning.py",".gitignore")
foreach ($f in $nuestros) { if (Test-Path $f) { & git.exe add -- $f } }
# si expulsamos secretos, registrar esa eliminacion tambien
if ($peligro) { & git.exe add -u }

Write-Host ""
Write-Host "--- Lo que se va a commitear ---"
& git.exe status --short

# --- 5) commit (con atribucion) ---
$msg = @"
feat(cerebro): LLM local llama.cpp + autoaprendizaje y fluidez ChatML

- brain_engine: inferencia en proceso con formato ChatML (Qwen), sin servidores
- aria_va_core: personalidad (Raphael/Echidna/Iroha), trato 'Raiden', chat con historial
- self_learning: ensenar/recordar hechos, skills dinamicas aprobadas, captura de huecos (fail-closed)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019jUcPxHZYnyN4AJycPLe2k
"@
& git.exe commit -m $msg
if ($LASTEXITCODE -ne 0) { Write-Host "Nada que commitear (quiza ya estaba)."; }

# --- 6) push ---
Write-Host ""
Write-Host "Subiendo a origin/$rama ... (si pide login, completalo en el navegador)"
& git.exe push -u origin $rama
if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "LISTO. Rama subida: $rama" -ForegroundColor Green
    Write-Host "Abre un Pull Request aqui:"
    Write-Host "  https://github.com/raidenia3-oss/ARIA/pull/new/$rama"
} else {
    Write-Host "El push fallo (revisa el login/credenciales de git)." -ForegroundColor Red
}
