# AURA Project Reorganization Script (Safe Version)
# Organizes the AURA project without breaking Python imports

$base = "C:\Users\User\Downloads\AURA"
$ErrorActionPreference = "SilentlyContinue"

Write-Host "=== AURA Project Reorganization (Safe) ===" -ForegroundColor Cyan
Write-Host "Base: $base" -ForegroundColor Gray
Write-Host ""

# Step 1: Create new directory structure
Write-Host "[1/6] Creating directory structure..." -ForegroundColor Yellow

$dirs = @(
    "archives\_AURA_Archive",
    "archives\otro_proyecto",
    "archives\vscode_backup",
    "archives\vercel-temp",
    "archives\jarvis",
    "backend\ame_backend",
    "backend\main",
    "chrome-extension\aura",
    "config\manifests",
    "data\blobs",
    "data\bridge_state",
    "data\cloud_work",
    "data\emotional_memory",
    "data\knowledge_base",
    "data\models\fine-tuned-ame",
    "data\output",
    "data\training",
    "deployments\aura-chat-repo",
    "deployments\aura-web",
    "deployments\hf-space",
    "deployments\hf-space-deploy",
    "deployments\Waifu-texto-ollama-xtts",
    "docs\AURA_OS_Workspace",
    "docs\google_sites_content",
    "docs\reference",
    "docs\spec",
    "docs\screenshots",
    "frontend\ame-mobile-rn",
    "frontend\AURA_Tactical_UI",
    "frontend\AURA_Tactics",
    "frontend\dashboard_ui",
    "frontend\FRONTEND_AME_GODOT",
    "frontend\ui_engine",
    "frontend\tests",
    "integrations\discord_service",
    "integrations\n8n_workflows",
    "integrations\plugins",
    "scripts\deploy",
    "src\AURA_Core",
    "src\AME_Core",
    "tests\unit",
    "tests\integration",
    "training\configs",
    "training\data",
    "training\output",
    "training\scripts",
    ".env"
)

foreach ($d in $dirs) {
    $path = Join-Path $base $d
    if (-not (Test-Path -LiteralPath $path)) {
        New-Item -ItemType Directory -Path $path -Force | Out-Null
    }
}

Write-Host "  Done." -ForegroundColor Green

# Step 2: Move archive/unrelated directories
Write-Host "[2/6] Moving archive/unrelated directories..." -ForegroundColor Yellow

$archiveMoves = @{
    "_AURA_Archive" = "archives\_AURA_Archive"
    "otro_proyecto" = "archives\otro_proyecto"
    "vscode_backup" = "archives\vscode_backup"
    "vercel-temp" = "archives\vercel-temp"
    "~" = "archives\jarvis"
}

foreach ($src in $archiveMoves.Keys) {
    $from = Join-Path $base $src
    $to = Join-Path $base $archiveMoves[$src]
    if (Test-Path -LiteralPath $from) {
        if (-not (Test-Path -LiteralPath $to)) {
            Move-Item -LiteralPath $from -Destination $to -Force
            Write-Host "  $src -> $($archiveMoves[$src])" -ForegroundColor Gray
        }
    }
}

# Move generated Python environments to .env/
$envMoves = @{
    "env" = ".env\env"
    "venv-training" = ".env\venv-training"
}

foreach ($src in $envMoves.Keys) {
    $from = Join-Path $base $src
    $to = Join-Path $base $envMoves[$src]
    if (Test-Path -LiteralPath $from) {
        if (-not (Test-Path -LiteralPath $to)) {
            Move-Item -LiteralPath $from -Destination $to -Force
            Write-Host "  $src -> $($envMoves[$src])" -ForegroundColor Gray
        }
    }
}

Write-Host "  Done." -ForegroundColor Green

# Step 3: Move standalone directories (not Python packages)
Write-Host "[3/6] Moving standalone directories..." -ForegroundColor Yellow

# Deployment directories
$deployMoves = @{
    "aura-chat-repo" = "deployments\aura-chat-repo"
    "hf-space" = "deployments\hf-space"
    "hf-space-deploy" = "deployments\hf-space-deploy"
    "Waifu-texto-ollama-xtts" = "deployments\Waifu-texto-ollama-xtts"
}

foreach ($src in $deployMoves.Keys) {
    $from = Join-Path $base $src
    $to = Join-Path $base $deployMoves[$src]
    if (Test-Path -LiteralPath $from) {
        if (-not (Test-Path -LiteralPath $to)) {
            Move-Item -LiteralPath $from -Destination $to -Force
            Write-Host "  $src -> $($deployMoves[$src])" -ForegroundColor Gray
        }
    }
}

