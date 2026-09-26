@echo off
REM AURA OS - VM Setup para Windows
REM NO toca C: ni D: - solo guarda archivos en carpetas de usuario
REM Requiere: VirtualBox instalado (descargar de virtualbox.org)

setlocal

echo.
echo =============================================================
echo   AURA OS - Instalador por Maquina Virtual (Windows)
echo   NO toca C: ni D: - disco virtual en carpeta de usuario
echo =============================================================
echo.

set VM_NAME=AURA_OS
set VM_DISK=%USERPROFILE%\Downloads\AURA\aura-os\vm\aura-os-vm.vdi
set ISO_PATH=%USERPROFILE%\Downloads\AURA\aura-os\iso\archlinux-x86_64.iso
set VM_RAM=4096
set VM_CPU=2
set VM_DISK_SIZE=20000

echo [*] Verificando VirtualBox...
where VirtualBox >nul 2>&1
if errorlevel 1 (
    echo [ERROR] VirtualBox no esta instalado.
    echo       Descargalo de: https://www.virtualbox.org/wiki/Downloads
    echo       Elegi "Windows hosts" y instalalo.
    pause
    exit /b 1
)
echo [+] VirtualBox detectado.

echo.
echo [*] Verificando ISO de Arch Linux...
if not exist "%ISO_PATH%" (
    echo [ERROR] No se encontro la ISO en: %ISO_PATH%
    echo.
    echo Descargala de: https://archlinux.org/download/
    echo Guardala en: %USERPROFILE%\Downloads\AURA\aura-os\iso\
    echo.
    pause
    exit /b 1
)
echo [+] ISO encontrada: %ISO_PATH%

echo.
echo [*] Creando disco virtual (%VM_DISK_SIZE% MB)...
if not exist "%USERPROFILE%\Downloads\AURA\aura-os\vm\" mkdir "%USERPROFILE%\Downloads\AURA\aura-os\vm\"

REM Borrar disco anterior si existe para empezar limpio
if exist "%VM_DISK%" del /f "%VM_DISK%"

REM Crear disco con VBoxManage
VBoxManage createhd --filename "%VM_DISK%" --size %VM_DISK_SIZE% --format VDI
if errorlevel 1 (
    echo [ERROR] No se pudo crear el disco virtual.
    pause
    exit /b 1
)
echo [+] Disco virtual creado.

echo.
echo [*] Creando VM: %VM_NAME%...
VBoxManage createvm --name "%VM_NAME%" --register
if errorlevel 1 (
    echo [ERROR] No se pudo crear la VM.
    pause
    exit /b 1
)

echo [*] Configurando VM...
VBoxManage modifyvm "%VM_NAME%" --memory %VM_RAM% --cpus %VM_CPU% --vram 128
VBoxManage modifyvm "%VM_NAME%" --nic1 nat --nictype1 virtio
VBoxManage modifyvm "%VM_NAME%" --audio none
VBoxManage modifyvm "%VM_NAME%" --boot1 dvd --boot2 disk --boot3 none --boot4 none
VBoxManage modifyvm "%VM_NAME%" --usb on --usbehci on

echo [*] Agregando controlador SATA...
VBoxManage storagectl "%VM_NAME%" --name "SATA Controller" --add sata --controller IntelAhci

echo [*] Conectando ISO de Arch Linux...
VBoxManage storageattach "%VM_NAME%" --storagectl "SATA Controller" --port 0 --device 0 --type dvddrive --medium "%ISO_PATH%"

echo [*] Conectando disco virtual...
VBoxManage storageattach "%VM_NAME%" --storagectl "SATA Controller" --port 1 --device 0 --type hdd --medium "%VM_DISK%"

echo.
echo =============================================================
echo   VM LISTA
echo =============================================================
echo.
echo Nombre:       %VM_NAME%
echo ISO:          %ISO_PATH%
echo Disco VM:     %VM_DISK%
echo RAM:          %VM_RAM% MB
echo CPUs:         %VM_CPU%
echo Disco:        %VM_DISK_SIZE% MB
echo.
echo Para iniciar la VM, ejecuta:
echo   VirtualBox --startvm "%VM_NAME%"
echo.
echo O desde VirtualBox Manager, selecciona "%VM_NAME%" y click en Iniciar.
echo.
echo =============================================================
echo   INSTRUCCIONES DE INSTALACION DENTRO DE LA VM
echo =============================================================
echo.
echo 1. En la VM, bootea desde la ISO de Arch Linux
echo 2. Configura internet si es necesario:
echo      iwctl
echo      station wlan0 scan
echo      station wlan0 connect "TU_WIFI"
echo      exit
echo 3. Ejecuta el instalador:
echo      sudo bash /ruta/a/install-aura.sh
echo      (la ISO monta el USB automaticamente, o copia el script antes)
echo 4. Despues del primer boot en AURA OS:
echo      bash ~/post-install.sh
echo.
echo NOTA: El disco virtual es un ARCHIVO en tu carpeta de usuario.
echo       NO modifica C: ni D: como particiones.
echo.
pause
