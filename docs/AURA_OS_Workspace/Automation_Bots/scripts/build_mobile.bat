@echo off
echo Configurando Capacitor para Android...

cd /d "%~dp0"

echo Instalando Capacitor...
npm install @capacitor/core @capacitor/cli

echo Inicializando Capacitor...
npx cap init AURA-Mobile ./dist

echo Añadiendo plataforma Android...
npx cap add android

echo Sincronizando archivos de configuración...
npx cap sync

echo Configuración de Capacitor completada.
echo Iniciando el servidor de desarrollo...
npx cap open android