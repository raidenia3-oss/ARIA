@echo off
REM ARIA OS - Windows Startup Auto-Runner
REM Place this file in: shell:startup
REM Launches AURA OS natively without any manual command
REM The binary auto-starts the 3D orb visualization and autonomy daemon

set "PROJECT_DIR=C:\Users\User\Downloads\AURA\v6\axum-poc"

if exist "%PROJECT_DIR%\target\release\aria-axum-poc.exe" (
    start "" /min "%PROJECT_DIR%\target\release\aria-axum-poc.exe"
) else (
    cd /d "%PROJECT_DIR%"
    start "" /min cmd /c "cargo run --release 2>nul"
)
