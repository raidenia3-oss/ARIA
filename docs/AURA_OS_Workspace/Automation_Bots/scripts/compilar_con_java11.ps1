# Compilación con Java 11 para APK de AME
Write-Host "============================================="
Write-Host "COMPILACION CON JAVA 11 DEL APK DE AME"
Write-Host "============================================="

# PASO 0: Verificar Java 11
Write-Host "`nPASO 0: Verificando Java..."
$javaVersion = java -version 2>&1 | Select-String "version"
if ($javaVersion -match "11") {
    Write-Host "Java 11 ya está configurada."
} else {
    Write-Host "Java 11 no está configurada. Intentando instalar..."
    # Intentar instalar Java 11 (esto es un placeholder, en un entorno real necesitarías descargar e instalar Java 11 manualmente)
    Write-Host "Por favor, descarga e instala Java 11 desde https://adoptium.net/ y configura JAVA_HOME manualmente."
    Write-Host "Luego ejecuta este script nuevamente."
    exit 1
}

# PASO 1: Copiar archivos JS
Write-Host "`nPASO 1: Copiando archivos necesarios..."

# Definir rutas absolutas
$jsSource = Join-Path -Path $PSScriptRoot -ChildPath "..\AME_Core\static\js"
$jsDest = Join-Path -Path $PSScriptRoot -ChildPath "..\dist\android\app\src\main\assets\public\static\js"

# Crear directorios de destino si no existen
if (!(Test-Path $jsDest)) { New-Item -ItemType Directory -Path $jsDest -Force | Out-Null }

# Copiar archivos JS
if (Test-Path $jsSource) {
    Copy-Item -Path "$jsSource\*" -Destination $jsDest -Recurse -Force
    Write-Host "Archivos JS copiados correctamente."
} else {
    Write-Host "Advertencia: No se encontró el directorio JS en $jsSource" -ForegroundColor Yellow
}

Write-Host "`nPASO 1 completado."

# PASO 2: Compilar el APK con Java 11
Write-Host "`nPASO 2: Compilando el APK con Java 11..."

# Cambiar al directorio android
$androidDir = Join-Path -Path $PSScriptRoot -ChildPath "android"
Set-Location $androidDir

# Verificar gradlew.bat
$gradlewPath = Join-Path -Path $PSScriptRoot -ChildPath "android\gradlew.bat"
if (Test-Path $gradlewPath) {
    Write-Host "Ejecutando gradlew.bat assembleDebug con Java 11..."
    $java11Path = "C:\Program Files\Java\jdk-11.0.22\bin\java.exe"
    if (Test-Path $java11Path) {
        & $java11Path -jar gradlew.bat assembleDebug
    } else {
        Write-Host "No se encontró Java 11 en $java11Path. Usando JAVA_HOME..."
        $env:JAVA_HOME = "C:\Program Files\Java\jdk-11.0.22"
        & $gradlewPath assembleDebug
    }
} else {
    Write-Host "Error: No se encontró gradlew.bat en $gradlewPath" -ForegroundColor Red
    exit 1
}

# Verificar el resultado de la compilación
if ($LASTEXITCODE -eq 0) {
    Write-Host "Compilación exitosa con Java 11."
} else {
    Write-Host "Error al compilar el APK. Código de salida: $LASTEXITCODE" -ForegroundColor Red
    exit 1
}

# PASO 3: Copiar el APK al escritorio
Write-Host "`nPASO 3: Copiando el APK al escritorio..."
$apkSource = Join-Path -Path $PSScriptRoot -ChildPath "android\app\build\outputs\apk\debug\app-debug.apk"
$apkDest = Join-Path -Path $env:USERPROFILE -ChildPath "Desktop\AME_PROD.apk"

if (Test-Path $apkSource) {
    Copy-Item -Path $apkSource -Destination $apkDest -Force
    Write-Host "APK copiado al escritorio como AME_PROD.apk"
} else {
    Write-Host "Advertencia: No se encontró el APK en $apkSource" -ForegroundColor Yellow
}

Write-Host "`n============================================="
Write-Host "Proceso de compilación completado con Java 11."
Write-Host "============================================="