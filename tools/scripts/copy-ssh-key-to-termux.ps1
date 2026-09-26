<#
.SYNOPSIS
    Copia la clave publica SSH de Windows a Termux.
.DESCRIPTION
    Intenta copiar id_rsa.pub a Termux via SCP. Si falla, muestra la clave
    para copiarla manualmente en Termux.
#>
param(
    [string]$TermuxUser = "u0_a252",
    [string]$TermuxHost = "192.168.18.21",
    [int]$TermuxPort = 8022,
    [string]$KeyPath = "$env:USERPROFILE\.ssh\id_rsa.pub"
)

if (-not (Test-Path $KeyPath)) {
    Write-Host "❌ No se encontro la clave publica en $KeyPath" -ForegroundColor Red
    exit 1
}

$pubKey = Get-Content $KeyPath -Raw
Write-Host "Clave publica a copiar:" -ForegroundColor Cyan
Write-Host $pubKey
Write-Host ""

# Intentar copia automatica
$target = "${TermuxUser}@${TermuxHost}"
$scpArgs = "-P $TermuxPort -i `"$env:USERPROFILE\.ssh\id_rsa`" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new `"$KeyPath`" $target`:~/.ssh/authorized_keys"
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = "scp"
$psi.Arguments = $scpArgs
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true

$p = [System.Diagnostics.Process]::Start($psi)
$p.WaitForExit()

if ($p.ExitCode -eq 0) {
    Write-Host "✅ Clave publica copiada exitosamente a Termux" -ForegroundColor Green
} else {
    Write-Host "❌ No se pudo copiar automaticamente. Copiala manualmente:" -ForegroundColor Yellow
    Write-Host "   1. Abre Termux" -ForegroundColor Yellow
    Write-Host "   2. Ejecuta: mkdir -p ~/.ssh && chmod 700 ~/.ssh" -ForegroundColor Yellow
    Write-Host "   3. Ejecuta: echo '$pubKey' >> ~/.ssh/authorized_keys" -ForegroundColor Yellow
    Write-Host "   4. Ejecuta: chmod 600 ~/.ssh/authorized_keys" -ForegroundColor Yellow
}
