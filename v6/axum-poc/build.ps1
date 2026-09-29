$ErrorActionPreference = "Stop"
$env:PATH = "C:\Users\User\.rustup\toolchains\stable-x86_64-pc-windows-msvc\bin;" + $env:PATH
$env:PATH = "C:\Users\User\.rustup\toolchains\stable-x86_64-pc-windows-gnu\lib\rustlib\x86_64-pc-windows-gnu\bin\self-contained;" + $env:PATH
$env:CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER = "link.exe"
Set-Location "C:\Users\User\Downloads\AURA\v6\axum-poc"
Write-Host "Building..." -ForegroundColor Green
& cargo build --release
if ($LASTEXITCODE -ne 0) { throw "Build failed" }
Write-Host "Build OK" -ForegroundColor Green