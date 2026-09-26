@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat" -arch=x64
set PATH=C:\Users\User\.cargo\bin;%PATH%
cd /d C:\Users\User\Downloads\AURA\aura-v5-tauri
npx tauri build