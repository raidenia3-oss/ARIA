$ErrorActionPreference = "Continue"
$secret = "dev-secret-admin-aura-localhost"

function MakeToken($uid, $role) {
    (python -c "import jwt,sys; from datetime import datetime,timedelta; now=datetime.utcnow(); sys.stdout.write(jwt.encode({'user_id':'$uid','role':'$role','iat':int((now-timedelta(seconds=60)).timestamp()),'exp':int((now+timedelta(hours=24)).timestamp()),'metadata':{}},'$secret',algorithm='HS256'))" 2>$null).Trim()
}

Write-Host "=== Test 1: sin auth (espera 401) ===" -ForegroundColor Cyan
curl.exe -s -o $null -w "HTTP %{http_code}`n" http://localhost:8000/api/admin/servers

$ADMIN = MakeToken "raiden-dev" "admin"
Write-Host "=== Test 2: admin GET (espera 200) ===" -ForegroundColor Cyan
curl.exe -s -w "`nHTTP %{http_code}`n" http://localhost:8000/api/admin/servers -H "Authorization: Bearer $ADMIN"

$VIEWER = MakeToken "viewer1" "viewer"
Write-Host "=== Test 3: viewer register (espera 403) ===" -ForegroundColor Cyan
curl.exe -s -w "`nHTTP %{http_code}`n" -X POST http://localhost:8000/api/admin/servers -H "Authorization: Bearer $VIEWER" -H "Content-Type: application/json" -d '{"action":"register","server_type":"railway","credentials":{}}'

Write-Host "=== Test 4: rate limit (11 GET admin rapidos, nro 11 espera 429) ===" -ForegroundColor Cyan
for ($i = 1; $i -le 11; $i++) {
    $code = curl.exe -s -o $null -w "%{http_code}" http://localhost:8000/api/admin/servers -H "Authorization: Bearer $ADMIN"
    Write-Host "req $i -> $code"
}

Write-Host "=== Test 5: audit-logs admin (espera 200) ===" -ForegroundColor Cyan
curl.exe -s -w "`nHTTP %{http_code}`n" "http://localhost:8000/api/admin/servers/audit-logs?limit=10" -H "Authorization: Bearer $ADMIN"
