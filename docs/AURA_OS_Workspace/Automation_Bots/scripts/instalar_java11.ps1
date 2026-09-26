<#
.SYNOPSIS
    Script para descargar e instalar Java 11 en el sistema.
.DESCRIPTION
    Este script intenta descargar e instalar Java 11 desde Adoptium y configurar JAVA_HOME.
.NOTES
    File Name      : instalar_java11.ps1
    Prerequisite   : PowerShell 5.1 o superior
#>

# Función para descargar un archivo
function Download-File {
    param (
        [string]$Url,
        [string]$Destination
    )

    try {
        Write-Host "Descargando $Url..."
        Invoke-WebRequest -Uri $Url -OutFile $Destination
        Write-Host "Descarga completada: $Destination"
        return $true
    }
    catch {
        Write-Host "Error al descargar $Url : $_" -ForegroundColor Red
        return $false
    }
}

# Función para instalar Java
function Install-Java11 {
    param (
        [string]$InstallerPath
    )

    try {
        Write-Host "Ejecutando instalador de Java desde $InstallerPath..."
        Start-Process -FilePath $InstallerPath -ArgumentList "/s" -Wait
        Write-Host "Instalación completada."
        return $true
    }
    catch {
        Write-Host "Error al ejecutar el instalador: $_" -ForegroundColor Red
        return $false
    }
}

# Configuración de variables
$java11Url = "https://github.com/adoptium/temurin11-binaries/releases/download/jdk-11.0.22%2B7/OpenJDK11U-jdk_x64_windows_hotspot_11.0.22_7.msi"
$installerPath = "$env:TEMP\OpenJDK11U-jdk_x64_windows_hotspot_11.0.22_7.msi"
$javaHomePath = "C:\Program Files\Java\jdk-11.0.22"

# Verificar si Java 11 ya está instalada
Write-Host "Verificando si Java 11 ya está instalada..."
if (Test-Path "$javaHomePath\bin\java.exe") {
    Write-Host "Java 11 ya está instalada en $javaHomePath" -ForegroundColor Green
    $env:JAVA_HOME = $javaHomePath
    $env:Path = "$javaHomePath\bin;$env:Path"
    Write-Host "JAVA_HOME configurado correctamente."
    Write-Host "Verificando versión de Java..."
    & "$javaHomePath\bin\java.exe" -version
    exit 0
}

# Descargar el instalador de Java 11
Write-Host "Java 11 no encontrada. Descargando instalador..."
if (Download-File -Url $java11Url -Destination $installerPath) {
    # Instalar Java 11
    Write-Host "Instalando Java 11..."
    if (Install-Java11 -InstallerPath $installerPath) {
        # Configurar JAVA_HOME
        Write-Host "Configurando JAVA_HOME..."
        $env:JAVA_HOME = $javaHomePath
        $env:Path = "$javaHomePath\bin;$env:Path"

        # Verificar instalación
        Write-Host "Verificando instalación de Java 11..."
        if (Test-Path "$javaHomePath\bin\java.exe") {
            & "$javaHomePath\bin\java.exe" -version
            Write-Host "Java 11 instalada y configurada correctamente." -ForegroundColor Green
        } else {
            Write-Host "Error: Java 11 no se instaló correctamente." -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "Error: No se pudo instalar Java 11." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "Error: No se pudo descargar el instalador de Java 11." -ForegroundColor Red
    Write-Host "Por favor, descarga e instala Java 11 manualmente desde: https://adoptium.net/" -ForegroundColor Yellow
    exit 1
}