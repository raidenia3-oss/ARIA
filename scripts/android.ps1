# AURA Android environment setup / APK build helper
# Requires: PowerShell 5.1+, Godot 4.6 installed, Android SDK present.

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$GodotDir = Join-Path $Root 'godot'
$Project = Join-Path $GodotDir 'project.godot'
$Presets = Join-Path $GodotDir 'export_presets.cfg'
$Dist = Join-Path $Root 'dist'
$GodotExe = 'C:\Users\User\OneDrive\Escritorio\Godot_v4.6-stable_win64.exe'
$AndroidSdk = Join-Path $env:LOCALAPPDATA 'Android\Sdk'
$NdkVersion = '25.1.8937393'
$NdkRoot = Join-Path $AndroidSdk "ndk\$NdkVersion"

function Write-Status($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Fail($msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red }

function Test-Command($name) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    return [bool]$cmd
}

function Invoke-AndroidSetup {
    Write-Status 'Android setup'
    if (-not (Test-Path $AndroidSdk)) {
        Write-Fail "Android SDK not found at $AndroidSdk"
        Write-Host 'Install Android Studio and the SDK first.' -ForegroundColor Yellow
        return $false
    }
    Write-Ok "Android SDK: $AndroidSdk"

    if (-not (Test-Path $NdkRoot)) {
        Write-Fail "NDK not found at $NdkRoot"
        Write-Host 'Install NDK r25 from Android Studio: SDK Manager -> SDK Tools -> NDK (Side-by-side).' -ForegroundColor Yellow
        return $false
    }
    Write-Ok "Android NDK: $NdkRoot"

    if (-not (Test-Command java)) {
        Write-Fail 'Java not found in PATH'
        return $false
    }
    Write-Ok 'Java available'

    if (-not (Test-Path $GodotExe)) {
        Write-Fail "Godot not found at $GodotExe"
        return $false
    }
    Write-Ok "Godot: $GodotExe"

    return $true
}

function Invoke-BuildAndroid {
    param(
        [string]$ExportMode = 'release'
    )

    if (-not (Invoke-AndroidSetup)) {
        return
    }

    if (-not (Test-Path $Project)) {
        Write-Fail "project.godot not found at $Project"
        return
    }
    if (-not (Test-Path $Presets)) {
        Write-Fail "export_presets.cfg not found at $Presets"
        return
    }

    if (-not (Test-Path $Dist)) {
        New-Item -ItemType Directory -Path $Dist -Force | Out-Null
    }

    $apkName = 'AURA_Android.apk'
    $apkPath = Join-Path $Dist $apkName
    $presetArg = if ($ExportMode -eq 'release') { '--export-preset 1' } else { '--export-preset 1' }

    Write-Status "Exporting APK using preset index 1..."
    & $GodotExe --headless --path $GodotDir $presetArg $apkPath
    if ($LASTEXITCODE -ne 0) {
        Write-Fail 'Godot export failed'
        return
    }
    Write-Ok "APK generated: $apkPath"

    $adb = Join-Path $AndroidSdk 'platform-tools\adb.exe'
    if (Test-Path $adb) {
        $devices = & $adb devices | Select-String 'device$'
        if ($devices) {
            Write-Status 'Detected Android device(s):'
            $devices | ForEach-Object { Write-Host $_.Line.Trim() }
            $answer = Read-Host 'Install APK on device? (y/N)'
            if ($answer -eq 'y') {
                & $adb install -r $apkPath
                if ($LASTEXITCODE -eq 0) {
                    Write-Ok 'APK installed'
                } else {
                    Write-Fail 'adb install failed'
                }
            }
        } else {
            Write-Host 'No Android device detected. Connect a device and run:' -ForegroundColor Yellow
            Write-Host "  adb install -r `"$apkPath`""
        }
    } else {
        Write-Fail "adb not found at $adb"
    }
}

function Invoke-CreateKeystore {
    $keystoreDir = Join-Path $GodotDir '.godot'
    if (-not (Test-Path $keystoreDir)) {
        New-Item -ItemType Directory -Path $keystoreDir -Force | Out-Null
    }
    $keystore = Join-Path $keystoreDir 'export_android_debug.keystore'
    if (-not (Test-Path $keystore)) {
        Write-Status 'Creating debug keystore...'
        keytool -genkeypair -v -keystore $keystore -storepass android -keypass android -keyalg RSA -keysize 2048 -validity 10000 -alias debug -dname 'CN=debug, OU=dev, O=AURA, L=City, S=State, C=US'
        Write-Ok "Keystore created: $keystore"
    } else {
        Write-Ok "Keystore exists: $keystore"
    }
}

switch ($args[0]) {
    'build' { Invoke-BuildAndroid -ExportMode 'release' }
    'debug' { Invoke-BuildAndroid -ExportMode 'debug' }
    'keystore' { Invoke-CreateKeystore }
    default {
        Write-Host ''
        Write-Host 'AURA Android helper' -ForegroundColor Cyan
        Write-Host ''
        Write-Host 'Usage: .\scripts\android.ps1 <command>' -ForegroundColor White
        Write-Host ''
        Write-Host 'Commands:' -ForegroundColor Yellow
        Write-Host '  build     Build release APK and optionally install'
        Write-Host '  debug     Build debug APK and optionally install'
        Write-Host '  keystore  Create debug keystore'
        Write-Host ''
    }
}
