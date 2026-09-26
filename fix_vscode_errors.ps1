# AURA — VS Code Auto-Repair System
# Detects and fixes common VS Code issues: extensions, settings, dependencies, Python/Ruby/Node environments

param(
    [switch]$DryRun,
    [switch]$Force,
    [switch]$NoGUI
)

$ErrorActionPreference = 'Stop'
$AuraRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VSCodeDir = Join-Path $AuraRoot ".vscode"
$LogFile = Join-Path $AuraRoot "vscode_repair.log"

function Write-Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] $msg"
    Write-Host $line
    Add-Content -Path $LogFile -Value $line
}

function Write-Status($msg, $color = "White") {
    if (-not $NoGUI) {
        Write-Host $msg -ForegroundColor $color
    }
    Write-Log $msg
}

function Test-Command($cmd) {
    return $null -ne (Get-Command $cmd -ErrorAction SilentlyContinue)
}

function Get-VSCodeExtensions {
    $extensions = @()
    $vscodeExtensions = "$env:USERPROFILE\.vscode\extensions"
    if (Test-Path $vscodeExtensions) {
        $extensions = Get-ChildItem $vscodeExtensions -Directory | Select-Object -ExpandProperty Name
    }
    return $extensions
}

function Get-VSCodeVersion {
    if (Test-Command "code") {
        $version = code --version 2>&1 | Select-Object -First 1
        return $version
    }
    return $null
}

function Repair-Extensions {
    Write-Status "`n[REPAIR] Checking VS Code extensions..." "Yellow"
    
    $requiredExtensions = @(
        "ms-python.python",
        "ms-python.vscode-pylance",
        "ms-python.debugpy",
        "ms-python.black-formatter",
        "ms-python.isort",
        "rebornix.ruby",
        "shopify.ruby-lsp",
        "dbaeumer.vscode-eslint",
        "esbenp.prettier-vscode",
        "ms-vscode.vscode-typescript-next",
        "ms-azuretools.vscode-docker",
        "github.vscode-github-actions",
        "github.copilot",
        "github.copilot-chat",
        "eamodio.gitlens",
        "usernamehw.errorlens",
        "redhat.vscode-yaml",
        "redhat.vscode-dotenv"
    )
    
    $installed = Get-VSCodeExtensions
    
    foreach ($ext in $requiredExtensions) {
        $isInstalled = $false
        foreach ($inst in $installed) {
            if ($inst -like "*$($ext.Split('.')[1])*" -or $inst -like "*$ext*") {
                $isInstalled = $true
                break
            }
        }
        
        if (-not $isInstalled) {
            Write-Status "  [MISSING] $ext - Installing..." "Red"
            if (-not $DryRun -and (Test-Command "code")) {
                try {
                    code --install-extension $ext --force 2>&1 | Out-Null
                    Write-Status "    [OK] Installed $ext" "Green"
                } catch {
                    Write-Status "    [FAIL] Could not install $ext : $_" "Red"
                }
            }
        } else {
            Write-Status "  [OK] $ext" "Green"
        }
    }
}

function Repair-VSCodeSettings {
    Write-Status "`n[REPAIR] Checking VS Code settings..." "Yellow"
    
    $settingsFile = Join-Path $VSCodeDir "settings.json"
    if (-not (Test-Path $settingsFile)) {
        Write-Status "  [MISSING] settings.json - Creating default..." "Red"
        if (-not $DryRun) {
            $settings = @{
                "python.pythonPath" = "python"
                "python.analysis.typeCheckingMode" = "basic"
                "python.formatting.provider" = "black"
                "python.linting.enabled" = $true
                "python.linting.ruffEnabled" = $true
                "typescript.tsdk" = "frontend/node_modules/typescript/lib"
                "editor.formatOnSave" = $true
                "files.autoSave" = "afterDelay"
            } | ConvertTo-Json -Depth 10
            Set-Content -Path $settingsFile -Value $settings -Encoding UTF8
            Write-Status "    [OK] Created settings.json" "Green"
        }
    } else {
        Write-Status "  [OK] settings.json exists" "Green"
        $content = Get-Content $settingsFile -Raw | ConvertFrom-Json
        
        $fixes = @{
            "python.pythonPath" = "python"
            "python.formatting.provider" = "black"
            "python.linting.enabled" = $true
            "python.linting.ruffEnabled" = $true
            "editor.formatOnSave" = $true
        }
        
        foreach ($key in $fixes.Keys) {
            if (-not $content.PSObject.Properties.Match($key)) {
                Write-Status "  [FIX] Adding missing setting: $key" "Yellow"
                if (-not $DryRun) {
                    $content | Add-Member -NotePropertyName $key -NotePropertyValue $fixes[$key] -Force
                }
            }
        }
        
        if (-not $DryRun) {
            $content | ConvertTo-Json -Depth 10 | Set-Content $settingsFile -Encoding UTF8
            Write-Status "    [OK] Settings repaired" "Green"
        }
    }
}

