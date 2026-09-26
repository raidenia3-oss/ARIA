# AURA Project Reorganization - Fix Remaining Moves
$base = "C:\Users\User\Downloads\AURA"
$ErrorActionPreference = "SilentlyContinue"

Write-Host "=== Fixing Remaining Moves ===" -ForegroundColor Cyan

# Fix: Move directories to their destinations
# If destination exists and is empty, remove it first, then move source
# If destination exists and has files, move source contents into destination

$moves = @{
    "ame-mobile-rn" = "frontend\ame-mobile-rn"
    "AURA-Brain" = "src\AURA-Brain"
    "aura-chat-repo" = "deployments\aura-chat-repo"
    "AURA_OS_Workspace" = "docs\AURA_OS_Workspace"
    "AURA_Tactical_UI" = "frontend\AURA_Tactical_UI"
    "AURA_Tactics" = "frontend\AURA_Tactics"
    "chrome-extension-aura" = "chrome-extension\aura"
    "dashboard_ui" = "frontend\dashboard_ui"
    "google_sites_content" = "docs\google_sites_content"
    "spec" = "docs\spec"
    "screenshots" = "docs\screenshots"
    "ui_engine" = "frontend\ui_engine"
    "FRONTEND_AME_GODOT" = "frontend\FRONTEND_AME_GODOT"
    "Waifu-texto-ollama-xtts" = "deployments\Waifu-texto-ollama-xtts"
}

foreach ($src in $moves.Keys) {
    $from = Join-Path $base $src
    $to = Join-Path $base $moves[$src]
    
    if (-not (Test-Path -LiteralPath $from)) { continue }
    
    # If destination exists and is empty, remove it so we can move the source
    if (Test-Path -LiteralPath $to) {
        $items = Get-ChildItem -LiteralPath $to -Force
        if ($items.Count -eq 0) {
            Remove-Item -LiteralPath $to -Force -Recurse
        } else {
            # Destination has files, move source contents into destination
            $srcItems = Get-ChildItem -LiteralPath $from -Force
            foreach ($item in $srcItems) {
                $destItem = Join-Path $to $item.Name
                if (-not (Test-Path -LiteralPath $destItem)) {
                    Move-Item -LiteralPath $item.FullName -Destination $destItem -Force
                }
            }
            # Remove source if now empty
            $remaining = Get-ChildItem -LiteralPath $from -Force
            if ($remaining.Count -eq 0) {
                Remove-Item -LiteralPath $from -Force -Recurse
            }
            Write-Host "  $src -> $($moves[$src]) (merged)" -ForegroundColor Gray
            continue
        }
    }
    
    Move-Item -LiteralPath $from -Destination $to -Force
    Write-Host "  $src -> $($moves[$src])" -ForegroundColor Gray
}

# Fix remaining root files
Write-Host ""
Write-Host "Moving remaining root files..." -ForegroundColor Yellow

$remainingMoves = @{
    "AUDITORÍA-RESULTADOS.md" = "docs\AUDITORÍA-RESULTADOS.md"
    "firebase-setup-logs.txt" = "docs\firebase-setup-logs.txt"
    "get_space_status.py" = "scripts\get_space_status.py"
    "hf_space_logs.json" = "data\hf_space_logs.json"
}

foreach ($f in $remainingMoves.Keys) {
    $from = Join-Path $base $f
    $to = Join-Path $base $remainingMoves[$f]
    if (Test-Path -LiteralPath $from -PathType Leaf) {
        if (-not (Test-Path -LiteralPath $to)) {
            Move-Item -LiteralPath $from -Destination $to -Force
            Write-Host "  $f -> $($remainingMoves[$f])" -ForegroundColor Gray
        }
    }
}

# Clean up empty directories
Write-Host ""
Write-Host "Cleaning empty directories..." -ForegroundColor Yellow

$emptyDirs = Get-ChildItem -LiteralPath $base -Directory | Where-Object {
    $items = Get-ChildItem -LiteralPath $_.FullName -Recurse -File -Force
    $items.Count -eq 0
}

foreach ($d in $emptyDirs) {
    Remove-Item -LiteralPath $d.FullName -Force -Recurse
    Write-Host "  Removed empty: $($d.Name)" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "=== Fix Complete ===" -ForegroundColor Cyan

# Final summary
Write-Host ""
Write-Host "Directory summary:" -ForegroundColor Cyan
Get-ChildItem -LiteralPath $base -Directory | Sort-Object Name | ForEach-Object {
    $count = (Get-ChildItem -LiteralPath $_.FullName -Recurse -File -Force -ErrorAction SilentlyContinue).Count
    Write-Host "  $($_.Name)/ ($count items)" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Root files remaining:" -ForegroundColor Cyan
Get-ChildItem -LiteralPath $base -File | ForEach-Object {
    Write-Host "  $($_.Name)" -ForegroundColor Gray
}
