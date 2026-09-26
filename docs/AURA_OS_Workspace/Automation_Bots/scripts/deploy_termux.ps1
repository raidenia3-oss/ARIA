<#
.SYNOPSIS
    Script para sincronizar archivos de AME desde la PC a Termux usando SCP.
.DESCRIPTION
    Este script copia automáticamente los archivos modificados desde la carpeta local AME-termux a la carpeta en Termux.
    También permite ejecutar comandos en Termux para reiniciar servicios.
.NOTES
    File Name      : deploy_termux.ps1
    Prerequisites  : PowerShell 5.1 o superior, acceso SSH a Termux
#>

# Configuración actualizada 2026-07-30
$localPath = "C:\Users\User\Downloads\AURA\AURA_OS_Workspace\AME_termux_sync"
$remoteUser = "u0_a252"
$remoteHost = "192.168.18.21"
$remotePort = "8022"
$remotePath = "$RemoteHome/ame_deploy"
$sshKeyPath = "$env:USERPROFILE\.ssh\id_rsa"
$RemoteHome = "/data/data/com.termux/files/home"

# Función para copiar archivos modificados usando SCP
function Invoke-SCP {
    param (
        [string]$localFile,
        [string]$remoteFile
    )

    $command = "scp -P $remotePort -i $sshKeyPath $localFile $remoteUser@$remoteHost:$remotePath/$remoteFile"
    Write-Host "Ejecutando: $command"
    $result = Invoke-Expression $command

    if ($result -eq $null) {
        Write-Host "✅ Archivo copiado correctamente: $localFile"
    } else {
        Write-Host "❌ Error al copiar $localFile: $result"
    }
}

# Función para reiniciar el servidor en Termux
function Restart-TermuxServer {
    $command = "ssh -p $remotePort -i $sshKeyPath $remoteUser@$remoteHost 'cd ~/AME-termux && pkill -f servidor.py && python servidor.py &'"
    Write-Host "Ejecutando en Termux: $command"
    Invoke-Expression $command
}

# Función para ejecutar un comando en Termux
function Invoke-TermuxCommand {
    param (
        [string]$command
    )

    $fullCommand = "ssh -p $remotePort -i $sshKeyPath $remoteUser@$remoteHost '$command'"
    Write-Host "Ejecutando en Termux: $fullCommand"
    Invoke-Expression $fullCommand
}

# Función principal para sincronizar archivos
function Sync-To-Termux {
    # Verificar si la carpeta local existe
    if (-not (Test-Path -Path $localPath)) {
        Write-Host "❌ La carpeta local $localPath no existe."
        return
    }

    # Obtener lista de archivos en la carpeta local
    $files = Get-ChildItem -Path $localPath -File

    # Copiar cada archivo al dispositivo Termux
    foreach ($file in $files) {
        $relativePath = $file.FullName.Substring($localPath.Length).TrimStart('\')
        Invoke-SCP -localFile $file.FullName -remoteFile $relativePath
    }

    # Reiniciar el servidor en Termux
    Restart-TermuxServer
}

# Función para verificar conexión SSH
function Test-SSHConnection {
    $testCommand = "ssh -p $remotePort -i $sshKeyPath -o ConnectTimeout=5 $remoteUser@$remoteHost 'echo Connected'"
    try {
        $result = Invoke-Expression $testCommand
        if ($result -match "Connected") {
            Write-Host "✅ Conexión SSH exitosa a $remoteHost"
            return $true
        } else {
            Write-Host "❌ No se pudo conectar a $remoteHost"
            return $false
        }
    } catch {
        Write-Host "❌ Error de conexión: $_"
        return $false
    }
}

# Verificar conexión SSH antes de continuar
if (-not (Test-SSHConnection)) {
    Write-Host "No se puede continuar sin conexión SSH. Verifica la configuración de red y SSH."
    exit 1
}

# Sincronizar archivos
Sync-To-Termux

Write-Host "Sincronización completada."