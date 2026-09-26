@echo off
:: Verificar privilegios de Administrador
net session >nul 2>&1
if %errorLevel% == 0 (
    echo [OK] Privilegios de Administrador detectados.
) else (
    echo [ERROR] Por favor, ejecuta este archivo como ADMINISTRADOR.
    pause
    exit /b
)

echo Configurando inicio automatico invisible...

:: Crear tarea en el Programador de Tareas de Windows
:: /tn = Nombre de la tarea
:: /tr = Comando a ejecutar (Llamamos a wscript para ejecutar el vbs)
:: /sc onlogon = Se ejecuta al iniciar sesión
:: /rl highest = Ejecutar con privilegios más altos
:: /f = Forzar creación si ya existe

schtasks /create /tn "AURA_Invisible_Startup" /tr "wscript.exe \"c:\Users\User\Downloads\AURA\Setup\iniciar_todo_invisible.vbs\"" /sc onlogon /rl highest /f

if %errorLevel% == 0 (
    echo.
    echo ============================================================
    echo ✅ INSTALACION EXITOSA
    echo ============================================================
    echo Ahora, al reiniciar tu PC o iniciar sesion:
    echo 1. Ollama se iniciara en segundo plano.
    echo 2. El núcleo de AURA se activara silenciosamente.
    echo 3. El servidor AME estara listo en el puerto 5000.
    echo TODO SERA INVISIBLE (sin ventanas negras).
    echo ============================================================
) else (
    echo [ERROR] No se pudo crear la tarea programada.
)

pause
exit