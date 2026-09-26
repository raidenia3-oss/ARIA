Write-Host "============================================="
Write-Host "COMPILACION CON POWERSHELL DEL APK DE AME"
Write-Host "============================================="

# PASO 1: Copiar archivos necesarios
Write-Host "`nPASO 1: Copiando archivos JS y CSS..."

# Definir rutas correctas
$jsSource = Join-Path -Path "..\AME_Core\static\js" -Path "*"
$jsDest = Join-Path -Path "..\dist\android\app\src\main\assets\public\static\js"
$cssSource = Join-Path -Path "..\AME_Core\static\css" -Path "*"
$cssDest = Join-Path -Path "..\dist\android\app\src\main\assets\public\static\css"
$dashboardSource = Join-Path -Path "..\AME_Core" -ChildPath "dashboard.html"
$dashboardDest = Join-Path -Path "..\dist\android\app\src\main\assets\public"

# Verificar si los directorios existen
if (Test-Path $jsSource) {
    # Crear directorios si no existen
    if (!(Test-Path $jsDest)) { New-Item -ItemType Directory -Path $jsDest -Force | Out-Null }
    Copy-Item -Path $jsSource -Destination $jsDest -Recurse -Force
    Write-Host "Archivos JS copiados correctamente."
} else {
    Write-Host "Advertencia: No se encontraron archivos JS en $jsSource" -ForegroundColor Yellow
}

if (Test-Path (Join-Path -Path "..\AME_Core\static\css")) {
    if (!(Test-Path $cssDest)) { New-Item -ItemType Directory -Path $cssDest -Force | Out-Null }
    $cssSource = Join-Path -Path "..\AME_Core\static\css" -Path "*"
    Copy-Item -Path $cssSource -Destination $cssDest -Recurse -Force
    Write-Host "Archivos CSS copiados correctamente."
} else {
    Write-Host "Advertencia: No se encontró el directorio CSS en ..\AME_Core\static" -ForegroundColor Yellow
}

if (Test-Path $dashboardSource) {
    Copy-Item -Path $dashboardSource -Destination $dashboardDest -Force
    Write-Host "dashboard.html copiado correctamente."
} else {
    Write-Host "Advertencia: No se encontró dashboard.html en $dashboardSource" -ForegroundColor Yellow
}

Write-Host "PASO 1 completado."

# PASO 2: Compilar el APK
Write-Host "`nPASO 2: Compilando el APK..."
Set-Location "..\dist\android"

# Intentar ejecutar el comando de Gradle
try {
    $gradlewPath = Join-Path -Path "." -ChildPath "gradlew.bat"
    if (Test-Path $gradlewPath) {
        Write-Host "Ejecutando $gradlewPath assembleDebug..."
        & $gradlewPath assembleDebug
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Compilación exitosa."
        } else {
            Write-Host "Error al compilar el APK. Código de salida: $LASTEXITCODE" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "No se encontró gradlew.bat en el directorio actual." -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "Error al ejecutar el comando Gradle: $_" -ForegroundColor Red
    exit 1
}

# PASO 3: Copiar el APK al escritorio
Write-Host "`nPASO 3: Copiando el APK al escritorio..."
$apkSource = Join-Path -Path "app\build\outputs\apk\debug" -ChildPath "app-debug.apk"
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