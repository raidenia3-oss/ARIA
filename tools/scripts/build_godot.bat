@echo off
setlocal
set GODOT_PATH=godot
if "%1"=="" (
  echo Uso: build_godot.bat [windows|linux|mac|android]
  exit /b 1
)

set TARGET=%1
echo Building AURA Desktop for %TARGET%...

if /i "%TARGET%"=="windows" (
  "%GODOT_PATH%" --export "Windows Desktop" --headless
) else if /i "%TARGET%"=="linux" (
  "%GODOT_PATH%" --export "Linux" --headless
) else if /i "%TARGET%"=="mac" (
  "%GODOT_PATH%" --export "macOS" --headless
) else if /i "%TARGET%"=="android" (
  "%GODOT_PATH%" --export "Android" --headless
) else (
  echo Target no soportado: %TARGET%
  exit /b 1
)

echo Build completado.
endlocal
