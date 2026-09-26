<#
.SYNOPSIS
    Automatizador maestro para conexion SSH con Termux (Android).
.DESCRIPTION
    Diagnostica red, prueba conexion SSH, ejecuta comandos remotos,
    sincroniza archivos y permite integracion con VS Code Remote-SSH.
.NOTES
    File Name      : termux-connect.ps1
    Prerequisites  : PowerShell 5.1+, OpenSSH Client instalado en Windows
#>

[CmdletBinding()]
param(
    [switch]$Diagnose,
    [switch]$Test,
    [string]$Command,
    [string]$Upload,
    [string]$Download,
    [switch]$Sync,
    [switch]$Menu
)

# ── Configuracion ──
$HostName = "192.168.18.21"
$Port     = 8022
$User     = "u0_a252"
$KeyPath  = "$env:USERPROFILE\.ssh\id_rsa"
$RemoteHome = "/data/data/com.termux/files/home"
$LocalSyncDir = "C:\Users\User\Downloads\AURA\AURA_OS_Workspace\AME_termux_sync"

# ── Funciones auxiliares ──
function Show-Banner {
    Write-Host ""
    Write-Host "==================================================" -ForegroundColor Cyan
    Write-Host "          AURA Termux Connect v2.1          " -ForegroundColor Cyan
    Write-Host "==================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Get-WlanIPv4 {
    $iface = Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias "Wi-Fi*" -ErrorAction SilentlyContinue |
             Where-Object { $_.IPAddress -ne "169.254.*" -and $_.IPAddress -ne "127.0.0.1" } |
             Select-Object -First 1
    if ($iface) { return $iface.IPAddress }
    $iface = Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias "wlan0" -ErrorAction SilentlyContinue |
             Where-Object { $_.IPAddress -ne "169.254.*" -and $_.IPAddress -ne "127.0.0.1" } |
             Select-Object -First 1
    if ($iface) { return $iface.IPAddress }
    return (Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias "*" -ErrorAction SilentlyContinue |
            Where-Object { $_.IPAddress -ne "169.254.*" -and $_.IPAddress -ne "127.0.0.1" -and $_.PrefixOrigin -ne "WellKnown" } |
            Select-Object -First 1).IPAddress
}

function Test-PortOpen {
    param([string]$ComputerName, [int]$Port, [int]$TimeoutMs = 3000)
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $iar = $tcp.BeginConnect($ComputerName, $Port, $null, $null)
        $success = $iar.AsyncWaitHandle.WaitOne($TimeoutMs, $false)
        if ($success) {
            $tcp.EndConnect($iar)
            $tcp.Close()
            return $true
        } else {
            $tcp.Close()
            return $false
        }
    } catch { return $false }
}

function Invoke-SSHCommand {
    param(
        [string]$Cmd,
        [switch]$Silent
    )
    if (-not $Silent) { Write-Host "[SSH] Ejecutando: $Cmd" -ForegroundColor DarkGray }

    $target = "${User}@${HostName}"
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "ssh"
    $psi.Arguments = "-p $Port -i `"$KeyPath`" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 $target `"$Cmd`""
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true

    $p = [System.Diagnostics.Process]::Start($psi)
    $stdout = $p.StandardOutput.ReadToEnd()
    $stderr = $p.StandardError.ReadToEnd()
    $p.WaitForExit()

    if ($p.ExitCode -eq 0) {
        if (-not $Silent) { Write-Host "[OK]" -ForegroundColor Green }
        if ($stdout) { Write-Host $stdout }
        return $stdout
    } else {
        if (-not $Silent) { Write-Host "[FAIL] Exit code: $($p.ExitCode)" -ForegroundColor Red }
        if ($stderr) { Write-Host $stderr -ForegroundColor Red }
        return $stderr
    }
}