function Repair-Environment {
    Write-Status "`n[REPAIR] Checking Python/Ruby/Node environments..." "Yellow"
    
    # Python
    if (Test-Command "python") {
        $pyVersion = python --version 2>&1
        Write-Status "  [OK] Python: $pyVersion" "Green"
        
        $pipList = pip list 2>&1 | Out-String
        $required = @("fastapi", "uvicorn", "sqlalchemy", "pydantic", "python-dotenv", "requests", "discord.py")
        foreach ($pkg in $required) {
            if ($pipList -notlike "*$pkg*") {
                Write-Status "  [MISSING] Python package: $pkg - Installing..." "Red"
                if (-not $DryRun) {
                    pip install $pkg -q 2>&1 | Out-Null
                    Write-Status "    [OK] Installed $pkg" "Green"
                }
            }
        }
    } else {
        Write-Status "  [FAIL] Python not found!" "Red"
    }
    
    # Node.js
    if (Test-Command "node") {
        $nodeVersion = node --version 2>&1
        Write-Status "  [OK] Node.js: $nodeVersion" "Green"
        
        $frontendDir = Join-Path $AuraRoot "frontend"
        if (Test-Path (Join-Path $frontendDir "package.json")) {
            if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
                Write-Status "  [MISSING] Frontend node_modules - Running npm install..." "Red"
                if (-not $DryRun) {
                    Push-Location $frontendDir
                    npm install 2>&1 | Out-Null
                    Pop-Location
                    Write-Status "    [OK] Frontend dependencies installed" "Green"
                }
            } else {
                Write-Status "  [OK] Frontend node_modules exists" "Green"
            }
        }
    } else {
        Write-Status "  [WARN] Node.js not found - Frontend will be unavailable" "Yellow"
    }
    
    # Ruby
    if (Test-Command "ruby") {
        $rubyVersion = ruby --version 2>&1
        Write-Status "  [OK] Ruby: $rubyVersion" "Green"
        
        $discordBotDir = Join-Path $AuraRoot "services\discord-bot"
        if (Test-Path (Join-Path $discordBotDir "Gemfile")) {
            if (-not (Test-Path (Join-Path $discordBotDir "Gemfile.lock"))) {
                Write-Status "  [MISSING] Discord bot Gemfile.lock - Running bundle install..." "Red"
                if (-not $DryRun) {
                    Push-Location $discordBotDir
                    bundle install 2>&1 | Out-Null
                    Pop-Location
                    Write-Status "    [OK] Discord bot dependencies installed" "Green"
                }
            } else {
                Write-Status "  [OK] Discord bot dependencies exist" "Green"
            }
        }
    } else {
        Write-Status "  [WARN] Ruby not found - Discord bot will be unavailable" "Yellow"
    }
}

function Repair-PythonSyntax {
    Write-Status "`n[REPAIR] Checking Python syntax errors..." "Yellow"
    
    $pythonFiles = Get-ChildItem -Path $AuraRoot -Filter "*.py" -Recurse -ErrorAction SilentlyContinue | 
                   Where-Object { $_.FullName -notlike "*node_modules*" -and $_.FullName -notlike "*.git*" }
    
    $errors = 0
    foreach ($file in $pythonFiles) {
        try {
            $null = [System.IO.File]::ReadAllText($file.FullName)
            python -m py_compile $file.FullName 2>&1 | Out-Null
        } catch {
            Write-Status "  [ERROR] Syntax error in: $($file.FullName)" "Red"
            $errors++
        }
    }
    
    if ($errors -eq 0) {
        Write-Status "  [OK] No Python syntax errors found" "Green"
    } else {
        Write-Status "  [FAIL] Found $errors Python syntax errors" "Red"
    }
}