# Integration directories
$integrationsMoves = @{
    "discord_service" = "integrations\discord_service"
    "n8n_workflows" = "integrations\n8n_workflows"
    "plugins" = "integrations\plugins"
}

foreach ($src in $integrationsMoves.Keys) {
    $from = Join-Path $base $src
    $to = Join-Path $base $integrationsMoves[$src]
    if (Test-Path -LiteralPath $from) {
        if (-not (Test-Path -LiteralPath $to)) {
            Move-Item -LiteralPath $from -Destination $to -Force
            Write-Host "  $src -> $($integrationsMoves[$src])" -ForegroundColor Gray
        }
    }
}

# Frontend sub-apps (standalone frontends, not main frontend with node_modules)
$frontendAppMoves = @{
    "AURA_Tactical_UI" = "frontend\AURA_Tactical_UI"
    "AURA_Tactics" = "frontend\AURA_Tactics"
    "dashboard_ui" = "frontend\dashboard_ui"
    "ui_engine" = "frontend\ui_engine"
    "aura-web" = "frontend\aura-web"
    "FRONTEND_AME_GODOT" = "frontend\FRONTEND_AME_GODOT"
    "ame-mobile-rn" = "frontend\ame-mobile-rn"
}

foreach ($src in $frontendAppMoves.Keys) {
    $from = Join-Path $base $src
    $to = Join-Path $base $frontendAppMoves[$src]
    if (Test-Path -LiteralPath $from) {
        if (-not (Test-Path -LiteralPath $to)) {
            Move-Item -LiteralPath $from -Destination $to -Force
            Write-Host "  $src -> $($frontendAppMoves[$src])" -ForegroundColor Gray
        }
    }
}

# Chrome extension
$from = Join-Path $base "chrome-extension-aura"
$to = Join-Path $base "chrome-extension\aura"
if (Test-Path -LiteralPath $from) {
    if (-not (Test-Path -LiteralPath $to)) {
        Move-Item -LiteralPath $from -Destination $to -Force
        Write-Host "  chrome-extension-aura -> chrome-extension\aura" -ForegroundColor Gray
    }
}

# Docs directories
$docsMoves = @{
    "AURA_OS_Workspace" = "docs\AURA_OS_Workspace"
    "google_sites_content" = "docs\google_sites_content"
    "spec" = "docs\spec"
    "screenshots" = "docs\screenshots"
    "docs" = "docs\reference"
}

foreach ($src in $docsMoves.Keys) {
    $from = Join-Path $base $src
    $to = Join-Path $base $docsMoves[$src]
    if (Test-Path -LiteralPath $from) {
        if (-not (Test-Path -LiteralPath $to)) {
            Move-Item -LiteralPath $from -Destination $to -Force
            Write-Host "  $src -> $($docsMoves[$src])" -ForegroundColor Gray
        }
    }
}

# Scripts subdirectories
$from = Join-Path $base "scripts\deploy"
$to = Join-Path $base "scripts\deploy"
if (Test-Path -LiteralPath $from) {
    if (-not (Test-Path -LiteralPath $to)) {
        Move-Item -LiteralPath $from -Destination $to -Force
        Write-Host "  scripts/deploy -> scripts/deploy" -ForegroundColor Gray
    }
}

Write-Host "  Done." -ForegroundColor Green

# Step 4: Move root loose files
Write-Host "[4/6] Organizing root files..." -ForegroundColor Yellow

# Documentation files -> docs/
$docFiles = @(
    "ARCHITECTURE.md",
    "AUDITORÍA-RESULTADOS.md",
    "AURA_SYSTEM_CONTEXT.md",
    "AUTONOMOUS_SETUP.md",
    "BACKEND_AUDIT.md",
    "BLOG_POST_PHASE58.md",
    "BLOG_POST_v3.md",
    "BLOG_POST_v4.0_FINAL.md",
    "CHANGELOG.md",
    "CHECKLIST.md",
    "CODE_OF_CONDUCT.md",
    "COLAB_TRAINING_README.md",
    "CONTRIBUTING.md",
    "CONTRIBUTING-ADVANCED.md",
    "EXAMPLES.md",
    "FASE4_CELEBRATION.md",
    "FINAL_REPORT.md",
    "FINAL_REPORT_PHASE58.md",
    "LOCALHOST_SETUP.md",
    "MARKETPLACE_TOOLS.md",
    "MEJORAS-FASE-57.md",
    "PERFORMANCE.md",
    "PHASE_58_PROGRESS.md",
    "PROJECT_COMPLETION_REPORT.md",
    "PROJECT_COMPLETION_REPORT_v3.md",
    "project-execution-log.md",
    "QUICK_START.md",
    "RAILWAY_SETUP_GUIDE.md",
    "README.md",
    "README_SETUP.md",
    "README-ROADMAP.md",
    "RELEASE_NOTES_v4.0.md",
    "setup-phase-58.md",
    "TROUBLESHOOTING.md",
    "PENDING_TASKS_AUDIT.md",
    "AURA_SYSTEM_ACTIVE.md"
)

