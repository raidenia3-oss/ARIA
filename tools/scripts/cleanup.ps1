# Direct cleanup of remaining root files
$base = "C:\Users\User\Downloads\AURA"
$ErrorActionPreference = "Continue"

Write-Host "=== Direct Cleanup ===" -ForegroundColor Cyan

# Documentation files
$docFiles = Get-ChildItem -LiteralPath $base -File | Where-Object { $_.Extension -eq '.md' -and $_.Name -ne 'requirements.txt' }
foreach ($f in $docFiles) {
    $to = Join-Path $base "docs\$($f.Name)"
    if (-not (Test-Path -LiteralPath $to)) {
        Move-Item -LiteralPath $f.FullName -Destination $to -Force
        Write-Host "  $($f.Name) -> docs/" -ForegroundColor Gray
    } else {
        Write-Host "  $($f.Name) already exists at docs/, removing root copy" -ForegroundColor Yellow
        Remove-Item -LiteralPath $f.FullName -Force
    }
}

# Training data JSONL files
$jsonlFiles = Get-ChildItem -LiteralPath $base -File | Where-Object { $_.Extension -eq '.jsonl' }
foreach ($f in $jsonlFiles) {
    $to = Join-Path $base "data\training\$($f.Name)"
    if (-not (Test-Path -LiteralPath $to)) {
        Move-Item -LiteralPath $f.FullName -Destination $to -Force
        Write-Host "  $($f.Name) -> data/training/" -ForegroundColor Gray
    } else {
        Remove-Item -LiteralPath $f.FullName -Force
        Write-Host "  $($f.Name) already exists at data/training/, removing root copy" -ForegroundColor Yellow
    }
}

# Python source files
$pyFiles = Get-ChildItem -LiteralPath $base -File | Where-Object { $_.Extension -eq '.py' }
foreach ($f in $pyFiles) {
    $to = Join-Path $base "src\$($f.Name)"
    if (-not (Test-Path -LiteralPath $to)) {
        Move-Item -LiteralPath $f.FullName -Destination $to -Force
        Write-Host "  $($f.Name) -> src/" -ForegroundColor Gray
    } else {
        Remove-Item -LiteralPath $f.FullName -Force
        Write-Host "  $($f.Name) already exists at src/, removing root copy" -ForegroundColor Yellow
    }
}

# HTML test files
$htmlFiles = Get-ChildItem -LiteralPath $base -File | Where-Object { $_.Extension -eq '.html' -and $_.Name -notmatch '^(index|offline)\.html$' }
foreach ($f in $htmlFiles) {
    $to = Join-Path $base "frontend\tests\$($f.Name)"
    if (-not (Test-Path -LiteralPath $to)) {
        Move-Item -LiteralPath $f.FullName -Destination $to -Force
        Write-Host "  $($f.Name) -> frontend/tests/" -ForegroundColor Gray
    } else {
        Remove-Item -LiteralPath $f.FullName -Force
        Write-Host "  $($f.Name) already exists at frontend/tests/, removing root copy" -ForegroundColor Yellow
    }
}

# Script files
$scriptFiles = Get-ChildItem -LiteralPath $base -File | Where-Object { $_.Extension -match '\.(bat|ps1|sh|vbs)$' }
foreach ($f in $scriptFiles) {
    $to = Join-Path $base "scripts\$($f.Name)"
    if (-not (Test-Path -LiteralPath $to)) {
        Move-Item -LiteralPath $f.FullName -Destination $to -Force
        Write-Host "  $($f.Name) -> scripts/" -ForegroundColor Gray
    } else {
        Remove-Item -LiteralPath $f.FullName -Force
        Write-Host "  $($f.Name) already exists at scripts/, removing root copy" -ForegroundColor Yellow
    }
}

# Notebook files
$nbFiles = Get-ChildItem -LiteralPath $base -File | Where-Object { $_.Extension -eq '.ipynb' }
foreach ($f in $nbFiles) {
    $to = Join-Path $base "training\$($f.Name)"
    if (-not (Test-Path -LiteralPath $to)) {
        Move-Item -LiteralPath $f.FullName -Destination $to -Force
        Write-Host "  $($f.Name) -> training/" -ForegroundColor Gray
    } else {
        Remove-Item -LiteralPath $f.FullName -Force
        Write-Host "  $($f.Name) already exists at training/, removing root copy" -ForegroundColor Yellow
    }
}

# Config files
$configFiles = Get-ChildItem -LiteralPath $base -File | Where-Object { $_.Extension -match '\.(yml|yaml|toml|json|ts|js|conf)$' -and $_.Name -ne 'requirements.txt' }
foreach ($f in $configFiles) {
    $to = Join-Path $base "config\$($f.Name)"
    if (-not (Test-Path -LiteralPath $to)) {
        Move-Item -LiteralPath $f.FullName -Destination $to -Force
        Write-Host "  $($f.Name) -> config/" -ForegroundColor Gray
    } else {
        Remove-Item -LiteralPath $f.FullName -Force
        Write-Host "  $($f.Name) already exists at config/, removing root copy" -ForegroundColor Yellow
    }
}

# Log files
$logFiles = Get-ChildItem -LiteralPath $base -File | Where-Object { $_.Extension -eq '.log' }
foreach ($f in $logFiles) {
    $to = Join-Path $base "training\output\$($f.Name)"
    if (-not (Test-Path -LiteralPath $to)) {
        Move-Item -LiteralPath $f.FullName -Destination $to -Force
        Write-Host "  $($f.Name) -> training/output/" -ForegroundColor Gray
    } else {
        Remove-Item -LiteralPath $f.FullName -Force
        Write-Host "  $($f.Name) already exists at training/output/, removing root copy" -ForegroundColor Yellow
    }
}

# Training config files
$trainingConfigs = Get-ChildItem -LiteralPath $base -File | Where-Object { $_.Name -match 'training' -and $_.Extension -match '\.(json|txt)$' }
foreach ($f in $trainingConfigs) {
    $to = Join-Path $base "training\configs\$($f.Name)"
    if (-not (Test-Path -LiteralPath $to)) {
        Move-Item -LiteralPath $f.FullName -Destination $to -Force
        Write-Host "  $($f.Name) -> training/configs/" -ForegroundColor Gray
    } else {
        Remove-Item -LiteralPath $f.FullName -Force
        Write-Host "  $($f.Name) already exists at training/configs/, removing root copy" -ForegroundColor Yellow
    }
}

# Remove empty root directories
Write-Host ""
Write-Host "Removing empty root directories..." -ForegroundColor Yellow
$emptyDirs = Get-ChildItem -LiteralPath $base -Directory | Where-Object {
    $items = Get-ChildItem -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue
    $items.Count -eq 0
}
foreach ($d in $emptyDirs) {
    Remove-Item -LiteralPath $d.FullName -Force -Recurse
    Write-Host "  Removed empty: $($d.Name)" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "=== Cleanup Complete ===" -ForegroundColor Cyan

Write-Host ""
Write-Host "Root files remaining:" -ForegroundColor Cyan
Get-ChildItem -LiteralPath $base -File | ForEach-Object {
    Write-Host "  $($_.Name)" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Root directories remaining:" -ForegroundColor Cyan
Get-ChildItem -LiteralPath $base -Directory | Sort-Object Name | ForEach-Object {
    $count = (Get-ChildItem -LiteralPath $_.FullName -Recurse -File -Force -ErrorAction SilentlyContinue).Count
    Write-Host "  $($_.Name)/ ($count items)" -ForegroundColor Gray
}
