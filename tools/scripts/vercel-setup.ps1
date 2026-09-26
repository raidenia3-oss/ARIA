# Vercel Setup Automation - Ejecutar SOLO UNA VEZ

Write-Host "🔐 Vercel Full Access Setup" -ForegroundColor Cyan

# 1. Pedir Vercel Token
$token = Read-Host "Pega tu Vercel API Token"

# 2. Guardar (NO en repo)
$token | Out-File -FilePath "vercel-token.txt" -Encoding UTF8 -Force
Write-Host "✅ Token guardado en vercel-token.txt (agregado a .gitignore)" -ForegroundColor Green

# 3. Agregar a .gitignore
if ((Get-Content ".gitignore" -ErrorAction SilentlyContinue) -notmatch "vercel-token.txt") {
    Add-Content ".gitignore" "`nvercel-token.txt"
}

# 4. Instalar dependencias
Write-Host "📦 Instalando dependencias..." -ForegroundColor Yellow
npm install node-fetch

# 5. Configurar variables en Vercel
Write-Host "⚙️ Configurando variables de entorno..." -ForegroundColor Yellow

$env:VERCEL_TOKEN = $token
$env:DATABASE_URL = Read-Host "DATABASE_URL (postgresql://...)"
$env:FASTAPI_URL = Read-Host "FASTAPI_URL (https://...)"
$env:CRON_SECRET = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | % {[char]$_})

# 6. Ejecutar script
node scripts/vercel-deploy.js set-env
node scripts/vercel-deploy.js redeploy

Write-Host "✅ Vercel configurado completamente" -ForegroundColor Green
Write-Host "🎯 Comandos disponibles para Cline:" -ForegroundColor Cyan
Write-Host "   node scripts/vercel-deploy.js redeploy   (Deploy automático)" -ForegroundColor White
Write-Host "   node scripts/vercel-deploy.js logs       (Ver logs)" -ForegroundColor White
Write-Host "   node scripts/vercel-deploy.js status     (Estado)" -ForegroundColor White