foreach ($f in $docFiles) {
    $from = Join-Path $base $f
    if (Test-Path -LiteralPath $from -PathType Leaf) {
        $to = Join-Path $base "docs\$f"
        if (-not (Test-Path -LiteralPath $to)) {
            Move-Item -LiteralPath $from -Destination $to -Force
            Write-Host "  $f -> docs/" -ForegroundColor Gray
        }
    }
}

# Source code files -> src/
$srcFiles = @(
    "api_puente.py",
    "aura_core.py",
    "bridge_server.py",
    "cliente_celular.py",
    "conexion_puente.py",
    "servidor.py"
)

foreach ($f in $srcFiles) {
    $from = Join-Path $base $f
    if (Test-Path -LiteralPath $from -PathType Leaf) {
        $to = Join-Path $base "src\$f"
        if (-not (Test-Path -LiteralPath $to)) {
            Move-Item -LiteralPath $from -Destination $to -Force
            Write-Host "  $f -> src/" -ForegroundColor Gray
        }
    }
}

# Scripts -> scripts/
$scriptFiles = @(
    "run_wifi.ps1",
    "run_training.bat",
    "run_training_ui.bat"
)

foreach ($f in $scriptFiles) {
    $from = Join-Path $base $f
    if (Test-Path -LiteralPath $from -PathType Leaf) {
        $to = Join-Path $base "scripts\$f"
        if (-not (Test-Path -LiteralPath $to)) {
            Move-Item -LiteralPath $from -Destination $to -Force
            Write-Host "  $f -> scripts/" -ForegroundColor Gray
        }
    }
}

# Test files -> tests/
$testFiles = Get-ChildItem -LiteralPath $base -File | Where-Object { $_.Name -match '^test_' }
foreach ($f in $testFiles) {
    $to = Join-Path $base "tests\$($f.Name)"
    if (-not (Test-Path -LiteralPath $to)) {
        Move-Item -LiteralPath $f.FullName -Destination $to -Force
        Write-Host "  $($f.Name) -> tests/" -ForegroundColor Gray
    }
}

# HTML test/demo files -> frontend/tests/
$htmlTestFiles = Get-ChildItem -LiteralPath $base -File | Where-Object { $_.Extension -eq '.html' -and $_.Name -notmatch '^(index|offline)\.html$' }
foreach ($f in $htmlTestFiles) {
    $to = Join-Path $base "frontend\tests\$($f.Name)"
    if (-not (Test-Path -LiteralPath $to)) {
        Move-Item -LiteralPath $f.FullName -Destination $to -Force
        Write-Host "  $($f.Name) -> frontend/tests/" -ForegroundColor Gray
    }
}

# Training files -> training/
$trainingFiles = @(
    "train_aura.py",
    "training_config_pc.json",
    "upload_training_to_hf.py"
)

foreach ($f in $trainingFiles) {
    $from = Join-Path $base $f
    if (Test-Path -LiteralPath $from -PathType Leaf) {
        $to = Join-Path $base "training\$f"
        if (-not (Test-Path -LiteralPath $to)) {
            Move-Item -LiteralPath $from -Destination $to -Force
            Write-Host "  $f -> training/" -ForegroundColor Gray
        }
    }
}

# Training data JSONL files -> data/training/
$jsonlFiles = Get-ChildItem -LiteralPath $base -File | Where-Object { $_.Extension -eq '.jsonl' }
foreach ($f in $jsonlFiles) {
    $to = Join-Path $base "data\training\$($f.Name)"
    if (-not (Test-Path -LiteralPath $to)) {
        Move-Item -LiteralPath $f.FullName -Destination $to -Force
        Write-Host "  $($f.Name) -> data/training/" -ForegroundColor Gray
    }
}

# Log files -> training/output/
$logFiles = Get-ChildItem -LiteralPath $base -File | Where-Object { $_.Extension -eq '.log' }
foreach ($f in $logFiles) {
    $to = Join-Path $base "training\output\$($f.Name)"
    if (-not (Test-Path -LiteralPath $to)) {
        Move-Item -LiteralPath $f.FullName -Destination $to -Force
        Write-Host "  $($f.Name) -> training/output/" -ForegroundColor Gray
    }
}

