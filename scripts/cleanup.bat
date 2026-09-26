@echo off
setlocal

echo ============================================
echo   AURA Cleanup / Mantenimiento
echo ============================================

echo.
echo [1/3] Limpiando datos antiguos...
python scripts\maintenance.py --dry-run

echo.
echo [2/3] Verificando backups...
python training\scripts\backup_model.py

echo.
echo [3/3] Reporte de espacio...
python scripts\maintenance.py --dry-run

echo.
echo ============================================
echo   Cleanup completado
echo ============================================
pause