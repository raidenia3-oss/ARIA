# Final comprehensive cleanup
$base = "C:\Users\User\Downloads\AURA"
$ErrorActionPreference = "SilentlyContinue"

Write-Host "=== Final Comprehensive Cleanup ===" -ForegroundColor Cyan

# Define all moves: source -> destination
$moves = @{
    "output" = "data\output"
    "otro_proyecto" = "archives\otro_proyecto"
    "knowledge_base" = "data\knowledge_base"
    "models" = "data\models"
    "Waifu-texto-ollama-xtts" = "deployments\Waifu-texto-ollama-xtts"
    "vscode_backup" = "archives\vscode_backup"
    "~" = "archives\jarvis"
    "_AURA_Archive" = "archives\_AURA_Archive"
    "vercel-temp" = "archives\vercel-temp"
    "venv-training" = ".env\venv-training"
    "blobs" = "data\blobs"
    "cloud_work" = "data\cloud_work"
    "emotional_memory" = "data\emotional_memory"
    "fine-tuned-ame" = "data\models\fine-tuned-ame"
    "ame-mobile-rn" = "frontend\ame-mobile-rn"
}

foreach ($src in $moves.Keys) {
    $from = Join-Path $base $src
    $to = Join-Path $base $moves[$src]
    
    if (-not (Test-Path -LiteralPath $from)) { continue }
    
    # Ensure parent of destination exists
    $parent = Split-Path -Parent $to
    if (-not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    
    # Check if destination already has content
    if (Test-Path -LiteralPath $to) {
        $destItems = Get-ChildItem -LiteralPath $to -Force
        $srcItems = Get-ChildItem -LiteralPath $from -Force
        
        if ($destItems.Count -eq 0) {
            # Destination is empty, just move source
            Remove-Item -LiteralPath $to -Force -Recurse
            Move-Item -LiteralPath $from -Destination $to -Force
            Write-Host "  $src -> $($moves[$src])" -ForegroundColor Green
        } elseif ($srcItems.Count -eq 0) {
            # Source is already empty, just remove it
            Remove-Item -LiteralPath $from -Force -Recurse
            Write-Output "  $src (was empty, removed)" -ForegroundColor Gray
        } else {
            # Both have content - merge using robocopy
            robocopy $from $to /E /R:1 /W:1 /NFL /NDL /NJH /NJS /nc /ns /np /PURGE
            # Try to delete source
            try {
                Remove-Item -LiteralPath $from -Force -Recurse -ErrorAction Stop
                Write-Host "  $src -> $($moves[$src]) (merged)" -ForegroundColor Green
            } catch {
                Write-Host "  $src -> $($moves[$src]) (merged, source remains)" -ForegroundColor Yellow
            }
        }
    } else {
        # Destination doesn't exist, just move
        Move-Item -LiteralPath $from -Destination $to -Force
        Write-Host "  $src -> $($moves[$src])" -ForegroundColor Green
    }
}

# Clean up empty directories
Write-Host ""
Write-Host "Cleaning empty directories..." -ForegroundColor Yellow
$emptyDirs = Get-ChildItem -LiteralPath $base -Directory | Where-Object {
    $items = Get-ChildItem -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue
    $items.Count -eq 0
}
foreach ($d in $emptyDirs) {
    Remove-Item -LiteralPath $d.FullName -Force -Recurse
    Write-Host "  Removed empty: $($d.Name)" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "=== Final State ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Root files:" -ForegroundColor Yellow
Get-ChildItem -LiteralPath $base -File | ForEach-Object {
    Write-Host "  $($_.Name)" -ForegroundColor Gray
}
Write-Host ""
Write-Host "Root directories:" -ForegroundColor Yellow
Get-ChildItem -LiteralPath $base -Directory | Sort-Object Name | ForEach-Object {
    $count = (Get-ChildItem -LiteralPath $_.FullName -Recurse -File -Force -ErrorAction SilentlyContinue).Count
    Write-Host "  $($_.Name)/ ($count items)" -ForegroundColor Gray
}
