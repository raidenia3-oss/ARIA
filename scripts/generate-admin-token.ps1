# Genera JWT token para testing local del admin API
# Uso: .\scripts\generate-admin-token.ps1 [-Role admin] [-UserId raiden-dev]
# Para producción, usar el endpoint POST /api/admin/servers/generate-token

param(
    [string]$Role = "admin",
    [string]$UserId = "raiden-dev"
)

$secret = "dev-secret-admin-aura-localhost"

$pyScript = @"
import jwt
from datetime import datetime, timedelta

secret = "$secret"
now = datetime.utcnow()
payload = {
    "user_id": "$UserId",
    "role": "$Role",
    "iat": int((now - timedelta(seconds=60)).timestamp()),
    "exp": int((now + timedelta(hours=24)).timestamp()),
    "metadata": {}
}
token = jwt.encode(payload, secret, algorithm="HS256")
print(token)
"@

$token = python -c $pyScript
Write-Host "✓ Token generado (role=$Role, user=$UserId):" -ForegroundColor Green
Write-Host $token -ForegroundColor Yellow
Write-Host ""
Write-Host "Uso: Authorization: Bearer $token" -ForegroundColor Cyan
