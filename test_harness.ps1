$ErrorActionPreference = "Continue"
$base = "http://127.0.0.1:8000/api/agents/harness"

# Test 1: Register skill
Write-Host "=== Test 1: Register skill ==="
$body1 = '{"name":"code_analyzer","description":"Analyzes code quality","actions":["run","status","reset"]}'
Invoke-RestMethod -Uri "$base/skills/register" -Method POST -ContentType "application/json" -Body $body1 | ConvertTo-Json -Depth 10
Write-Host ""

# Test 2: List skills
Write-Host "=== Test 2: List skills ==="
Invoke-RestMethod -Uri "$base/skills" -Method GET | ConvertTo-Json -Depth 10
Write-Host ""

# Test 3: Set custom prompt
Write-Host "=== Test 3: Set custom prompt ==="
$body3 = '{"prompt":"Eres un agente de mejora automatica"}'
Invoke-RestMethod -Uri "$base/prompts/self-improvement" -Method POST -ContentType "application/json" -Body $body3 | ConvertTo-Json -Depth 10
Write-Host ""

# Test 4: Get agent config
Write-Host "=== Test 4: Get agent config ==="
Invoke-RestMethod -Uri "$base/config/self-improvement" -Method GET | ConvertTo-Json -Depth 10
Write-Host ""

# Test 5: Register MCP
Write-Host "=== Test 5: Register MCP ==="
$body5 = '{"name":"filesystem","url":"mcp://fs"}'
Invoke-RestMethod -Uri "$base/mcp/register" -Method POST -ContentType "application/json" -Body $body5 | ConvertTo-Json -Depth 10
Write-Host ""

# Test 6: List MCP servers
Write-Host "=== Test 6: List MCP servers ==="
Invoke-RestMethod -Uri "$base/mcp/list" -Method GET | ConvertTo-Json -Depth 10
Write-Host ""