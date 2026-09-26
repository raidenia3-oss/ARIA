<#
.SYNOPSIS
    Configura una tarea programada en Windows para realizar backups semanales del sistema AURA.
.DESCRIPTION
    Este script crea una tarea programada en el Programador de Tareas de Windows que ejecuta
    el script de backup cada domingo a las 00:00 con permisos de administrador.
.NOTES
    File Name      : setup_backup_task.ps1
    Prerequisites  : Windows 10/11, PowerShell 5.1 o superior, permisos de administrador
#>

# Configuración
$scriptDir = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition
$backupScript = "backup_system.py"
$taskName = "AURA Weekly Backup"
$taskDescription = "Backup semanal automático del sistema AURA"
$taskDay = "SUN"  # Domingo
$taskTime = "00:00"

# Verificar si el script de backup existe
if (-not (Test-Path -Path "$scriptDir\$backupScript")) {
    Write-Error "Script de backup '$backupScript' no encontrado en $scriptDir"
    exit 1
}

# Verificar si Python está disponible
$pythonPath = & where python 2>$null
if (-not $pythonPath) {
    Write-Error "Python no está disponible en el PATH"
    exit 1
}

# Verificar si la tarea ya existe
$taskExists = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($taskExists) {
    Write-Host "La tarea '$taskName' ya existe. Verificando..."
    goto VerifyTask
}

# Crear la tarea programada
try {
    Write-Host "Configurando tarea programada '$taskName'..."

    $action = New-ScheduledTaskAction -Execute "$pythonPath" -Argument '"$scriptDir\$backupScript backup"'
    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $taskDay -At $taskTime -StartTime (Get-Date -Year 2026 -Month 1 -Day 1 -Hour $taskTime.Split(':')[0] -Minute $taskTime.Split(':')[1])
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description $taskDescription -RunLevel Highest -Force

    Write-Host "Tarea programada creada con éxito: $taskName"
    Write-Host "Descripción: $taskDescription"
    Write-Host "Programación: Cada $taskDay a las $taskTime"
    Write-Host "Comando: $pythonPath `"$scriptDir\$backupScript`" backup"
    goto VerifyTask
}
catch {
    Write-Error "Error creando tarea en Windows: $_"
    exit 1
}

# Verificar la tarea programada
:VerifyTask
try {
    Write-Host "`nVerificando tarea programada..."
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction Stop

    Write-Host "Tarea verificada: $($task.TaskName)"
    Write-Host "Descripción: $($task.Description)"
    Write-Host "Estado: $($task.Enabled)"
    Write-Host "Próxima ejecución: $($task.NextRunTime)"

    # Mostrar detalles de los triggers
    $task.Triggers | ForEach-Object {
        Write-Host "Trigger: $($_.DaysOfWeek) a las $($_.At)"
    }

    # Mostrar detalles de las acciones
    $task.Actions | ForEach-Object {
        Write-Host "Acción: $($_.Execute) $($_.Arguments)"
    }
}
catch {
    Write-Error "Error verificando tarea en Windows: $_"
    exit 1
}

Write-Host "`nConfiguración completada con éxito."
Write-Host "La tarea '$taskName' se ejecutará cada domingo a las $taskTime."
Write-Host "`nPara verificar el estado de la tarea, usa:"
Write-Host "Get-ScheduledTask -TaskName '$taskName' | Get-ScheduledTaskInfo"
Write-Host "`nPara eliminar la tarea, usa:"
Write-Host "Unregister-ScheduledTask -TaskName '$taskName' -Confirm"