function Invoke-SCPUpload {
    param([string]$LocalFile, [string]$RemotePath)
    if (-not (Test-Path $LocalFile)) {
        Write-Host "❌ Archivo local no encontrado: $LocalFile" -ForegroundColor Red
        return $false
    }
    Write-Host "[SCP] Subiendo $LocalFile -> $RemotePath" -ForegroundColor Yellow

    $target = "${User}@${HostName}"
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "scp"
    $psi.Arguments = "-P $Port -i `"$KeyPath`" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new `"$LocalFile`" $target`:$RemotePath"
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true

    $p = [System.Diagnostics.Process]::Start($psi)
    $stdout = $p.StandardOutput.ReadToEnd()
    $stderr = $p.StandardError.ReadToEnd()
    $p.WaitForExit()

    if ($p.ExitCode -eq 0) {
        Write-Host "✅ Subida exitosa" -ForegroundColor Green
        return $true
    } else {
        Write-Host "❌ Error en subida: $stderr" -ForegroundColor Red
        return $false
    }
}

function Invoke-SCPDownload {
    param([string]$RemotePath, [string]$LocalDir)
    if (-not (Test-Path $LocalDir)) { New-Item -ItemType Directory -Path $LocalDir -Force | Out-Null }
    Write-Host "[SCP] Descargando $RemotePath -> $LocalDir" -ForegroundColor Yellow

    $target = "${User}@${HostName}"
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "scp"
    $psi.Arguments = "-P $Port -i `"$KeyPath`" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -r $target`:$RemotePath `"$LocalDir`""
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true

    $p = [System.Diagnostics.Process]::Start($psi)
    $stdout = $p.StandardOutput.ReadToEnd()
    $stderr = $p.StandardError.ReadToEnd()
    $p.WaitForExit()

    if ($p.ExitCode -eq 0) {
        Write-Host "✅ Descarga exitosa" -ForegroundColor Green
        return $true
    } else {
        Write-Host "❌ Error en descarga: $stderr" -ForegroundColor Red
        return $false
    }
}

function Start-SSHDTermux {
    Write-Host "[*] Iniciando sshd en Termux..." -ForegroundColor Yellow
    Invoke-SSHCommand -Cmd "pkg install -y openssh > /dev/null 2>&1; ssh-keygen -A > /dev/null 2>&1; sshd -p 8022" -Silent
    Start-Sleep -Seconds 2
    if (Test-PortOpen -Host $HostName -Port $Port) {
        Write-Host "✅ sshd activo en ${HostName}:${Port}" -ForegroundColor Green
    } else {
        Write-Host "❌ No se pudo verificar sshd activo" -ForegroundColor Red
    }
}

