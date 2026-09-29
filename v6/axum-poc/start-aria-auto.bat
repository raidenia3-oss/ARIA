@echo off
REM ARIA OS - Auto-start script for Windows startup folder
REM Launches the AURA orb automatically on system boot (no manual command needed)
REM This script runs the Rust+wgpu Axum backend on port 8002 with native 3D orb

cd /d "C:\Users\User\Downloads\AURA\v6\axum-poc"
start "" /b /min "C:\Users\User\Downloads\AURA\.venv\Scripts\python.exe" -c "import subprocess; subprocess.Popen(['cargo', 'run', '--release'], cwd=r'C:\Users\User\Downloads\AURA\v6\axum-poc', creationflags=0x08000000)" 2>nul

endlocal
