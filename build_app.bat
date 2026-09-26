@echo off
:: Build AURA Desktop App as standalone executable
:: Requires: pip install pyinstaller

echo Building AURA Desktop App...
python -m PyInstaller --onefile --windowed ^
    --name "AURA Desktop" ^
    --icon=assets/aura_icon.ico ^
    --add-data "backend_embedded.py;." ^
    --add-data "agent_bridge.py;." ^
    --add-data "aura_app.py;." ^
    --hidden-import=tkinter ^
    --hidden-import=dotenv ^
    aura_app.py

echo.
echo Build complete! Check dist/AURA Desktop.exe
pause
