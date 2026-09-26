# WSL2 y Docker Desktop — comando único para ejecutar como Administrador
Set-ExecutionPolicy Bypass -Scope Process -Force
Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux -NoRestart
Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -NoRestart
wsl --install -d Ubuntu
Write-Host 'WSL2 instalado. Reinicia Windows y ejecuta: docker --version'
