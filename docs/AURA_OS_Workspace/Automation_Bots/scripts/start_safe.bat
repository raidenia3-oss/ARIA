@echo off
:: AURA Safe Startup Script — Inmunidad Total
:: Configuración de PM2 con retraso extremo y límite de reinicios
:: --max-restarts 2: Solo 2 intentos de reinicio
:: --restart-delay 10000: 10 segundos entre reinicios

echo 🛡️ AURA SAFE STARTUP — Iniciando con configuración de inmunidad extrema...
echo 📝 Monitoreando: AURA_Core/crash_overseer.py
echo 🛑 Regla: Máx. 2 fallos → CIRCUIT BREAKER + AUTO-REPARACIÓN
echo 🔄 Retraso entre reinicios: 10 segundos

:: Detener cualquier proceso existente
echo 🔪 Eliminando procesos residuales...
taskkill /f /im python.exe >nul 2>&1
taskkill /f /im node.exe >nul 2>&1
taskkill /f /im cmd.exe >nul 2>&1

:: Iniciar PM2 con configuración segura
echo 🚀 Iniciando AURA Zero-Tolerance Shield con PM2...
pm2 start AURA_Core/crash_overseer.py --name "AURA_CRASH_OVERSEER" --interpreter .\env\Scripts\python.exe --max-restarts 2 --restart-delay 10000

:: Guardar configuración para persistencia
echo 💾 Guardando configuración de PM2...
pm2 save

:: Verificar estado
echo 📊 Estado del sistema:
pm2 list

echo ✅ AURA ahora está protegida con:
echo   - Máx. 2 reinicios permitidos
echo   - Retraso de 10 segundos entre intentos
echo   - Auto-reparación sintáctica
echo   - Circuit Breaker activado en fallos múltiples