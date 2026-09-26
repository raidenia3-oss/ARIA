$ErrorActionPreference = "Stop"
pip install -r backend/requirements.txt -q

$process = Start-Process -FilePath "python" -ArgumentList "-m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload" -PassThru -NoNewWindow
Start-Sleep -Seconds 3

$endpoints = @(
    "http://localhost:8000/api/status",
    "http://localhost:8000/api/news/recommend",
    "http://localhost:8000/docs"
)

foreach ($ep in $endpoints) {
    try {
        $r = Invoke-WebRequest -Uri $ep -TimeoutSec 5
        Write-Host "✅ $ep (Status: $($r.StatusCode))"
    } catch {
        Write-Host "❌ $ep - Error"
    }
}

$process | Stop-Process -Force
Write-Host "🎉 Backend listo para producción"