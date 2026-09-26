<#
.SYNOPSIS
    Lanza Claude Code desviado a OpenRouter en modo gratuito/ilimitado.
    Lee automáticamente la API key de OpenRouter desde el .env del proyecto.
#>

[CmdletBinding()]
param(
    [string]$Model = "nvidia/nemotron-3-ultra-550b-a55b:free"
)

# ── Detección automática de la API key desde .env ──
$ProjectRoot = (Get-Location).Path
$EnvFile = Join-Path $ProjectRoot ".env"

$openRouterKey = $null
if (Test-Path $EnvFile) {
    $lines = Get-Content $EnvFile -ErrorAction SilentlyContinue
    foreach ($line in $lines) {
        if ($line -match '^OPENROUTER_API_KEY\s*=\s*(.+)$') {
            $openRouterKey = $Matches[1].Trim()
            break
        }
    }
}

if (-not $openRouterKey) {
    Write-Host "❌ No se encontró OPENROUTER_API_KEY en .env. Abortando." -ForegroundColor Red
    Write-Host "   Ruta buscada: $EnvFile" -ForegroundColor DarkGray
    exit 1
}

# ── Limpieza de variables previas de Anthropic ──
Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue
Remove-Item Env:ANTHROPIC_BASE_URL -ErrorAction SilentlyContinue
Remove-Item Env:ANTHROPIC_AUTH_TOKEN -ErrorAction SilentlyContinue

# ── Inyección del entorno falso para Claude Code ──
$env:ANTHROPIC_BASE_URL = "https://openrouter.ai/api"
$env:ANTHROPIC_AUTH_TOKEN = $openRouterKey
$env:OPENROUTER_API_KEY = $openRouterKey
$env:ANTHROPIC_MODEL = $Model

# ── Verificación previa del ejecutable claude ──
$claudeCmd = Get-Command claude -ErrorAction SilentlyContinue
if (-not $claudeCmd) {
    Write-Host "❌ 'claude' no está en PATH. Instálalo primero con: irm https://claude.ai/install.ps1 | iex" -ForegroundColor Red
    exit 1
}

Write-Host "🚀 Lanzando Claude Code desviado a OpenRouter (Modo Ilimitado Gratis)..." -ForegroundColor Cyan
Write-Host "   Modelo activo: $Model" -ForegroundColor Gray
Write-Host "   Proxy: $env:ANTHROPIC_BASE_URL" -ForegroundColor Gray

# ── Ejecutar Claude Code ──
& claude
