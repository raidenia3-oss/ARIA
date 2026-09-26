@echo off
REM DESCARGAR MODELO SIN CENSURA DOLPHIN-2.6-PHI-2
REM Corregido: repo, ruta y nombre de archivo correctos
REM AURA lo detecta automaticamente via Jan (localhost:1337)

echo.
echo ============================================================
echo   AURA OS - DESCARGAR MODELO DOLPHIN-2.6-PHI-2 (sin censura)
echo ============================================================
echo.

REM Jan modelos ubicacion verificada
set JAN_MODELS=%APPDATA%\Jan\data\llamacpp\models
if not exist "%JAN_MODELS%" (
    echo [!] Creando directorio de modelos Jan...
    mkdir "%JAN_MODELS%"
)

echo [*] Repositorio: TheBloke/dolphin-2_6-phi-2-GGUF
echo [*] Modelo: dolphin-2.6-phi-2.Q4_K_M.gguf (1.6 GB)
echo [*] Ubicacion: %JAN_MODELS%\dolphin-2_6-phi-2\
echo.
echo Esto toma 5-10 minutos segun conexion...
echo.

python -c "
from huggingface_hub import hf_hub_download
import os, sys

model_dir = r'%APPDATA%\Jan\data\llamacpp\models\dolphin-2_6-phi-2'
os.makedirs(model_dir, exist_ok=True)

print('[*] Descargando modelo...')
try:
    path = hf_hub_download(
        repo_id='TheBloke/dolphin-2_6-phi-2-GGUF',
        filename='dolphin-2_6-phi-2.Q4_K_M.gguf',
        local_dir=model_dir,
        local_dir_use_symlinks=False
    )
    size_gb = os.path.getsize(path) / 1e9
    print(f'[OK] Modelo descargado: {path}')
    print(f'[OK] Tamano: {size_gb:.2f} GB')
    print()
    print('[OK] LISTO')
    print()
    print('Para usar este modelo:')
    print('  1. Abrir Jan (localhost:1337)')
    print('  2. Seleccionar modelo: dolphin-2_6-phi-2')
    print('  3. Reiniciar Jan')
except Exception as e:
    print(f'[ERROR] {e}')
    print()
    print('Alternativa manual:')
    print('  https://huggingface.co/TheBloke/dolphin-2_6-phi-2-GGUF')
    print('  Descargar: dolphin-2_6-phi-2.Q4_K_M.gguf')
    print('  Guardar en: %APPDATA%\Jan\data\llamacpp\models\dolphin-2_6-phi-2\')
" 2>&1

echo.
echo ============================================================
echo   [OK] Modelo listo. Ejecuta AURA_OS.bat ahora
echo ============================================================
echo.
pause