function Repair-VSCodeWorkspace {
    Write-Status "`n[REPAIR] Checking VS Code workspace configuration..." "Yellow"
    
    $requiredFiles = @(
        "extensions.json",
        "launch.json",
        "tasks.json",
        "settings.json"
    )
    
    foreach ($file in $requiredFiles) {
        $path = Join-Path $VSCodeDir $file
        if (-not (Test-Path $path)) {
            Write-Status "  [MISSING] $file - Creating minimal version..." "Red"
            if (-not $DryRun) {
                switch ($file) {
                    "extensions.json" {
                        '{"recommendations":[],"unwantedRecommendations":[]}' | Set-Content $path -Encoding UTF8
                    }
                    "settings.json" {
                        '{"python.pythonPath":"python","editor.formatOnSave":true}' | Set-Content $path -Encoding UTF8
                    }
                    "launch.json" {
                        '{"version":"0.2.0","configurations":[]}' | Set-Content $path -Encoding UTF8
                    }
                    "tasks.json" {
                        '{"version":"2.0.0","tasks":[]}' | Set-Content $path -Encoding UTF8
                    }
                }
                Write-Status "    [OK] Created $file" "Green"
            }
        } else {
            Write-Status "  [OK] $file exists" "Green"
        }
    }
}

function Repair-CorruptedState {
    Write-Status "`n[REPAIR] Checking for corrupted VS Code state..." "Yellow"
    
    $vscodeAppData = "$env:APPDATA\Code"
    if (Test-Path $vscodeAppData) {
        $cachedDirs = @("CachedData", "Cache", "CachedExtensionVSIXs", "logs")
        foreach ($dir in $cachedDirs) {
            $path = Join-Path $vscodeAppData $dir
            if (Test-Path $path) {
                $size = (Get-ChildItem $path -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1MB
                if ($size -gt 500) {
                    Write-Status "  [WARN] $dir is $([math]::Round($size, 2)) MB - Consider clearing cache" "Yellow"
                    if (-not $DryRun -and $Force) {
                        Write-Status "    [CLEAR] Clearing $dir..." "Cyan"
                        Remove-Item "$path\*" -Recurse -Force -ErrorAction SilentlyContinue
                        Write-Status "    [OK] Cleared $dir" "Green"
                    }
                }
            }
        }
    }
    
    $kiloState = Join-Path $AuraRoot ".kilo"
    if (Test-Path $kiloState) {
        Write-Status "  [OK] Kilo state directory exists" "Green"
    }
}

function Repair-All {
    $startTime = Get-Date
    
    Write-Status "========================================" "Cyan"
    Write-Status "  AURA VS Code Auto-Repair" "Cyan"
    Write-Status "========================================" "Cyan"
    Write-Status "Project: $AuraRoot" "Gray"
    Write-Status "Mode: $(if ($DryRun) { 'DRY RUN' } else { 'LIVE' })" "Gray"
    Write-Status "Start time: $startTime" "Gray"
    Write-Status ""
    
    $vscodeVersion = Get-VSCodeVersion
    if ($vscodeVersion) {
        Write-Status "[INFO] VS Code: $vscodeVersion" "Cyan"
    } else {
        Write-Status "[WARN] VS Code not found in PATH" "Yellow"
    }
    
    Repair-VSCodeWorkspace
    Repair-VSCodeSettings
    Repair-Extensions
    Repair-Environment
    Repair-PythonSyntax
    Repair-CorruptedState
    
    $endTime = Get-Date
    $duration = $endTime - $startTime
    
    Write-Status "`n========================================" "Cyan"
    Write-Status "  Repair Complete!" "Green"
    Write-Status "========================================" "Cyan"
    Write-Status "Duration: $($duration.TotalSeconds) seconds" "Gray"
    Write-Status "Log: $LogFile" "Gray"
    
    if (-not $NoGUI) {
        $result = [System.Windows.Forms.MessageBox]::Show(
            "VS Code repair completed.`nCheck $LogFile for details.",
            "AURA Repair",
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Information
        )
    }
}

# Main execution
if ($MyInvocation.PSCmdlet.Path -eq $null) {
    Repair-All
}
