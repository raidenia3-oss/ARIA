# Compilación final del APK de AME
Write-Host "============================================="
Write-Host "COMPILACION FINAL DEL APK DE AME"
Write-Host "============================================="

# PASO 1: Copiar archivos JS y CSS
Write-Host "`nPASO 1: Copiando archivos JS y CSS..."

# Crear directorios de destino si no existen
$jsDest = "..\dist\android\app\src\main\assets\public\static\js"
$cssDest = "..\dist\android\app\src\main\assets\public\static\css"
if (!(Test-Path $jsDest)) { New-Item -ItemType Directory -Path $jsDest -Force | Out-Null }
if (!(Test-Path $cssDest)) { New-Item -ItemType Directory -Path $cssDest -Force | Out-Null }

# Copiar archivos JS
$jsSource = "..\AME_Core\static\js\*"
if (Test-Path $jsSource) {
    Copy-Item -Path $jsSource -Destination $jsDest -Recurse -Force
    Write-Host "Archivos JS copiados correctamente."
} else {
    Write-Host "Advertencia: No se encontraron archivos JS en ..\AME_Core\static\js" -ForegroundColor Yellow
}

# Copiar archivos CSS
$cssSource = "..\AME_Core\static\css\*"
if (Test-Path (Join-Path -Path "..\AME_Core\static" -ChildPath "css")) {
    Copy-Item -Path $cssSource -Destination $cssDest -Recurse -Force
    Write-Host "Archivos CSS copiados correctamente."
} else {
    Write-Host "Advertencia: No se encontró el directorio CSS en ..\AME_Core\static" -ForegroundColor Yellow
}

# Copiar dashboard.html
$dashboardSource = "..\AME_Core\dashboard.html"
$dashboardDest = "..\dist\android\app\src\main\assets\public\dashboard.html"
if (Test-Path $dashboardSource) {
    Copy-Item -Path $dashboardSource -Destination $dashboardDest -Force
    Write-Host "dashboard.html copiado correctamente."
} else {
    Write-Host "Advertencia: No se encontró dashboard.html en $dashboardSource" -ForegroundColor Yellow
}

Write-Host "`nPASO 1 completado."

# PASO 2: Compilar el APK
Write-Host "`nPASO 2: Compilando el APK..."
Set-Location "..\dist\android"

# Intentar ejecutar el comando de Gradle
$gradlewPath = "gradlew.bat"
if (Test-Path $gradlewPath) {
    Write-Host "Ejecutando $gradlewPath assembleDebug..."
    & cmd.exe /c $gradlewPath assembleDebug
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Compilación exitosa."
    } else {
        Write-Host "Error al compilar el APK. Código de salida: $LASTEXITCODE" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "No se encontró $gradlewPath en el directorio actual." -ForegroundColor Red
    exit 1
}

# PASO 3: Copiar el APK al escritorio
Write-Host "`nPASO 3: Copiando el APK al escritorio..."
$apkSource = "app\build\outputs\apk\debug\app-debug.apk"
$apkDest = "$env:USERPROFILE\Desktop\AME_PROD.apk"

if (Test-Path $apkSource) {
    Copy-Item -Path $apkSource -Destination $apkDest -Force
    Write-Host "APK copiado al escritorio como AME_PROD.apk"
} else {
    Write-Host "Advertencia: No se encontró el APK en $apkSource" -ForegroundColor Yellow
}

Write-Host "`n============================================="
Write-Host "Proceso de compilación completado."
Write-Host "============================================="