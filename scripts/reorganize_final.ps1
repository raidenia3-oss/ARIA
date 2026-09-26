# Final AURA Reorganization Fix - Using robocopy for reliability
$base = "C:\Users\User\Downloads\AURA"

Write-Host "=== Final Reorganization Fix ===" -ForegroundColor Cyan

# Remove the nul file (Windows artifact)
$nulPath = Join-Path $base "nul"
if (Test-Path -LiteralPath $nulPath) {
    Remove-Item -LiteralPath $nulPath -Force
    Write-Host "Removed nul file" -ForegroundColor Gray
}

# Move remaining directories using robocopy (more reliable on Windows)
$moves = @{
    "AURA_OS_Workspace" = "docs\AURA_OS_Workspace"
    "AURA-Brain" = "src\AURA-Brain"
    "aura-chat-repo" = "deployments\aura-chat-repo"
    "chrome-extension-aura" = "chrome-extension\aura"
    "hf-space" = "deployments\hf-space"
    "hf-space-deploy" = "deployments\hf-space-deploy"
    "n8n_workflows" = "integrations\n8n_workflows"
    "plugins" = "integrations\plugins"
    "discord_service" = "integrations\discord_service"
    "manifests" = "config\manifests"
}

foreach ($src in $moves.Keys) {
    $from = Join-Path $base $src
    $to = Join-Path $base $moves[$src]
    
    if (-not (Test-Path -LiteralPath $from)) { continue }
    
    # Ensure parent directory exists
    $parent = Split-Path -Parent $to
    if (-not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    
    # Use robocopy to move directory contents
    robocopy $from $to /E /MOVE /R:1 /W:1 /NFL /NDL /NJH /NJS /nc /ns /np
    
    # Check if source is now empty and remove it
    $remaining = Get-ChildItem -LiteralPath $from -Force -ErrorAction SilentlyContinue
    if ($remaining.Count -eq 0) {
        Remove-Item -LiteralPath $from -Force -Recurse
        Write-Host "  $src -> $($moves[$src])" -ForegroundColor Green
    } else {
        Write-Host "  $src -> $($moves[$src]) (partial, $($remaining.Count) items remain)" -ForegroundColor Yellow
    }
}

# Move remaining root files
Write-Host ""
Write-Host "Moving remaining root files..." -ForegroundColor Yellow

$remainingFiles = @{
    "AUDITORÍA-RESULTADOS.md" = "docs\AUDITORÍA-RESULTADOS.md"
    "reorganize_fix.ps1" = "scripts\reorganize_fix.ps1"
}

foreach ($f in $remainingFiles.Keys) {
    $from = Join-Path $base $f
    $to = Join-Path $base $remainingFiles[$f]
    if (Test-Path -LiteralPath $from -PathType Leaf) {
        if (-not (Test-Path -LiteralPath $to)) {
            Move-Item -LiteralPath $from -Destination $to -Force
            Write-Host "  $f -> $($remainingFiles[$f])" -ForegroundColor Gray
        }
    }
}

# Clean up empty directories
Write-Host ""
Write-Host "Cleaning empty directories..." -ForegroundColor Yellow

$emptyDirs = Get-ChildItem -LiteralPath $base -Directory | Where-Object {
    $items = Get-ChildItem -LiteralPath $_.FullName -Recurse -File -Force -ErrorAction SilentlyContinue
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