# Config files that belong in config/
$configFiles = @(
    "capacitor.config.ts",
    "docker-compose.yml",
    "Dockerfile",
    "backend.Dockerfile",
    "frontend.Dockerfile",
    "ecosystem.config.js",
    "nginx.conf",
    "railway.toml",
    "render.yaml",
    "package.json",
    "package-lock.json"
)

foreach ($f in $configFiles) {
    $from = Join-Path $base $f
    if (Test-Path -LiteralPath $from -PathType Leaf) {
        $to = Join-Path $base "config\$f"
        if (-not (Test-Path -LiteralPath $to)) {
            Move-Item -LiteralPath $from -Destination $to -Force
            Write-Host "  $f -> config/" -ForegroundColor Gray
        }
    }
}

# Notebook files -> training/
$nbFiles = Get-ChildItem -LiteralPath $base -File | Where-Object { $_.Extension -eq '.ipynb' }
foreach ($f in $nbFiles) {
    $to = Join-Path $base "training\$($f.Name)"
    if (-not (Test-Path -LiteralPath $to)) {
        Move-Item -LiteralPath $f.FullName -Destination $to -Force
        Write-Host "  $($f.Name) -> training/" -ForegroundColor Gray
    }
}

# Database files -> data/
$dbFiles = Get-ChildItem -LiteralPath $base -File | Where-Object { $_.Extension -eq '.db' }
foreach ($f in $dbFiles) {
    $to = Join-Path $base "data\$($f.Name)"
    if (-not (Test-Path -LiteralPath $to)) {
        Move-Item -LiteralPath $f.FullName -Destination $to -Force
        Write-Host "  $($f.Name) -> data/" -ForegroundColor Gray
    }
}

# Archive/zip files -> archives/
$zipFiles = Get-ChildItem -LiteralPath $base -File | Where-Object { $_.Extension -eq '.zip' }
foreach ($f in $zipFiles) {
    $to = Join-Path $base "archives\$($f.Name)"
    if (-not (Test-Path -LiteralPath $to)) {
        Move-Item -LiteralPath $f.FullName -Destination $to -Force
        Write-Host "  $($f.Name) -> archives/" -ForegroundColor Gray
    }
}

# Empty/null files -> remove
$emptyFiles = Get-ChildItem -LiteralPath $base -File | Where-Object { $_.Length -eq 0 }
foreach ($f in $emptyFiles) {
    Remove-Item -LiteralPath $f.FullName -Force
    Write-Host "  Removed empty file: $($f.Name)" -ForegroundColor DarkGray
}

Write-Host "  Done." -ForegroundColor Green

# Step 5: Consolidate scripts directory
Write-Host "[5/6] Consolidating scripts..." -ForegroundColor Yellow

# Move root .bat, .ps1, .sh files to scripts/
$rootScripts = Get-ChildItem -LiteralPath $base -File | Where-Object { $_.Extension -match '\.(bat|ps1|sh|vbs)$' }
foreach ($f in $rootScripts) {
    $to = Join-Path $base "scripts\$($f.Name)"
    if (-not (Test-Path -LiteralPath $to)) {
        Move-Item -LiteralPath $f.FullName -Destination $to -Force
        Write-Host "  $($f.Name) -> scripts/" -ForegroundColor Gray
    }
}

Write-Host "  Done." -ForegroundColor Green

# Step 6: Clean up
Write-Host "[6/6] Cleanup..." -ForegroundColor Yellow

# Remove empty directories at root (except important ones)
$emptyDirs = Get-ChildItem -LiteralPath $base -Directory | Where-Object {
    $items = Get-ChildItem -LiteralPath $_.FullName -Recurse -File
    $items.Count -eq 0
}

foreach ($d in $emptyDirs) {
    Remove-Item -LiteralPath $d.FullName -Force -Recurse
    Write-Host "  Removed empty dir: $($d.Name)" -ForegroundColor DarkGray
}

Write-Host "  Done." -ForegroundColor Green
Write-Host ""
Write-Host "=== Reorganization Complete ===" -ForegroundColor Cyan

# Final summary
Write-Host ""
Write-Host "Directory summary:" -ForegroundColor Cyan
Get-ChildItem -LiteralPath $base -Directory | Sort-Object Name | ForEach-Object {
    $count = (Get-ChildItem -LiteralPath $_.FullName -Recurse -File -ErrorAction SilentlyContinue).Count
    Write-Host "  $($_.Name)/ ($count items)" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Root files remaining:" -ForegroundColor Cyan
Get-ChildItem -LiteralPath $base -File | ForEach-Object {
    Write-Host "  $($_.Name)" -ForegroundColor Gray
}
