# Script para corregir errores de notificaciones en VS Code
# Ejecutar como Administrador

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  FIX ERRORES VS CODE - AURA" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# 1. Desactivar extensiones problemáticas
Write-Host "[1/5] Desactivando extensiones problemáticas..." -ForegroundColor Yellow

$extensionsToDisable = @(
    "codeium.codeium",                    # Error de permisos EPERM
    "ms-vsliveshare.vsliveshare",         # API proposal no existe
    "ms-vscode.js-debug-nightly",         # Registro duplicado de vistas
    "anthropic.claude-code"               # chatParticipant no declarado
)

foreach ($ext in $extensionsToDisable) {
    Write-Host "      Desactivando: $ext" -ForegroundColor Gray
    code --disable-extension $ext 2>$null
}

Write-Host "      [OK] Extensiones desactivadas" -ForegroundColor Green
Write-Host ""

# 2. Corregir configuración de Continue (quitar LM Studio que no está disponible)
Write-Host "[2/5] Corrigiendo configuración de Continue..." -ForegroundColor Yellow

$continueConfig = "$env:USERPROFILE\.continue\config.yaml"
if (Test-Path $continueConfig) {
    $lines = Get-Content $continueConfig
    $newLines = @()
    $skipBlock = $false
    
    foreach ($line in $lines) {
        if ($line -match '^\s*- name: Autodetect') {
            $skipBlock = $true
            continue
        }
        if ($skipBlock) {
            # Si encontramos una nueva entrada de modelo o el final, dejamos de saltar
            if ($line -match '^\s*- name:') {
                $skipBlock = $false
                $newLines += $line
            }
            continue
        }
        $newLines += $line
    }
    
    $newLines | Set-Content $continueConfig -Encoding UTF8
    Write-Host "      [OK] Configuración de Continue corregida" -ForegroundColor Green
} else {
    Write-Host "      [WARN] No se encontró config.yaml de Continue" -ForegroundColor Yellow
}
Write-Host ""

# 3. Instalar extensión YAML (necesaria para Continue)
Write-Host "[3/5] Instalando extensión YAML..." -ForegroundColor Yellow
code --install-extension redhat.vscode-yaml --force 2>$null
Write-Host "      [OK] Extensión YAML instalada" -ForegroundColor Green
Write-Host ""

# 4. Actualizar configuración de VS Code para limitar editores abiertos
Write-Host "[4/5] Actualizando configuración de VS Code..." -ForegroundColor Yellow

$settingsPath = "$env:APPDATA\Code\User\settings.json"
if (Test-Path $settingsPath) {
    $settings = Get-Content $settingsPath -Raw | ConvertFrom-Json
    
    # Limitar el número de editores abiertos para evitar listener leaks
    $settings | Add-Member -NotePropertyName "workbench.editor.limit.enabled" -NotePropertyValue $true -Force
    $settings | Add-Member -NotePropertyName "workbench.editor.limit.value" -NotePropertyValue 20 -Force
    $settings | Add-Member -NotePropertyName "workbench.editor.limit.perEditorGroup" -NotePropertyValue $true -Force
    
    # Desactivar telemetría para reducir ruido
    $settings | Add-Member -NotePropertyName "telemetry.telemetryLevel" -NotePropertyValue "off" -Force
    
    # Desactivar actualizaciones automáticas de extensiones problemáticas
    $settings | Add-Member -NotePropertyName "extensions.autoUpdate" -NotePropertyValue $false -Force
    
    $settings | ConvertTo-Json -Depth 10 | Set-Content $settingsPath -Encoding UTF8
    Write-Host "      [OK] Configuración de VS Code actualizada" -ForegroundColor Green
} else {
    Write-Host "      [WARN] No se encontró settings.json" -ForegroundColor Yellow
}
Write-Host ""

# 5. Limpiar caché de VS Code
Write-Host "[5/5] Limpiando caché de VS Code..." -ForegroundColor Yellow

$cachePaths = @(
    "$env:APPDATA\Code\Cache",
    "$env:APPDATA\Code\CachedData",
    "$env:APPDATA\Code\CachedExtensionVSIXs"
)

foreach ($cachePath in $cachePaths) {
    if (Test-Path $cachePath) {
        Remove-Item $cachePath -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "      [OK] Limpiado: $cachePath" -ForegroundColor Gray
    }
}

Write-Host "      [OK] Caché limpiada" -ForegroundColor Green
Write-Host ""

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  LISTO - Reinicia VS Code" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Cambios aplicados:" -ForegroundColor White
Write-Host "  1. Desactivadas extensiones problemáticas (Codeium, LiveShare, js-debug-nightly, Claude Code)" -ForegroundColor Gray
Write-Host "  2. Corregida configuración de Continue (eliminados modelos LM Studio no disponibles)" -ForegroundColor Gray
Write-Host "  3. Instalada extensión YAML para Continue" -ForegroundColor Gray
Write-Host "  4. Limitado número de editores abiertos (evita listener leaks)" -ForegroundColor Gray
Write-Host "  5. Limpiada caché de VS Code" -ForegroundColor Gray
Write-Host ""
Write-Host "Después de reiniciar VS Code:" -ForegroundColor White
Write-Host "  - Cierra los archivos que no necesites (Ctrl+W)" -ForegroundColor Gray
Write-Host "  - Si usas Claude Code, actualízalo desde el marketplace" -ForegroundColor Gray
Write-Host "  - Si usas Codeium, reinstálalo" -ForegroundColor Gray
Write-Host ""
Read-Host "Presiona Enter para salir"