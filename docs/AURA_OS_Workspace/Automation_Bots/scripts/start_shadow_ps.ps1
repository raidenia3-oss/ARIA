$pythonPath = "python"
$scriptPath = "run_shadow.py"
$logFile = "shadow_core_output.log"

Write-Host "🚀 Iniciando Shadow-Core desde run_shadow.py..."
$process = Start-Process -FilePath $pythonPath -ArgumentList $scriptPath -NoNewWindow -RedirectStandardOutput $logFile -RedirectStandardError $logFile -PassThru
Start-Sleep -Seconds 3

# Verificar puerto 5001
$netstatResult = netstat -an | Select-String "127.0.0.1:5001"
if ($netstatResult) {
    Write-Host "✅ Puerto 5001: LISTENING"
    Write-Host "🔒 SISTEMA OPERATIVO. ESCUDO ACTIVO. PUERTO 5001 ESCUCHANDO"
} else {
    Write-Host "❌ Puerto 5001 no está escuchando"
    Write-Host "Log de salida:"
    Get-Content $logFile -Tail 10
}