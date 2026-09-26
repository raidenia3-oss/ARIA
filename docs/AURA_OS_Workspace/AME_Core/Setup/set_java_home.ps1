<#
.SYNOPSIS
Script para configurar la variable de entorno JAVA_HOME en Windows.
.DESCRIPTION
Este script configura la variable de entorno JAVA_HOME para apuntar a la ruta del JDK 8 instalado.
.NOTES
File Name      : set_java_home.ps1
Prerequisite   : PowerShell 5.1 o superior
#>

# Ruta del JDK
$javaHomePath = "C:\Program Files\RedHat\java-1.8.0-openjdk-1.8.0.492-1"

# Verificar si la ruta existe
if (-not (Test-Path -Path $javaHomePath)) {
    Write-Error "La ruta del JDK no existe: $javaHomePath"
    exit 1
}

# Obtener el usuario actual
$user = [System.Environment]::UserName

# Configurar JAVA_HOME para el usuario actual
[System.Environment]::SetEnvironmentVariable("JAVA_HOME", $javaHomePath, "User")

# Agregar JAVA_HOME y el bin del JDK al PATH
$javaBinPath = Join-Path $javaHomePath "bin"
$currentPath = [System.Environment]::GetEnvironmentVariable("Path", "User")

if ($currentPath -notlike "*$javaBinPath*") {
    [System.Environment]::SetEnvironmentVariable("Path", "$currentPath;$javaBinPath", "User")
}

Write-Host "JAVA_HOME configurado correctamente en: $javaHomePath"
Write-Host "PATH actualizado para incluir el binario del JDK."