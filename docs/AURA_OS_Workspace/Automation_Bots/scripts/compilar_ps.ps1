Write-Host "============================================="
Write-Host "COMPILACION CON POWERSHELL DEL APK DE AME"
Write-Host "============================================="

# PASO 1: Copiar archivos necesarios
Write-Host "`nPASO 1: Copiando archivos JS y CSS..."
$jsSource = "..\AME_Core\static\js"
$jsDest = "..\dist\android\app\src\main\assets\public\static\js"
$cssSource = "..\AME_Core\static\css"
$cssDest = "..\dist\android\app\src\main\assets\public\static\css"
$dashboardSource = "..\AME_Core\dashboard.html"
$dashboardDest = "..\dist\android\app\src\main\assets\public"

# Crear directorios si no existen
if (!(Test-Path $jsDest)) { New-Item -ItemType Directory -Path $jsDest | Out-Null }
if (!(Test-Path $cssDest)) { New-Item -ItemType Directory -Path $cssDest | Out-Null }

# Copiar archivos JS
Copy-Item -Path "$jsSource\*" -Destination $jsDest -Recurse -Force

# Copiar archivos CSS
Copy-Item -Path "$cssSource\*" -Destination $cssDest -Recurse -Force

# Copiar dashboard.html
Copy-Item -Path $dashboardSource -Destination $dashboardDest -Force

Write-Host "PASO 1 completado con éxito."

# PASO 2: Compilar el APK
Write-Host "`nPASO 2: Compilando el APK..."
Set-Location "..\dist\android"
Write-Host "Ejecutando gradlew assembleDebug..."
& .\gradlew.bat assembleDebug

if ($LASTEXITCODE -ne 0) {
    Write-Host "Error al compilar el APK." -ForegroundColor Red
    exit 1
}

Write-Host "PASO 2 completado con éxito."

# PASO 3: Copiar el APK al escritorio
Write-Host "`nPASO 3: Copiando el APK al escritorio..."
$apkSource = "app\build\outputs\apk\debug\app-debug.apk"
$apkDest = "$env:USERPROFILE\Desktop\AME_PROD.apk"
Copy-Item -Path $apkSource -Destination $apkDest -Force

if ($LASTEXITCODE -ne 0) {
    Write-Host "Error al copiar el APK al escritorio." -ForegroundColor Red
    exit 1
}

Write-Host "`n============================================="
Write-Host "APK compilado y copiado al escritorio como AME_PROD.apk"
Write-Host "============================================="