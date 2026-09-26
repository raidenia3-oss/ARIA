@echo off
:: AURA Camera Modules Launcher
:: Runs gesture and vision camera modules in separate windows

title AURA Camera Modules

echo.
echo ========================================
echo   AURA Camera Modules
echo ========================================
echo.
echo Available modules:
echo   1. Gesture Engine (hand tracking + overlays)
echo   2. Vision ROI (filters by hand polygon)
echo   3. Both
echo.

set /p choice="Select module (1-3): "

if "%choice%"=="1" goto gesture
if "%choice%"=="2" goto vision
if "%choice%"=="3" goto both
goto end

:gesture
echo Starting Gesture Engine...
start "AURA Gestures" python gesture_engine.py
goto end

:vision
echo Starting Vision ROI...
start "AURA Vision ROI" python vision_roi.py
goto end

:both
echo Starting both modules...
start "AURA Gestures" python gesture_engine.py
timeout /t 2 /nobreak >nul
start "AURA Vision ROI" python vision_roi.py
goto end

:end
pause