# ── Diagnostico ──
function Invoke-Diagnose {
    Show-Banner
    Write-Host "=== DIAGNOSTICO DE CONEXION ===" -ForegroundColor Cyan
    Write-Host ""

    # 1. Interfaz WiFi
    $wlanIP = Get-WlanIPv4
    Write-Host "[Red] IP Windows WiFi: $wlanIP"
    Write-Host "[Red] IP Termux objetivo: $HostName"

    # 2. Subred
    $subnet = ($wlanIP -split '\.')[0..2] -join '.'
    Write-Host "[Red] Subred detectada: ${subnet}.0/24"
    if (-not ($HostName -like "$subnet.*")) {
        Write-Host "WARNING: IP Termux no esta en la misma subred que Windows." -ForegroundColor Yellow
    } else {
        Write-Host "OK: Misma subred." -ForegroundColor Green
    }

    # 3. Ping
    Write-Host ""
    Write-Host "[Ping] Intentando ping a $HostName..." -ForegroundColor Yellow
    $ping = Test-Connection -ComputerName $HostName -Count 2 -Quiet -ErrorAction SilentlyContinue
    if ($ping) {
        Write-Host "OK: Ping exitoso ($HostName alcanzable)" -ForegroundColor Green
    } else {
        Write-Host "ERROR: Ping fallido. Posibles causas:" -ForegroundColor Red
        Write-Host "   - Termux no esta en la misma red WiFi" -ForegroundColor Red
        Write-Host "   - Firewall/AV bloqueando ICMP" -ForegroundColor Red
        Write-Host "   - IP movil incorrecta" -ForegroundColor Red
    }

    # 4. Puerto SSH
    Write-Host ""
    Write-Host "[Puerto] Verificando TCP $HostName`:$Port..." -ForegroundColor Yellow
    $portOpen = Test-PortOpen -ComputerName $HostName -Port $Port
    if ($portOpen) {
        Write-Host "OK: Puerto $Port abierto" -ForegroundColor Green
    } else {
        Write-Host "ERROR: Puerto $Port cerrado/rechazado. Verifica:" -ForegroundColor Red
        Write-Host "   - sshd corriendo en Termux (sshd -p 8022)" -ForegroundColor Red
        Write-Host "   - Reglas iptables/termux-firewall" -ForegroundColor Red
        Write-Host "   - WiFi con acceso local activo" -ForegroundColor Red
    }

    # 5. SSH key
    Write-Host ""
    Write-Host "[SSH] Verificando clave local..." -ForegroundColor Yellow
    if (Test-Path $KeyPath) {
        Write-Host "OK: Clave encontrada: $KeyPath" -ForegroundColor Green
    } else {
        Write-Host "ERROR: Clave no encontrada en $KeyPath" -ForegroundColor Red
    }

    # 6. Conexion SSH
    Write-Host ""
    Write-Host "[SSH] Probando autenticacion SSH..." -ForegroundColor Yellow
    $testResult = Invoke-SSHCommand -Cmd "echo CONNECTED; uname -a; whoami"
    if ($testResult -match "CONNECTED") {
        Write-Host "OK: Conexion SSH exitosa" -ForegroundColor Green
        Write-Host "   $($testResult -join "`n")" -ForegroundColor Gray
    } else {
        Write-Host "ERROR: Conexion SSH fallida" -ForegroundColor Red
        Write-Host "   Asegurate de haber copiado la clave publica a ~/.ssh/authorized_keys en Termux" -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "=== Fin del diagnostico ===" -ForegroundColor Cyan
}

# ── Menu interactivo ──
function Show-Menu {
    while ($true) {
        Show-Banner
        Write-Host "1. Diagnostico completo" -ForegroundColor White
        Write-Host "2. Probar conexion SSH" -ForegroundColor White
        Write-Host "3. Iniciar sshd en Termux" -ForegroundColor White
        Write-Host "4. Ejecutar comando remoto" -ForegroundColor White
        Write-Host "5. Subir archivo a Termux" -ForegroundColor White
        Write-Host "6. Descargar archivo de Termux" -ForegroundColor White
        Write-Host "7. Sincronizar carpeta AURA -> Termux" -ForegroundColor White
        Write-Host "8. Abrir Remote-SSH en VS Code" -ForegroundColor White
        Write-Host "9. Salir" -ForegroundColor White
        Write-Host ""
        $opt = Read-Host "Selecciona una opcion"
        switch ($opt) {
            "1" { Invoke-Diagnose; Pause }
            "2" { Invoke-SSHCommand -Cmd "echo CONNECTED"; Pause }
            "3" { Start-SSHDTermux; Pause }
            "4" {
                $cmd = Read-Host "Comando a ejecutar en Termux"
                if ($cmd) { Invoke-SSHCommand -Cmd $cmd }
                Pause
            }
            "5" {
                $local = Read-Host "Ruta archivo local"
                $remote = Read-Host "Ruta remota (ej: ~/file.py)"
                if ($local) { Invoke-SCPUpload -LocalFile $local -RemotePath $remote }
                Pause
            }
            "6" {
                $remote = Read-Host "Ruta remota (ej: ~/file.py)"
                $local = Read-Host "Carpeta local destino"
                if ($remote) { Invoke-SCPDownload -RemotePath $remote -LocalDir $local }
                Pause
            }
            "7" {
                if (-not (Test-Path $LocalSyncDir)) { New-Item -ItemType Directory -Path $LocalSyncDir -Force | Out-Null }
                Invoke-SCPUpload -LocalFile "C:\Users\User\Downloads\AURA\AURA_Core\sync_termux.py" -RemotePath "$RemoteHome/sync_termux.py"
                Invoke-SSHCommand -Cmd "cd $RemoteHome; python sync_termux.py --mode scp"
                Pause
            }
            "8" {
                Write-Host "Abriendo VS Code Remote-SSH..." -ForegroundColor Green
                code --remote ssh-remote+termux "$RemoteHome"
            }
            "9" { break }
        }
    }
}

# ── Main ──
Show-Banner

if ($Diagnose) {
    Invoke-Diagnose
    exit 0
}

if ($Test) {
    $ok = Invoke-SSHCommand -Cmd "echo CONNECTED"
    if ($ok -match "CONNECTED") { exit 0 } else { exit 1 }
}

if ($Command) {
    Invoke-SSHCommand -Cmd $Command
    exit 0
}

if ($Upload) {
    if ($Upload -match '->') {
        $parts = $Upload -split '->'
        Invoke-SCPUpload -LocalFile $parts[0].Trim() -RemotePath $parts[1].Trim()
    } else {
        Write-Host "Formato: -Upload `"local->remoto`"" -ForegroundColor Yellow
    }
    exit 0
}

if ($Download) {
    if ($Download -match '->') {
        $parts = $Download -split '->'
        Invoke-SCPDownload -RemotePath $parts[0].Trim() -LocalDir $parts[1].Trim()
    } else {
        Write-Host "Formato: -Download `"remoto->local`"" -ForegroundColor Yellow
    }
    exit 0
}

if ($Sync) {
    Invoke-Diagnose | Out-Null
    Write-Host ""
    Write-Host "[Sync] Sincronizando AURA_Core/sync_termux.py a Termux..." -ForegroundColor Cyan
    Invoke-SCPUpload -LocalFile "C:\Users\User\Downloads\AURA\AURA_Core\sync_termux.py" -RemotePath "$RemoteHome/sync_termux.py"
    Invoke-SSHCommand -Cmd "cd $RemoteHome; python sync_termux.py --mode scp"
    exit 0
}

if ($Menu -or ($args.Count -eq 0)) {
    Show-Menu
    exit 0
}
