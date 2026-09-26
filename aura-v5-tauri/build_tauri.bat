@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat" -arch=x64
cd /d C:\Users\User\Downloads\AURA\aura-v5-tauri\src-tauri
if exist target rmdir /s /q target
if exist Cargo.lock del Cargo.lock
cargo build --release --target x86_64-pc-windows-msvc