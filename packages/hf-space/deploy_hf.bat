@echo off
setlocal

echo ==========================================
echo AURA Chat - HF Space Deploy Helper
echo ==========================================
echo.

set "HF_USERNAME=raiden456"
set "SPACE_NAME=aura-chat"
set "HF_SPACE_URL=https://huggingface.co/spaces/%HF_USERNAME%/%SPACE_NAME%"

echo [1/4] Verificando git...
git --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: git no esta instalado. Instalalo desde https://git-scm.com/
    pause
    exit /b 1
)
echo Git OK.

echo.
echo [2/4] Clonando Space desde Hugging Face...
echo URL: %HF_SPACE_URL%
echo.

if exist "%SPACE_NAME%" (
    echo La carpeta %SPACE_NAME% ya existe. Actualizando...
    cd "%SPACE_NAME%"
    git pull
    cd ..
) else (
    git clone "%HF_SPACE_URL%"
)

if errorlevel 1 (
    echo.
    echo ERROR: No se pudo clonar el Space.
    echo - Verifica que el Space exista en https://huggingface.co/spaces/%HF_USERNAME%/%SPACE_NAME%
    echo - Si no existe, crealo en https://huggingface.co/new-space primero.
    pause
    exit /b 1
)

echo.
echo [3/4] Copiando archivos de hf-space/ al Space...

pushd "%SPACE_NAME%"

xcopy /E /Y /I "C:\Users\User\Downloads\AURA\hf-space\app.py" .
xcopy /E /Y /I "C:\Users\User\Downloads\AURA\hf-space\requirements.txt" .
xcopy /E /Y /I "C:\Users\User\Downloads\AURA\hf-space\README.md" .
xcopy /E /Y /I "C:\Users\User\Downloads\AURA\hf-space\DEPLOY.md" .
xcopy /E /Y /I "C:\Users\User\Downloads\AURA\hf-space\src\*.*" "src\" >nul
if not exist "src" mkdir src
xcopy /E /Y /I "C:\Users\User\Downloads\AURA\hf-space\src\*.*" "src\"

popd

echo.
echo [4/4] Commiteando y pusheando...
cd "%SPACE_NAME%"

git add .
git commit -m "Initial commit: AURA Chat"
git push

if errorlevel 1 (
    echo.
    echo ERROR: git push fallo.
    echo - Verifica que tengas permisos en el Space (logueado con huggingface-cli o token SSH).
    pause
    exit /b 1
)

echo.
echo ==========================================
echo DEPLOY COMPLETADO
echo ==========================================
echo.
echo Proximos pasos:
echo 1. Ve a %HF_SPACE_URL%
echo 2. En Settings ^> Repository Secrets agrega:
echo    - HF_TOKEN = tu_token_de_huggingface
echo    - HF_MODEL = openbmb/MiniCPM5-1B
echo 3. Espera el build y accede al Space.
echo.
echo Para mantenerlo 24/7:
echo - Opcion gratis: https://cron-job.org ping cada 5min a %HF_SPACE_URL%
echo - Opcion gratis: Settings ^> Replicas ^> agregar 1 replica
echo - Opcion $9/mes: Settings ^> Keep Space Awake
echo.
pause
