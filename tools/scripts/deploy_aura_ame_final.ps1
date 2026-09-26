$ErrorActionPreference = "Stop"
npm install -g @railway/cli @vercel/cli -f

Write-Host "🚀 Configurando Railway..."
railway login
railway connect
$vars = railway variables list | ConvertFrom-Json
$dbUrl = $vars.DATABASE_URL
railway variables set QWEN_ENDPOINT="https://raiden456-slut.hf.space/v1/chat/completions"
railway variables set HF_TOKEN="tu_token_hf"

Write-Host "🚀 Desplegando backend..."
railway deploy --build-command="pip install -r backend/requirements.txt" --start-command="uvicorn backend.main:app --host 0.0.0.0 --port $PORT"

$backendUrl = "https://$(railway variables get RAILWAY_DOMAIN).railway.app"
Write-Host "✅ Backend: $backendUrl"

Write-Host "`n🚀 Configurando Vercel..."
vercel login
Set-Content "frontend/.env.local" @"
NEXT_PUBLIC_API_URL=$backendUrl
NEXT_PUBLIC_WS_URL=wss://$backendUrl/ws
"@
cd frontend
$vercelOutput = vercel deploy --prod --name aura-ame-frontend --scope raidenia3
$vercelUrl = ($vercelOutput -match "https://.*\.vercel\.app").Matches.Value
cd ..

Write-Host "✅ Frontend: $vercelUrl"
Write-Host "`n⚠️ N8N: Importa manualmente n8n/aura_news_workflow.json a https://n8n-onme.onrender.com"