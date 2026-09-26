# Compilación con Java 11 para APK de AME
Write-Host "============================================="
Write-Host "COMPILACION CON JAVA 11 DEL APK DE AME"
Write-Host "============================================="

# PASO 0: Verificar y configurar Java 11
Write-Host "`nPASO 0: Configurando entorno de Java..."

# Intentar usar Java 11 si está disponible
$java11Path = "C:\Program Files\Java\jdk-11.0.22\bin\java.exe"
if (Test-Path $java11Path) {
    Write-Host "Java 11 encontrada en $java11Path"
    $env:JAVA_HOME = "C:\Program Files\Java\jdk-11.0.22"
} else {
    Write-Host "Java 11 no encontrada en la ruta predeterminada. Verificando otras ubicaciones..."
    $javaPaths = @(
        "C:\Program Files\Java\jdk-11\bin\java.exe",
        "C:\Program Files\Java\jdk11\bin\java.exe",
        "C:\Program Files\AdoptOpenJDK\jdk-11.0.11.13-hotspot\bin\java.exe"
    )

    foreach ($path in $javaPaths) {
        if (Test-Path $path) {
            Write-Host "Java 11 encontrada en $path"
            $env:JAVA_HOME = $path.Substring(0, $path.Length - 13) # Quitar '\bin\java.exe' y dejar solo el path de JAVA_HOME
            break
        }
    }
}

# Verificar que JAVA_HOME esté configurado correctamente
if ($env:JAVA_HOME -and (Test-Path "$env:JAVA_HOME\bin\java.exe")) {
    Write-Host "JAVA_HOME configurado correctamente: $env:JAVA_HOME"
    $javaVersion = & "$env:JAVA_HOME\bin\java.exe" -version 2>&1 | Select-String "version"
    if ($javaVersion -match "11") {
        Write-Host "Java 11 confirmada."
    } else {
        Write-Host "Error: JAVA_HOME está configurado pero no es Java 11." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "Error: No se pudo configurar Java 11. Por favor, instala Java 11 y configura JAVA_HOME manualmente." -ForegroundColor Red
    Write-Host "Puedes descargar Java 11 desde: https://adoptium.net/" -ForegroundColor Yellow
    exit 1
}

# PASO 1: Copiar archivos necesarios
Write-Host "`nPASO 1: Copiando archivos JS..."

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
    # Usar el JAVA_HOME configurado
    & $gradlewPath assembleDebug
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