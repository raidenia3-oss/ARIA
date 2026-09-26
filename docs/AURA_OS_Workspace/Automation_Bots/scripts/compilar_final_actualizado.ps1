# Compilación final actualizada del APK de AME
Write-Host "============================================="
Write-Host "COMPILACION FINAL ACTUALIZADA DEL APK DE AME"
Write-Host "============================================="

# PASO 1: Copiar archivos JS y CSS
Write-Host "`nPASO 1: Copiando archivos necesarios..."

# Definir rutas absolutas
$jsSource = Join-Path -Path $PSScriptRoot -ChildPath "..\AME_Core\static\js"
$jsDest = Join-Path -Path $PSScriptRoot -ChildPath "..\dist\android\app\src\main\assets\public\static\js"
$cssSource = Join-Path -Path $PSScriptRoot -ChildPath "..\AME_Core\static\css"
$cssDest = Join-Path -Path $PSScriptRoot -ChildPath "..\dist\android\app\src\main\assets\public\static\css"
$dashboardSource = Join-Path -Path $PSScriptRoot -ChildPath "..\AME_Core\dashboard.html"
$dashboardDest = Join-Path -Path $PSScriptRoot -ChildPath "..\dist\android\app\src\main\assets\public"

# Crear directorios de destino si no existen
if (!(Test-Path $jsDest)) { New-Item -ItemType Directory -Path $jsDest -Force | Out-Null }
if (!(Test-Path $cssDest)) { New-Item -ItemType Directory -Path $cssDest -Force | Out-Null }

# Copiar archivos JS
if (Test-Path $jsSource) {
    Copy-Item -Path "$jsSource\*" -Destination $jsDest -Recurse -Force
    Write-Host "Archivos JS copiados correctamente."
} else {
    Write-Host "Advertencia: No se encontró el directorio JS en $jsSource" -ForegroundColor Yellow
}

# Copiar archivos CSS si el directorio existe
if (Test-Path $cssSource) {
    Copy-Item -Path "$cssSource\*" -Destination $cssDest -Recurse -Force
    Write-Host "Archivos CSS copiados correctamente."
} else {
    Write-Host "Advertencia: No se encontró el directorio CSS en $cssSource" -ForegroundColor Yellow
}

# Copiar dashboard.html si existe
if (Test-Path $dashboardSource) {
    Copy-Item -Path $dashboardSource -Destination $dashboardDest -Force
    Write-Host "dashboard.html copiado correctamente."
} else {
    Write-Host "Advertencia: No se encontró dashboard.html en $dashboardSource" -ForegroundColor Yellow
}

Write-Host "`nPASO 1 completado."

# PASO 2: Compilar el APK
Write-Host "`nPASO 2: Compilando el APK..."

# Cambiar al directorio correcto donde está gradlew.bat
$androidDir = Join-Path -Path $PSScriptRoot -ChildPath "android"
Set-Location $androidDir

# Verificar si gradlew.bat existe en el directorio android
$gradlewPath = Join-Path -Path $PSScriptRoot -ChildPath "android\gradlew.bat"
if (Test-Path $gradlewPath) {
    Write-Host "Ejecutando gradlew.bat assembleDebug..."
    & cmd.exe /c "$gradlewPath assembleDebug"
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Compilación exitosa."
    } else {
        Write-Host "Error al compilar el APK. Código de salida: $LASTEXITCODE" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "Error: No se encontró gradlew.bat en $gradlewPath" -ForegroundColor Red
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
Write-Host "Proceso de compilación completado."
Write-Host "============================================="